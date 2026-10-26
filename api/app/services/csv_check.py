"""Checks on an uploaded CSV, in the order the upload endpoint runs them. Pure functions: bytes in,
a verdict out. A refusal is an AppError with a code; nothing here logs or echoes file content."""

import csv
import io
import unicodedata
from dataclasses import dataclass
from itertools import islice
from pathlib import PurePosixPath
from typing import BinaryIO

from app.core.config import Limits
from app.core.errors import AppError, ErrorCode

# Mirrors CSV in web/lib/workspace/validate.ts MIME_BY_EXTENSION: browsers disagree about CSV
# (Windows reports Excel's type, some report nothing).
CSV_MIMES = frozenset({"text/csv", "application/csv", "application/vnd.ms-excel", ""})
CSV_EXTENSION = "csv"

# Magic numbers of files that are not text: a zip (xlsx, docx), a PDF, an old Excel (OLE2), images.
_BINARY_SIGNATURES = (
    b"PK\x03\x04",
    b"PK\x05\x06",
    b"PK\x07\x08",
    b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1",
    b"\x89PNG\r\n\x1a\n",
    b"\xff\xd8\xff",
    b"GIF87a",
    b"GIF89a",
)
_PDF_MAGIC = b"%PDF-"
_PDF_SCAN_BYTES = 1024  # a PDF may start with a few junk bytes before the magic number
_DELIMITERS = (",", "\t", ";")
_DELIMITER_SAMPLE_ROWS = 20
# Seoul open data is often saved as cp949 (EUC-KR); decoded only after UTF-8 fails.
_ENCODINGS = ("utf-8-sig", "cp949")  # utf-8-sig reads plain UTF-8 too and drops a BOM
HEADER_MAX_BYTES = 64 * 1024  # a longer header line is refused without reading the rest
_HEADER_CHUNK = 8 * 1024


@dataclass(frozen=True)
class CheckedCsv:
    utf8_bytes: bytes  # what is stored: always UTF-8, no BOM
    row_count: int  # data rows, header not counted
    column_count: int


def _refuse(status: int, code: ErrorCode) -> AppError:
    return AppError(status, code)


def sanitize_filename(raw: str | None, max_chars: int) -> str:
    """A display label only: no path, no control or invisible characters, capped length. It is never
    used to build a path. A name with nothing left is "", which the type check then refuses."""
    name = unicodedata.normalize("NFC", raw or "")
    name = name.replace("\\", "/").rsplit("/", 1)[-1]
    # Cc: control (NUL, newline). Cf: invisible format, such as the right-to-left override.
    name = "".join(ch for ch in name if unicodedata.category(ch) not in ("Cc", "Cf"))
    name = name.strip().strip(".").strip()
    if len(name) > max_chars:
        suffix = PurePosixPath(name).suffix  # keep the extension so the type check still sees it
        if len(suffix) >= max_chars:
            suffix = ""
        name = name[: max_chars - len(suffix)] + suffix
    return name


def extension_of(name: str) -> str:
    dot = name.rfind(".")
    return "" if dot < 0 else name[dot + 1 :].lower()


def normalize_mime(declared: str | None) -> str:
    return (declared or "").split(";", 1)[0].strip().lower()


def check_declared_type(name: str, declared_mime: str | None) -> None:
    """The extension and the MIME type must both say CSV. Extension decides the kind (as in the web
    check); a CSV-looking MIME on another extension, or a foreign MIME on .csv, is a mismatch."""
    mime = normalize_mime(declared_mime)
    mime_says_csv = mime in CSV_MIMES
    if extension_of(name) != CSV_EXTENSION:
        if mime_says_csv and mime != "":
            raise _refuse(415, ErrorCode.TYPE_MISMATCH)
        raise _refuse(415, ErrorCode.UNSUPPORTED_TYPE)
    if not mime_says_csv:
        raise _refuse(415, ErrorCode.TYPE_MISMATCH)


def sniff_content(data: bytes) -> None:
    """Do not trust the headers: NUL bytes or a known binary magic number mean this is not text."""
    if (
        b"\x00" in data
        or data.startswith(_BINARY_SIGNATURES)
        or _PDF_MAGIC in data[:_PDF_SCAN_BYTES]
    ):
        raise _refuse(415, ErrorCode.TYPE_MISMATCH)


def decode_to_text(data: bytes) -> str:
    for encoding in _ENCODINGS:
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise _refuse(422, ErrorCode.BAD_CSV)


