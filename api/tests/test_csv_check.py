import pytest

from app.core.config import load_limits
from app.core.errors import AppError, ErrorCode
from app.services import csv_check

LIMITS = load_limits()


def refused(call: object, *args: object) -> AppError:
    with pytest.raises(AppError) as info:
        call(*args)  # type: ignore[operator]
    return info.value


def test_limits_come_from_the_config_file_with_the_documented_numbers() -> None:
    assert LIMITS.max_file_bytes == 5 * 1024 * 1024  # DECISIONS #79
    assert LIMITS.max_rows == 5000  # DATA.md uploads.row_count, Free
    assert LIMITS.max_filename_chars == 255  # DATA.md uploads.filename
    assert LIMITS.upload_ttl_hours == 24  # DATA.md uploads.expires_at
    assert LIMITS.sweep_interval_seconds == 3600  # ROADMAP 3.16
    assert LIMITS.max_columns is None  # no doc gives it: an open question
    assert LIMITS.files_per_slot == {
        "files": 5,
        "document": 1,
        "sources": 4,
        "fileA": 1,
        "fileB": 1,
    }


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("../../etc/passwd.csv", "passwd.csv"),
        ("/etc/passwd.csv", "passwd.csv"),
        ("..\\..\\win\\data.csv", "data.csv"),
        ("a\x00b.csv", "ab.csv"),
        ("line\nbreak\r.csv", "linebreak.csv"),
        ("evil\u202egnp.csv", "evilgnp.csv"),
        ("  spaced.csv  ", "spaced.csv"),
        ("..", ""),
        ("", ""),
        (None, ""),
    ],
)
def test_sanitize_filename(raw: str | None, expected: str) -> None:
    assert csv_check.sanitize_filename(raw, 255) == expected


def test_sanitize_filename_caps_the_length_and_keeps_the_extension() -> None:
    name = csv_check.sanitize_filename("x" * 400 + ".csv", 255)
    assert len(name) == 255
    assert name.endswith(".csv")


@pytest.mark.parametrize(
    ("name", "mime"),
    [
        ("a.csv", "text/csv"),
        ("a.CSV", "application/csv"),
        ("a.csv", "application/vnd.ms-excel"),
        ("a.csv", ""),
        ("a.csv", None),
        ("a.csv", "text/csv; charset=utf-8"),
    ],
)
def test_declared_types_the_web_accepts(name: str, mime: str | None) -> None:
    csv_check.check_declared_type(name, mime)


@pytest.mark.parametrize(
    ("name", "mime", "code"),
    [
        ("a.txt", "text/plain", ErrorCode.UNSUPPORTED_TYPE),
        ("a.pdf", "application/pdf", ErrorCode.UNSUPPORTED_TYPE),
        ("a", "", ErrorCode.UNSUPPORTED_TYPE),
        ("a.csv", "application/pdf", ErrorCode.TYPE_MISMATCH),
        ("a.csv", "application/octet-stream", ErrorCode.TYPE_MISMATCH),
        ("a.pdf", "text/csv", ErrorCode.TYPE_MISMATCH),
    ],
)
def test_declared_type_refusals(name: str, mime: str, code: ErrorCode) -> None:
    assert refused(csv_check.check_declared_type, name, mime).code == code


@pytest.mark.parametrize(
    "data",
    [b"PK\x03\x04rest", b"%PDF-1.7\n", b"junk%PDF-1.4", b"a,b\n\x00\n", b"\x89PNG\r\n\x1a\n"],
)
def test_binary_content_is_a_type_mismatch(data: bytes) -> None:
    assert refused(csv_check.check_csv, data, LIMITS).code == ErrorCode.TYPE_MISMATCH


def test_encodings_are_transcoded_to_utf8() -> None:
    text = "역,승차\n합정,100\n"
    for raw in (text.encode("utf-8"), b"\xef\xbb\xbf" + text.encode("utf-8"), text.encode("cp949")):
        checked = csv_check.check_csv(raw, LIMITS)
        assert checked.utf8_bytes == text.encode("utf-8")  # no BOM, always UTF-8
        assert (checked.row_count, checked.column_count) == (1, 2)


def test_undecodable_bytes_are_bad_csv() -> None:
    assert refused(csv_check.check_csv, b"a,b\n\xff\xfe\xfd,1\n", LIMITS).code == ErrorCode.BAD_CSV


@pytest.mark.parametrize(
    ("data", "delimiter"),
    [(b"a,b,c\n1,2,3\n", ","), (b"a;b;c\n1;2;3\n", ";"), (b"a\tb\tc\n1\t2\t3\n", "\t")],
)
def test_delimiters(data: bytes, delimiter: str) -> None:
    text = data.decode()
    assert csv_check.detect_delimiter(text) == delimiter
    assert csv_check.check_csv(data, LIMITS).column_count == 3


def test_rows_columns_and_shape_rules() -> None:
    small = LIMITS.model_copy(update={"max_rows": 3, "max_columns": 2})
    ok = csv_check.check_csv(b"a,b\n1,2\n\n3,4\n", small)  # a blank line is not a row
    assert ok.row_count == 2
    assert (
        refused(csv_check.check_csv, b"a,b\n1,2\n3,4\n5,6\n7,8\n", small).code
        == ErrorCode.TOO_MANY_ROWS
    )
    assert refused(csv_check.check_csv, b"a,b,c\n1,2,3\n", small).code == ErrorCode.BAD_CSV
    assert refused(csv_check.check_csv, b"a,b\n1,2\n3\n", small).code == ErrorCode.BAD_CSV  # ragged
    assert refused(csv_check.check_csv, b"a,b\n1,2,3\n", small).code == ErrorCode.BAD_CSV
    assert refused(csv_check.check_csv, b"a,b\n", small).code == ErrorCode.EMPTY_FILE  # header only
    assert refused(csv_check.check_csv, b"\n\n", small).code == ErrorCode.BAD_CSV  # no header
    assert (
        refused(csv_check.check_csv, b'a,b\n"1,2\n', small).code == ErrorCode.BAD_CSV
    )  # open quote


def test_the_column_limit_is_off_while_the_config_leaves_it_unset() -> None:
    header = ",".join(f"c{i}" for i in range(500)).encode()
    assert (
        csv_check.check_csv(header + b"\n" + b",".join([b"1"] * 500) + b"\n", LIMITS).column_count
        == 500
    )
