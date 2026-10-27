import logging
import argparse
from pathlib import Path
from datetime import datetime, timezone

from etl.extract import get_channel_details, get_channel_playlists, get_channel_videos, get_video_comments
from etl.transform import load_json, save_to_json, transform_all
from etl.load import load_to_bigquery
from etl.config import setup_logging


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract, transform, and load YouTube artist data into BigQuery")
    parser.add_argument("--mapping-file", default="data/mapping/channel_mapping.json", help="Path to artist-channel mapping JSON")
    parser.add_argument("--max-videos",type=int,default=50,help="Số video tối đa cần lấy cho mỗi nghệ sĩ (mặc định: 100)")
    parser.add_argument("--comments-limit",type=int,default=30,help="Số comments tối đa mỗi video; bỏ trống để lấy tất cả comments API cho phép")
    parser.add_argument("--raw-dir",default="data/raw",help="Thư mục lưu dữ liệu raw")
    parser.add_argument("--processed-dir",default="data/processed",help="Thư mục lưu dữ liệu sau transform")
    parser.add_argument("--skip-load",action="store_true",help="Chỉ extract và transform, không load dữ liệu lên BigQuery")
    parser.add_argument("--log-level",default="INFO",choices=["DEBUG", "INFO", "WARNING", "ERROR"],help="Mức độ chi tiết của log (mặc định: INFO)")

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    project_root = Path(__file__).resolve().parent

    mapping_file = project_root / args.mapping_file
    raw_dir = project_root / args.raw_dir
    processed_dir = project_root / args.processed_dir
    log_dir = project_root / "logs"

    raw_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)

    # 1. Setup logging
    log_file = setup_logging(log_dir, args.log_level)

    logging.info("YouTube ETL pipeline started")
    logging.info("Log file: %s", log_file)

    # 2. Load channel mapping
    channel_mapping = load_json(str(mapping_file))

    if not isinstance(channel_mapping, dict):
        raise ValueError("Channel mapping must be a dictionary.")

    artist_names = list(channel_mapping.keys())

    if not artist_names:
        raise ValueError("Channel mapping contains no artists.")

    logging.info("Loaded %s artist mappings", len(artist_names))

    # 3. Initialize raw data
    raw_data = {
        "artists": [],
        "playlists": [],
        "videos": [],
        "comments": [],
    }

    # 4. Extract data
    for index, artist_name in enumerate(artist_names, start=1):
        logging.info(
            "[%s/%s] Processing artist: %s",
            index,
            len(artist_names),
            artist_name,
        )

        try:
            # Get mapped channel ID
            mapping = channel_mapping[artist_name]
            candidates = mapping.get("candidates", [])

            if not candidates:
                logging.warning(
                "No candidates found for artist: %s",
                artist_name
                )
                continue

            # channel_id trong mapping đã được xác nhận
            channel_id = candidates[0].get("channel_id")

            if not channel_id:
                logging.warning(
                "Missing channel_id in mapping for artist: %s",
                artist_name
                )
                continue

            # Retrieve channel metadata and uploads playlist ID
            channel = get_channel_details(
                channel_id=channel_id,
                artist_name=artist_name,
            )

            if not channel:
                logging.warning(
                    "Could not retrieve channel details for artist: %s",
                    artist_name,
                )
                continue

            uploads_playlist_id = channel.get("uploads_playlist_id")

            # Save channel details
            raw_data["artists"].append(channel)

            logging.info(
                "Using mapped channel: %s | %s",
                artist_name,
                channel.get("channel_title", channel_id),
            )

            # Extract playlists
            try:
                playlists = get_channel_playlists(channel_id)
                raw_data["playlists"].extend(playlists)

                logging.info(
                    "Extracted %s playlists for %s",
                    len(playlists),
                    artist_name,
                )

            except Exception:
                logging.exception(
                    "Failed to extract playlists for %s",
                    artist_name,
                )

            # Validate uploads playlist ID
            if not uploads_playlist_id:
                logging.warning(
                    "No uploads playlist found for %s",
                    artist_name,
                )
                continue

            # Extract videos
            try:
                videos = get_channel_videos(
                    channel_id=channel_id,
                    uploads_playlist_id=uploads_playlist_id,
                    limit=args.max_videos,
                )

                raw_data["videos"].extend(videos)

                logging.info(
                    "Extracted %s videos for %s",
                    len(videos),
                    artist_name,
                )

            except Exception:
                logging.exception(
                    "Failed to extract videos for %s",
                    artist_name,
                )
                continue

            # Extract comments
            for video in videos:
                video_id = video.get("video_id")

                if not video_id:
                    logging.warning(
                        "Missing video_id for artist %s",
                        artist_name,
                    )
                    continue

                try:
                    comments = get_video_comments(
                        video_id=video_id,
                        limit=args.comments_limit,
                    )

                    raw_data["comments"].extend(comments)

                    logging.info(
                        "Video %s: extracted %s comments",
                        video_id,
                        len(comments),
                    )

                except Exception:
                    logging.exception(
                        "Failed to extract comments for video %s",
                        video_id,
                    )

        except Exception:
            logging.exception(
                "Failed to process artist: %s",
                artist_name,
            )

    # 5. Save raw data
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    raw_file = raw_dir / f"youtube_raw_{timestamp}.json"

    save_to_json(raw_data, str(raw_file))

    logging.info("Raw data saved to %s", raw_file)

    # 6. Transform data
    processed_data = transform_all(
        artists=raw_data["artists"],
        playlists=raw_data["playlists"],
        videos=raw_data["videos"],
        comments=raw_data["comments"],
    )

    logging.info(
        "Transformation completed: artists=%s, playlists=%s, "
        "videos=%s, comments=%s",
        len(processed_data["artists"]),
        len(processed_data["playlists"]),
        len(processed_data["videos"]),
        len(processed_data["comments"]),
    )

    # 7. Save processed data
    processed_file = processed_dir / f"youtube_processed_{timestamp}.json"

    save_to_json(processed_data, str(processed_file))

    logging.info("Processed data saved to %s", processed_file)

    # 8. Load data into BigQuery
    if args.skip_load:
        logging.info("Skipping BigQuery load (--skip-load enabled)")

    else:
        for table_name in [
            "artists",
            "playlists",
            "videos",
            "comments",
        ]:
            records = processed_data[table_name]

            if not records:
                logging.warning(
                    "No records to load for %s",
                    table_name,
                )
                continue

            load_to_bigquery(
                data=records,
                table_name=table_name,
            )

            logging.info(
                "Loaded %s records into BigQuery table %s",
                len(records),
                table_name,
            )

    logging.info("YouTube ETL pipeline completed")


if __name__ == "__main__":
    main()