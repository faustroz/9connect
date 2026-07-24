import os
import json
import sys
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
import queue

from log_style import install_pretty_print

install_pretty_print()

import db_helper
import automation
import automation_kiro

ACCOUNTS_FILE = "accounts.txt"
PARALLEL_BROWSERS = 1

from config import DEBUG_PORTS

PROVIDERS = {
    "1": {
        "key": "antigravity",
        "name": "Antigravity",
        "title": "9Router Antigravity Account Connection Automator",
        "results_file": "results.json",
        "connect": automation.connect_antigravity_account,
        "skip_success_results": False,
    },
    "2": {
        "key": "kiro",
        "name": "Kiro",
        "title": "9Router Kiro AWS Builder ID Automator",
        "results_file": "results_kiro.json",
        "connect": automation_kiro.connect_kiro_account,
        "skip_success_results": True,
    },
}

PROVIDER_ALIASES = {
    "antigravity": "1",
    "anti": "1",
    "ag": "1",
    "kiro": "2",
}

def load_accounts():
    """Load accounts from accounts.txt (email|password format)."""
    if not os.path.exists(ACCOUNTS_FILE):
        print(f"[Error] '{ACCOUNTS_FILE}' not found. Please create it first.")
        with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
            f.write("sample_email_1@gmail.com|sample_password_1\n")
            f.write("sample_email_2@gmail.com|sample_password_2\n")
        print(f"[Info] Created a template '{ACCOUNTS_FILE}'. Please configure it before running.")
        return []

    try:
        accounts = []
        with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split("|", 1)
                if len(parts) == 2:
                    accounts.append({"email": parts[0].strip(), "password": parts[1].strip()})
        return accounts
    except Exception as e:
        print(f"[Error] Failed to read '{ACCOUNTS_FILE}': {e}")
        return []

def load_results(results_file):
    """Load existing results if they exist to support resuming."""
    if os.path.exists(results_file):
        try:
            with open(results_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_results(results, results_file):
    """Save results in pretty JSON format."""
    try:
        with open(results_file, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
    except Exception as e:
        print(f"[Error] Failed to save results: {e}")

def select_provider():
    """Select provider from CLI argument or interactive prompt."""
    if len(sys.argv) > 1:
        requested = sys.argv[1].strip().lower()
        provider_id = PROVIDER_ALIASES.get(requested, requested)
        if provider_id in PROVIDERS:
            return PROVIDERS[provider_id]
        print(f"[Warning] Unknown provider '{sys.argv[1]}'. Please select from the menu.")

    print("=" * 72)
    print(f"{'9Router Provider Selector':^72}")
    print("=" * 72)
    for provider_id, provider in PROVIDERS.items():
        print(f"  {provider_id}. {provider['name']}")
    print("-" * 72)

    while True:
        choice = input("Choose provider [1-2]: ").strip().lower()
        provider_id = PROVIDER_ALIASES.get(choice, choice)
        if provider_id in PROVIDERS:
            return PROVIDERS[provider_id]
        print("[Error] Invalid choice. Enter 1 for Antigravity or 2 for Kiro.")

def process_account(acc, i, total, provider, provider_key, results, results_lock, results_file, port_queue):
    port = port_queue.get()
    email = acc.get("email")
    password = acc.get("password")

    try:
        if not email or not password:
            print(f"[Warning] Account #{i} has missing email or password. Skipping.")
            return

        if (
            provider["skip_success_results"]
            and email in results
            and results[email].get("status") == "Account Connected"
        ):
            print(f"[Info] Account {email} already marked Connected in results. Skipping.")
            return

        print("\n" + "-" * 72)
        print(f"[Info] Account {i}/{total}: {email} (port {port})")
        print("-" * 72)

        is_active = db_helper.is_connection_active(email, provider=provider_key)
        if is_active:
            print(f"[Info] Account {email} is already active/connected for {provider['name']} in 9Router. Skipping.")
            db_conn = db_helper.get_connection(email, provider=provider_key)
            with results_lock:
                results[email] = {
                    "status": "Account Connected",
                    "last_checked": datetime.now().isoformat(),
                    "session_info": db_conn["data"] if db_conn else None,
                    "error": None
                }
                save_results(results, results_file)
            return "skip"

        existing_conn = db_helper.get_connection(email, provider=provider_key)
        if existing_conn:
            print(f"[Info] Found existing broken connection for {email} ({provider_key}). Deleting it first.")
            db_helper.delete_connection(email, provider=provider_key)

        res = provider["connect"](email, password, port)

        timestamp = datetime.now().isoformat()
        with results_lock:
            if res["success"]:
                results[email] = {
                    "status": "Account Connected",
                    "last_checked": timestamp,
                    "session_info": res["session_info"]["data"] if res["session_info"] else None,
                    "error": None
                }
            else:
                results[email] = {
                    "status": "Failed",
                    "last_checked": timestamp,
                    "session_info": None,
                    "error": res["error"]
                }
            save_results(results, results_file)

        return res["success"]

    finally:
        port_queue.put(port)

def main():
    provider = select_provider()
    provider_key = provider["key"]
    results_file = provider["results_file"]

    print("=" * 72)
    print(f"{provider['title']:^72}")
    print("=" * 72)
    print(f"[Info] Provider: {provider['name']} | Results: {results_file}")

    accounts = load_accounts()
    if not accounts:
        print("[Exit] No accounts found to process.")
        return

    print(f"[Info] Loaded {len(accounts)} accounts from '{ACCOUNTS_FILE}'.")
    print(f"[Info] Running with {PARALLEL_BROWSERS} parallel browsers.")

    results = load_results(results_file)
    results_lock = threading.Lock()

    success_count = 0
    failed_count = 0
    processed = 0

    port_queue = queue.Queue()
    for p in DEBUG_PORTS:
        port_queue.put(p)

    with ThreadPoolExecutor(max_workers=PARALLEL_BROWSERS) as executor:
        futures = {}
        for i, acc in enumerate(accounts, 1):
            future = executor.submit(process_account, acc, i, len(accounts), provider, provider_key, results, results_lock, results_file, port_queue)
            futures[future] = acc.get("email")

        for future in as_completed(futures):
            email = futures[future]
            try:
                result = future.result()
                processed += 1
                if result is True:
                    success_count += 1
                elif result is False:
                    failed_count += 1
            except Exception as e:
                print(f"[Error] Unexpected error for {email}: {e}")
                failed_count += 1
                processed += 1

    print("\n" + "=" * 72)
    print("RUN SUMMARY")
    print("=" * 72)
    print(f"Total Accounts Processed : {processed}")
    print(f"Successfully Connected   : {success_count}")
    print(f"Failed Connections       : {failed_count}")
    print(f"Results saved to         : {results_file}")
    print("=" * 72)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n[Info] Interrupted. Exiting...")