"""Destination coordination shared by house and product renderers."""
from contextlib import contextmanager
from pathlib import Path

from gilvy.errors import GilvyError


@contextmanager
def publication_lock(output: Path):
    """Reject concurrent writers, including other renderers and processes.

    Keep the lock file: unlinking it would let a new writer lock a different inode.
    """
    import fcntl
    output = Path(output).expanduser().resolve()
    with output.with_name(f".{output.name}.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise GilvyError(f"render already in progress for {output}") from exc
        try:
            yield
        finally:
            fcntl.flock(lock, fcntl.LOCK_UN)
