"""Update Grace's portfolio site from her Drive folder.

  python pipeline/update.py --drive FOLDER_ID      (automatic runs; key in $GDRIVE_SA_KEY)
  python pipeline/update.py --local "/path/to/Student Teaching"

Only new or changed files are downloaded and converted. Everything the site needs between runs
is kept in pipeline/state/ and site/files, site/thumbs (committed to the repo)."""
import argparse, hashlib, json, os, re, shutil, subprocess, sys, warnings
warnings.filterwarnings('ignore')
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import yaml
from lp_parse import text_of, parse
from sources import LocalSource, DriveSource

REPO = os.path.dirname(HERE); SITE = os.path.join(REPO, 'site'); WORK = os.path.join(REPO, '.work'); SRC = os.path.join(WORK, 'src')
ST = os.path.join(HERE, 'state')
SUPPORTED = {'.pdf', '.docx', '.doc', '.pptx', '.ppt', '.xlsx', '.xls', '.odt', '.rtf', '.txt', '.png', '.jpg', '.jpeg', '.gif', '.webp', '.avif', '.heic', '.bmp', '.tif', '.tiff'}
IMAGES = {'.png', '.jpg', '.jpeg', '.gif', '.webp', '.avif', '.heic', '.bmp', '.tif', '.tiff'}
CANVA_RE = r'https://(?:canva\.link/[A-Za-z0-9]+|www\.canva\.com/design/[A-Za-z0-9_-]+/[A-Za-z0-9_-]+/[a-z]+)'

def load(name, default):
    p = os.path.join(ST, name); return json.load(open(p)) if os.path.exists(p) else default
def save(name, obj):
    os.makedirs(ST, exist_ok=True); json.dump(obj, open(os.path.join(ST, name), 'w'), indent=1, ensure_ascii=False, sort_keys=True)
def log(*a): print(*a, flush=True)

def slug(s):
    s = s.replace('&', 'and').replace('+', '-')
    return re.sub(r'-+', '-', re.sub(r'[^a-z0-9]+', '-', s.lower())).strip('-')
def slug_path(rel):
    parts = rel.split('/'); return '/'.join(slug(p) for p in parts[:-1] + [os.path.splitext(parts[-1])[0]])

# ---------------- content fingerprint + extraction ----------------
def content_hash(p):
    ext = os.path.splitext(p)[1].lower()
    if ext == '.docx':   # Google re-exports differ byte-wise; compare the words instead
        try: return 'txt:' + hashlib.md5(text_of(p).encode()).hexdigest()
        except Exception: pass
    return hashlib.md5(open(p, 'rb').read()).hexdigest()

def pdf_links(p):
    import fitz
    d = fitz.open(p); out = []
    for pg in d:
        for l in pg.get_links():
            if 'canva' in l.get('uri', ''): out.append(l['uri'])
    return out

def extract(p, looks_like_lesson):
    """Canva links (with the label text before them) and lesson-plan sections."""
    ext = os.path.splitext(p)[1].lower(); res = {}
    if ext in ('.docx', '.pdf'):
        try: t = text_of(p)
        except Exception: t = ''
        links, label = [], None
        for line in t.split('\n'):
            line = line.strip()
            if not line: continue
            urls = re.findall(CANVA_RE, line); lab = re.sub(CANVA_RE, '', line).strip(' :')
            if lab and not urls: label = lab; continue
            for u in urls: links.append([lab or label or '', u])
        if ext == '.docx':   # hyperlinks whose text isn't the URL itself
            import docx
            try:
                d = docx.Document(p)
                for rel in d.part.rels.values():
                    if 'hyperlink' in rel.reltype and re.match(CANVA_RE, rel.target_ref) and rel.target_ref not in [u for _, u in links]:
                        links.append(['', rel.target_ref])
            except Exception: pass
        else:
            for u in pdf_links(p):
                m = re.match(CANVA_RE, u)
                if m and m.group(0) not in [x for _, x in links]: links.append(['', m.group(0)])
        res['canva'] = links
        if looks_like_lesson and t:
            meta, secs = parse(t); res['lesson'] = {'meta': meta, 'sections': secs, 'text': t.strip()}
    return res

