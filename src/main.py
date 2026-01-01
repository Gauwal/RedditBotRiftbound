"""Entry point for the Reddit Riftbound bot."""
import logging
import os
import threading
import time
from typing import Iterable

from reddit_api import (
    build_reddit_client,
    extract_card_tags,
    stream_comments,
    stream_submissions,
)

from riftbound_api import compose_card_reply, fallback_search_card_image, search_card_details


logger = logging.getLogger(__name__)

# You can fill these inline instead of using environment variables.
HARD_CODED_CLIENT_ID = "FILL_ME"
HARD_CODED_CLIENT_SECRET = "FILL_ME"
HARD_CODED_USER_AGENT = "riftbound_cardfetcher_bot/0.1 by Gauwal"

# Optional, only needed if you want the bot to reply.
HARD_CODED_USERNAME = ""
HARD_CODED_PASSWORD = ""


def load_config(config_path: str | None = None) -> dict:
    """Load credentials, preferring env vars, else inline constants above."""
    client_id = os.environ.get("REDDIT_CLIENT_ID", "") or HARD_CODED_CLIENT_ID
    client_secret = os.environ.get("REDDIT_CLIENT_SECRET", "") or HARD_CODED_CLIENT_SECRET
    user_agent = os.environ.get("REDDIT_USER_AGENT", "") or HARD_CODED_USER_AGENT
    username = os.environ.get("REDDIT_USERNAME", "") or HARD_CODED_USERNAME
    password = os.environ.get("REDDIT_PASSWORD", "") or HARD_CODED_PASSWORD
    backfill_limit = int(os.environ.get("BACKFILL_LIMIT", "25"))
    reply_enabled = os.environ.get("BOT_REPLY", "0") == "1"
    return {
        "client_id": client_id,
        "client_secret": client_secret,
        "user_agent": user_agent,
        "username": username,
        "password": password,
        "backfill_limit": backfill_limit,
        "reply_enabled": reply_enabled,
    }


def run_bot(subreddits: Iterable[str]) -> None:
    """Backfill + stream submissions and comments.

    Prints everything it sees; when it finds [[Card Name]] tags it resolves them
    via Riftcodex and prints the image URL.

    If BOT_REPLY=1 and REDDIT_USERNAME/REDDIT_PASSWORD are set, it will reply.
    """
    cfg = load_config(None)
    if not cfg["client_id"] or not cfg["client_secret"]:
        raise RuntimeError("Set REDDIT_CLIENT_ID and REDDIT_CLIENT_SECRET in the environment.")

    reddit = build_reddit_client(cfg["client_id"], cfg["client_secret"], cfg["user_agent"])
    me = None
    if cfg["reply_enabled"] and cfg["username"] and cfg["password"]:
        try:
            me = reddit.user.me()
        except Exception:
            me = None

    processed_fullnames: set[str] = set()
    card_cache: dict[str, str] = {}

    def _unique_in_order(values: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for v in values:
            key = v.strip().lower()
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(v.strip())
        return out

    def resolve_card_cached(card_name: str) -> str:
        key = card_name.strip().lower()
        if key in card_cache:
            return card_cache[key]

        details = search_card_details(card_name)
        image_url = details.get("image_url") if details else None
        if not image_url:
            image_url = fallback_search_card_image(card_name)

        msg = compose_card_reply(card_name, image_url, details if details else None)
        card_cache[key] = msg
        return msg

    def maybe_reply(thing, card_names: list[str]) -> None:
        if not cfg["reply_enabled"]:
            return
        if not cfg["username"] or not cfg["password"]:
            logger.warning("BOT_REPLY=1 but REDDIT_USERNAME/REDDIT_PASSWORD not set; skipping replies")
            return
        if me is not None and getattr(thing, "author", None) is not None:
            try:
                if str(thing.author).lower() == str(me).lower():
                    return
            except Exception:
                pass

        lines = [resolve_card_cached(cn) for cn in _unique_in_order(card_names)]
        if not lines:
            return
        reply_text = "\n\n---\n\n".join(lines)
        try:
            thing.reply(reply_text)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Reply failed: %s", exc)

    def process_comment(comment) -> None:
        fullname = getattr(comment, "fullname", None) or f"t1_{comment.id}"
        if fullname in processed_fullnames:
            return
        processed_fullnames.add(fullname)

        tags = _unique_in_order(extract_card_tags(comment.body or ""))
        preview = (comment.body or "").replace("\n", " ")
        print(f"[comment] {comment.id} :: {preview[:140]} :: tags={tags}")
        if tags:
            for tag in tags:
                print(resolve_card_cached(tag))
            maybe_reply(comment, tags)

    def process_submission_and_comments(submission) -> None:
        fullname = getattr(submission, "fullname", None) or f"t3_{submission.id}"
        if fullname not in processed_fullnames:
            processed_fullnames.add(fullname)

            body = (submission.title or "") + "\n" + (getattr(submission, "selftext", "") or "")
            tags = _unique_in_order(extract_card_tags(body))
            print(f"[submission] {submission.id} :: {submission.title} :: tags={tags}")
            if tags:
                for tag in tags:
                    print(resolve_card_cached(tag))
                maybe_reply(submission, tags)

        try:
            submission.comments.replace_more(limit=0)
            for comment in submission.comments.list():
                process_comment(comment)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Failed to load comments for %s: %s", submission.id, exc)

    # Backfill: fetch recent posts and all their comments.
    for sub in subreddits:
        print(f"[backfill] r/{sub} latest {cfg['backfill_limit']}")
        for submission in reddit.subreddit(sub).new(limit=cfg["backfill_limit"]):
            process_submission_and_comments(submission)
            time.sleep(0.2)

    def watch_submissions() -> None:
        for submission in stream_submissions(subreddits):
            process_submission_and_comments(submission)

    def watch_comments() -> None:
        for comment in stream_comments(subreddits):
            process_comment(comment)

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
    """Resolve a card name to a reply string using Riftcodex then fallback."""
    details = search_card_details(card_name)
    image_url = details.get("image_url") if details else None
    if not image_url:
        image_url = fallback_search_card_image(card_name)
    return compose_card_reply(card_name, image_url, details if details else None)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run_bot(["riftboundtcg"])
