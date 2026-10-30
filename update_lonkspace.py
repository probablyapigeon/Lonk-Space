"""Update program files in this folder, preserving data and backing up replaced code."""
import argparse
from datetime import datetime
import io
from pathlib import Path, PurePosixPath
import shutil
import tempfile
import urllib.request
import zipfile

FILES = ('lonkspace.py','town_store.py','town_runtime.py','llm_mouth.py','webapp.py','worker.py',
         'launch.py','Start-LonkSpace.bat','terminal_chat.py','requirements-web.txt',
         'README.md','HOSTING.md','templates/town.html','templates/dashboard.html',
         'static/town.css','static/town.js')


def install_archive(content, root):
    root=Path(root).resolve()
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        paths={}
        for info in archive.infolist():
            parts=PurePosixPath(info.filename).parts
            if '..' in parts or info.filename.startswith('/') or '\\' in info.filename:
                raise ValueError('Invalid archive path.')
            relative='/'.join(parts[1:])
            if relative in FILES:
                if info.file_size > 2_000_000 or relative in paths:
                    raise ValueError('Unexpected archive file.')
                paths[relative]=info
        if set(paths)!=set(FILES):
            raise ValueError('Incomplete update. No files were changed.')
        payload={name:archive.read(info) for name,info in paths.items()}
    backup=root/'.update-backups'/datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    for name in FILES:
        target=root/name
        if target.is_symlink() or not target.resolve().is_relative_to(root):
            raise ValueError('Refusing to replace symlink: '+name)
    for name in FILES:
        target=root/name
        if target.exists():
            dest=backup/name
            dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(target,dest)
    for name,data in payload.items():
        target=root/name
        target.parent.mkdir(parents=True,exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=target.parent,delete=False) as file:
            file.write(data)
            staged=Path(file.name)
        staged.replace(target)
    return backup


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ref',default='feature/browser-towns')
    args=parser.parse_args()
    root=Path(__file__).resolve().parent
    if not (root/'webapp.py').is_file():
        raise SystemExit('Put this updater beside your existing webapp.py before running it.')
    # Ref is an explicitly selected repository revision, never a shell command.
    from urllib.parse import quote
    import re
    revision=args.ref if re.fullmatch(r'[0-9a-fA-F]{40}',args.ref) else 'refs/heads/'+args.ref
    url='https://github.com/probablyapigeon/Lonk-Space/archive/'+quote(revision,safe='/')+'.zip'
    print('Downloading program update. Your data folder will not be replaced.')
    with urllib.request.urlopen(url,timeout=60) as response:
        content=response.read(10_000_001)
    if len(content)>10_000_000:
        raise SystemExit('Update was unexpectedly large. Nothing changed.')
    import os, socket
    with socket.socket() as probe:
        probe.settimeout(1)
        if probe.connect_ex(('127.0.0.1',int(os.environ.get('PORT','8080')))) == 0:
            raise SystemExit('The old website is still running. Stop it with Ctrl+C before updating.')
    from worker import worker_lock
    db=Path(os.environ.get('LONK_DB',str(root/'data'/'town.db'))).resolve()
    db.parent.mkdir(parents=True,exist_ok=True)
    with worker_lock(str(db)+'.worker.lock'):
        backup=install_archive(content,root)
    print('Updated. Previous code saved at:',backup)
    print('Start with: python launch.py  (or double-click Start-LonkSpace.bat)')


if __name__=='__main__':
    try:
        main()
    except Exception as error:
        raise SystemExit('Update stopped: '+str(error))
