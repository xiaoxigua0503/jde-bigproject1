import json
import logging
from datetime import datetime, timezone, date
from pathlib import Path

logger = logging.getLogger(__name__)

def save_to_json(data, file_path:str) -> None:
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "w", encoding = "utf-8-sig") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

def load_json(file_path:str):
    with open(file_path, "r", encoding = "utf-8-sig") as f:
        return json.load(f)


def clean_text(value):
    if value is None:
        return None

    if not isinstance(value, str):
        return value

    value = value.strip()

    return value if value else None

def clean_timestamp(value):
    if value is None:
        return None

    if not isinstance(value, str) or not value.strip():
        return None

    try:
        timestamp = datetime.fromisoformat(
            value.strip().replace("Z", "+00:00")
        )

        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        timestamp = timestamp.astimezone(timezone.utc)

        return timestamp.isoformat().replace("+00:00", "Z")

    except (ValueError, TypeError):
        logger.warning("Invalid timestamp: %s", value)
        return None

def clean_date(value):
    if value is None:
        return None

    if not isinstance(value, str) or not value.strip():
        return None

    try:
        return date.fromisoformat(value.strip()).isoformat()

    except (ValueError, TypeError):
        logger.warning("Invalid date: %s", value)
        return None

def clean_integer(value):
    if value is None or isinstance(value, bool):
        return None

    try:
        if isinstance(value, str):
            value = value.strip()

            if not value:
                return None

        if isinstance(value, float) and not value.is_integer():
            logger.warning("Invalid integer value: %s", value)
            return None

        return int(value)

    except (ValueError, TypeError, OverflowError):
        logger.warning("Invalid integer value: %s", value)
        return None

def deduplicate_records(records: list[dict], key: str) -> list[dict]:
    cleaned_records = []
    seen = set()

    for record in records:
        record_key = record.get(key)

        if record_key is None:
            logger.warning("Skipping record without %s", key)
            continue

        if isinstance(record_key, str) and not record_key.strip():
            logger.warning("Skipping record with empty %s", key)
            continue

        if record_key in seen:
            logger.warning(
                "Skipping duplicate record: %s=%s",
                key,
                record_key,
            )
            continue

        seen.add(record_key)
        cleaned_records.append(record)

    return cleaned_records


def clean_artists(data: list[dict]) -> list[dict]:
    """Clean artist and YouTube channel records."""
    cleaned = []

    for record in data:
        artist = {
            "artist_name": clean_text(record.get("artist_name")),
            "channel_id": clean_text(record.get("channel_id")),
            "channel_title": clean_text(record.get("channel_title")),
            "description": record.get("description"),
            "channel_created_at": clean_timestamp(
                record.get("channel_created_at")
            ),
            "uploads_playlist_id": clean_text(
                record.get("uploads_playlist_id")
            ),
            "subscriber_count": clean_integer(
                record.get("subscriber_count")
            ),
            "view_count": clean_integer(record.get("view_count")),
            "video_count": clean_integer(record.get("video_count")),
        }

        cleaned.append(artist)

    cleaned = deduplicate_records(cleaned, "channel_id")

    logger.info("Artists cleaned: %s records", len(cleaned))

    return cleaned

def clean_playlists(data: list[dict]) -> list[dict]:
    """Clean playlist records."""
    cleaned = []

    for record in data:
        playlist = {
            "playlist_id": clean_text(record.get("playlist_id")),
            "channel_id": clean_text(record.get("channel_id")),
            "playlist_title": clean_text(
                record.get("playlist_title")
            ),
            "description": record.get("description"),
            "published_at": clean_timestamp(
                record.get("published_at")
            ),
            "video_count": clean_integer(record.get("video_count")),
            "privacy_status": clean_text(
                record.get("privacy_status")
            ),
        }

        cleaned.append(playlist)

    cleaned = deduplicate_records(cleaned, "playlist_id")

    logger.info("Playlists cleaned: %s records", len(cleaned))

    return cleaned

def clean_videos(data: list[dict]) -> list[dict]:
    """Clean video metadata and statistics."""
    cleaned = []

    for record in data:
        tags = record.get("tags")

        # Preserve tags as a list of strings.
        if isinstance(tags, list):
            tags = [
                tag.strip()
                for tag in tags
                if isinstance(tag, str) and tag.strip()
            ]
        else:
            tags = []

        video = {
            "video_id": clean_text(record.get("video_id")),
            "channel_id": clean_text(record.get("channel_id")),
            "video_title": clean_text(record.get("video_title")),
            "description": record.get("description"),
            "published_at": clean_timestamp(
                record.get("published_at")
            ),
            "duration": clean_text(record.get("duration")),
            "category_id": clean_text(record.get("category_id")),
            "tags": tags,
            "view_count": clean_integer(record.get("view_count")),
            "like_count": clean_integer(record.get("like_count")),
            "comment_count": clean_integer(
                record.get("comment_count")
            ),
            "privacy_status": clean_text(
                record.get("privacy_status")
            ),
            "collected_at": clean_timestamp(
                record.get("collected_at")
            ),
        }

        cleaned.append(video)

    cleaned = deduplicate_records(cleaned, "video_id")

    logger.info("Videos cleaned: %s records", len(cleaned))

    return cleaned

def clean_comments(data: list[dict]) -> list[dict]:
    """Clean YouTube comment records."""
    cleaned = []

    for record in data:
        comment = {
            "video_id": clean_text(record.get("video_id")),
            "comment_id": clean_text(record.get("comment_id")),
            "parent_id": clean_text(record.get("parent_id")),
            "author_name": clean_text(record.get("author_name")),

            # Preserve comment text to avoid losing meaning.
            "comment_text": record.get("comment_text"),

            "published_at": clean_timestamp(
                record.get("published_at")
            ),
            "updated_at": clean_timestamp(
                record.get("updated_at")
            ),
            "like_count": clean_integer(record.get("like_count")),
            "reply_count": clean_integer(
                record.get("reply_count")
            ),
            "extracted_at": clean_timestamp(
                record.get("extracted_at")
            ),
            "source": clean_text(record.get("source")),
            "ingestion_date": clean_date(
                record.get("ingestion_date")
            ),
        }

        cleaned.append(comment)

    cleaned = deduplicate_records(cleaned, "comment_id")

    logger.info("Comments cleaned: %s records", len(cleaned))

    return cleaned


def transform_all(artists: list[dict], playlists: list[dict], videos: list[dict], comments: list[dict]) -> dict[str, list[dict]]:
    processed = {
        "artists": clean_artists(artists),
        "playlists": clean_playlists(playlists),
        "videos": clean_videos(videos),
        "comments": clean_comments(comments),
    }

    for table_name, records in processed.items():
        logger.info(
            "Transform result | table=%s | records=%s",
            table_name,
            len(records),
        )

    return processed