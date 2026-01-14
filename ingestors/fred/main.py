import os
import pandas as pd
from fredapi import Fred
from google.cloud import storage
from datetime import datetime

def run_ingestion():
    # 1. Configuration from Environment Variables
    api_key = os.environ.get('FRED_API_KEY')
    bucket_name = os.environ.get('BRONZE_BUCKET')
    series_id = os.environ.get('SERIES_ID', 'STLFSI3') # Default: Stress Index
    resolution = os.environ.get('RESOLUTION', 'daily')

    # 2. Fetch Data
    fred = Fred(api_key=api_key)
    # Using 'realtime_start' ensures we see the data as it was known today
    data = fred.get_series(series_id)
    df = data.to_frame(name='value').reset_index()
    df.columns = ['date', 'value']

    # 3. Define the Hive Path
    # format: source/series/resolution/ingest_date=YYYY-MM-DD/data.parquet
    today = datetime.now().strftime('%Y-%m-%d')
    blob_path = f"fred/{series_id}/{resolution}/ingest_date={today}/data.parquet"

    # 4. Upload to GCS
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_path)

    # Convert to Parquet in-memory and upload
    blob.upload_from_string(
        df.to_parquet(index=False), 
        content_type='application/octet-stream'
    )
    print(f"Successfully uploaded {series_id} to {blob_path}")

if __name__ == "__main__":
    run_ingestion()