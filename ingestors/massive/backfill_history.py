import subprocess
from datetime import datetime, date, timedelta
import argparse
import logging
import sys
import os

ADC = '/Users/jmp/.config/gcloud/application_default_credentials.json'
TAG = 'massive_ingestor'
VERSION = 'latest'

def run(rundate: str):
  cmd = [ 
    "docker", "run", "-it", 
    "--env-file", "../../.env", 
    "-v", f"{ADC}:/tmp/keys/creds.json:ro", 
    "-e", "GOOGLE_APPLICATION_CREDENTIALS=/tmp/keys/creds.json", 
    "-t", f"{TAG}:{VERSION}" 
  ]
  result = subprocess.Popen(
    cmd,
    env=os.environ | {"REPORT_DATE": rundate},
    stdout=subprocess.PIPE, 
    stderr=subprocess.STDOUT, 
    text=True,
    bufsize=1 # Line buffering
  )
  while True:
    line = result.stdout.readline()
    if not line:
      break
    sys.stdout.write(line)
    sys.stdout.flush() # Ensure it prints immediately
  #   print(result.stdout)
  #   if result.stderr:
  #     print("Error:", result.stderr)
  # except subprocess.CalledProcessError as e:
  #   print(f"Command failed with return code {e.returncode}")
  #   print("STDOUT:", result.stdout)
  #   print("STDERR:", result.stderr)
  # except FileNotFoundError:
  #   print("Command not found. Check your command name and path.")

if __name__ == "__main__":
  logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
  parser = argparse.ArgumentParser(description="Backfill data history by running docker image")
  parser.add_argument("--start", type=datetime.date, required=False, help="Start date (YYYY-MM-DD)")
  parser.add_argument("--end", type=datetime.date, required=False, help="End date (YYYY-MM-DD)")
  parser.add_argument("--days-ago", type=int, required=False, help="run for the date = today - DAYS_AGO")
  args = parser.parse_args()

  if args.days_ago is not None:
    report_date = (datetime.today() - timedelta(days=args.days_ago)).date()
    logging.info(f"Running for: {report_date}")
    run(report_date.strftime("%Y-%m-%d"))






# process for n days ago, usually n = 1 to process yesterday's updates
# try:
#     result = subprocess.run(
#         ["ls", "-l"],
#         capture_output=True,
#         text=True,
#         check=True # Raise an exception if the command fails
#     )
#     print(result.stdout)
#     if result.stderr:
#         print("Error:", result.stderr)
# except subprocess.CalledProcessError as e:
#     print(f"Command failed with return code {e.returncode}")
# except FileNotFoundError:
#     print("Command not found. Check your command name and path.")

  # docker run -it \
  #     --env-file ../../.env \
  #     -v $(ADC):/tmp/keys/creds.json:ro \
  #     -e GOOGLE_APPLICATION_CREDENTIALS=/tmp/keys/creds.json \
  #     -t $(TAG):$(VERSION) 
    


# parser.print_help()


# start = datetime.strptime("2023-10-01", "%Y-%m-%d")
# end = datetime.strptime("2023-10-05", "%Y-%m-%d")

# current = start
# while current <= end:
#     print(current.strftime("%Y-%m-%d"))
#     current += timedelta(days=1)


    

# try:
#     result = subprocess.run(
#         ["ls", "-l"],
#         capture_output=True,
#         text=True,
#         check=True # Raise an exception if the command fails
#     )
#     print(result.stdout)
#     if result.stderr:
#         print("Error:", result.stderr)
# except subprocess.CalledProcessError as e:
#     print(f"Command failed with return code {e.returncode}")
# except FileNotFoundError:
#     print("Command not found. Check your command name and path.")


# # run_long_task(["make", "build"])

# # docker run -it \
# # 		--env-file ../../.env \
# # 		-v $(ADC):/tmp/keys/creds.json:ro \
# # 		-e GOOGLE_APPLICATION_CREDENTIALS=/tmp/keys/creds.json \
# # 		-t $(TAG):$(VERSION) 