def detect_delimiter(text: str) -> str:
    """Comma, tab or semicolon: the one that splits the first rows into equal-width columns.
    Comma when none does."""
    best, best_score = ",", (-1, -1)
    for delimiter in _DELIMITERS:
        reader = csv.reader(io.StringIO(text), delimiter=delimiter)
        try:
            widths = {len(row) for row in islice(reader, _DELIMITER_SAMPLE_ROWS) if row}
        except csv.Error:
            continue
        # Equal widths of two or more columns is a real split; one column proves nothing.
        score = (1, max(widths)) if len(widths) == 1 and max(widths) > 1 else (0, 0)
        if score > best_score:
            best, best_score = delimiter, score
    return best


def _is_blank(row: list[str]) -> bool:
    return not any(cell.strip() for cell in row)


def _header_width(header: bytes) -> int:
    """Columns of one header line. The delimiter is not known yet (it needs the first rows), so the
    one that gives the most columns is used; parse_rows then counts again with the real one."""
    try:
        text = decode_to_text(header)
    except AppError:
        return 0  # not decodable: the full parse refuses it with the usual code
    widths = []
    for delimiter in _DELIMITERS:
        try:
            row = next(csv.reader(io.StringIO(text), delimiter=delimiter), [])
        except csv.Error:
            continue
        widths.append(len(row))
    return max(widths, default=0)


def read_header(stream: BinaryIO, limits: Limits) -> bytes:
    """Read from the stream up to the end of the header line and return the bytes read (the caller
    puts them back in front of the rest). Too many columns, or a header line over 64 KB, is refused
    before the rest of the file is read. A newline inside quotes does not end the header."""
    cap = min(HEADER_MAX_BYTES, limits.max_file_bytes + 1)
    head = b""
    scanned = 0  # bytes of `head` already looked at for the end of the line
    quotes = 0
    while True:
        chunk = stream.read(min(_HEADER_CHUNK, cap + 1 - len(head)))
        if not chunk:
            break  # end of file inside the header: the caller's size and shape checks decide
        head += chunk
        while scanned < len(head):
            byte = head[scanned : scanned + 1]
            scanned += 1
            if byte == b'"':
                quotes += 1
            elif byte in (b"\n", b"\r") and quotes % 2 == 0:
                return _check_header(head[:scanned], limits, head)
        if len(head) > cap:
            if len(head) > limits.max_file_bytes:
                return head  # over the size limit anyway: the caller answers 413
            raise _refuse(422, ErrorCode.BAD_CSV)  # no end of line within 64 KB
    return _check_header(head, limits, head)


def _check_header(line: bytes, limits: Limits, head: bytes) -> bytes:
    if limits.max_columns is not None and _header_width(line) > limits.max_columns:
        raise _refuse(422, ErrorCode.TOO_MANY_COLUMNS)
    return head


def parse_rows(text: str, limits: Limits) -> tuple[int, int]:
    """Stream the rows once and return (data rows, columns). The header sets the width and every
    row must match it; a row that does not is a broken file, not something to guess about."""
    try:
        reader = csv.reader(io.StringIO(text), delimiter=detect_delimiter(text), strict=True)
        header = next(reader, None)
        if header is None or _is_blank(header):
            raise _refuse(422, ErrorCode.BAD_CSV)
        width = len(header)
        if limits.max_columns is not None and width > limits.max_columns:
            raise _refuse(422, ErrorCode.TOO_MANY_COLUMNS)
        rows = 0
        for row in reader:
            if _is_blank(row):
                continue
            if len(row) != width:
                raise _refuse(422, ErrorCode.BAD_CSV)
            rows += 1
            if rows > limits.max_rows:
                raise _refuse(422, ErrorCode.TOO_MANY_ROWS)
    except csv.Error:
        raise _refuse(422, ErrorCode.BAD_CSV) from None
    if rows == 0:
        raise _refuse(422, ErrorCode.EMPTY_FILE)
    return rows, width


def check_csv(data: bytes, limits: Limits) -> CheckedCsv:
    """Content checks after the size and declared-type checks: sniff, decode, transcode, parse."""
    sniff_content(data)
    text = decode_to_text(data)
    rows, width = parse_rows(text, limits)
    return CheckedCsv(utf8_bytes=text.encode("utf-8"), row_count=rows, column_count=width)
