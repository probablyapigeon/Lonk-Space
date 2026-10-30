"""Start the website and all personal town clocks with one command."""
import argparse
import contextlib
import json
import os
from pathlib import Path
import shutil
import sqlite3
import threading
import webbrowser


def choose_legacy_owner(path):
    if not path.exists():
        return
    with contextlib.closing(sqlite3.connect(path)) as db:
        if db.execute("SELECT 1 FROM sqlite_master WHERE name='towns'").fetchone():
            return
        if not db.execute("SELECT 1 FROM sqlite_master WHERE name='users'").fetchone():
            return
        names = [r[0] for r in db.execute('SELECT username FROM users ORDER BY created,id')]
    if len(names) > 1 and not os.environ.get('LONK_LEGACY_OWNER'):
        print('Which account should keep your EXISTING town? Other accounts get new towns.')
        for i,name in enumerate(names,1):
            print(f'  {i}. {name}')
        while True:
            answer = input('Account number: ').strip()
            if answer.isdigit() and 1 <= int(answer) <= len(names):
                os.environ['LONK_LEGACY_OWNER'] = names[int(answer)-1]
                break


def import_local_moltbook(store):
    # Only the owner of the migrated town may inherit the operator's old credential file.
    source = Path.home()/'.lonkspace'/'moltbook.json'
    if not source.is_file():
        return
    with store.transaction() as db:
        if db.execute("SELECT 1 FROM meta WHERE key='moltbook_import_checked'").fetchone():
            return
        row = db.execute("SELECT value FROM meta WHERE key='legacy_owner'").fetchone()
        if not row:
            return
        destination = store.path.parent/'moltbook'/row[0]/'moltbook.json'
        if not destination.exists():
            # Validate before copying; never display or put the key into the database/feed.
            value = json.loads(source.read_text(encoding='utf-8'))
            if not isinstance(value,dict):
                raise ValueError('Existing Moltbook credential file has an invalid format.')
            destination.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
            shutil.copyfile(source,destination)
            os.chmod(destination,0o600)
        db.execute("INSERT INTO meta VALUES('moltbook_import_checked','1')")


def main():
    from waitress.server import create_server
    from webapp import create_app
    from worker import worker_lock, serve_towns
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--no-browser',action='store_true')
    args=parser.parse_args()
    root=Path(__file__).resolve().parent
    os.chdir(root)
    path=Path(os.environ.get('LONK_DB','data/town.db')).resolve()
    path.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
    # Same lock used by the old standalone worker: never run two clocks.
    with worker_lock(str(path)+'.worker.lock'):
        choose_legacy_owner(path)
        app=create_app()
        store=app.extensions['town']
        import_local_moltbook(store)
        port=int(os.environ.get('PORT','8080'))
        # Bind before starting any world clocks; an occupied port must fail without ticking.
        server=create_server(app,host=os.environ.get('LONK_HOST','127.0.0.1'),port=port,
                             threads=4,max_request_body_size=16384)
        stop=threading.Event()
        worker=threading.Thread(target=serve_towns,args=(store,stop),name='town-clocks')
        worker.start()
        print(f'Lonk-Space is ready: http://127.0.0.1:{port}')
        print('Chat, reading, Moltbook, and world activity are on the website.')
        print('Keep this ONE window open (you can minimize it). Ctrl+C stops the app.')
        if not args.no_browser:
            webbrowser.open(f'http://127.0.0.1:{port}')
        try:
            server.run()
        finally:
            stop.set()
            server.close()
            print('Finishing the current action and saving…')
            worker.join()


if __name__=='__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('Stopped. Your towns are saved.')
    except (OSError,RuntimeError,ValueError) as error:
        print('Could not start:',error)
        print('Close the OLD webapp.py and worker.py windows with Ctrl+C, then try again.')
        raise SystemExit(1)
