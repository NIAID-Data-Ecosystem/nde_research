# 🔍 NDE URL Monitor

This Python script monitors a list of URLs defined in a Google Sheet and checks:

- If each URL returns the expected HTTP status code
- If the response body contains an expected string

It keeps track of failures in a local file and sends alerts to Slack when URLs have been failing for more than 3 days.

---

## ✅ Features

- Async URL testing with retries and exponential backoff
- Reads test cases from Google Sheets
- Validates status codes and response content
- Saves test status locally (in `url_status.json`)
- Sends Slack alerts for persistent failures
- Logs all actions to `logs.txt`

---

## 📦 Requirements

Install dependencies with:

```bash
pip install -r requirements.txt
```

Dependencies include:

- `aiohttp`
- `gspread`
- `python-dotenv`

Make sure to also have:

- `credentials.json` — Google service account credentials
- `secrets.env` — Environment variables (see below)

---

## 🔐 Environment Variables

Create a file named `secrets.env` in the root directory with the following content:

```env
GOOGLE_SHEET_URL=https://docs.google.com/spreadsheets/d/your-sheet-id
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/your/webhook/url
```

---

## 📋 Google Sheet Format

The Google Sheet must contain a header row and the following columns:

| Repository      | URL                 | Expected HTTP Code | Expected result               | Notes                           |
|-----------------|---------------------|--------------------|-------------------------------|---------------------------------|
| Repository Name | https://example.com | 200                | Any text in the response body | Any notes about the current URL |

---

## 🚀 Running the Script

```bash
python your_script_name.py
```

Make sure `credentials.json` and `secrets.env` are in the same directory as the script.

---

## 📝 How It Works

1. Loads environment variables from `secrets.env`
2. Loads test data from the Google Sheet
3. Tests each URL for:
   - Validity
   - Expected status code
   - Expected content
4. Saves test results to `url_status.json`
5. If any URL has been failing for over 3 days and hasn't been notified yet, it sends a report to Slack
6. Logs details in `logs.txt`

---

## 📬 Slack Alerts

Slack messages include:

- Number of URLs tested
- Number of failing URLs (after 3 days of consistent failure)
- List of URLs with specific issues:
  - ❌ Wrong status code
  - ❌ Missing expected content

Example:

```
:red_circle: NDE URL Test Report  
Total URLs tested: 20  
Failed: 2

Consistently Failing URLs:
• https://example.com ❌ HTTP 500 ❌ Body mismatch
```

---

## 🧠 Notes

- Retries up to 4 times with exponential backoff if a request fails
- Uses a desktop browser-style User-Agent to avoid basic bot blocks
- Only notifies Slack once per failure episode to avoid noise

---

