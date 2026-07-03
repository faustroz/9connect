import os
import json
import sys
import time
from datetime import datetime

from log_style import install_pretty_print

install_pretty_print()

import db_helper
import automation
import automation_kiro

ACCOUNTS_FILE = "accounts.json"

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
    """Load accounts from accounts.json."""
    if not os.path.exists(ACCOUNTS_FILE):
        print(f"[Error] '{ACCOUNTS_FILE}' not found. Please create it first.")
        sample = [
            {"email": "sample_email_1@gmail.com", "password": "sample_password_1"},
            {"email": "sample_email_2@gmail.com", "password": "sample_password_2"}
        ]
        with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
            json.dump(sample, f, indent=2)
        print(f"[Info] Created a template '{ACCOUNTS_FILE}'. Please configure it before running.")
        return []

    try:
        with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
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

    results = load_results(results_file)

    processed = 0
    success_count = 0
    failed_count = 0

    for i, acc in enumerate(accounts, 1):
        email = acc.get("email")
        password = acc.get("password")

        if not email or not password:
            print(f"[Warning] Account #{i} has missing email or password. Skipping.")
            continue

        if (
            provider["skip_success_results"]
            and email in results
            and results[email].get("status") == "Account Connected"
        ):
            print(f"[Info] Account {email} already marked Connected in results. Skipping.")
            success_count += 1
            processed += 1
            continue

        print("\n" + "-" * 72)
        print(f"[Info] Account {i}/{len(accounts)}: {email}")
        print("-" * 72)

        is_active = db_helper.is_connection_active(email, provider=provider_key)
        if is_active:
            print(f"[Info] Account {email} is already active/connected for {provider['name']} in 9Router. Skipping.")
            db_conn = db_helper.get_connection(email, provider=provider_key)
            results[email] = {
                "status": "Account Connected",
                "last_checked": datetime.now().isoformat(),
                "session_info": db_conn["data"] if db_conn else None,
                "error": None
            }
            save_results(results, results_file)
            success_count += 1
            processed += 1
            continue

        existing_conn = db_helper.get_connection(email, provider=provider_key)
        if existing_conn:
            print(f"[Info] Found existing broken connection for {email} ({provider_key}). Deleting it first.")
            db_helper.delete_connection(email, provider=provider_key)

        res = provider["connect"](email, password)

        timestamp = datetime.now().isoformat()
        if res["success"]:
            results[email] = {
                "status": "Account Connected",
                "last_checked": timestamp,
                "session_info": res["session_info"]["data"] if res["session_info"] else None,
                "error": None
            }
            success_count += 1
        else:
            results[email] = {
                "status": "Failed",
                "last_checked": timestamp,
                "session_info": None,
                "error": res["error"]
            }
            failed_count += 1

        processed += 1
        save_results(results, results_file)

        if i < len(accounts):
            cooldown = 60 + (i * 5)  # Increase cooldown progressively: 60s, 65s, 70s, etc.
            print(f"[Info] Cooling down {cooldown} seconds before next account to avoid captcha...")
            time.sleep(cooldown)

    print("\n" + "=" * 72)
    print("RUN SUMMARY")
    print("=" * 72)
    print(f"Total Accounts Processed : {processed}")
    print(f"Successfully Connected   : {success_count}")
    print(f"Failed Connections       : {failed_count}")
    print(f"Results saved to         : {results_file}")
    print("=" * 72)

if __name__ == "__main__":
    main()