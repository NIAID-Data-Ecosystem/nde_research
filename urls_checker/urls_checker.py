#!/usr/bin/env python3

import aiohttp
import asyncio
import gspread
import urllib.parse
import json
import os
import logging
from datetime import datetime
from dotenv import load_dotenv


logging.basicConfig(
    filename="logs.txt",
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)


load_dotenv(dotenv_path=Path("secrets.env"))  # Loads from .env by default

GOOGLE_SHEET_URL = os.getenv("GOOGLE_SHEET_URL")
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL")

STATUS_FILE = "url_status.json"
FAILURE_THRESHOLD_MINUTES = 4320  # 3 days


def load_status():
    """Load the status file containing previous URL test results."""
    logging.info("Loading status from file...")
    if os.path.exists(STATUS_FILE):
        with open(STATUS_FILE, "r") as f:
            return json.load(f)
    logging.info("No status file found, starting fresh.")
    return {}

def save_status(status):
    """Save the updated URL status to the JSON file."""
    logging.info("Saving updated status to file...")
    with open(STATUS_FILE, "w") as f:
        json.dump(status, f, indent=4)

async def fetch_google_sheet_data(sheet_url):
    """Fetch data from the first tab of the Google Sheet."""
    logging.info("Fetching Google Sheet data...")
    try:
        gc = gspread.service_account(filename='credentials.json')
        sheet = gc.open_by_url(sheet_url)
        worksheet = sheet.get_worksheet(0)  # First sheet
        return worksheet.get_all_records()
    except Exception as e:
        logging.error(f"Error fetching Google Sheet data: {e}")
        return []

def is_valid_url(url):
    """Check if the URL is well-formed."""
    try:
        result = urllib.parse.urlparse(url)
        return all([result.scheme, result.netloc])
    except ValueError:
        return False

async def test_url(session, url, expected_code, expected_content, status, retries=4, backoff_factor=2):
    """Test URL and update the failure count in the status file."""
    logging.info(f"Testing URL: {url}")
    result = {
        "url": url,
        "code_passed": False,
        "content_passed": False,
        "valid": False,
        "status_code": None,
    }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",  # Chrome User-Agent
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",  # Accept all types of content
        # "Accept-Encoding": "gzip, deflate",  # Chrome accepts compressed content
        "Accept-Language": "en-US,en;q=0.9",  # Language preference
        "Connection": "keep-alive",  # Keep the connection open
        "Upgrade-Insecure-Requests": "1",  # Chrome sends this header when navigating
    }
    if not is_valid_url(url):
        logging.warning(f"Invalid URL: {url}")
        return result

    for attempt in range(retries):
        try:
            async with session.get(url, headers=headers, timeout=10) as response:
                result["valid"] = True
                result["status_code"] = response.status
                result["code_passed"] = (response.status == expected_code)
                body = await response.text()
                result["content_passed"] = str(expected_content) in body
                logging.info(f"Attempt {attempt+1} succeeded for {url} (status {response.status})")
                break
        except Exception as e:
            logging.warning(f"Error testing {url} (attempt {attempt+1}): {e}")
            if attempt < retries - 1:
                wait_time = backoff_factor ** attempt
                logging.info(f"Retrying {url} in {wait_time:.2f} seconds...")
                await asyncio.sleep(wait_time)
            else:
                logging.error(f"Max retries reached for {url}")

    url_entry = status.get(url, {"fail_count": 0, "last_fail_time": None, "notified": False})
    if result["code_passed"] and result["content_passed"]:
        logging.info(f"Test passed for {url}")
        url_entry["fail_count"] = 0  # Reset failure count on success
        url_entry["last_fail_time"] = None
        url_entry["notified"] = False
    else:
        logging.info(f"Test failed for {url}")
        url_entry["fail_count"] += 1
        if url_entry["last_fail_time"] is None:
            url_entry["last_fail_time"] = datetime.now().isoformat()

    status[url] = url_entry
    return result

def generate_slack_report(results, status):
    """Generate a Slack message based on the test results."""
    logging.info("Generating Slack report...")
    total = len(results)
    failed = [
        {"url": r["url"], "code_passed": r["code_passed"], "content_passed": r["content_passed"], "status_code": r["status_code"]}
        for r in results if (not r['code_passed'] or not r['content_passed'])
    ]

    now = datetime.now()
    truly_failing = []
    for entry in failed:
        url = entry["url"]
        status_entry = status.get(url, {})
        last_fail_time = status_entry.get("last_fail_time")
        if last_fail_time:
            fail_duration = (now - datetime.fromisoformat(last_fail_time)).total_seconds() / 60
            if fail_duration > FAILURE_THRESHOLD_MINUTES:
                if not status_entry.get("notified", False):
                    truly_failing.append(entry)
                    status_entry["notified"] = True
                # status[url] = status_entry

    logging.info(f"Total URLs: {total}, Failing beyond threshold: {len(truly_failing)}")

    message = {
        "blocks": [
            {"type": "section", "text": {"type": "mrkdwn", "text": f":large_green_circle: *NDE URL Test Report*\nTotal URLs tested: *{total}*\nFailed: *{len(truly_failing)}*"}},
        ]
    }

    if truly_failing:
        message = {
            "blocks": [
                {"type": "section", "text": {"type": "mrkdwn", "text": f":red_circle: *NDE URL Test Report*\nTotal URLs tested: *{total}*\nFailed: *{len(truly_failing)}*"}},
            ]
        }

        message["blocks"].append({"type": "section", "text": {"type": "mrkdwn", "text": "*Consistently Failing URLs:*"}})

        for entry in truly_failing:
            str_error = ""
            if 'code_passed' in entry and entry['code_passed'] == False:
                str_error += f"❌ HTTP {entry['status_code']} "
            if 'content_passed' in entry and not entry['content_passed']:
                str_error += "❌ Body mismatch"

            message["blocks"].append({"type": "section", "text": {"type": "mrkdwn", "text": f"• <{entry['url']}|{entry['url']}> {str_error}"}})
        return True, message
    else:
        return False, message

async def send_to_slack(webhook_url, message):
    """Send the message to Slack using the webhook URL."""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(webhook_url, json=message) as response:
                response.raise_for_status()
                logging.info("Slack message sent successfully.")
    except Exception as e:
        logging.error(f"Error sending message to Slack: {e}")

async def main():
    logging.info("===== Starting URL Monitor Script =====")
    data = await fetch_google_sheet_data(GOOGLE_SHEET_URL)

    if not data:
        logging.warning("No data fetched from Google Sheets.")
        return

    status = load_status()

    async with aiohttp.ClientSession() as session:
        tasks = [
            test_url(session, row["URL"], int(row.get("Expected HTTP Code", 200)), row.get("Expected result", ""), status)
            for row in data if row.get("URL")
        ]
        results = await asyncio.gather(*tasks)

    save_status(status)
    send_message, slack_message = generate_slack_report(results, status)
    if send_message:
        logging.info("Sending message to Slack...")
        await send_to_slack(SLACK_WEBHOOK_URL, slack_message)
    else:
        logging.info("Don't send Slack message: there are no active errors.")

    save_status(status)
    logging.info("===== Script completed =====")

if __name__ == "__main__":
    asyncio.run(main())

