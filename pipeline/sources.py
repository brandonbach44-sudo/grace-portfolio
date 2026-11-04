"""Where Grace's files come from: her Google Drive folder (automatic runs) or a local copy (testing)."""
import hashlib, io, os, re

EXPORT = {  # native Google files -> Office format
    'application/vnd.google-apps.document': ('application/vnd.openxmlformats-officedocument.wordprocessingml.document', '.docx'),
    'application/vnd.google-apps.presentation': ('application/vnd.openxmlformats-officedocument.presentationml.presentation', '.pptx'),
    'application/vnd.google-apps.spreadsheet': ('application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', '.xlsx'),
    'application/vnd.google-apps.drawing': ('image/png', '.png'),
}
SKIP_MIME = {'application/vnd.google-apps.shortcut', 'application/vnd.google-apps.form', 'application/vnd.google-apps.site',
             'application/vnd.google-apps.map', 'application/vnd.google-apps.jam'}


def skipped(name, excludes):
    n = name.strip().lower()
    return n in excludes or n.endswith('(private)')


class LocalSource:
    """A folder on disk, e.g. an unzipped Google Drive download."""
    def __init__(self, root): self.root = root

    def list(self, include, excludes):
        out = []
        for top in include:
            base = os.path.join(self.root, top)
            for dp, dns, fns in os.walk(base):
                dns[:] = [d for d in dns if not skipped(d, excludes)]
                for f in fns:
                    if f.startswith('.') or skipped(f, excludes) or skipped(os.path.splitext(f)[0], excludes): continue
                    p = os.path.join(dp, f)
                    out.append({'path': os.path.relpath(p, self.root), 'key': hashlib.md5(open(p, 'rb').read()).hexdigest(), 'id': None})
        return out

    def fetch(self, entry, dest):
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        with open(os.path.join(self.root, entry['path']), 'rb') as a, open(dest, 'wb') as b: b.write(a.read())


class DriveSource:
    """Grace's 'Student Teaching' folder, read with a view-only service account."""
    def __init__(self, folder_id, key_json):
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        creds = service_account.Credentials.from_service_account_info(key_json, scopes=['https://www.googleapis.com/auth/drive.readonly'])
        self.svc = build('drive', 'v3', credentials=creds, cache_discovery=False)
        self.root = folder_id

    def _children(self, fid):
        items, tok = [], None
        while True:
            r = self.svc.files().list(q=f"'{fid}' in parents and trashed=false", pageSize=1000, pageToken=tok,
                                      fields='nextPageToken, files(id,name,mimeType,md5Checksum,modifiedTime,shortcutDetails)',
                                      supportsAllDrives=True, includeItemsFromAllDrives=True).execute()
            items += r.get('files', []); tok = r.get('nextPageToken')
            if not tok: return items

    def list(self, include, excludes):
        out = []
        tops = {f['name'].strip(): f for f in self._children(self.root) if f['mimeType'] == 'application/vnd.google-apps.folder'}
        if not set(include) & set(tops) and 'Student Teaching' in tops:   # shared the parent folder instead
            tops = {f['name'].strip(): f for f in self._children(tops['Student Teaching']['id']) if f['mimeType'] == 'application/vnd.google-apps.folder'}
        self.found_tops = sorted(tops)
        def walk(fid, prefix):
            seen = {}
            for f in sorted(self._children(fid), key=lambda f: (f['name'], f['id'])):
                mt, name = f['mimeType'], f['name']
                if skipped(name, excludes) or skipped(os.path.splitext(name)[0], excludes): continue
                if mt == 'application/vnd.google-apps.folder':
                    walk(f['id'], prefix + name + '/'); continue
                if mt in SKIP_MIME or (mt.startswith('application/vnd.google-apps.') and mt not in EXPORT): continue
                if mt in EXPORT and not name.lower().endswith(EXPORT[mt][1]): name += EXPORT[mt][1]
                if name in seen:   # same name twice in one folder: number it like Drive's zip download does
                    seen[name] += 1; b, x = os.path.splitext(name); name = f'{b} ({seen[name]}){x}'
                else: seen[name] = 0
                out.append({'path': prefix + name, 'id': f['id'], 'mime': mt,
                            'key': f.get('md5Checksum') or ('mod:' + f['modifiedTime'])})
        for top in include:
            if top in tops: walk(tops[top]['id'], tops[top]['name'] + '/')
        return out

    def fetch(self, entry, dest):
        from googleapiclient.http import MediaIoBaseDownload
        os.makedirs(os.path.dirname(dest), exist_ok=True)
        if entry['mime'] in EXPORT: req = self.svc.files().export_media(fileId=entry['id'], mimeType=EXPORT[entry['mime']][0])
        else: req = self.svc.files().get_media(fileId=entry['id'], supportsAllDrives=True)
        buf = io.FileIO(dest, 'wb'); dl = MediaIoBaseDownload(buf, req, chunksize=16 * 1024 * 1024); done = False
        while not done: _, done = dl.next_chunk()
        buf.close()
