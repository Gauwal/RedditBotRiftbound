"""Entry point for the Reddit Riftbound bot."""
import logging
import os
import threading
from typing import Iterable

from reddit_api import (
    build_reddit_client,
    extract_card_tags,
    stream_comments,
    stream_submissions,
)


logger = logging.getLogger(__name__)

# You can fill these inline instead of using environment variables.
HARD_CODED_CLIENT_ID = "FILL_ME"
HARD_CODED_CLIENT_SECRET = "FILL_ME"
HARD_CODED_USER_AGENT = "riftbound-bot/0.1 by YOUR_USERNAME"


def load_config(config_path: str | None = None) -> dict:
    """Load credentials, preferring env vars, else inline constants above."""
    client_id = os.environ.get("REDDIT_CLIENT_ID", "") or HARD_CODED_CLIENT_ID
    client_secret = os.environ.get("REDDIT_CLIENT_SECRET", "") or HARD_CODED_CLIENT_SECRET
    user_agent = os.environ.get("REDDIT_USER_AGENT", "") or HARD_CODED_USER_AGENT
    return {
        "client_id": client_id,
        "client_secret": client_secret,
        "user_agent": user_agent,
    }


def run_bot(subreddits: Iterable[str]) -> None:
    """Stream submissions and comments, printing basic info as a smoke test."""
    cfg = load_config(None)
    if not cfg["client_id"] or not cfg["client_secret"]:
        raise RuntimeError("Set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET in the environment.")

    build_reddit_client(cfg["client_id"], cfg["client_secret"], cfg["user_agent"])

    def watch_submissions() -> None:
        for submission in stream_submissions(subreddits):
            handle_submission(submission)

    def watch_comments() -> None:
        for comment in stream_comments(subreddits):
            handle_comment(comment)

    threads = [
        threading.Thread(target=watch_submissions, name="submission-stream", daemon=True),
        threading.Thread(target=watch_comments, name="comment-stream", daemon=True),
    ]
    for t in threads:
        t.start()

    # Keep the main thread alive while workers stream.
    for t in threads:
        t.join()


def handle_submission(submission) -> None:
    """Process a new submission: print title, URL, and any card tags."""
    body = (submission.title or "") + "\n" + (getattr(submission, "selftext", "") or "")
    tags = extract_card_tags(body)
    logger.info("Submission: %s (tags=%s)", submission.title, tags)
    print(f"[submission] {submission.id} :: {submission.title} :: tags={tags}")


def handle_comment(comment) -> None:
    """Process a new comment: print author, body, and any card tags."""
    tags = extract_card_tags(comment.body or "")
    logger.info("Comment by %s (tags=%s)", comment.author, tags)
    preview = (comment.body or "").replace("\n", " ")
    print(f"[comment] {comment.id} :: {preview[:140]} :: tags={tags}")


def resolve_card(card_name: str) -> str:
    """Placeholder resolver until Riftbound integration is wired."""
    return f"Stub lookup for {card_name}"


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run_bot(["riftboundtcg"])
