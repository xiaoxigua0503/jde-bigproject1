import argparse
import logging
from pathlib import Path
from venv import logger

from charset_normalizer.api import logger
from dateutil import parser
import pandas as pd

from etl.extract import search_channels
from etl.transform import save_to_json


def parse_args():
    parser = argparse.ArgumentParser(description="Build YouTube artist-to-channel mapping.")
    parser.add_argument("--input-csv", default="artists.csv",help="Path to the artist CSV file.")
    parser.add_argument("--output-json", default="data/mapping/channel_mapping.json",help="Path to save the channel mapping JSON.")

    return parser.parse_args()


def main():
    args = parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    logger = logging.getLogger(__name__)

    input_path = Path(args.input_csv)
    output_path = Path(args.output_json)

    if not input_path.exists():
        logger.error("Artist CSV not found: %s", input_path)
        return

    # Avoid accidentally spending search quota again.
    if output_path.exists():
        logger.error(
            "Mapping file already exists: %s. "
            "Review or rename it before rebuilding the mapping.",
            output_path,
        )
        return

    # Read artist names from CSV.
    df = pd.read_csv(input_path, encoding="utf-8-sig")

    if "Artist Name" not in df.columns:
        logger.error("CSV must contain an 'Artist Name' column.")
        return

    artists = (
        df["Artist Name"]
        .dropna()
        .astype(str)
        .str.strip()
    )

    artists = artists[artists != ""].drop_duplicates().tolist()

    logger.info("Loaded %d unique artists.", len(artists))

    # Mapping structure: artist name -> channel information.
    channel_mapping = {}

    failed_artists = []

    for index, artist_name in enumerate(artists, start=1):
        logger.info(
            "[%d/%d] Searching channel for: %s",
            index,
            len(artists),
            artist_name,
        )

        try:
            channel = search_channels(artist_name)

            if not channel:
                logger.warning("No channel found for: %s", artist_name)
                failed_artists.append(artist_name)
                continue

            channel_mapping[artist_name] = channel

            logger.info(
                "Selected channel: %s | Channel ID: %s",
                channel.get("channel_title"),
                channel.get("channel_id"),
            )

        except Exception:
            logger.exception("Failed to search channel for: %s", artist_name)
            failed_artists.append(artist_name)

    # Save mapping using the existing helper in transform.py.
    if channel_mapping:
        save_to_json(channel_mapping, output_path)

        logger.info(
            "Saved %d channel mappings to %s",
            len(channel_mapping),
            output_path,
        )
    else:
        logger.error("No channel mappings were created.")

    if failed_artists:
        logger.warning(
            "%d artists failed: %s",
            len(failed_artists),
            ", ".join(failed_artists),
        )


if __name__ == "__main__":
    main()