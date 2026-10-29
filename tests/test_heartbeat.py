import os
import time

from wrfdb_bot.heartbeat import touch_heartbeat


def test_touch_creates_file(tmp_path):
    path = tmp_path / 'heartbeat'
    touch_heartbeat(path)
    assert path.exists()


def test_touch_updates_mtime(tmp_path):
    path = tmp_path / 'heartbeat'
    path.touch()
    old = time.time() - 600
    os.utime(path, (old, old))
    touch_heartbeat(path)
    assert path.stat().st_mtime > old + 500


def test_touch_unwritable_does_not_raise(tmp_path):
    touch_heartbeat(tmp_path / 'missing-dir' / 'heartbeat')
