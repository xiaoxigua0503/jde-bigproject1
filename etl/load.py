import os
from pathlib import Path
from etl.transform import load_json

from dotenv import load_dotenv
from google.cloud import bigquery


load_dotenv()

PROJECT_ID = os.getenv("GCP_PROJECT_ID")
DATASET_ID = os.getenv("BQ_DATASET_ID")

client = bigquery.Client(project=PROJECT_ID)


def load_to_bigquery(data, table_name):
    table_id = f"{PROJECT_ID}.{DATASET_ID}.{table_name}"

    job_config = bigquery.LoadJobConfig(
        autodetect=True,
        write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
    )

    job = client.load_table_from_json(
        data,
        table_id,
        job_config=job_config,
    )

    job.result()

    print(f"Loaded {len(data)} rows into {table_id}")

def load_json_to_tables(file_path, suffix):
    data = load_json(file_path)

    for table_name in ["artists", "playlists", "videos", "comments"]:
        records = data.get(table_name, [])

        if not records:
            print(f"No records to load for {table_name}_{suffix}")
            continue

        load_to_bigquery(
            data=records,
            table_name=f"{table_name}_{suffix}",
        )


if __name__ == "__main__":
    files = [
        (Path("data/raw/youtube_raw.json"), "raw"),
        (Path("data/processed/youtube_processed.json"), "processed"),
    ]

    for file_path, suffix in files:
        if not file_path.exists():
            print(f"File not found: {file_path}")
            continue

        print(f"\nLoading {file_path}...")

        load_json_to_tables(
            file_path=file_path,
            suffix=suffix,
        )