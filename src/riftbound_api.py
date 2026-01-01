"""Riftbound and fallback card image lookups.
Only function signatures and docstrings are defined for planning.
"""
from typing import Optional


def build_riftbound_client(api_key: Optional[str] = None) -> object:
    """Create an HTTP client configured for the Riftbound API."""
    raise NotImplementedError


def search_card_image(card_name: str) -> Optional[str]:
    """Look up a card image URL by exact or fuzzy name via Riftbound."""
    raise NotImplementedError


def search_card_details(card_name: str) -> dict:
    """Return structured card details (name, rarity, text, image) from Riftbound."""
    raise NotImplementedError


def fallback_search_card_image(card_name: str) -> Optional[str]:
    """Fallback to an alternate API (e.g., apiTCG) to find the card image URL."""
    raise NotImplementedError


def compose_card_reply(card_name: str, image_url: Optional[str], details: Optional[dict]) -> str:
    """Format a Reddit-friendly reply that includes the card name and image link."""
    raise NotImplementedError
