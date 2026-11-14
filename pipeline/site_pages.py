"""Generate Grace's portfolio pages, mirroring her Google Drive folder structure.
Plain styling on purpose: organization first, theme later. Called by update.py."""
import json, os, re, html, shutil
from collections import OrderedDict

def build(D, OUT_DIR):
    global CAT, ASSETS, OUT, SECTIONS, BLURB, LESSONS, MATS, SLIDES, TOPICS, CANVA, CANVA_OK, HOLD_DECKS
    CAT = D; ASSETS = {k: dict(v) for k, v in D['assets'].items()}; OUT = OUT_DIR
    SECTIONS = D['sections']; BLURB = D['blurbs']
    LESSONS = {l['id']: l for l in D['lessons']}; MATS = {m['id']: m for m in D['materials']}
    SLIDES = D['slides']; TOPICS = D['topics']; CANVA = D['canva']
    CANVA_OK = {u: v.get('ok', True) for u, v in CANVA.items()}
    HOLD_DECKS = set(D['hold_decks'])
    for s in SLIDES:   # held decks are matched by Canva design id
        if CANVA.get(s['url'], {}).get('design') in HOLD_DECKS: HOLD_DECKS.add(s['id'])
    # wipe old pages (converted files and previews are kept)
    for dp, dn, fn in os.walk(OUT):
        if os.path.relpath(dp, OUT).split(os.sep)[0] in ('files', 'thumbs'): continue
        for f in fn:
            if f.endswith('.html') or f in ('style.css', '.nojekyll'): os.remove(os.path.join(dp, f))
    # slide documents: first slide of the first playable deck as the folder preview
    for s in SLIDES:
        v = CANVA.get(s['url'], {}); rel = f"thumbs/slides/{v.get('design')}.jpg"
        if s['id'] in HOLD_DECKS or not v.get('design') or s['source'] not in ASSETS or ASSETS[s['source']].get('slide_thumb'): continue
        if os.path.exists(os.path.join(OUT, rel)): ASSETS[s['source']].update(thumb=rel, slide_thumb=True)
    _pages()

HIDDEN_FLAGS = {'third-party'}   # still recorded in the catalog, just not shown
def canva_view(u):
    v = CANVA.get(u, {}); return f"https://www.canva.com/design/{v['design']}/{v['token']}/view" if v.get('design') else u
def canva_embed(u):
    v = CANVA.get(u, {}); return f"https://www.canva.com/design/{v['design']}/{v['token']}/view?embed" if v.get('design') else None
SEC_LABEL = {'standards': 'PA Standards', 'essential_questions': 'Essential Questions', 'objectives': 'Objectives',
             'assessment': 'Assessment', 'differentiation': 'Differentiation', 'environment': 'Classroom Environment & Routines',
             'prior_knowledge': 'Activating Prior Knowledge', 'materials': 'Materials Needed', 'vocabulary': 'Vocabulary',
             'sequence': 'Lesson Sequence', 'closure': 'Closure'}
TAGNOTE = {'third-party': 'Not created by Grace (purchased or published resource)', "cooperating teacher's": "Cooperating teacher's material",
           'university paperwork': 'University program document', 'school staff': 'School staff material', 'source unknown': 'Source not yet confirmed'}
e = html.escape

def slug(s):
    s = s.replace('&', 'and').replace('+', '-')
    return re.sub(r'-+', '-', re.sub(r'[^a-z0-9]+', '-', s.lower())).strip('-')
def slug_dir(folder_path): return '/'.join(slug(p) for p in folder_path.split('/') if p)
def page_for_file(rel):
    parts = rel.split('/'); return '/'.join(slug(p) for p in parts[:-1]) + '/' + slug(os.path.splitext(parts[-1])[0]) + '.html'
