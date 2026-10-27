# YouTube Data Pipeline

A Python-based ETL pipeline that collects public YouTube channel, playlist, video, and comment data using the YouTube Data API v3, transforms the extracted data, and loads it into Google BigQuery for analytical querying.

## Overview

This project demonstrates an end-to-end data engineering workflow, from API data extraction to cloud data warehousing.

The pipeline is designed to collect data for a predefined list of artists, process the raw API responses into structured datasets, and make the resulting data available in BigQuery for further analysis.

### Key Features

- **API Data Extraction:** Retrieve public channel information, playlists, videos, and comments through the YouTube Data API v3.
- **Channel Mapping:** Use a JSON mapping file to associate artists with their confirmed YouTube channel IDs.
- **Data Transformation:** Clean and standardize extracted data before loading it into the data warehouse.
- **Cloud Data Warehousing:** Load processed datasets into Google BigQuery.
- **Configurable Execution:** Use command-line arguments to control pipeline execution and testing.
- **Logging and Error Handling:** Record pipeline execution details and handle extraction errors.
- **Cloud Deployment:** Designed to run on a Google Cloud virtual machine, with scheduling through cron as a subsequent deployment step.

## Architecture

```text
Artist Channel Mapping
        |
        v
YouTube Data API v3
        |
        v
Python ETL Pipeline
        |
        +------------------+
        |                  |
        v                  v
   Raw JSON Data      Data Transformation
                           |
                           v
                    Processed JSON Data
                           |
                           v
                    Google BigQuery
                           |
                           v
                   SQL-Based Analysis
```

The pipeline follows three main stages:

1. **Extract:** Retrieve data from the YouTube Data API v3.
2. **Transform:** Clean and standardize the extracted records.
3. **Load:** Upload the resulting datasets to Google BigQuery.

Raw and processed JSON files are also stored locally to support debugging, data inspection, and pipeline development.

## Data Collected

The pipeline is designed to collect four categories of YouTube data.

| Dataset   | Description                                                   |
| --------- | ------------------------------------------------------------- |
| Artists   | Channel information and publicly available channel statistics |
| Playlists | Playlists associated with each channel                        |
| Videos    | Video metadata and publicly available statistics              |
| Comments  | Publicly accessible comments retrieved for collected videos   |

The exact fields available in each dataset depend on the API response and the transformation logic implemented in the project.

## Technology Stack

| Technology          | Purpose                                |
| ------------------- | -------------------------------------- |
| Python              | ETL development                        |
| YouTube Data API v3 | Data source                            |
| Requests            | HTTP requests to the API               |
| JSON                | Data storage and exchange              |
| Google BigQuery     | Cloud data warehouse                   |
| Google Cloud        | Cloud infrastructure                   |
| Git and GitHub      | Version control and project management |
| Ubuntu              | Target environment for VM deployment   |
| Cron                | Planned automated execution on the VM  |

## Project Structure

```text
jde-bigproject1/
│
├── data/
│   ├── mapping/
│   │   └── channel_mapping.json
│   ├── raw/
│   └── processed/
│
├── etl/
│   ├── config.py
│   ├── extract.py
│   ├── transform.py
│   └── load.py
│
├── main.py
├── artists.csv
├── requirements.txt
├── .env
├── .gitignore
└── README.md
```

### Main Components

- `main.py`: Parses command-line arguments and coordinates the ETL workflow.
- `etl/config.py`: Stores shared configuration and logging setup.
- `etl/extract.py`: Handles API requests and retrieves channel, playlist, video, and comment data.
- `etl/transform.py`: Cleans and transforms extracted records and manages JSON input/output.
- `etl/load.py`: Loads datasets into Google BigQuery.
- `data/mapping/channel_mapping.json`: Maps artist names to confirmed YouTube channel IDs.
- `data/raw/`: Stores extracted data before transformation.
- `data/processed/`: Stores transformed datasets before loading.

The precise directory contents may vary depending on the current development stage.

## Prerequisites

Before running the pipeline, prepare the following:

- Python 3.10 or later, subject to compatibility with the project's dependencies.
- A Google Cloud project.
- An enabled YouTube Data API v3 service and a valid API key.
- A BigQuery dataset.
- A Google Cloud service account with the necessary BigQuery permissions.
- The artist-to-channel mapping JSON file.

## Setup

### 1. Clone the Repository

```bash
git clone https://github.com/xiaoxigua0503/jde-bigproject1.git
cd jde-bigproject1
```

Replace `<YOUR_GITHUB_REPOSITORY_URL>` with the repository's actual clone URL.

### 2. Create a Virtual Environment

On Ubuntu or other Linux systems:

```bash
python3 -m venv venv
source venv/bin/activate
```

On Windows:

