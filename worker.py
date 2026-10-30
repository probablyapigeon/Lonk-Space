"""One persistent world clock; browser visits never create worlds or advance time."""
import argparse
import contextlib
import os
import time
from pathlib import Path
from lonkspace import ReadingNetwork, capture_output
from town_store import Store


class OfflineReader:
    def read(self, *args, **kwargs):
        return False


@contextlib.contextmanager
def worker_lock(path):
    # OS locks are released on crash; a leftover file is harmless.
    f = open(path, 'a+b')
    try:
        f.seek(0)
        if os.name == 'nt':
            import msvcrt
            if Path(path).stat().st_size == 0:
                f.write(b'0'); f.flush(); f.seek(0)
            try:
                msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError as error:
                raise RuntimeError('Another world worker is already running.') from error
        else:
            import fcntl
            try:
                fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except OSError as error:
                raise RuntimeError('Another world worker is already running.') from error
        yield
    finally:
        f.close()


def tick_once(store, reader=None, force=False):
    with store.transaction() as db, capture_output() as output:
        if not force and store.resolved_owner(db) and store.settings(db)['paused']:
            return
        world = store.read(db)
        world.reading_network = reader or OfflineReader()
        world.world_tick(population_limit=world.max_population)
        store.write(db, world)
        owner = store.resolved_owner(db)
        if owner:
            db.execute('UPDATE towns SET last_tick=? WHERE owner_id=?', (time.time(), owner))
            store.log(db, world.tick, output.getvalue())
        else:
            db.execute('UPDATE world SET last_tick=? WHERE id=1', (time.time(),))


def serve_towns(store, stop):
    from town_runtime import TownRuntime
    runtimes = {}
    while not stop.is_set():
        with contextlib.closing(store.connect()) as db:
            rows = db.execute('SELECT owner_id,last_tick,settings FROM towns').fetchall()
        for row in rows:
            if stop.is_set():
                break
            owner = row['owner_id']
            if owner not in runtimes:
                from square_runtime import SquareRuntime
                from square import SQUARE_ID
                runtime_type = SquareRuntime if owner == SQUARE_ID else TownRuntime
                runtimes[owner] = runtime_type(store.for_user(owner))
                runtimes[owner].recover()
            runtime = runtimes[owner]
            try:
                runtime.run_command()
                with contextlib.closing(store.connect()) as db:
                    settings = runtime.store.settings(db)
                if not settings['paused'] and time.time() - (row['last_tick'] or 0) >= settings['interval']:
                    runtime.tick()
            except Exception as error:
                import logging
                logging.exception('Background town action failed')
                # Keep other towns running; record a bounded diagnostic, never credential data.
                try:
                    runtime.message('World clock encountered ' + type(error).__name__ + '. Check the server log if this repeats.')
                except Exception:
                    pass
        stop.wait(1)


def main():
    import threading
    store = Store()
    with worker_lock(str(store.path) + '.worker.lock'):
        serve_towns(store, threading.Event())


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('World clocks stopped. Completed ticks are saved.')
