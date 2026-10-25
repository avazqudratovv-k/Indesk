"""Where uploaded files live. Callers hold only an opaque key; the backend decides the layout.
Local disk now, S3 or R2 later (DECISIONS #20)."""

from typing import Protocol


class StorageError(Exception):
    """A key that is not ours, a path that leaves the storage root, or a disk failure."""


class Storage(Protocol):
    def put(self, data: bytes) -> str:
        """Store the bytes under a new random key and return the key."""
        ...

    def get(self, key: str) -> bytes: ...

    def delete(self, key: str) -> None:
        """Remove the file. A file that is already gone is not an error."""
        ...
