import subprocess
from datetime import datetime, date, timedelta
import argparse
import logging
import pathlib

ADC = str(pathlib.Path('~/.config/gcloud/application_default_credentials.json').expanduser())
TAG = 'massive_ingestor'
VERSION = 'latest'

def run(rundate: str):
  cmd = [ 
    "docker", "run", "-it", 
    "--env-file", "../../.env", 
    "-v", f"{ADC}:/tmp/keys/creds.json:ro", 
    "-e", "GOOGLE_APPLICATION_CREDENTIALS=/tmp/keys/creds.json", 
    "-e", f"REPORT_DATE={rundate}",
    "-t", f"{TAG}:{VERSION}" 
  ]
  result = subprocess.Popen(
    cmd,
    stdout=subprocess.PIPE, 
    stderr=subprocess.STDOUT, 
    text=True,
    universal_newlines=True,
    bufsize=1 # Line buffering
  )
  stdout, stderr = result.communicate()
  logging.info(f"Stdout: {stdout}")
  if stderr is not None:
    logging.info(f"Stderr: {stderr}")

if __name__ == "__main__":
  logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
  parser = argparse.ArgumentParser(description="Backfill data history by running docker image")
  parser.add_argument("--start", type=lambda d: datetime.strptime(d, '%Y-%m-%d').date(), required=False, help="Start date (YYYY-MM-DD)")
  parser.add_argument("--end", type=lambda d: datetime.strptime(d, '%Y-%m-%d').date(), required=False, help="End date (YYYY-MM-DD)")
  parser.add_argument("--days-ago", type=int, required=False, help="run for the date = today - DAYS_AGO")
  args = parser.parse_args()

  if args.days_ago is not None:
    report_date = (datetime.today() - timedelta(days=args.days_ago)).date()
    logging.info(f"Running for: {report_date}")
    run(report_date.strftime("%Y-%m-%d"))
  if args.start is not None and args.end is not None:
    delta = timedelta(days=1)
    current_date = args.start
    while current_date < args.end:
      logging.info(f"Running for: {current_date}")
      run(current_date)
      current_date = current_date + delta
