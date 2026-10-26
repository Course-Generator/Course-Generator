"""Unit tests for chapter normalization and filtering rules."""

from __future__ import annotations

import unittest

from coursegen.models import Chapter
from coursegen.services.chapters import filter_chapters, normalize_chapters


class ChapterTests(unittest.TestCase):
    def test_overlapping_ranges_are_moved_forward(self) -> None:
        chapters = [
            Chapter("One", 1, 10),
            Chapter("Two", 8, 12),
            Chapter("Three", 20, 18),
        ]
        normalized = normalize_chapters(chapters)

        self.assertEqual((normalized[0].start_page, normalized[0].end_page), (1, 10))
        self.assertEqual((normalized[1].start_page, normalized[1].end_page), (11, 12))
        self.assertEqual((normalized[2].start_page, normalized[2].end_page), (20, 20))

    def test_front_and_back_matter_is_removed(self) -> None:
        chapters = [
            Chapter("Cover", 1, 1),
            Chapter("Preface", 2, 3),
            Chapter("Chapter 1", 4, 10),
            Chapter("Appendix A", 11, 12),
            Chapter("Index", 13, 13),
        ]
        filtered = filter_chapters(normalize_chapters(chapters))
        self.assertEqual([chapter.title for chapter in filtered], ["Chapter 1"])

    def test_duplicate_start_pages_are_removed(self) -> None:
        chapters = [Chapter("Chapter 1", 4, 6), Chapter("Chapter 1 continued", 4, 8)]
        filtered = filter_chapters(chapters)
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0].title, "Chapter 1")


if __name__ == "__main__":
    unittest.main()
