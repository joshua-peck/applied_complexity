import os
import tempfile
from datetime import date, datetime
from typing import BinaryIO
import logging
import boto3
import botocore
from google.cloud import storage
import pandas as pd

# Configure global logging settings
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

SOURCE_BUCKET_NAME = "flatfiles"
REPORT_AGGREGATIONS_MAP = {
    'daily': 'day_aggs_v1',
}

def report_aggregation_stub(resolution: string):
    return REPORT_AGGREGATIONS_MAP[resolution]

def massive_object_key(series_id: str, resolution: str, report_date: date):
    object_key = f"{series_id}/{resolution}/{report_date.year}/{report_date.month:02}/{report_date.year}-{report_date.month:02}-{report_date.day:02}.csv.gz"
    return object_key

def gcp_blob_path(series_id: str, resolution: str, report_date: date, format: str):
    ingest_date: str = datetime.now().date().strftime("%Y-%m-%d")
    return f"massive/{series_id}/frequency={resolution}/ingest_date={ingest_date}/{report_date.year}-{report_date.month:02}-{report_date.day:02}{format}"

def gcp_landing_zone_upload(client: storage.Client, tmpfile: tempfile.TemporaryFile, bucket_name: str, blob_path: str):
    tmpfile.seek(0)
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_path)
    return blob.upload_from_file(tmpfile)

def gcp_bronze_upload(client: storage.Client, tmpfile: tempfile.TemporaryFile, bucket_name: str, blob_path: str):
    tmpfile.seek(0)
    df = pd.read_csv(tmpfile, compression='gzip')
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(blob_path)
    return blob.upload_from_string(
        df.to_parquet(index=False), 
        content_type='application/octet-stream'
    )

def run_ingestion():
    # create GCP connection
    storage_client = storage.Client()

    # prep dates for constructing download / upload paths later...
    today: date = datetime.now().date()
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
    source_object_key = massive_object_key(series_id, report_aggregation_stub(resolution), report_date)
    with tempfile.TemporaryFile() as tmpfile:
        try:
            s3.download_fileobj(SOURCE_BUCKET_NAME, source_object_key, tmpfile)
            logging.info(f"Massive source file downloaded: {SOURCE_BUCKET_NAME}/{source_object_key}")
            landing_zone_blob_path = gcp_blob_path(series_id, resolution, today, '.csv.gz')
            gcp_landing_zone_upload(storage_client, tmpfile, landing_zone_bucket_name, landing_zone_blob_path)
            logging.info(f"Landing Zone file uploaded: {landing_zone_bucket_name}/{landing_zone_blob_path}")
            bronze_blob_path = gcp_blob_path(series_id, resolution, today, '.parquet')
            gcp_bronze_upload(storage_client, tmpfile, bronze_bucket_name, bronze_blob_path)
            logging.info(f"Bronze file uploaded: {bronze_bucket_name}/{bronze_blob_path}")
        except Exception as e:
            print(f'Error ingesting file ({source_object_key}): {type(e).__name__}:{e}')

if __name__ == "__main__":
    run_ingestion()