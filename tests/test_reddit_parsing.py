import unittest

import os
import sys


REPO_ROOT = os.path.dirname(os.path.dirname(__file__))
SRC_DIR = os.path.join(REPO_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import reddit_api as reddit_api


class TestRedditParsing(unittest.TestCase):
    def test_extract_card_tags_basic(self):
        text = "I love [[Teemo, Scout]] and [[  Jinx ]]!"
        self.assertEqual(reddit_api.extract_card_tags(text), ["Teemo, Scout", "Jinx"])

    def test_extract_card_tags_ignores_empty(self):
        text = "[[   ]] [[A]]"
        self.assertEqual(reddit_api.extract_card_tags(text), ["A"])

    def test_extract_card_tags_multiple_lines(self):
        text = "Line1 [[A]]\nLine2 [[B]]"
        self.assertEqual(reddit_api.extract_card_tags(text), ["A", "B"])


if __name__ == "__main__":
    unittest.main()
