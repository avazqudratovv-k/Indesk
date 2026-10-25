import os
import re
import uuid
from pathlib import Path

from app.storage.base import StorageError

_KEY = re.compile(r"[0-9a-f]{32}")
_FILE_MODE = 0o600
_DIR_MODE = 0o700


class LocalDiskStorage:
    """Files at <root>/<first two hex characters>/<32 hex characters>. The key is a random uuid:
    no path is ever built from a filename or any other user input."""

    def __init__(self, root: Path) -> None:
        self._root = root

    def _path(self, key: str) -> Path:
        if not _KEY.fullmatch(key):
            raise StorageError("bad key")
        root = self._root.resolve()
        path = (root / key[:2] / key).resolve()  # resolve() follows symlinks
        if not path.is_relative_to(root):
            raise StorageError("path leaves the storage root")
        return path

    def put(self, data: bytes) -> str:
        key = uuid.uuid4().hex
        path = self._path(key)
        try:
            path.parent.mkdir(mode=_DIR_MODE, parents=True, exist_ok=True)
            # O_EXCL: never overwrite; O_NOFOLLOW: never write through a planted symlink.
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, _FILE_MODE)
            with os.fdopen(fd, "wb") as handle:
                handle.write(data)
            path.chmod(_FILE_MODE)  # the umask can only remove bits; this makes the mode certain
        except OSError as exc:
            path.unlink(missing_ok=True)  # no half-written file is left behind
            raise StorageError("write failed") from exc
        return key

    def get(self, key: str) -> bytes:
        try:
            return self._path(key).read_bytes()
        except OSError as exc:
            raise StorageError("read failed") from exc

    def delete(self, key: str) -> None:
        try:
            self._path(key).unlink(missing_ok=True)
        except OSError as exc:
            raise StorageError("delete failed") from exc
