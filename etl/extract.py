import logging
import time
import requests
from etl.config import YOUTUBE_API_KEY, YOUTUBE_API_BASE_URL, YOUTUBE_REQUEST_TIMEOUT, YOUTUBE_BATCH_SIZE, YOUTUBE_PROXY
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

def youtube_get(endpoint: str, params: dict) -> dict:
    if not YOUTUBE_API_KEY:
        raise ValueError("Missing YOUTUBE_API_KEY in .env")

    url = f"{YOUTUBE_API_BASE_URL}/{endpoint}"
    request_params = {
        **params,
        "key": YOUTUBE_API_KEY,
    }

    max_attempts = 5
    base_delay = 2

    for attempt in range(1, max_attempts + 1):
        try:
            response = requests.get(
                url,
                params=request_params,
                timeout=YOUTUBE_REQUEST_TIMEOUT,
                proxies={"http": YOUTUBE_PROXY, "https": YOUTUBE_PROXY} if YOUTUBE_PROXY else None,
            )

        except requests.exceptions.RequestException as error:
            if attempt == max_attempts:
                logger.error(
                    "Network request failed after %s attempts. "
                    "Endpoint: %s | Error type: %s",
                    max_attempts,
                    endpoint,
                    type(error).__name__,
                )

                raise RuntimeError(
                    f"YouTube API network request failed after "
                    f"{max_attempts} attempts. "
                    f"Endpoint: {endpoint}"
                ) from None

            delay = min(base_delay * (2 ** (attempt - 1)), 30)

            logger.warning(
                "Network error on attempt %s/%s. "
                "Endpoint: %s | Error type: %s | Retry in %s seconds",
                attempt,
                max_attempts,
                endpoint,
                type(error).__name__,
                delay,
            )

            time.sleep(delay)
            continue

        # Retry for rate limiting and temporary server errors.
        if response.status_code == 429 or 500 <= response.status_code < 600:
            if attempt == max_attempts:
                logger.error(
                    "Temporary HTTP error persisted after %s attempts. "
                    "Endpoint: %s | Status: %s",
                    max_attempts,
                    endpoint,
                    response.status_code,
                )

                raise RuntimeError(
                    f"YouTube API temporary HTTP error after "
                    f"{max_attempts} attempts. "
                    f"Endpoint: {endpoint} | "
                    f"Status: {response.status_code}"
                )

            retry_after = response.headers.get("Retry-After")

            try:
                delay = float(retry_after) if retry_after else (
                    base_delay * (2 ** (attempt - 1))
                )
            except ValueError:
                delay = base_delay * (2 ** (attempt - 1))

            delay = min(max(delay, 1), 60)

            logger.warning(
                "Temporary HTTP error on attempt %s/%s. "
                "Endpoint: %s | Status: %s | Retry in %s seconds",
                attempt,
                max_attempts,
                endpoint,
                response.status_code,
                delay,
            )

            time.sleep(delay)
            continue

        # Do not retry permanent HTTP errors such as invalid API keys
        # or quota-related errors.
        try:
            response.raise_for_status()
        except requests.exceptions.HTTPError:
            try:
                error_data = response.json()
                error_message = (
                    error_data.get("error", {}).get("message", "")
                )
            except ValueError:
                error_message = ""

            logger.error(
                "YouTube API HTTP error. Endpoint: %s | "
                "Status: %s | Message: %s",
                endpoint,
                response.status_code,
                error_message,
            )

            raise RuntimeError(
                f"YouTube API HTTP error: {response.status_code} "
                f"| Endpoint: {endpoint} "
                f"| {error_message}"
            ) from None

        try:
            return response.json()
        except ValueError:
            raise RuntimeError(
                f"YouTube API returned invalid JSON. "
                f"Endpoint: {endpoint}"
            ) from None

    raise RuntimeError(
        f"YouTube API request failed. Endpoint: {endpoint}"
    )

