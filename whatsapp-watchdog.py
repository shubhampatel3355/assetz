import gspread
from oauth2client.service_account import ServiceAccountCredentials
import requests
import time
import os
import json
import re

# ---------- CONFIG ----------
SHEET_NAME = "Coolify-Assertz"
API_URL = "http://evo-v40s8cc8o8gw0kgswos4w0wc.72.62.197.26.sslip.io"
API_KEY = "QM6HxQI2oBX3gkwLu6qn8RSBFtWXvlMv"
INSTANCE = "houseline"
OWNER_PHONE = "919686350903"

POLL_INTERVAL = 10
WAIT_LOG_INTERVAL = 120
MAX_RETRIES = 3
RETRY_DELAY = 5
# ----------------------------

def setup_google_sheets():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
    if not creds_json:
        raise Exception("GOOGLE_CREDENTIALS_JSON env variable not found")
    creds_dict = json.loads(creds_json)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    client = gspread.authorize(creds)
    return client.open(SHEET_NAME).sheet1

def format_phone(phone):
    if not phone: return None
    digits = re.sub(r"\D", "", str(phone))
    if not digits: return None
    if digits.startswith("91") and len(digits) >= 12: return digits
    if len(digits) == 10: return "91" + digits
    return digits

def send_whatsapp(phone, message, label="Owner"):
    clean_phone = format_phone(phone)
    url = f"{API_URL}/message/sendText/{INSTANCE}"
    payload = {"number": clean_phone, "text": message}
    headers = {"apikey": API_KEY, "Content-Type": "application/json"}

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            # Note: Checking for 200 or 201 as success codes
            response = requests.post(url, json=payload, headers=headers, timeout=15)
            if response.status_code in [200, 201]:
                print(f"✅ [{label}] Message sent to {clean_phone}")
                return True
            else:
                print(f"❌ [{label}] API Error {response.status_code}: {response.text}")
        except Exception as e:
            print(f"⚠️ [{label}] Attempt {attempt} failed: {e}")
        
        if attempt < MAX_RETRIES:
            time.sleep(RETRY_DELAY)
    return False

def run_automation():
    sheet = setup_google_sheets()
    last_wait_log_time = time.time()
    print("🚀 Houseline System Live (Owner Alerts Only). Waiting for leads...")

    while True:
        processed_any = False
        try:
            # Get headers to find the 'Processed' column dynamically
            headers = sheet.row_values(1)
            if "Processed" not in headers:
                print("❌ Error: 'Processed' column not found in sheet!")
                time.sleep(60)
                continue
            
            processed_col_idx = headers.index("Processed") + 1
            rows = sheet.get_all_records()

            for idx, row in enumerate(rows, start=2):
                # Skip if already marked TRUE
                if str(row.get("Processed")).strip().upper() == "TRUE":
                    continue

                processed_any = True
                c_name = row.get("Name", "N/A")
                c_phone = row.get("Phone", "N/A")
                visit_time = row.get("when_you_are☻_available_to_visit?", "N/A")
                connect_time = row.get("best_time_to_connect_with_you?", "N/A")

                # Build the message for the owner
                owner_msg = (
                    f"✨ *New Lead Received*\n\n"
                    f"👤 *Name:* {c_name}\n"
                    f"📞 *Phone:* {c_phone}\n"
                    f"🕒 *Best time to connect:* {connect_time}\n"
                    f"🗓️ *Planned Visit:* {visit_time}\n\n"
                    f"_Sent via Mavixy Automation_"
                )

                # Send the message
                success = send_whatsapp(OWNER_PHONE, owner_msg)

                # If successful, mark the sheet immediately
                if success:
                    sheet.update_cell(idx, processed_col_idx, "TRUE")
                    print(f"✔️ Row {idx} updated to TRUE.")
                else:
                    print(f"⏸️ Row {idx} failed to send. Will retry next loop.")

        except Exception as e:
            print(f"⚠️ System error: {e}")
            time.sleep(30)

        # Log heartbeat if idle
        if not processed_any:
            if time.time() - last_wait_log_time >= WAIT_LOG_INTERVAL:
                print(f"🕒 [{time.strftime('%H:%M:%S')}] Monitoring sheet for new leads...")
                last_wait_log_time = time.time()
        
        time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    run_automation()
