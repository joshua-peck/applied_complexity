import os
import tempfile
from datetime import date, datetime
from typing import BinaryIO
from dataclasses import dataclass
import boto3
import botocore
from google.cloud import storage

report_aggregations_map = {
    'daily': 'day_aggs_v1',
}

@dataclass
class MassiveSourceObject:
    series_id: str
    resolution: str
    report_date: date

    # Example path: 's3://flatfiles/us_stocks_sip/day_aggs_v1/2026/01/2026-01-22.csv.gz'
    def getObjectKey(self):
        object_key = f"{self.series_id}/{self.resolution}/{self.report_date.year}/{self.report_date.month:02}/{self.report_date.year}-{self.report_date.month:02}-{self.report_date.day:02}.csv.gz"
        return object_key


def run_ingestion():
    # create GCP connection
    storage_client = storage.Client()

    # prep dates for constructing download / upload paths later...
    today: date = datetime.now().date()
    today_str: str = today.strftime("%Y-%m-%d")
    report_date_str: str = os.environ.get('REPORT_DATE', f"{today.year}-{today.month}-{today.day}")
    report_date: date = datetime.strptime(report_date_str, "%Y-%m-%d").date()

    # Fetch keys and initialize S3 connection
    landing_zone_bucket_name: str = os.environ.get('LANDING_ZONE_BUCKET')
    bronze_bucket_name: str = os.environ.get('BRONZE_BUCKET')
    aws_access_key_id: str = os.environ.get('MASSIVE_ACCESS_KEY_ID')
    aws_secret_access_key: str = os.environ.get('MASSIVE_SECRET_ACCESS_KEY')
    series_id: str = os.environ.get('SERIES_ID', 'us_stocks_sip')
    resolution: str = os.environ.get('RESOLUTION', 'daily')
    
    # Initialize a session using your credentials
    session = boto3.Session(
        aws_access_key_id=aws_access_key_id,
        aws_secret_access_key=aws_secret_access_key,
    )
    s3 = session.client(
        's3',
        endpoint_url='https://files.massive.com',
        config=botocore.config.Config(signature_version='s3v4'),
    )

    # 1. Download flat file via S3
    bucket_name = "flatfiles"
    mso = MassiveSourceObject(series_id, report_aggregations_map[resolution], report_date)

    # object_key = f"flatfiles/{series_id}/{report_aggregations_map[resolution]}/{report_date.year}/{report_date.month}/{report_date.year}-{report_date.month}-{report_date.day}.csv.gz"
    with tempfile.TemporaryFile() as tmpfile:
        try:
            s3.download_fileobj(bucket_name, mso.getObjectKey(), tmpfile)
            print("-- MASSIVE SOURCE FILE DOWNLOAD: COMPLETE")
            # gcp_upload(storage_client, landing_zone_bucket_name, )
        except Exception as e:
            print(f'Error downloading file: {type(e).__name__}:{e}')

        # XXX: refactor into function or class to simplify
        # 2. Write original file to landing zone without ANY modification for traceability later
        tmpfile.seek(0)
        landing_zone_blob_path = f"massive/{series_id}/frequency={resolution}/ingest_date={today}/{report_date.year}-{report_date.month:02}-{report_date.day:02}.csv.gz"
        bucket = storage_client.bucket(landing_zone_bucket_name)
        blob = bucket.blob(landing_zone_blob_path)
        blob.upload_from_file(tmpfile)
        print(f"Successfully wrote {series_id} to {landing_zone_blob_path}")

        # XXX: refactor into function or class to simplify
        # 2. Write original file to landing zone without ANY modification for traceability later
        tmpfile.seek(0)
        bronze_blob_path = f"massive/{series_id}/frequency={resolution}/ingest_date={today}/{report_date.year}-{report_date.month:02}-{report_date.day:02}.parquet"
        bucket = storage_client.bucket(bronze_bucket_name)
        blob = bucket.blob(bronze_blob_path)
        blob.upload_from_file(tmpfile)
        print(f"Successfully wrote {series_id} to {bronze_blob_path}")

if __name__ == "__main__":
    run_ingestion()