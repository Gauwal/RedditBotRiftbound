"""Riftbound and fallback card image lookups.

This module intentionally avoids extra dependencies.
It uses the community Riftbound API first, then a configurable fallback.
"""

from __future__ import annotations

import http.client
import json
import os
import urllib.parse
from typing import Any, Optional


RIFTBOUND_HOST = os.environ.get("RIFTBOUND_HOST", "api.riftcodex.com")


def build_riftbound_client(api_key: Optional[str] = None) -> http.client.HTTPSConnection:
    """Create an HTTP client configured for the Riftbound API."""
    # api_key currently unused; kept for future auth support.
    return http.client.HTTPSConnection(RIFTBOUND_HOST)


def _http_get_json(host: str, path: str, headers: Optional[dict[str, str]] = None) -> tuple[int, Any]:
    conn = http.client.HTTPSConnection(host)
    hdrs = {"Accept": "application/json"}
    if headers:
        hdrs.update(headers)
    conn.request("GET", path, "", hdrs)
    res = conn.getresponse()
    raw = res.read()
    try:
        payload = json.loads(raw.decode("utf-8")) if raw else None
    except json.JSONDecodeError:
        payload = raw.decode("utf-8", errors="replace")
    return res.status, payload


def _first_card_obj(payload: Any) -> Optional[dict[str, Any]]:
    if payload is None:
        return None
    if isinstance(payload, dict):
        # Some APIs return { data: [...] }
        if "data" in payload and isinstance(payload["data"], list) and payload["data"]:
            first = payload["data"][0]
            return first if isinstance(first, dict) else None
        return payload
    if isinstance(payload, list) and payload:
        first = payload[0]
        return first if isinstance(first, dict) else None
    return None


def _extract_image_url(card: dict[str, Any]) -> Optional[str]:
    # Try common key names.
    for key in ("image", "imageUrl", "image_url", "imageURI", "imageUri", "image_uri"):
        value = card.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    images = card.get("images")
    if isinstance(images, dict):
        for key in ("normal", "large", "small", "png", "default"):
            value = images.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    return None


def search_card_details(card_name: str) -> dict:
    """Return structured card details from Riftbound.

Because the community API surface may change, this function tries a few
reasonable endpoints and normalizes the result.
"""
    name = (card_name or "").strip()
    if not name:
        return {}

    encoded = urllib.parse.quote(name)

    # Try a few plausible patterns.
    candidates = [
        f"/cards/name?name={encoded}",
        f"/cards/name/{encoded}",
        f"/cards/search?name={encoded}",
        f"/cards?name={encoded}",
    ]
    last_payload: Any = None
    for path in candidates:
        status, payload = _http_get_json(RIFTBOUND_HOST, path)
        last_payload = payload
        if status == 200 and payload is not None:
            card = _first_card_obj(payload)
            if card is None:
                continue
            return {
                "raw": card,
                "name": card.get("name") or name,
                "image_url": _extract_image_url(card),
                "source": "riftbound",
            }

    # No success; return empty but include last response for debugging.
    if last_payload is not None:
        return {"raw": last_payload, "name": name, "image_url": None, "source": "riftbound"}
    return {}


def search_card_image(card_name: str) -> Optional[str]:
    """Look up a card image URL by name via Riftbound."""
    details = search_card_details(card_name)
    if not details:
        return None
    return details.get("image_url")


def fallback_search_card_image(card_name: str) -> Optional[str]:
    """Fallback lookup for a card image URL.

This is intentionally configurable because "apiTCG" can vary.

Set environment variables:
- APITCG_HOST (example: "example.com")
- APITCG_PATH_TEMPLATE (example: "/cards?name={name}")

The response can be a dict or list; this function will attempt to extract
an image URL from common fields.
"""
    host = os.environ.get("APITCG_HOST", "").strip()
    path_template = os.environ.get("APITCG_PATH_TEMPLATE", "").strip()
    if not host or not path_template:
        return None

    name = (card_name or "").strip()
    if not name:
        return None

    encoded = urllib.parse.quote(name)
    path = path_template.format(name=encoded)
    status, payload = _http_get_json(host, path)
    if status != 200 or payload is None:
        return None

    card = _first_card_obj(payload)
    if card is None:
        return None
    return _extract_image_url(card)


def compose_card_reply(card_name: str, image_url: Optional[str], details: Optional[dict]) -> str:
    """Format a Reddit-friendly reply that includes the card name and image link."""
    name = (card_name or "").strip() or "(unknown card)"
    if image_url:
        return f"{name}\n\nImage: {image_url}"
    return f"{name}\n\nImage: (not found)"
