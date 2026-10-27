"""A tiny PDF writer for tests: no dependency, standard library only. It makes just what the P14
tests
need: text pages (Helvetica, or a Korean Type0 font that has a ToUnicode map and no font file), a
page with only an image (a "scan"), an encrypted file (a stub /Encrypt entry; the parser refuses
before it tries to decrypt), a truncated file and a compressed-stream bomb. Nothing here is a real
document; the text is made up."""

import zlib
from collections.abc import Sequence


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _stream(body: bytes, extra: str = "", compress: bool = False) -> bytes:
    if compress:
        body = zlib.compress(body, 9)
        extra += " /Filter /FlateDecode"
    return f"<< /Length {len(body)}{extra} >>\nstream\n".encode() + body + b"\nendstream"


def _tounicode(chars: list[str]) -> bytes:
    lines = [f"<{i + 1:04X}> <{ord(ch):04X}>" for i, ch in enumerate(chars)]
    return (
        "/CIDInit /ProcSet findresource begin 12 dict begin begincmap\n"
        "/CMapName /Adobe-Identity-UCS def /CMapType 2 def\n"
        "1 begincodespacerange <0000> <FFFF> endcodespacerange\n"
        f"{len(lines)} beginbfchar\n" + "\n".join(lines) + "\nendbfchar\n"
        "endcmap CMapName currentdict /CMap defineresource pop end end"
    ).encode()


def build_pdf(
    pages: Sequence[Sequence[str]],
    *,
    korean: bool = False,
    image_only: bool = False,
    encrypted: bool = False,
    content: bytes | None = None,
) -> bytes:
    """`pages` is one list of text lines per page. `image_only` draws a picture and no text.
    `content` replaces every page's content stream (for a bomb or a heavy page)."""
    objects: list[bytes] = []

    def add(body: bytes) -> int:
        objects.append(body)
        return len(objects)

    catalog = add(b"")  # filled in below, once the page tree exists
    tree = add(b"")
    chars = sorted({ch for lines in pages for line in lines for ch in line})
    if korean:
        to_unicode = add(_stream(_tounicode(chars)))
        descendant = add(
            b"<< /Type /Font /Subtype /CIDFontType2 /BaseFont /Nanum "
            b"/CIDSystemInfo << /Registry (Adobe) /Ordering (Identity) /Supplement 0 >> "
            b"/DW 1000 >>"
        )
        font = add(
            f"<< /Type /Font /Subtype /Type0 /BaseFont /Nanum /Encoding /Identity-H "
            f"/DescendantFonts [{descendant} 0 R] /ToUnicode {to_unicode} 0 R >>".encode()
        )
    else:
        font = add(
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"
        )
    image = add(
        _stream(
            b"\x00\xff\xff\x00",
            " /Type /XObject /Subtype /Image /Width 2 /Height 2"
            " /ColorSpace /DeviceGray /BitsPerComponent 8",
        )
    )
    page_ids: list[int] = []
    for lines in pages:
        if content is not None:
            body = content
        elif image_only:
            body = b"q 400 0 0 400 100 200 cm /Im0 Do Q"
        else:
            ops = ["BT /F1 12 Tf 14 TL 72 760 Td"]
            for line in lines:
                if korean:
                    hexed = "".join(f"{chars.index(ch) + 1:04X}" for ch in line)
                    ops.append(f"<{hexed}> Tj T*")
                else:
                    ops.append(f"({_escape(line)}) Tj T*")
            ops.append("ET")
            body = "\n".join(ops).encode("latin-1" if not korean else "ascii")
        data = add(_stream(body, compress=content is not None))
        page_ids.append(
            add(
                f"<< /Type /Page /Parent {tree} 0 R /MediaBox [0 0 595 842] "
                f"/Resources << /Font << /F1 {font} 0 R >> /XObject << /Im0 {image} 0 R >> >> "
                f"/Contents {data} 0 R >>".encode()
            )
        )
    kids = " ".join(f"{i} 0 R" for i in page_ids)
    objects[tree - 1] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>".encode()
    objects[catalog - 1] = f"<< /Type /Catalog /Pages {tree} 0 R >>".encode()
    trailer_extra = ""
    if encrypted:
        enc = add(
            b"<< /Filter /Standard /V 1 /R 2 /P -4 /O ("
            + b"o" * 32
            + b") /U ("
            + b"u" * 32
            + b") >>"
        )
        file_id = "<00112233445566778899AABBCCDDEEFF>"
        trailer_extra = f" /Encrypt {enc} 0 R /ID [{file_id} {file_id}]"

    out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets: list[int] = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += f"{number} 0 obj\n".encode() + body + b"\nendobj\n"
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for offset in offsets:
        out += f"{offset:010d} 00000 n \n".encode()
    out += (
        f"trailer\n<< /Size {len(objects) + 1} /Root {catalog} 0 R{trailer_extra} >>\n"
        f"startxref\n{xref}\n%%EOF\n"
    ).encode()
    return bytes(out)


def sentences(count: int, *, page: int = 1) -> list[str]:
    """Plain English lines with numbers, unique per page, so a search has something to find."""
    return [
        f"Line {n} of page {page}: ridership on Line {n} reached {page * 1000 + n} thousand riders."
        for n in range(1, count + 1)
    ]


def text_pdf(page_count: int = 3, lines: int = 8) -> bytes:
    return build_pdf([sentences(lines, page=p) for p in range(1, page_count + 1)])


def bomb_content(repeats: int) -> bytes:
    """A page content stream that is tiny compressed and `repeats` text operators when read."""
    return b"BT /F1 12 Tf (x) Tj ET\n" * repeats