# ---------------- Canva ----------------
def canva_resolve(u, canva):
    if u in canva and canva[u].get('design'): return canva[u]
    m = re.match(r'https://www\.canva\.com/design/([^/]+)/([^/]+)/', u)
    if not m:
        loc = subprocess.run(['curl', '-sS', '-o', '/dev/null', '--max-time', '20', '-w', '%{redirect_url}', u], capture_output=True, text=True).stdout
        m = re.match(r'https://www\.canva\.com/design/([^/]+)/([^/]+)/', loc)
    canva[u] = {'design': m.group(1), 'token': m.group(2)} if m else {}
    return canva[u]

def canva_check_and_capture(todo, canva):
    """Load each new deck's embed once: does it play, and grab the first slide as a preview."""
    if not todo: return
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log('playwright missing: new decks assumed playable, no preview'); [canva[u].update(ok=True) for u in todo]; return
    os.makedirs(os.path.join(SITE, 'thumbs', 'slides'), exist_ok=True)
    proxy = os.environ.get('HTTPS_PROXY')
    with sync_playwright() as pw:
        b = pw.chromium.launch(**({'proxy': {'server': proxy}} if proxy else {}))
        ctx = b.new_context(ignore_https_errors=True, viewport={'width': 1280, 'height': 720},
                            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36')
        for u in todo:
            v = canva[u]; page = ctx.new_page(); state = 'unknown'
            try:
                page.goto(f"https://www.canva.com/design/{v['design']}/{v['token']}/view?embed", wait_until='domcontentloaded', timeout=60000)
                page.wait_for_timeout(7000); txt = page.evaluate('document.body.innerText')
                if re.search(r"can.t show this page", txt, re.I): state = 'blocked'
                elif re.search(r'\b1\s*/\s*\d+', txt):
                    state = 'ok'; page.mouse.move(640, 5)
                    page.add_style_tag(content='button,[role=toolbar],[class*=controls],[class*=Controls]{opacity:0!important}'); page.wait_for_timeout(2000)
                    png = os.path.join(WORK, 'cap.png'); page.screenshot(path=png)
                    subprocess.run(['convert', png, '-strip', '-thumbnail', '640x640', '-quality', '82',
                                    os.path.join(SITE, 'thumbs', 'slides', v['design'] + '.jpg')], check=True)
            except Exception as ex: log('canva check failed', u, str(ex)[:120])
            v['ok'] = state != 'blocked'; v['checked'] = state; page.close(); log('canva', v['design'], state)
        b.close()

# ---------------- conversion ----------------
def to_pdf(src):
    od = os.path.join(WORK, 'pdf', hashlib.md5(src.encode()).hexdigest()[:10]); os.makedirs(od, exist_ok=True)
    pdf = os.path.join(od, os.path.splitext(os.path.basename(src))[0] + '.pdf')
    if os.path.exists(pdf): os.remove(pdf)
    subprocess.run(['soffice', '--headless', '--convert-to', 'pdf', '--outdir', od, src], capture_output=True, timeout=300)
    if not os.path.exists(pdf): raise RuntimeError('LibreOffice could not convert this file')
    return pdf

def fix_canva_links(d, canva):
    """Canva share links are edit links; point them at the view-only page instead."""
    import fitz
    for pg in d:
        links = [l for l in pg.get_links() if 'canva.link' in l.get('uri', '') or ('/edit' in l.get('uri', '') and 'canva.com' in l.get('uri', ''))]
        texts = re.findall(r'https://canva\.link/[A-Za-z0-9]+', pg.get_text())
        if not links and not texts: continue
        keep = []
        for l in links:
            if 'canva.link' in l['uri']:
                v = canva_resolve(l['uri'].split('?')[0], canva); new = f"https://www.canva.com/design/{v['design']}/{v['token']}/view" if v.get('design') else None
            else: new = re.sub(r'/edit.*$', '/view', l['uri'])
            keep.append((l['from'], new)); pg.delete_link(l)
        for t in set(texts):
            for r in pg.search_for(t): pg.add_redact_annot(r, text='Canva link (view only)', fontsize=0, fill=(1, 1, 1))
        pg.apply_redactions()
        for r, new in keep:
            if new: pg.insert_link({'kind': fitz.LINK_URI, 'from': r, 'uri': new})

def convert(rel, src, canva):
    import fitz
    ext = os.path.splitext(rel)[1].lower(); sp = slug_path(rel)
    thumb = os.path.join(SITE, 'thumbs', sp + '.jpg'); os.makedirs(os.path.dirname(thumb), exist_ok=True)
    if ext in IMAGES:
        dst = os.path.join(SITE, 'files', sp + ('.jpg' if ext in ('.jpg', '.jpeg') else '.png')); os.makedirs(os.path.dirname(dst), exist_ok=True)
        subprocess.run(['convert', src + '[0]', '-auto-orient', '-strip', dst], check=True)
        subprocess.run(['convert', dst, '-strip', '-thumbnail', '520x520', '-quality', '82', thumb], check=True)
        rec = {'file': dst, 'type': 'image', 'pages': 1}
    else:
        pdf = src if ext == '.pdf' else to_pdf(src)
        dst = os.path.join(SITE, 'files', sp + '.pdf'); os.makedirs(os.path.dirname(dst), exist_ok=True)
        d = fitz.open(pdf); fix_canva_links(d, canva); d.set_metadata({}); d.save(dst, garbage=4, deflate=True); n = len(d); d.close()
        d = fitz.open(dst); pg = d[0]; z = 520 / max(pg.rect.width, 1)
        png = thumb[:-4] + '.png'; pg.get_pixmap(matrix=fitz.Matrix(z, z), alpha=False).save(png); d.close()
        subprocess.run(['convert', png, '-quality', '82', thumb], check=True); os.remove(png)
        rec = {'file': dst, 'type': 'pdf', 'pages': n}
    rec['thumb'] = thumb; rec['bytes'] = os.path.getsize(rec['file']); rec['orig_ext'] = ext
    return {k: (os.path.relpath(v, SITE) if k in ('file', 'thumb') else v) for k, v in rec.items()}

# ---------------- catalog rules for files without hand-made entries ----------------
def class_of(path):
    p = path.lower()
    if 'block 2' in p or '/b2' in p or p.startswith('b2'): return 'b2'
    if 'block 3' in p or '/b3' in p or p.startswith('b3'): return 'b3'
    if p.startswith('ess') or '/b4' in p or 'ess' in os.path.basename(p): return 'ess'
    return 'all'

def weeks_of(path):
    m = re.search(r'[Ww]eeks? ([\d+]+)', path)
    return [int(x) for x in m.group(1).split('+') if x] if m else []

def looks_like_lesson(path):
    return path.startswith('Lesson Plans/') or bool(re.search(r'lesson ?plan', os.path.basename(path), re.I)) or '/Lesson Plans/' in path

def looks_like_slides(path, ex):
    return bool(ex.get('canva')) and bool(re.search(r'slide', path, re.I))

# ---------------- main ----------------
def main():
    ap = argparse.ArgumentParser(); g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--drive'); g.add_argument('--local'); ap.add_argument('--no-canva', action='store_true')
    a = ap.parse_args()
    S = yaml.safe_load(open(os.path.join(HERE, 'settings.yml')))
    excludes = {x.strip().lower() for x in S.get('exclude') or []}
    src = LocalSource(a.local) if a.local else DriveSource(a.drive, json.loads(os.environ['GDRIVE_SA_KEY']))
    CUR = json.load(open(os.path.join(HERE, 'curation.json')))
    files = load('files.json', {}); extracted = load('extracted.json', {}); assets = load('assets.json', {}); canva = load('canva.json', {})
    seed = load('assets_seed.json', {}) if not assets else {}   # one-time: reuse the hand-built conversions
    held_designs = set(S.get('hold_decks') or {})

    entries = src.list(S['include'], excludes)
    if a.drive: log('top-level folders in Drive:', getattr(src, 'found_tops', '?'))
    log(len(entries), 'files found')
    if not entries: sys.exit('No files found: is the folder shared with the service account, and are the folder names in settings.yml right?')
    E = {e['path']: e for e in entries}
    fetched = set()
    def ensure_local(path):
        dest = os.path.join(SRC, path)
        if path not in fetched or not os.path.exists(dest): src.fetch(E[path], dest); fetched.add(path)
        return dest

    # 1. fingerprint new/changed files, extract links + lesson text
    cur_paths = CUR['paths']
    for path, e in E.items():
        f = files.get(path)
        if f and f['key'] == e['key'] and f['hash'] in extracted: continue
        p = ensure_local(path); h = content_hash(p)
        lessonish = (cur_paths.get(path, {}).get('kind') == 'lesson') or looks_like_lesson(path)
        if h not in extracted or (lessonish and 'lesson' not in extracted[h]): extracted[h] = extract(p, lessonish)
        files[path] = {'key': e['key'], 'hash': h}; log('new/changed:', path)
    for path in list(files):
        if path not in E: files.pop(path); log('removed:', path)

    # 2. duplicates -> one canonical copy
    groups = {}
    for path in sorted(E): groups.setdefault(files[path]['hash'], []).append(path)
    canonical = {}
    for h, ps in groups.items():
        cur_c = [cur_paths[p]['canonical'] for p in ps if p in cur_paths and cur_paths[p]['canonical'] in ps]
        c = cur_c[0] if cur_c else sorted(ps, key=lambda p: (not p.startswith('Lesson Plans/') if any(looks_like_lesson(x) for x in ps) else 0, p.count('/'), p))[0]
        for p in ps: canonical[p] = c

    # 3. tree
    hold = set(S.get('hold') or []); tree = []
    lessons = {l['id']: l for l in CUR['lessons']}; materials = {m['id']: m for m in CUR['materials']}
    lesson_by_src = {l['source']: l['id'] for l in CUR['lessons']}
    for path in sorted(E):
        c = canonical[path]; info = cur_paths.get(path) if path in cur_paths and cur_paths[path]['canonical'] == c else None
        ex = extracted[files[c]['hash']]
        if info and files[path]['hash'] == files[c]['hash']: kind, ref, flag = info['kind'], info['ref'], info['flag']
        elif looks_like_slides(c, ex): kind, ref, flag = 'slides', None, None
        elif looks_like_lesson(c) and ex.get('lesson'):
            ref = lesson_by_src.get(c) or 'auto-' + slug(c); kind, flag = 'lesson', None
            if ref not in lessons:
                dates = [f"2026-{int(m):02d}-{int(d):02d}" for m, d in re.findall(r'(?<!\d)(1[0-2]|[1-9])[-_](3[01]|[12]\d|[1-9])(?!\d)', os.path.basename(c))]
                L = ex['lesson']; fmt = 'formal' if len(L['sections']) >= 6 else 'short'
                lessons[ref] = {'id': ref, 'class': class_of(c), 'title': os.path.splitext(os.path.basename(c))[0].strip(), 'dates': dates,
                                'weeks': weeks_of(path), 'topics': [], 'format': fmt, 'source': c, 'subject_line': L['meta'].get('subject'),
                                'sections': L['sections'] if fmt == 'formal' else {}, 'text': '' if fmt == 'formal' else L['text'],
                                'recurring': False, 'materials': []}
        else: kind, ref, flag = 'file', None, None
        ext = os.path.splitext(path)[1].lower()
        status = 'held' if path in hold else 'on_site' if ext in SUPPORTED else 'left_off'
        tree.append({'path': path, 'section': path.split('/')[0], 'name': path.split('/')[-1], 'canonical': c, 'duplicate': c != path,
                     'kind': kind, 'ref': ref, 'flag': flag, 'status': status})
    # lesson text follows the current file (so edits show up), titles/dates stay hand-made
    for l in lessons.values():
        s = l['source'] if l['source'] in files else next((r['canonical'] for r in tree if r['ref'] == l['id']), None)
        L = extracted.get(files[s]['hash'], {}).get('lesson') if s in files else None
        if L:
            if l['format'] == 'formal' and len(L['sections']) >= 6: l['sections'] = L['sections']
            elif l['format'] != 'formal': l['text'] = L['text']

    # 4. convert on-site canonical files (only new/changed)
    on = sorted({r['canonical'] for r in tree if r['status'] == 'on_site'})
    for c in on:
        h = files[c]['hash']; a_ = assets.get(c)
        if not a_ and c in seed and 'error' not in seed[c]: a_ = assets[c] = dict(seed[c], hash=h)
        if a_ and a_.get('hash') == h and os.path.exists(os.path.join(SITE, a_['file'])) and os.path.exists(os.path.join(SITE, a_['thumb'])): continue
        log('converting:', c)
        try: assets[c] = dict(convert(c, ensure_local(c), canva), hash=h)
        except Exception as ex_: assets[c] = {'error': str(ex_)[:200], 'hash': h}; log('  failed:', ex_)
    for c in list(assets):
        if c not in on: assets.pop(c)

    # 5. slide decks
    slides = []
    for c in sorted({r['canonical'] for r in tree if r['kind'] == 'slides' and r['status'] == 'on_site'}):
        for i, (label, u) in enumerate(extracted[files[c]['hash']].get('canva', []), 1):
            slides.append({'id': f'{slug(c)}-{i}', 'class': class_of(c), 'weeks': weeks_of(c), 'label': label, 'url': u, 'source': c})
    for s in slides: canva_resolve(s['url'], canva)
    todo = [s['url'] for s in slides if canva[s['url']].get('design') and 'ok' not in canva[s['url']] and canva[s['url']]['design'] not in held_designs]
    if a.no_canva: [canva[u].update(ok=True) for u in todo]
    else: canva_check_and_capture(list(dict.fromkeys(todo)), canva)

    # 6. tidy: remove converted files no longer used
    keep = {os.path.join(SITE, v[k]) for v in assets.values() for k in ('file', 'thumb') if v.get(k)}
    keep |= {os.path.join(SITE, 'thumbs', 'slides', v['design'] + '.jpg') for v in canva.values() if v.get('design') and v['design'] not in held_designs}
    for sub in ('files', 'thumbs'):
        for dp, dn, fn in os.walk(os.path.join(SITE, sub)):
            for f in fn:
                p = os.path.join(dp, f)
                if p not in keep: os.remove(p)
    save('files.json', files); save('extracted.json', extracted); save('assets.json', assets); save('canva.json', canva)
    if seed and os.path.exists(os.path.join(ST, 'assets_seed.json')): os.remove(os.path.join(ST, 'assets_seed.json'))

    # 7. pages
    import site_pages
    site_pages.build({'tree': tree, 'lessons': list(lessons.values()), 'materials': list(materials.values()), 'slides': slides,
                      'topics': CUR['topics'], 'assets': assets, 'canva': canva, 'hold_decks': S.get('hold_decks') or {},
                      'sections': S['include'], 'blurbs': S.get('blurbs') or {}}, SITE)
    errs = [c for c, v in assets.items() if 'error' in v]
    if errs: log('could not convert:', errs)

if __name__ == '__main__': main()
