"""Reddit API interactions for scanning posts and comments."""
import logging
import os
import re
from typing import Iterable, Iterator, List, Optional

try:
    import praw
    from praw.models import Comment, Submission
except ModuleNotFoundError as exc:
    raise RuntimeError("praw is required for reddit_api but is not installed") from exc


logger = logging.getLogger(__name__)
_CARD_TAG_PATTERN = re.compile(r"\[\[([^\[\]]+)\]\]")
_reddit_client: Optional[praw.Reddit] = None


def _ensure_client() -> praw.Reddit:
    """Return the active Reddit client or raise if not configured."""
    if _reddit_client is None:
        raise RuntimeError("Reddit client is not initialized. Call build_reddit_client first.")
    return _reddit_client


def stream_submissions(subreddits: Iterable[str]) -> Iterator[Submission]:
    """Yield new submissions from the given subreddits using PRAW streaming."""
    reddit = _ensure_client()
    subreddit = reddit.subreddit("+".join(subreddits))
    for submission in subreddit.stream.submissions(skip_existing=True):
        yield submission


def stream_comments(subreddits: Iterable[str]) -> Iterator[Comment]:
    """Yield new comments from the given subreddits using PRAW streaming."""
    reddit = _ensure_client()
    subreddit = reddit.subreddit("+".join(subreddits))
    for comment in subreddit.stream.comments(skip_existing=True):
        yield comment


def fetch_submission_comments(submission_id: str) -> List[str]:
    """Fetch all comment bodies for a given submission ID."""
    reddit = _ensure_client()
    submission = reddit.submission(id=submission_id)
    submission.comments.replace_more(limit=0)
    return [comment.body for comment in submission.comments.list()]


def extract_card_tags(text: str) -> List[str]:
    """Parse a text body and return card tags formatted like [[Card Name]]."""
    matches = _CARD_TAG_PATTERN.findall(text or "")
    cleaned = []
    for match in matches:
        card_name = match.strip()
        if card_name:
            cleaned.append(card_name)
    return cleaned


def reply_with_card_info(thing_fullname: str, message: str) -> None:
    """Post a reply to a submission or comment using its fullname."""
    reddit = _ensure_client()
    if thing_fullname.startswith("t3_"):
        target = reddit.submission(id=thing_fullname.split("_", 1)[1])
    elif thing_fullname.startswith("t1_"):
        target = reddit.comment(id=thing_fullname.split("_", 1)[1])
    else:
        raise ValueError(f"Unsupported fullname: {thing_fullname}")

    try:
        target.reply(message)
    except Exception as exc:  # noqa: BLE001 - surface Reddit API issues
        logger.exception("Failed to reply to %s: %s", thing_fullname, exc)
        raise


def build_reddit_client(client_id: str, client_secret: str, user_agent: str) -> praw.Reddit:
    """Initialize and store a Reddit API client instance."""
    global _reddit_client
    username = os.environ.get("REDDIT_USERNAME", "").strip()
    password = os.environ.get("REDDIT_PASSWORD", "").strip()
    kwargs = {
        "client_id": client_id,
        "client_secret": client_secret,
        "user_agent": user_agent,
    }
    # If present, authenticate (needed to reply/post).
    if username and password:
        kwargs.update({"username": username, "password": password})

    _reddit_client = praw.Reddit(**kwargs)
    return _reddit_client
