import os
import json
import time
from datetime import datetime

import db_helper
import automation
from config import RESULTS_FILE

ACCOUNTS_FILE = "accounts.json"

def load_accounts():
    """Load accounts from accounts.json."""
    if not os.path.exists(ACCOUNTS_FILE):
        print(f"[Error] '{ACCOUNTS_FILE}' not found. Please create it first.")
        # Create a sample template if not exists
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

def load_results():
    """Load existing results if they exist to support resuming."""
    if os.path.exists(RESULTS_FILE):
        try:
            with open(RESULTS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_results(results):
    """Save results in pretty JSON format."""
    try:
        with open(RESULTS_FILE, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
    except Exception as e:
        print(f"[Error] Failed to save results: {e}")

def main():
    print("=" * 60)
    print("       9Router Antigravity Account Connection Automator       ")
    print("=" * 60)
    
    # 1. Load accounts
    accounts = load_accounts()
    if not accounts:
        print("[Exit] No accounts found to process.")
        return
        
    print(f"[Info] Loaded {len(accounts)} accounts from '{ACCOUNTS_FILE}'.")
    
    # 2. Load existing results
    results = load_results()
    
    processed = 0
    success_count = 0
    failed_count = 0
    
    for i, acc in enumerate(accounts, 1):
        email = acc.get("email")
        password = acc.get("password")
        
        if not email or not password:
            print(f"[Warning] Account #{i} has missing email or password. Skipping.")
            continue
            
        print("\n" + "-" * 50)
        print(f"Processing Account {i}/{len(accounts)}: {email}")
        print("-" * 50)
        
        # Check database status
        is_active = db_helper.is_connection_active(email)
        if is_active:
            print(f"[Info] Account {email} is already active/connected in 9Router. Skipping.")
            # Record it as successful from database
            db_conn = db_helper.get_connection(email)
            results[email] = {
                "status": "Account Connected",
                "last_checked": datetime.now().isoformat(),
                "session_info": db_conn["data"] if db_conn else None,
                "error": None
            }
            save_results(results)
            success_count += 1
            processed += 1
            continue
            
        # Clean up any existing broken connection in database
        existing_conn = db_helper.get_connection(email)
        if existing_conn:
            print(f"[Info] Found existing broken connection for {email}. Deleting it first.")
            db_helper.delete_connection(email)
            
        # Run automation
        res = automation.connect_antigravity_account(email, password)
        
        # Record result
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
        
        # Save incrementally
        save_results(results)
        
        # Short cooldown between accounts
        if i < len(accounts):
            print("[Info] Cooling down 5 seconds before next account...")
            time.sleep(5)
            
    print("\n" + "=" * 60)
    print("                         RUN SUMMARY                          ")
    print("=" * 60)
    print(f"Total Accounts Processed : {processed}")
    print(f"Successfully Connected   : {success_count}")
    print(f"Failed Connections       : {failed_count}")
    print(f"Results saved to         : {RESULTS_FILE}")
    print("=" * 60)

if __name__ == "__main__":
    main()
