import unittest

import os
import sys
import urllib.parse
from unittest.mock import patch


# Allow `python -m unittest` from repo root.
REPO_ROOT = os.path.dirname(os.path.dirname(__file__))
SRC_DIR = os.path.join(REPO_ROOT, "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

import riftbound_api as riftbound_api


class TestRiftboundApi(unittest.TestCase):
    def test_live_fuzzy_endpoint_returns_items_schema(self):
        """Live call to Riftcodex API.

        This is an integration test: it may be skipped if offline.
        """
        query = "teem"
        encoded = urllib.parse.quote(query)
        path = f"/cards/name?fuzzy={encoded}"
        try:
            status, payload = riftbound_api._http_get_json(riftbound_api.RIFTBOUND_HOST, path)
        except Exception as exc:  # noqa: BLE001
            self.skipTest(f"Riftcodex API unavailable/offline: {exc}")

        self.assertEqual(status, 200)
        self.assertIsInstance(payload, dict)
        self.assertIn("items", payload)
        self.assertIsInstance(payload["items"], list)

    def test_live_search_card_details(self):
        """Live call through the high-level helper."""
        try:
            details = riftbound_api.search_card_details("teem")
        except Exception as exc:  # noqa: BLE001
            self.skipTest(f"Riftcodex API unavailable/offline: {exc}")

        self.assertIsInstance(details, dict)
        self.assertEqual(details.get("source"), "riftbound")
        self.assertIn("raw", details)
        self.assertTrue(details.get("name"))
        raw = details.get("raw")
        self.assertIsInstance(raw, dict)
        media = raw.get("media")
        if isinstance(media, dict) and isinstance(media.get("image_url"), str):
            self.assertEqual(details.get("image_url"), media.get("image_url"))
            self.assertTrue(str(details.get("image_url")).startswith("http"))

    def test_live_known_queries_return_image_url(self):
        """Live checks for a few known/likely queries.

        If the API is unreachable, these will be skipped.
        If a query returns no results, the test will fail (signals parsing/endpoint drift).
        """
        queries = [
            "Teemo, scout",
            "thousand watcher",
            "ravenbloom studnt",
        ]

        for q in queries:
            with self.subTest(query=q):
                try:
                    details = riftbound_api.search_card_details(q)
                except Exception as exc:  # noqa: BLE001
                    self.skipTest(f"Riftcodex API unavailable/offline: {exc}")

                self.assertIsInstance(details, dict)
                self.assertEqual(details.get("source"), "riftbound")
                raw = details.get("raw")
                self.assertTrue(raw, msg=f"No raw payload for query: {q}")

                image_url = details.get("image_url")
                print(f"{q} -> {image_url}")
                self.assertTrue(
                    isinstance(image_url, str) and image_url.startswith("http"),
                    msg=f"Expected image_url for query '{q}', got: {image_url}\nraw={raw}",
                )

    def test_fallback_disabled_without_env(self):
        # Ensure fallback does nothing unless configured.
        with patch.dict("os.environ", {}, clear=True):
            self.assertIsNone(riftbound_api.fallback_search_card_image("anything"))


if __name__ == "__main__":
    unittest.main()
