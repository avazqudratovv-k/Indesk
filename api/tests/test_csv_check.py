import io

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
    assert LIMITS.max_rows == 20000  # limits.toml, Free (raised from 5,000)
    assert LIMITS.max_filename_chars == 255  # DATA.md uploads.filename
    assert LIMITS.upload_ttl_hours == 24  # DATA.md uploads.expires_at
    assert LIMITS.sweep_interval_seconds == 3600  # ROADMAP 3.16
    assert LIMITS.max_columns == 200  # owner decision for P5
    assert LIMITS.uploads_per_hour == 30  # owner decision for P5
    assert LIMITS.files_per_slot == {
        "files": 1,
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
    over = refused(csv_check.check_csv, b"a,b\n1,2\n3,4\n5,6\n7,8\n", small)
    assert over.code == ErrorCode.TOO_MANY_ROWS
    assert over.extra == {"rows": 4, "max": 3}
    # The error names the real row count (blank lines not counted), not the limit plus one.
    many = refused(csv_check.check_csv, b"a,b\n" + b"1,2\n\n" * 9, small)
    assert many.extra == {"rows": 9, "max": 3}
    assert refused(csv_check.check_csv, b"a,b,c\n1,2,3\n", small).code == ErrorCode.TOO_MANY_COLUMNS
    assert refused(csv_check.check_csv, b"a,b\n1,2\n3\n", small).code == ErrorCode.BAD_CSV  # ragged
    assert refused(csv_check.check_csv, b"a,b\n1,2,3\n", small).code == ErrorCode.BAD_CSV
    assert refused(csv_check.check_csv, b"a,b\n", small).code == ErrorCode.EMPTY_FILE  # header only
    assert refused(csv_check.check_csv, b"\n\n", small).code == ErrorCode.BAD_CSV  # no header
    assert (
        refused(csv_check.check_csv, b'a,b\n"1,2\n', small).code == ErrorCode.BAD_CSV
    )  # open quote


def test_a_trailing_empty_cell_on_every_row_is_accepted_and_not_counted() -> None:
    data = b'"a","b","c"\r\n"1","x","3",""\n"4","y","6",""\n'
    checked = csv_check.check_csv(data, LIMITS)
    assert (checked.row_count, checked.column_count) == (2, 3)  # the header's width, not 4
    assert checked.utf8_bytes == data  # nothing is re-encoded or cut
    two = csv_check.check_csv(b"a,b\n1,2,,\n3,4,,\n", LIMITS)  # several trailing cells are fine too
    assert (two.row_count, two.column_count) == (2, 2)


@pytest.mark.parametrize(
    "data",
    [
        b"a,b,c\n1,2,3,4\n",  # a non-empty extra cell
        b"a,b,c\n1,,3,4\n5,6,7,\n",  # an empty cell in the middle is not a trailing cell
        b"a,b,c\n1,2,3,\n4,5\n",  # a short row
        b"a,b,c\n1,2,3,\n4,5,6\n",  # a mix of 4-cell and 3-cell rows
        b"a,b,c\n1,2,3\n4,5,6,\n",  # the same mix, the other way round
        b"a,b,c\n1,2,3,\n4,5,6,,\n",  # extra cells of different counts
    ],
)
def test_other_ragged_rows_are_still_refused(data: bytes) -> None:
    assert refused(csv_check.check_csv, data, LIMITS).code == ErrorCode.BAD_CSV


def test_the_column_limit_is_off_when_it_is_unset() -> None:
    off = LIMITS.model_copy(update={"max_columns": None})
    header = ",".join(f"c{i}" for i in range(500)).encode()
    assert (
        csv_check.check_csv(header + b"\n" + b",".join([b"1"] * 500) + b"\n", off).column_count
        == 500
    )


def wide(columns: int, *, rows: int = 1, sep: str = ",") -> bytes:
    header = sep.join(f"c{i}" for i in range(columns))
    return (header + "\n" + (sep.join(["1"] * columns) + "\n") * rows).encode()


def test_200_columns_pass_and_201_are_refused() -> None:
    assert csv_check.check_csv(wide(200), LIMITS).column_count == 200
    assert refused(csv_check.check_csv, wide(201), LIMITS).code == ErrorCode.TOO_MANY_COLUMNS


class Counting(io.BytesIO):
    """A stream that remembers how many bytes were taken from it."""

    taken = 0

    def read(self, size: int | None = -1) -> bytes:
        data = super().read(size)
        self.taken += len(data)
        return data


def test_the_header_is_checked_before_the_rest_of_the_file_is_read() -> None:
    stream = Counting(wide(201, rows=2000))  # about 700 KB
    assert refused(csv_check.read_header, stream, LIMITS).code == ErrorCode.TOO_MANY_COLUMNS
    assert stream.taken < 20_000


def test_read_header_returns_the_bytes_it_read_so_nothing_is_lost() -> None:
    data = wide(5, rows=10)
    stream = io.BytesIO(data)
    head = csv_check.read_header(stream, LIMITS)
    assert data.startswith(head) and head.endswith(b"\n")
    assert head + stream.read() == data


@pytest.mark.parametrize("sep", [",", ";", "\t"])
def test_header_check_works_for_every_delimiter(sep: str) -> None:
    refusal = refused(csv_check.read_header, io.BytesIO(wide(201, sep=sep)), LIMITS)
    assert refusal.code == ErrorCode.TOO_MANY_COLUMNS
    assert csv_check.read_header(io.BytesIO(wide(200, sep=sep)), LIMITS)


def test_a_header_longer_than_one_chunk_is_counted_across_chunks() -> None:
    long_names = ",".join(f"{'n' * 100}{i}" for i in range(201)).encode() + b"\n1\n"
    assert len(long_names) > 8 * 1024  # more than one read
    assert refused(csv_check.read_header, io.BytesIO(long_names), LIMITS).code == (
        ErrorCode.TOO_MANY_COLUMNS
    )


def test_header_line_over_64_kb_is_refused_without_reading_on() -> None:
    stream = Counting(b"a" * 1_000_000)
    assert refused(csv_check.read_header, stream, LIMITS).code == ErrorCode.BAD_CSV
    assert stream.taken <= csv_check.HEADER_MAX_BYTES + 8 * 1024
    assert csv_check.read_header(io.BytesIO(b"a" * 100), LIMITS) == b"a" * 100  # no newline, short


def test_a_newline_inside_quotes_does_not_end_the_header() -> None:
    cells = ",".join(f'"c{i}\nx"' for i in range(201)).encode() + b"\n1\n"
    assert refused(csv_check.read_header, io.BytesIO(cells), LIMITS).code == (
        ErrorCode.TOO_MANY_COLUMNS
    )


def test_a_cp949_header_is_decoded_like_the_full_parse() -> None:
    korean = ",".join(f"역{i}" for i in range(201)).encode("cp949") + b"\n1\n"
    assert refused(csv_check.read_header, io.BytesIO(korean), LIMITS).code == (
        ErrorCode.TOO_MANY_COLUMNS
    )
    fine = ",".join(f"역{i}" for i in range(3)).encode("cp949") + b"\n1,2,3\n"
    assert csv_check.read_header(io.BytesIO(fine), LIMITS) == fine
    bom = b"\xef\xbb\xbf" + wide(200)
    assert csv_check.read_header(io.BytesIO(bom), LIMITS) == bom


def test_an_empty_stream_is_left_to_the_empty_file_check() -> None:
    assert csv_check.read_header(io.BytesIO(b""), LIMITS) == b""
