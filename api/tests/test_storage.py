import os
import re
import stat
from pathlib import Path

import pytest

from app.storage import LocalDiskStorage, StorageError


@pytest.fixture
def storage(tmp_path: Path) -> LocalDiskStorage:
    return LocalDiskStorage(tmp_path / "uploads")


def test_put_get_delete_round_trip(storage: LocalDiskStorage, tmp_path: Path) -> None:
    key = storage.put(b"a,b\n1,2\n")
    assert re.fullmatch(r"[0-9a-f]{32}", key)
    assert storage.get(key) == b"a,b\n1,2\n"
    assert (tmp_path / "uploads" / key[:2] / key).is_file()  # two-character fan-out
    storage.delete(key)
    storage.delete(key)  # already gone: not an error
    with pytest.raises(StorageError):
        storage.get(key)


def test_file_mode_is_0600_and_directories_are_private(
    storage: LocalDiskStorage, tmp_path: Path
) -> None:
    key = storage.put(b"x")
    path = tmp_path / "uploads" / key[:2] / key
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700


@pytest.mark.parametrize(
    "key",
    [
        "../../etc/passwd",
        "/etc/passwd",
        "a" * 31,
        "A" * 32,
        "g" * 32,
        ("a" * 31) + "\x00",
        "",
        "ab/" + "c" * 29,
    ],
)
def test_keys_that_are_not_ours_are_refused(storage: LocalDiskStorage, key: str) -> None:
    for call in (storage.get, storage.delete):
        with pytest.raises(StorageError):
            call(key)


def test_a_symlink_that_leaves_the_root_is_refused(
    storage: LocalDiskStorage, tmp_path: Path
) -> None:
    secret = tmp_path / "outside.txt"
    secret.write_text("secret")
    key = "ab" + "0" * 30
    folder = tmp_path / "uploads" / "ab"
    folder.mkdir(parents=True)
    os.symlink(secret, folder / key)
    with pytest.raises(StorageError):
        storage.get(key)
    with pytest.raises(StorageError):
        storage.delete(key)
    assert secret.read_text() == "secret"
