"""Pure chapter normalization and filtering rules."""

from __future__ import annotations

from typing import Iterable, List

from coursegen.models import Chapter

SKIP_TITLES = frozenset(
    {
        "cover",
        "copyright",
        "packt page",
        "contributors",
        "title page",
        "table of contents",
        "preface",
        "other books you may enjoy",
        "index",
        "references",
        "acknowledgements",
        "acknowledgments",
        "acronyms",
        "about the author",
        "about the reviewers",
        "contents",
        "notes",
        "biography",
        "bibliography",
        "appendix",
        "glossary",
        "background",
        "prologue",
        "credits",
        "www",
        "customer",
        "pdf",
        "front matter",
        "front-matter",
        "frontmatter",
        "back matter",
        "back-matter",
        "backmatter",
        "colophon",
        "about this book",
    }
)


def normalize_chapters(chapters: Iterable[Chapter]) -> List[Chapter]:
    """Repair overlapping or inverted page ranges."""
    normalized: List[Chapter] = []
    previous_end = 0
    for chapter in chapters:
        start_page = chapter.start_page
        end_page = chapter.end_page
        if end_page < start_page:
            end_page = start_page
        if start_page < previous_end:
            start_page = previous_end + 1
        if end_page < start_page:
            end_page = start_page
        normalized.append(Chapter(title=chapter.title, start_page=start_page, end_page=end_page))
        previous_end = end_page
    return normalized


def filter_chapters(
    chapters: Iterable[Chapter],
    skip_titles: frozenset[str] = SKIP_TITLES,
) -> List[Chapter]:
    """Drop front/back matter and duplicate start pages."""
    filtered: List[Chapter] = []
    seen_start_pages: set[int] = set()
    for chapter in chapters:
        title = chapter.title.lower()
        if any(skip_title in title for skip_title in skip_titles):
            continue
        if chapter.start_page in seen_start_pages:
            continue
        filtered.append(chapter)
        seen_start_pages.add(chapter.start_page)
    return filtered
