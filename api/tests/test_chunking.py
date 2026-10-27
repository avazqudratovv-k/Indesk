"""Chunking (P14): pure functions. The rules the retrieval and the quote check rely on."""

import random

import pytest

from app.services.chunking import chunk_document, clean_page_text, split_page

SIZE, OVERLAP = 1000, 150


def words(count: int, seed: int = 1) -> str:
    rng = random.Random(seed)  # noqa: S311  # test data, not security
    vocab = ["ridership", "station", "Hapjeong", "line", "2.5", "percent", "boardings", "weekday"]
    return " ".join(rng.choice(vocab) for _ in range(count))


def check_invariants(text: str, size: int = SIZE, overlap: int = OVERLAP) -> None:
    spans = split_page(text, size, overlap)
    covered = [False] * len(text)
    previous_end = -1
    previous_start = -1
    for span in spans:
        piece = text[span.start : span.end]
        assert 0 < len(piece) <= size
        assert not piece[0].isspace() and not piece[-1].isspace()
        assert span.start > previous_start and span.end > previous_end  # moves forward
        if previous_end != -1:
            assert span.start <= previous_end  # no gap: the next chunk starts inside the last
        previous_start, previous_end = span.start, span.end
        for index in range(span.start, span.end):
            covered[index] = True
    assert all(covered[i] or ch.isspace() for i, ch in enumerate(text))  # every character is kept


@pytest.mark.parametrize("seed", range(8))
def test_invariants_on_random_text(seed: int) -> None:
    check_invariants(words(random.Random(seed).randint(1, 900), seed))  # noqa: S311


def test_short_page_is_one_chunk_with_exact_offsets() -> None:
    text = "  Hapjeong rose 18 percent.  "
    (span,) = split_page(text, SIZE, OVERLAP)
    assert text[span.start : span.end] == "Hapjeong rose 18 percent."


def test_blank_and_empty_pages_have_no_chunks() -> None:
    assert split_page("", SIZE, OVERLAP) == []
    assert split_page(" \n\t  \n", SIZE, OVERLAP) == []


def test_chunks_break_at_a_paragraph_when_there_is_one() -> None:
    first = words(120, 2)[:700].rsplit(" ", 1)[0]
    text = first + "\n\n" + words(300, 3)
    spans = split_page(text, SIZE, OVERLAP)
    assert text[spans[0].start : spans[0].end] == first  # ended at the blank line, not mid-sentence
    assert len(spans) > 1


def test_overlap_is_shared_between_neighbours() -> None:
    text = words(600, 4)
    spans = split_page(text, SIZE, OVERLAP)
    assert len(spans) >= 3
    for earlier, later in zip(spans, spans[1:], strict=False):
        shared = earlier.end - later.start
        assert 0 < shared <= OVERLAP + 20  # a start is moved to the next word, so a little less


def test_text_without_spaces_is_cut_at_the_limit() -> None:
    text = "가" * 2500  # no space to break at (and no word start to move to)
    spans = split_page(text, SIZE, OVERLAP)
    assert all(span.end - span.start <= SIZE for span in spans)
    assert spans[0].end - spans[0].start == SIZE
    check_invariants(text)


def test_a_chunk_never_crosses_a_page() -> None:
    pages = [words(250, 5), "", words(250, 6), "Short last page."]
    chunks = chunk_document(pages, SIZE, OVERLAP)
    assert [c.ord for c in chunks] == list(range(len(chunks)))  # numbered over the whole document
    assert {c.page for c in chunks} == {1, 3, 4}  # the empty page 2 gives none
    for chunk in chunks:
        assert pages[chunk.page - 1][chunk.start : chunk.end] == chunk.text
    assert [c.page for c in chunks] == sorted(c.page for c in chunks)


def test_bad_overlap_is_refused() -> None:
    with pytest.raises(ValueError, match="overlap"):
        split_page("text", 1000, 500)


def test_clean_page_text() -> None:
    raw = "Café a\x00b\r\nline\rtwo\tend \ud800 \x07bell"
    cleaned = clean_page_text(raw)
    assert cleaned == "Café ab\nline\ntwo\tend  bell"  # NFC, no NUL, no surrogate, no BEL
    assert clean_page_text("서울​역") == "서울​역"  # invisible format characters stay