def search_channels(artist_name: str) -> dict:
    try:
        # Step 1: Search for candidate channels.
        search_data = youtube_get(
            endpoint="search",
            params={
                "part": "snippet",
                "type": "channel",
                "q": artist_name,
                "maxResults": 50,
            },
        )

        items = search_data.get("items", [])

        if not items:
            logger.warning("No channels found for artist: %s", artist_name)
            return {}

        # Step 2: Extract candidate channel IDs.
        channel_ids = [
            item["id"]["channelId"]
            for item in items
            if item.get("id", {}).get("channelId")
        ]

        if not channel_ids:
            logger.warning("No valid channel IDs for artist: %s", artist_name)
            return {}

        # Step 3: Retrieve subscriber counts in batches.
        candidates = []

        for start in range(0, len(channel_ids), YOUTUBE_BATCH_SIZE):
            batch_ids = channel_ids[
                start : start + YOUTUBE_BATCH_SIZE
            ]

            channel_data = youtube_get(
                endpoint="channels",
                params={
                    "part": "snippet,statistics,contentDetails",
                    "id": ",".join(batch_ids),
                },
            )

            candidates.extend(channel_data.get("items", []))

        if not candidates:
            logger.warning(
                "No channel details found for artist: %s",
                artist_name,
            )
            return {}

        # Step 4: Keep channels with a publicly available subscriber count.
        eligible_channels = []

        for channel in candidates:
            statistics = channel.get("statistics", {})

            if "subscriberCount" not in statistics:
                continue

            try:
                subscriber_count = int(statistics["subscriberCount"])
            except (TypeError, ValueError):
                logger.warning(
                    "Invalid subscriber count for channel: %s",
                    channel.get("id"),
                )
                continue

            snippet = channel.get("snippet", {})
            content_details = channel.get("contentDetails", {})
            related_playlists = content_details.get("relatedPlaylists", {})

            eligible_channels.append(
                {
                    "artist_name": artist_name,
                    "channel_id": channel.get("id"),
                    "channel_title": snippet.get("title"),
                    "description": snippet.get("description"),
                    "channel_created_at": snippet.get("publishedAt"),
                    "uploads_playlist_id": related_playlists.get("uploads"),
                    "subscriber_count": subscriber_count,
                    "view_count": statistics.get("viewCount"),
                    "video_count": statistics.get("videoCount"),
                }
            )

        if not eligible_channels:
            logger.warning(
                "No channels with public subscriber counts for artist: %s",
                artist_name,
            )
            return {}

        # Step 5: Select the channel with the highest subscriber count.
        selected_channel = max(
            eligible_channels,
            key=lambda channel: channel["subscriber_count"],
        )

        logger.info(
            "Selected channel for %s: %s | Subscribers: %s",
            artist_name,
            selected_channel["channel_title"],
            selected_channel["subscriber_count"],
        )

        return selected_channel

    except Exception:
        logger.exception(
            "Failed to search channels for artist: %s",
            artist_name,
        )
        raise


def get_channel_playlists(channel_id: str) -> list[dict]:
    playlists = []
    next_page_token = None

    try:
        while True:
            params = {
                "part": "snippet,contentDetails,status",
                "channelId": channel_id,
                "maxResults": 50,
            }

            # Add pageToken only when another page exists.
            if next_page_token:
                params["pageToken"] = next_page_token

            # Request one page of playlists.
            data = youtube_get(
                endpoint="playlists",
                params=params,
            )

            # Extract playlist information.
            for item in data.get("items", []):
                snippet = item.get("snippet", {})
                content_details = item.get("contentDetails", {})
                status = item.get("status", {})

                playlist = {
                    "playlist_id": item.get("id"),
                    "channel_id": channel_id,
                    "playlist_title": snippet.get("title"),
                    "description": snippet.get("description"),
                    "published_at": snippet.get("publishedAt"),
                    "video_count": content_details.get("itemCount"),
                    "privacy_status": status.get("privacyStatus"),
                }

                playlists.append(playlist)

            logger.info(
                "Fetched %s playlists so far for channel %s",
                len(playlists),
                channel_id,
            )

            # Check whether another page exists.
            next_page_token = data.get("nextPageToken")

            if not next_page_token:
                break

        logger.info(
            "Finished fetching playlists for channel %s. Total: %s",
            channel_id,
            len(playlists),
        )

        return playlists

    except Exception:
        logger.exception(
            "Failed to fetch playlists for channel %s",
            channel_id,
        )
        raise