def natkey(s): return [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', s)]
def rel_to(frm, to):  # frm, to are site-relative paths
    return os.path.relpath(to, os.path.dirname(frm) or '.')

CSS = """
:root{--bg:#ffd3ca;--fg:#6e0009;--paper:#ffffff;--soft:#ffe6e0;color-scheme:light}
*{box-sizing:border-box}
html{background:var(--bg)}
body{margin:0;background:var(--bg);color:var(--fg);font:18px/1.6 "Antic Didone",Georgia,"Times New Roman",serif;
 padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px))}
a{color:var(--fg);text-decoration:none} a:hover{text-decoration:underline}
:focus-visible{outline:2px solid var(--fg);outline-offset:3px}
.wrap{max-width:1080px;margin:0 auto}
header{text-align:center;padding-top:36px}
.brand{display:inline-block;font-size:34px;line-height:1.1;color:var(--fg)}
.brand:hover{text-decoration:none}
.kicker{display:block;font-size:13px;letter-spacing:.3em;text-transform:uppercase;margin-bottom:12px}
.home header{padding-top:72px}
.home .brand{font-size:clamp(52px,9vw,92px);line-height:1}
.tagline{margin:18px 0 0;font-size:20px;font-style:italic}
.rule{margin-top:28px;border-top:1px solid var(--fg);border-bottom:1px solid var(--fg);height:4px}
.home .rule{margin-top:40px}
nav.top{display:flex;flex-wrap:wrap;justify-content:center;gap:8px 34px;padding:16px 0;font-size:18px;border-bottom:1px solid var(--fg)}
nav.top a.on{border-bottom:1px solid var(--fg)}
nav.top a:hover{text-decoration:none;border-bottom:1px solid var(--fg)}
main{padding-block:36px 72px}
.crumbs{font-size:15px;text-align:center;margin-bottom:6px;letter-spacing:.04em}
.crumbs span{margin:0 8px}
h1{font-weight:400;font-size:clamp(2.2rem,6vw,4.4rem);line-height:1.05;margin:0 0 8px;text-align:center;text-wrap:balance}
h2{font-weight:400;font-size:1.65rem;margin:52px 0 18px;text-align:center}
h2 a{color:var(--fg)}
h3{font-weight:400;font-size:1.2rem;margin:20px 0 6px}
.sub{margin:0 0 20px;text-align:center;font-style:italic;font-size:19px}
.list{list-style:none;margin:0;padding:0;background:var(--paper);border:1px solid var(--fg)}
.list li+li{border-top:1px solid var(--bg)}
.list a{display:flex;justify-content:space-between;gap:16px;padding:16px 22px;color:var(--fg);font-size:19px}
.list a:hover{background:var(--soft);text-decoration:none}
.list a>span{min-width:0;overflow-wrap:anywhere}
.list a>span .count{white-space:normal}
.count{font-size:15px;font-style:italic;white-space:nowrap}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:30px 24px}
.item{display:flex;flex-direction:column;gap:10px;color:var(--fg);min-width:0;text-align:center}
.item:hover{text-decoration:none} .item:hover .t{text-decoration:underline}
.thumb{aspect-ratio:4/5;max-width:100%;background:var(--paper);border:1px solid var(--fg);padding:12px;display:flex;align-items:center;justify-content:center;overflow:hidden}
.thumb img{width:100%;height:100%;object-fit:contain;background:var(--paper)}
.thumb.slide img{height:auto}
.thumb .noimg{font-size:15px;font-style:italic;padding:8px;text-align:center}
.t{font-size:18px;line-height:1.3;overflow-wrap:anywhere}
.fn{font-size:13px;opacity:.75;overflow-wrap:anywhere}
.tag{display:inline-block;align-self:center;font-size:12px;letter-spacing:.08em;padding:1px 8px;border:1px solid var(--fg)}
.meta{display:flex;flex-wrap:wrap;justify-content:center;gap:6px 18px;font-size:16px;font-style:italic;margin:4px 0 16px}
.btns{display:flex;flex-wrap:wrap;justify-content:center;gap:12px;margin:14px 0 22px}
.btn{display:inline-block;padding:10px 20px;border:1px solid var(--fg);background:var(--paper);color:var(--fg);font-size:16px;letter-spacing:.04em;min-height:44px}
.btn:hover{background:var(--fg);color:var(--paper);text-decoration:none}
.viewer{width:100%;height:85vh;min-height:440px;border:1px solid var(--fg);background:var(--paper)}
.imgview{display:block;max-width:100%;margin:0 auto;border:1px solid var(--fg);background:var(--paper);padding:12px}
.lp{background:var(--paper);border:1px solid var(--fg);padding:8px 28px 22px}
.lp section{border-top:1px solid var(--bg);padding-top:14px;margin-top:14px;display:grid;grid-template-columns:220px 1fr;gap:18px}
.lp section:first-child{border-top:0}
.lp section>*{min-width:0} .lp h3{margin:0;font-size:1.1rem;font-style:italic}
.lp ul{margin:0;padding-left:20px} .lp li{margin-bottom:4px}
.pre{white-space:pre-wrap;overflow-wrap:anywhere}
.deck{background:var(--paper);border:1px solid var(--fg);padding:16px 20px;margin-bottom:18px;display:grid;grid-template-columns:minmax(0,1fr) auto;gap:14px;align-items:center}
.embed-slot{grid-column:1/-1;max-width:100%;padding:14px!important;background:var(--soft);border:1px dashed var(--fg);display:flex;align-items:center;justify-content:center;font-size:15px;text-align:center}
.embed{grid-column:1/-1;position:relative;width:100%;aspect-ratio:16/9;max-width:100%;background:var(--bg);border:1px solid var(--fg)}
.embed iframe{position:absolute;inset:0;width:100%;height:100%;border:0}
.pn{display:flex;justify-content:space-between;gap:12px;padding:12px 0;margin:16px 0;font-size:17px;font-style:italic;border-top:1px solid var(--fg);border-bottom:1px solid var(--fg)}
.pn a{max-width:48%;overflow-wrap:anywhere}
.pn a:last-child{text-align:right}
.note{background:var(--paper);border:1px solid var(--fg);padding:16px 20px;font-size:17px;margin:16px 0;text-align:center;font-style:italic}
.also{font-size:15px;text-align:center;font-style:italic}
details summary{cursor:pointer;margin:14px 0;text-align:center}
input[type=search]{display:block;width:100%;max-width:560px;margin:0 auto 10px;font:inherit;color:var(--fg);background:var(--paper);padding:12px 16px;border:1px solid var(--fg)}
input[type=search]::placeholder{color:var(--fg);opacity:.6}
#n{text-align:center}
.blocks{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:28px;margin-top:28px}
.block{display:flex;flex-direction:column;gap:12px;background:var(--paper);border:1px solid var(--fg);padding:38px 34px;color:var(--fg)}
.block:hover{text-decoration:none;outline:1px solid var(--fg)}
.block .k{font-size:13px;letter-spacing:.24em;text-transform:uppercase}
.block .n{font-size:34px;line-height:1.1}
.block .d{font-size:18px;font-style:italic}
.block .c{margin-top:auto;padding-top:14px;border-top:1px solid var(--fg);font-size:16px}
footer{border-top:1px solid var(--fg);padding:20px 0 40px;text-align:center;font-size:15px}
.small{font-size:15px}
@media (max-width:900px){.blocks{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media (max-width:620px){.blocks{grid-template-columns:1fr}.lp section{grid-template-columns:1fr;gap:4px}.viewer{height:70vh}nav.top{gap:6px 20px;font-size:17px}.block{padding:28px 24px}}
"""

RESUME_NAMES = ('Résumé', 'Resume', 'Résume', 'Resumé')
PICTURES = 'Photos'

def main_sections(): return [s for s in SECTIONS if s not in RESUME_NAMES and s != PICTURES]

def layout(path, title, body, active=None, crumbs=None, home=False):
    def L(to): return e(rel_to(path, to))
    items = [(s, slug(s) + '/index.html') for s in main_sections()] + [('Résumé', 'resume.html'), (PICTURES, slug(PICTURES) + '/index.html'), ('Search', 'search.html')]
    nav = ''.join(f'<a href="{L(h)}"{" class=\"on\" aria-current=\"page\"" if active == t else ""}>{e(t)}</a>' for t, h in items)
    cr = ''
    if crumbs:
        cr = '<div class="crumbs">' + '<span>›</span>'.join(f'<a href="{L(h)}">{e(t)}</a>' if h else e(t) for t, h in crumbs) + '</div>'
    head = (f'<span class="kicker">Student Teaching Portfolio</span><a class="brand" href="{L("index.html")}">Grace Dittman</a>'
            f'<p class="tagline">Special Education · Grades 9–12</p>') if home else f'<a class="brand" href="{L("index.html")}">Grace Dittman</a>'
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<title>{e(title)} · Grace Dittman Portfolio</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Antic+Didone&display=swap" rel="stylesheet">
<link rel="stylesheet" href="{L('style.css')}"></head>
<body class="{'home' if home else ''}"><div class="wrap"><header>{head}<div class="rule"></div><nav class="top" aria-label="Sections">{nav}</nav></header>
<main>{cr}{body}</main><footer>Grace Dittman · Student Teaching Portfolio</footer></div></body></html>"""

def pn_html(frm, prev, nxt, what):
    if not prev and not nxt: return ''
    a = f'<a href="{e(rel_to(frm, prev[1]))}">← {e(prev[0])}</a>' if prev else '<span></span>'
    b = f'<a href="{e(rel_to(frm, nxt[1]))}">{e(nxt[0])} →</a>' if nxt else '<span></span>'
    return f'<nav class="pn" aria-label="{e(what)}">{a}{b}</nav>'

def write(path, content):
    p = os.path.join(OUT, path); os.makedirs(os.path.dirname(p), exist_ok=True); open(p, 'w').write(content)

def _pages():
    global on, held_n, FILE_PAGE, LOCATIONS, folders
    # ---------- index of tree ----------
    on = [r for r in CAT['tree'] if r['status'] == 'on_site']
    held_n = sum(1 for r in CAT['tree'] if r['status'] == 'held')

    def display_title(r):
        if r['kind'] == 'lesson' and r['ref'] in LESSONS: return LESSONS[r['ref']]['title']
        if r['kind'] == 'material' and r['ref'] in MATS:
            m = MATS[r['ref']]
            if r['canonical'] in m['key_files']: return m['title'] + ' (Answer Key)'
            if len(m['files']) > 1: return f"{m['title']} ({m['files'].index(r['canonical'])+1} of {len(m['files'])})"
            return m['title']
        return os.path.splitext(r['name'])[0]

    FILE_PAGE = {}   # canonical -> page path
    for r in on:
        if not r['duplicate']: FILE_PAGE[r['canonical']] = page_for_file(r['canonical'])
    for r in on:      # canonical copies that live only in a held/left-off spot are not expected, but guard anyway
        FILE_PAGE.setdefault(r['canonical'], page_for_file(r['canonical']))
    LOCATIONS = {}
    for r in on: LOCATIONS.setdefault(r['canonical'], []).append(r['path'])

    # folders: every directory that contains on-site files (directly or below)
    folders = OrderedDict()
    for r in on:
        parts = r['path'].split('/')
        for i in range(1, len(parts)):
            folders.setdefault('/'.join(parts[:i]), {'files': [], 'subs': set()})
        folders['/'.join(parts[:-1])]['files'].append(r)
        for i in range(1, len(parts) - 1):
            folders['/'.join(parts[:i])]['subs'].add('/'.join(parts[:i + 1]))
    for s in SECTIONS:
        if s not in RESUME_NAMES: folders.setdefault(s, {'files': [], 'subs': set()})
    def count_under(f): return sum(1 for r in on if r['path'].startswith(f + '/'))

    def tile(frm, r):
        a = ASSETS.get(r['canonical'], {}); page = FILE_PAGE[r['canonical']]
        img = f'<img loading="lazy" src="{e(rel_to(frm, a["thumb"]))}" alt="">' if a.get('thumb') else '<span class="noimg">No preview</span>'
        tags = ''
        if r.get('flag') and r['flag'] not in HIDDEN_FLAGS: tags += f'<span class="tag">{e(r["flag"])}</span>'
        return f'<a class="item" href="{e(rel_to(frm, page))}"><div class="thumb{' slide' if a.get('slide_thumb') else ''}">{img}</div><span class="t">{e(display_title(r))}</span><span class="fn">{e(r["name"])}</span>{tags}</a>'

    def crumbs_for(folder, extra_last=None):
        parts = folder.split('/'); cr = [('Home', 'index.html')]
        for i in range(1, len(parts) + 1):
            f = '/'.join(parts[:i]); cr.append((parts[i - 1], slug_dir(f) + '/index.html'))
        if extra_last: cr.append((extra_last, None))
        else: cr[-1] = (cr[-1][0], None)
        return cr

    # ---------- folder pages ----------
    for f, info in folders.items():
        path = slug_dir(f) + '/index.html'; sec = f.split('/')[0]
        body = f'<h1>{e(f.split("/")[-1])}</h1>'
        if '/' not in f: body += f'<p class="sub">{e(BLURB.get(f, ""))}</p>'
        if f == PICTURES and not info['files'] and not info['subs']: body += '<div class="note">Photos are coming soon.</div>'
        subs = sorted(info['subs'], key=natkey)
        if sec == 'Student Teaching Journal' and not info['files']:
            body += '<div class="note">The journal is held back for now because it describes a specific student. It will be added after review.</div>'
        # direct files
        files = sorted(info['files'], key=lambda r: natkey(r['name']))
        if files:
            if subs: body += '<h2>Files in this folder</h2>'
            body += '<div class="grid">' + ''.join(tile(path, r) for r in files) + '</div>'
        # sub-folders: shallow folders (weeks) show each sub-sub-folder inline as a group
        for s in subs:
            sname = s.split('/')[-1]; n = count_under(s)
            inner = folders[s]
            if '/' not in f:  # section page: folders listed as rows below
                continue
            body += f'<h2><a href="{e(rel_to(path, slug_dir(s) + "/index.html"))}">{e(sname)}</a> <span class="count">· {n} file{"s" if n != 1 else ""}</span></h2>'
            if inner['subs']:
                body += '<ul class="list">' + ''.join(f'<li><a href="{e(rel_to(path, slug_dir(x) + "/index.html"))}"><span>📁 {e(x.split("/")[-1])}</span><span class="count">{count_under(x)} file{"s" if count_under(x)!=1 else ""}</span></a></li>' for x in sorted(inner['subs'], key=natkey)) + '</ul>'
            if inner['files']:
                body += '<div class="grid">' + ''.join(tile(path, r) for r in sorted(inner['files'], key=lambda r: natkey(r['name']))) + '</div>'
        if '/' not in f:
            rows = subs
            if rows:
                body += '<ul class="list">' + ''.join(
                    f'<li><a href="{e(rel_to(path, slug_dir(s) + "/index.html"))}"><span>📁 {e(s.split("/")[-1])} <span class="count">' +
                    ('· ' + ', '.join(e(x.split('/')[-1]) for x in sorted(folders[s]['subs'], key=natkey)) if folders[s]['subs'] else '') +
                    f'</span></span><span class="count">{count_under(s)} file{"s" if count_under(s)!=1 else ""}</span></a></li>' for s in rows) + '</ul>'
        if '/' in f:
            parent = '/'.join(f.split('/')[:-1]); sibs = sorted(folders[parent]['subs'], key=natkey); i = sibs.index(f)
            prev = (sibs[i-1].split('/')[-1], slug_dir(sibs[i-1]) + '/index.html') if i > 0 else None
            nxt = (sibs[i+1].split('/')[-1], slug_dir(sibs[i+1]) + '/index.html') if i + 1 < len(sibs) else None
            pn = pn_html(path, prev, nxt, 'Previous and next folder')
            body = body.replace('</h1>', '</h1>' + pn, 1) + pn
        write(path, layout(path, f.split('/')[-1], body, active=sec, crumbs=crumbs_for(f) if '/' in f else None))

    # ---------- file pages ----------
    def lesson_html(l):
        h = f'<div class="meta"><span>{e(", ".join(d.replace("2026-", "").replace("-", "/") for d in l["dates"]) or ("Recurring" if l["recurring"] else ""))}</span>'
        h += f'<span>{e(" · ".join(TOPICS[t] for t in l["topics"]))}</span>'
        if l.get('subject_line'): h += f'<span>{e(l["subject_line"])}</span>'
        h += '</div>'
        if l['format'] == 'formal':
            h += '<div class="lp">'
            for k, lab in SEC_LABEL.items():
                lines = l['sections'].get(k)
                if not lines: continue
                body = f'<p>{e(lines[0])}</p>' if len(lines) == 1 else '<ul>' + ''.join(f'<li>{e(x)}</li>' for x in lines) + '</ul>'
                h += f'<section><h3>{e(lab)}</h3><div>{body}</div></section>'
            h += '</div>'
        else:
            h += f'<div class="pre">{e(l["text"])}</div>'
        return h

    def related_html(frm, l):
        out = ''
        ms = [MATS[m] for m in l['materials'] if m in MATS]
        ms = [m for m in ms if m['files'][0] in FILE_PAGE]
        if ms:
            out += '<h2>Materials from the same week</h2><div class="grid">'
            for m in ms:
                r = next(x for x in on if x['canonical'] == m['files'][0])
                out += tile(frm, r)
            out += '</div>'
        ss = [s for s in SLIDES if s['class'] == l['class'] and set(s['weeks']) & set(l['weeks']) and not l.get('recurring') and s['id'] not in HOLD_DECKS]
        if ss:
            out += '<h2>Slides from the same week</h2><ul class="list">' + ''.join(
                f'<li><a href="{e(canva_view(s["url"]))}" target="_blank" rel="noopener"><span>▶ {e(s["label"] or "Slides")}</span><span class="count">Open in Canva ↗</span></a></li>' for s in ss) + '</ul>'
        return out

    for canon, page in FILE_PAGE.items():
        r = next(x for x in on if x['canonical'] == canon and not x['duplicate']) if any(x['canonical'] == canon and not x['duplicate'] for x in on) else next(x for x in on if x['canonical'] == canon)
        a = ASSETS.get(canon, {}); folder = '/'.join(canon.split('/')[:-1]); title = display_title(r)
        body = f'<h1>{e(title)}</h1><p class="sub">{e(r["name"])}</p>'
        if r.get('flag') and r['flag'] not in HIDDEN_FLAGS: body += f'<div class="note">{e(TAGNOTE.get(r["flag"], r["flag"]))}.</div>'
        locs = LOCATIONS.get(canon, [])
        if len(locs) > 1:
            body += '<p class="also">Also in: ' + ', '.join(f'<a href="{e(rel_to(page, slug_dir("/".join(p.split("/")[:-1])) + "/index.html"))}">{e("/".join(p.split("/")[:-1]))}</a>' for p in locs if p != canon) + '</p>'
        fileurl = rel_to(page, a['file']) if a.get('file') else None
        if r['kind'] == 'slides':
            decks = [s for s in SLIDES if s['source'] == canon]
            body += '<p class="small">Canva slide decks. Use the arrows to click through each one, or open it full size in Canva.</p>'
            for s in decks:
                if s['id'] in HOLD_DECKS:
                    body += f'<div class="deck"><b>{e(s["label"] or "Slides")}</b><span></span><div class="embed-slot">This slide deck is held back for review.</div></div>'
                    continue
                emb = canva_embed(s['url'])
                if emb and CANVA_OK.get(s['url'], False):
                    frame = f'<div class="embed"><iframe loading="lazy" src="{e(emb)}" allowfullscreen allow="fullscreen" title="{e(s["label"] or "Slides")}"></iframe></div>'
                else:
                    frame = '<div class="embed-slot">This deck can\'t be shown yet: its sharing setting in Canva needs to be turned on.</div>'
                body += f'<div class="deck"><b>{e(s["label"] or "Slides")}</b><a class="btn" href="{e(canva_view(s["url"]))}" target="_blank" rel="noopener">Open in Canva ↗</a>{frame}</div>'
        elif r['kind'] == 'lesson' and r['ref'] in LESSONS:
            l = LESSONS[r['ref']]
            body += lesson_html(l)
            if fileurl: body += f'<div class="btns"><a class="btn" href="{e(fileurl)}" target="_blank">Open original document (PDF)</a></div><details><summary>Show the original document here</summary><iframe class="viewer" src="{e(fileurl)}" loading="lazy" title="{e(title)}"></iframe></details>'
            body += related_html(page, l)
        else:
            if a.get('type') == 'image':
                body += f'<div class="btns"><a class="btn" href="{e(fileurl)}" target="_blank">Open full size</a></div><img class="imgview" src="{e(fileurl)}" alt="{e(title)}">'
            elif fileurl:
                pg = a.get('pages'); body += f'<div class="meta"><span>{pg} page{"s" if pg != 1 else ""}</span></div>' if pg else ''
                body += f'<div class="btns"><a class="btn" href="{e(fileurl)}" target="_blank">Open PDF</a></div><iframe class="viewer" src="{e(fileurl)}" loading="lazy" title="{e(title)}"></iframe>'
            else:
                body += '<div class="note">Preview not available.</div>'
            if r['kind'] == 'material' and r['ref'] in MATS:
                m = MATS[r['ref']]; others = [f for f in m['files'] + m['key_files'] if f != canon and f in FILE_PAGE]
                if others:
                    body += '<h2>Goes with</h2><div class="grid">' + ''.join(tile(page, next(x for x in on if x['canonical'] == f)) for f in others) + '</div>'
                ls = [LESSONS[i] for i in m['lessons'] if i in LESSONS]
                if ls:
                    body += '<h2>Lesson plans from the same week</h2><ul class="list">' + ''.join(
                        f'<li><a href="{e(rel_to(page, FILE_PAGE[l["source"]]))}"><span>{e(l["title"])}</span><span class="count">{e(", ".join(d.replace("2026-", "").replace("-", "/") for d in l["dates"]))}</span></a></li>'
                        for l in ls if l['source'] in FILE_PAGE) + '</ul>'
        seq = []
        for x in sorted(folders[folder]['files'], key=lambda x: natkey(x['name'])):
            pg_ = FILE_PAGE[x['canonical']]
            if pg_ not in [q[1] for q in seq]: seq.append((display_title(x), pg_))
        i = [q[1] for q in seq].index(page) if page in [q[1] for q in seq] else -1
        if i >= 0:
            pn = pn_html(page, seq[i-1] if i > 0 else None, seq[i+1] if i + 1 < len(seq) else None, 'Previous and next file')
            body = body.replace('</p>', '</p>' + pn, 1) + pn
        write(page, layout(page, title, body, active=canon.split('/')[0], crumbs=crumbs_for(folder, title)))

    # ---------- home, résumé, search ----------
    def block(href, kind, name, desc, count):
        return f'<a class="block" href="{e(href)}"><span class="k">{e(kind)}</span><span class="n">{e(name)}</span><span class="d">{e(desc)}</span><span class="c">{e(count)}</span></a>'
    def nfiles(n, word='file'): return f'{n} {word}{"s" if n != 1 else ""}'
    blocks = ''
    for s in main_sections():
        n = count_under(s); kind = 'Collection' if s == 'Lesson Plans' else 'Class'
        blocks += block(slug(s) + '/index.html', kind, s, BLURB.get(s, ''), nfiles(n, 'lesson plan' if s == 'Lesson Plans' else 'file'))
    res_files = sorted([r for r in on if r['section'] in RESUME_NAMES and not r['duplicate']], key=lambda r: natkey(r['name']))
    blocks += block('resume.html', 'About', 'Résumé', BLURB.get('Résumé', 'Education, certification and experience'), 'View or download' if res_files else 'Coming soon')
    npic = count_under(PICTURES)
    blocks += block(slug(PICTURES) + '/index.html', 'Gallery', PICTURES, BLURB.get(PICTURES, 'The classroom and student work'), nfiles(npic, 'photo') if npic else 'Coming soon')
    write('index.html', layout('index.html', 'Home', f'<div class="blocks">{blocks}</div>', home=True))
    if res_files:
        r = res_files[0]; a = ASSETS.get(r['canonical'], {}); f_ = a.get('file')
        body = '<h1>Résumé</h1>'
        if f_:
            body += f'<div class="btns"><a class="btn" href="{e(f_)}" download>Download</a><a class="btn" href="{e(f_)}">Open full screen</a></div>'
            body += (f'<img class="imgview" src="{e(f_)}" alt="Résumé">' if a.get('type') == 'image' else f'<iframe class="viewer" src="{e(f_)}#view=FitH" title="Résumé"></iframe>')
        if len(res_files) > 1:
            body += '<h2>Also</h2><div class="grid">' + ''.join(tile('resume.html', x) for x in res_files[1:]) + '</div>'
    else:
        body = '<h1>Résumé</h1><div class="note">Grace\'s résumé is coming soon.</div>'
    write('resume.html', layout('resume.html', 'Résumé', body, active='Résumé', crumbs=[('Home', 'index.html'), ('Résumé', None)]))
    idx = [{'t': display_title(r), 'n': r['name'], 'f': '/'.join(r['canonical'].split('/')[:-1]), 'u': FILE_PAGE[r['canonical']],
            'k': 'Lesson plan' if r['kind'] == 'lesson' else 'Slides' if r['kind'] == 'slides' else 'File'} for r in on if not r['duplicate']]
    search = f"""<h1>Search</h1><p class="sub">Find any lesson plan, worksheet or file by name, topic or folder.</p>
    <input type="search" id="q" placeholder="Try: two-step equations, bingo, money, Week 7" autofocus>
    <p class="count" id="n"></p><ul class="list" id="res"></ul>
    <script>const D={json.dumps(idx)};const q=document.getElementById('q'),res=document.getElementById('res'),n=document.getElementById('n');
    function esc(s){{return s.replace(/[&<>"]/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}}[c]))}}
    function go(){{const t=q.value.toLowerCase().trim().split(/\\s+/).filter(Boolean);const m=D.filter(d=>{{const h=(d.t+' '+d.n+' '+d.f+' '+d.k).toLowerCase();return t.every(w=>h.includes(w))}});
    n.textContent=t.length?m.length+' results':D.length+' files';res.innerHTML=m.slice(0,300).map(d=>'<li><a href="'+d.u+'"><span>'+esc(d.t)+'<br><span class="count">'+esc(d.f)+' · '+esc(d.n)+'</span></span><span class="count">'+d.k+'</span></a></li>').join('')}}
    q.addEventListener('input',go);go();</script>"""
    write('search.html', layout('search.html', 'Search', search, active='Search', crumbs=[('Home', 'index.html'), ('Search', None)]))
    open(os.path.join(OUT, 'style.css'), 'w').write(CSS)
    open(os.path.join(OUT, '.nojekyll'), 'w').write('')
    print('folders:', len(folders), '| file pages:', len(FILE_PAGE), '| on-site entries:', len(on), '| held:', held_n)