```bash
python -m venv venv
venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Create a local `.env` file using the variable names expected by `etl/config.py` and `etl/load.py`.

The Google Cloud configuration includes:

```dotenv
GCP_PROJECT_ID=your_google_cloud_project_id
BQ_DATASET_ID=your_bigquery_dataset_id
```

Configure your YouTube API key using the variable name expected by the extraction module.

Do not commit API keys, service account credentials, or other secrets to GitHub.

### 5. Configure Google Cloud Authentication

For local development, authenticate using an appropriately configured Google Cloud service account or Application Default Credentials.

If using a service account JSON key, keep the file outside the public repository and configure the `GOOGLE_APPLICATION_CREDENTIALS` environment variable to point to its local path.

For a Google Cloud VM, prefer attaching a service account with the required permissions and using Application Default Credentials where practical.

The identity running the pipeline needs permission to create or update the relevant BigQuery tables.

### 6. Prepare the Channel Mapping

The mapping file associates each artist with a confirmed YouTube channel ID.

Example structure:

```json
{
  "Example Artist": {
    "artist_name": "Example Artist",
    "candidates": [
      {
        "artist_name": "Example Artist",
        "channel_name": "Example Artist Official",
        "channel_id": "YOUR_CONFIRMED_CHANNEL_ID",
        "channel_url": "https://www.youtube.com/channel/YOUR_CONFIRMED_CHANNEL_ID"
      }
    ]
  }
}
```

Use valid channel IDs in your actual mapping file.

The pipeline should use the confirmed channel ID to retrieve canonical channel information from the YouTube Data API rather than relying on potentially outdated metadata in the mapping file.

## Running the Pipeline

### Run with Default Settings

```bash
python main.py
```

This executes the pipeline using the configured defaults and input files.

### Test with a Small Dataset

Before processing the full mapping, use a small test mapping containing one or a few confirmed channels.

For example, if the corresponding command-line arguments are supported by your current `main.py`:

```bash
python main.py \
  --mapping-file data/mapping/test_mapping.json \
  --max-videos 5 \
  --comments-limit 5 \
  --skip-load
```

This limits the extraction workload and skips BigQuery loading.

The exact argument names and behavior should match the command-line interface implemented in `main.py`. Inspect `python main.py --help` if needed.

### Inspect the Output

After execution, check:

- Application logs for extraction or transformation errors.
- `data/raw/` for extracted JSON files.
- `data/processed/` for transformed JSON files.
- BigQuery tables when loading is enabled.

A successful process exit alone does not guarantee that records were extracted. Confirm that the expected datasets contain actual records before proceeding to a full run.

## BigQuery

The pipeline is intended to organize the collected data into four logical datasets:

- Artists
- Playlists
- Videos
- Comments

The corresponding table names and schemas should be verified against the current implementation of `etl/load.py`.

Once the data has been loaded successfully, BigQuery can be used to:

- Analyze channel growth and publicly available engagement metrics.
- Compare video performance across artists.
- Examine comment activity.
- Build SQL-based analytical datasets for downstream reporting.

These are potential analytical use cases; the project does not assume that a dashboard or a particular analytical result has already been implemented.

## Deployment and Automation

The intended deployment workflow is:

1. Validate the ETL pipeline locally.
2. Commit and push the tested code to GitHub.
3. Create an Ubuntu virtual machine on Google Cloud.
4. Install Python and the project's dependencies.
5. Configure authentication and environment variables securely.
6. Clone the repository onto the VM.
7. Run a small test directly on the VM.
8. Verify the extracted data and BigQuery results.
9. Configure cron to execute the pipeline on a schedule.

Cron scheduling should be enabled only after the VM execution and BigQuery loading behavior have been verified.

If the current BigQuery load configuration uses `WRITE_TRUNCATE`, loading a table can replace its existing contents. An incremental ingestion strategy should be implemented and tested before scheduling recurring runs if historical records must be preserved.

## Security

- Never commit `.env` files containing credentials.
- Never expose YouTube API keys or service account private keys.
- Keep credential files out of version control.
- Grant cloud identities only the permissions required by the pipeline.
- Review `.gitignore` before pushing code or generated data.

## Current Scope and Future Improvements

Potential next steps include:

- Completing and validating the cloud VM deployment.
- Implementing incremental extraction and loading.
- Tracking ingestion timestamps and pipeline execution status.
- Improving retry handling and API quota management.
- Adding automated data-quality checks.
- Scheduling recurring pipeline execution.
- Building SQL analyses on top of the collected datasets.

These improvements should be marked as completed only after they have been implemented and tested.

## Author

**Xiaoxigua**

GitHub: [https://github.com/xiaoxigua0503](https://github.com/xiaoxigua0503)

---

*This project is developed as a hands-on data engineering project focused on API-based data collection, ETL development, and cloud data warehousing.*
