"""One persistent world clock; browser visits never create worlds or advance time."""
import argparse
import contextlib
import os
import time
from pathlib import Path
from lonkspace import ReadingNetwork
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


def tick_once(store, reader=None):
    with store.transaction() as db:
        world = store.read(db)
        world.reading_network = reader or OfflineReader()
        world.world_tick(population_limit=world.max_population)
        store.write(db, world)
        db.execute('UPDATE world SET last_tick=? WHERE id=1', (time.time(),))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--interval', type=float, default=30, help='Seconds between ticks (minimum 1)')
    parser.add_argument('--once', action='store_true')
    parser.add_argument('--internet', action='store_true', help='Enable Wikipedia/NASA reading; no Moltbook credentials are loaded')
    args = parser.parse_args()
    if args.interval < 1:
        parser.error('interval must be at least one second')
    store = Store()
    reader = ReadingNetwork() if args.internet else OfflineReader()
    with worker_lock(str(store.path) + '.worker.lock'):
        while True:
            tick_once(store, reader)
            if args.once:
                return
            time.sleep(args.interval)


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\nWorld clock stopped. Completed ticks are saved.')