def get_channel_videos(channel_id: str,uploads_playlist_id: str,limit: int = 100,) -> list[dict]:
    try:
        # Step 1: Collect video IDs from the uploads playlist.
        video_ids = []
        next_page_token = None

        while len(video_ids) < limit:
            params = {
                "part": "snippet,contentDetails",
                "playlistId": uploads_playlist_id,
                "maxResults": min(50, limit - len(video_ids)),
            }

            if next_page_token:
                params["pageToken"] = next_page_token

            data = youtube_get(
                endpoint="playlistItems",
                params=params,
            )

            for item in data.get("items", []):
                video_id = (
                    item.get("contentDetails", {}).get("videoId")
                )

                if video_id and video_id not in video_ids:
                    video_ids.append(video_id)

            next_page_token = data.get("nextPageToken")

            logger.info(
                "Collected %s video IDs for channel %s",
                len(video_ids),
                channel_id,
            )

            if not next_page_token or not data.get("items"):
                break

        if not video_ids:
            logger.warning(
                "No videos found for channel %s",
                channel_id,
            )
            return []

        # Step 2: Retrieve video details in batches.
        videos = []

        for start in range(0, len(video_ids), YOUTUBE_BATCH_SIZE):
            batch_ids = video_ids[
                start : start + YOUTUBE_BATCH_SIZE
            ]

            video_data = youtube_get(
                endpoint="videos",
                params={
                    "part": "snippet,contentDetails,statistics,status",
                    "id": ",".join(batch_ids),
                },
            )

            for item in video_data.get("items", []):
                snippet = item.get("snippet", {})
                content_details = item.get("contentDetails", {})
                statistics = item.get("statistics", {})
                status = item.get("status", {})

                video = {
                    "video_id": item.get("id"),
                    "channel_id": snippet.get("channelId", channel_id),
                    "video_title": snippet.get("title"),
                    "description": snippet.get("description"),
                    "published_at": snippet.get("publishedAt"),
                    "duration": content_details.get("duration"),
                    "category_id": snippet.get("categoryId"),
                    "tags": snippet.get("tags", []),
                    "view_count": statistics.get("viewCount"),
                    "like_count": statistics.get("likeCount"),
                    "comment_count": statistics.get("commentCount"),
                    "privacy_status": status.get("privacyStatus"),
                    "collected_at": datetime.now(
                        timezone.utc
                    ).isoformat(),
                }

                videos.append(video)

        # Step 3: Sort by publication time, newest first.
        videos.sort(
            key=lambda video: video.get("published_at") or "",
            reverse=True,
        )

        # Step 4: Keep at most the requested number of videos.
        videos = videos[:limit]

        logger.info(
            "Finished fetching videos for channel %s. Total: %s",
            channel_id,
            len(videos),
        )

        return videos

    except Exception:
        logger.exception(
            "Failed to fetch videos for channel %s",
            channel_id,
        )
        raise

def get_video_comments(video_id: str, limit: int | None = None) -> list[dict]:
    try:
        comments = []
        next_page_token = None

        while True:
            params = {
                "part": "snippet",
                "videoId": video_id,
                "maxResults": (
                    min(100, limit - len(comments))
                    if limit is not None
                    else 100
                ),
                "order": "time",
                "textFormat": "plainText",
            }

            if next_page_token:
                params["pageToken"] = next_page_token

            data = youtube_get(
                endpoint="commentThreads",
                params=params,
            )

            for item in data.get("items", []):
                snippet = item.get("snippet", {})
                top_comment = snippet.get("topLevelComment", {})
                comment_snippet = top_comment.get("snippet", {})

                comment = {
                    "video_id": video_id,
                    "comment_id": top_comment.get("id"),
                    "parent_id": None,
                    "author_name": comment_snippet.get(
                        "authorDisplayName"
                    ),
                    "comment_text": comment_snippet.get(
                        "textDisplay"
                    ),
                    "published_at": comment_snippet.get(
                        "publishedAt"
                    ),
                    "updated_at": comment_snippet.get(
                        "updatedAt"
                    ),
                    "like_count": comment_snippet.get(
                        "likeCount", 0
                    ),
                    "reply_count": snippet.get(
                        "totalReplyCount", 0
                    ),
                    "extracted_at": datetime.now(
                        timezone.utc
                    ).isoformat(),
                    "source": "youtube_data_api",
                    "ingestion_date": datetime.now(
                        timezone.utc
                    ).date().isoformat(),
                }

                comments.append(comment)

                if limit is not None and len(comments) >= limit:
                    break

            logger.info(
                "Collected %s comments for video %s",
                len(comments),
                video_id,
            )

            next_page_token = data.get("nextPageToken")

            if (
                (limit is not None and len(comments) >= limit)
                or not next_page_token
                or not data.get("items")
            ):
                break

        logger.info(
            "Finished fetching comments for video %s. Total: %s",
            video_id,
            len(comments),
        )

        return comments

    except Exception as error:
        error_message = str(error).lower()

        if (
            "commentsdisabled" in error_message
            or "disabled comments" in error_message
            or "comments are disabled" in error_message
        ):
            logger.warning(
                "Comments disabled for video %s. Skipping comments.",
                video_id,
            )
            return []

        logger.error(
            "Failed to fetch comments for video %s: %s",
            video_id,
            error,
        )
        raise