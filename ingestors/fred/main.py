import os
import pandas as pd
from fredapi import Fred
from google.cloud import storage
from datetime import datetime

def run_ingestion():
    today = datetime.now().strftime('%Y-%m-%d')
    storage_client = storage.Client()

    # 1. Configuration from Environment Variables
    api_key = os.environ.get('FRED_API_KEY')
    landing_zone_bucket_name = os.environ.get('LANDING_ZONE_BUCKET')
    bronze_bucket_name = os.environ.get('BRONZE_BUCKET')
    series_id = os.environ.get('SERIES_ID', 'STLFSI3') # Default: Stress Index
    resolution = os.environ.get('RESOLUTION', 'daily')

    # 2. Fetch report and report metadata
    fred = Fred(api_key=api_key)
    data = fred.get_series(series_id)

    # Get series metadata
    # Info fields as of 2026-01-22
    # id                                                                      PAYEMS
    # realtime_start                                                      2026-01-09
    # realtime_end                                                        2026-01-09
    # title                                             All Employees, Total Nonfarm
    # observation_start                                                   1939-01-01
    # observation_end                                                     2025-12-01
    # frequency                                                              Monthly
    # frequency_short                                                              M
    # units                                                     Thousands of Persons
    # units_short                                                  Thous. of Persons
    # seasonal_adjustment                                        Seasonally Adjusted
    # seasonal_adjustment_short                                                   SA
    # last_updated                                            2026-01-09 08:11:04-06
    # popularity                                                                  85
    # notes                        All Employees: Total Nonfarm, commonly known a...
    info = fred.get_series_info(series_id)

    # 3. Write original file to landing zone without ANY modification for traceability later
    landing_zone_blob_path = f"fred/{series_id}/frequency={info['frequency_short']}/ingest_date={today}x/{info['id']}-{info['last_updated']}.csv"
    bucket = storage_client.bucket(landing_zone_bucket_name)
    blob = bucket.blob(landing_zone_blob_path)
    blob.upload_from_string(
        # data.to_csv(index=False), 
        data.to_csv(), 
        content_type='application/octet-stream'
    )

    # 4. Convert data to parquet and add to bronze bucket for easier querying
    df = data.to_frame(name='value').reset_index()
    df.columns = ['date', 'value']
    bronze_blob_path = f"fred/{series_id}/frequency={info['frequency_short']}/ingest_date={today}/{info['id']}-{info['last_updated']}.parquet"
    bucket = storage_client.bucket(landing_zone_bucket_name)
    blob = bucket.blob(landing_zone_blob_path)
    blob.upload_from_string(
        df.to_parquet(index=False), 
        content_type='application/octet-stream'
    )

    print(f"Successfully uploaded {series_id} to {blob_path}")

if __name__ == "__main__":
    run_ingestion()