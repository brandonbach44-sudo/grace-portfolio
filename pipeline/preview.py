"""Print the folder layout of the shared Drive folder: folder names and file counts only (logs are public)."""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from sources import DriveSource
PRIVATE = {'iep', 'praxis', 'general information', 'student teaching journal'}
d = DriveSource(sys.argv[1], json.loads(os.environ['GDRIVE_SA_KEY']))
def walk(fid, depth, name):
    kids = d._children(fid); folders = [k for k in kids if k['mimeType'] == 'application/vnd.google-apps.folder']
    print('  ' * depth + f'{name}/  ({len(kids) - len(folders)} files)')
    if name.strip().lower() in PRIVATE: print('  ' * (depth + 1) + '(not listed)'); return
    for f in sorted(folders, key=lambda f: f['name']): walk(f['id'], depth + 1, f['name'])
walk(sys.argv[1], 0, '(shared folder)')
