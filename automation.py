import time
import subprocess
import os
import sys
import socket
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from config import (
    CHROME_PATH, CHROMEDRIVER_PATH, CHROME_USER_DATA_DIR, DEBUG_PORTS,
    ROUTER_URL, ROUTER_PASSWORD
)
import db_helper

def kill_dev_chrome(port):
    """Kill any existing Chrome processes running on the given debug port."""
    cmd = f'powershell -NonInteractive -Command "Get-CimInstance Win32_Process -Filter \\"Name = \'chrome.exe\'\\" | Where-Object CommandLine -like \\"*chrome_dev_profile_{port}*\\" | ForEach-Object {{ Stop-Process $_.ProcessId -Force }}"'
    try:
        subprocess.run(cmd, shell=True, timeout=5, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1)
    except:
        pass

def clean_user_data_dir(port):
    """Delete the temporary Chrome profile directory for the given port."""
    import shutil
    profile_dir = f"{CHROME_USER_DATA_DIR}_{port}"
    if os.path.exists(profile_dir):
        for _ in range(3):
            try:
                shutil.rmtree(profile_dir)
                break
            except:
                time.sleep(1)

def launch_chrome(port):
    """Launch Google Chrome with remote debugging on the given port."""
    print(f"[Chrome] Cleaning up stale Chrome processes and profile for port {port}...")
    kill_dev_chrome(port)
    clean_user_data_dir(port)

    profile_dir = f"{CHROME_USER_DATA_DIR}_{port}"
    print(f"[Chrome] Launching Chrome with remote debugging on port {port}...")
    chrome_cmd = [
        CHROME_PATH,
        f"--remote-debugging-port={port}",
        f"--user-data-dir={profile_dir}",
        "--no-sandbox",
        "--disable-gpu",
        "--window-size=1280,800",
        "about:blank"
    ]

    proc = subprocess.Popen(chrome_cmd)
    time.sleep(5)
    return proc

def get_driver(port):
    """Connect Selenium to the remote debugging Chrome instance on the given port."""
    options = Options()
    options.add_experimental_option("debuggerAddress", f"127.0.0.1:{port}")
    service = Service(executable_path=CHROMEDRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=options)
    return driver

def login_to_router(driver):
    """Log in to 9Router if not already authenticated."""
    print("[9Router] Checking login status...")
    driver.get(f"{ROUTER_URL}/login")
    time.sleep(2)
    
    # If redirect didn't happen or we are on login page, authenticate
    if "/login" in driver.current_url:
        print("[9Router] Logging in with password...")
        wait = WebDriverWait(driver, 10)
        try:
            password_input = wait.until(
                EC.presence_of_element_located((By.XPATH, "//input[@type='password']"))
            )
            password_input.clear()
            password_input.send_keys(ROUTER_PASSWORD)
            
            submit_btn = driver.find_element(By.XPATH, "//button[@type='submit']")
            submit_btn.click()
            time.sleep(3)
        except Exception as e:
            print(f"[9Router] Login input failed: {e}")
            raise e

def connect_antigravity_account(email, password, port=9222):
    """Run the entire automation flow for a single account."""
    chrome_proc = None
    driver = None
    try:
        # 1. Launch Chrome
        chrome_proc = launch_chrome(port)
        
        # 2. Get Driver
        driver = get_driver(port)
        wait = WebDriverWait(driver, 15)
        
        # 3. Login to Router
        login_to_router(driver)
        
        # 4. Navigate to Antigravity Provider page
        print("[9Router] Navigating to Antigravity page...")
        driver.get(f"{ROUTER_URL}/dashboard/providers/antigravity")
        time.sleep(5)

        # 5. Open Credentials form (click Add, and bypass warning notice)
        print("[9Router] Opening connection form...")
        for attempt in range(3):
            add_btn = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Add') and not(contains(., 'Model')) and not(contains(., 'Added'))]"))
            )
            add_btn.click()
            time.sleep(2)

            try:
                continue_btn = WebDriverWait(driver, 8).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'I Understand, Continue')]"))
                )
                continue_btn.click()
                time.sleep(2)
            except:
                pass

            try:
                WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, "//input[@readonly]"))
                )
                break
            except:
                if attempt < 2:
                    print(f"[9Router] OAuth input not found, retrying... (attempt {attempt + 1})")
                    driver.get(f"{ROUTER_URL}/dashboard/providers/antigravity")
                    time.sleep(3)

        # 6. Read Google OAuth URL
        oauth_input = wait.until(
            EC.presence_of_element_located((By.XPATH, "//input[@readonly]"))
        )
        oauth_url = oauth_input.get_attribute("value")
        print(f"[OAuth] Google OAuth URL successfully extracted: {oauth_url[:80]}...")
        
        # 7. Perform Google Auth (sign-in)
        print(f"[Google] Navigating to Google Sign-in to authenticate {email}...")
        driver.get(oauth_url)
        time.sleep(4)
        
        # 7.1 Enter email robustly (handles focus, clears, and verifies text entry)
        email_field = wait.until(
            EC.visibility_of_element_located((By.XPATH, "//input[@type='email' or @id='identifierId' or @name='identifier']"))
        )
        email_field.click()
        time.sleep(1)
        
        # Write-verify loop to handle dynamic JS clearing inputs
        for attempt in range(3):
            email_field.clear()
            email_field.send_keys(email)
            time.sleep(0.5)
            entered_text = email_field.get_attribute("value")
            if entered_text == email:
                break
            time.sleep(0.5)
            
        next_btn = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//*[@id='identifierNext']//button | //button[contains(., 'Next')]"))
        )
        next_btn.click()
        time.sleep(4)
        
        # 7.2 Enter password
        print("[Google] Entering password...")
        password_field = None
        for _ in range(20):
            try:
                password_field = driver.find_element(By.XPATH, "//input[@type='password' or @name='password']")
                if password_field.is_displayed():
                    break
                password_field = None
            except:
                password_field = None

            page_text = driver.page_source
            if "find your Google Account" in page_text or "Couldn't find your" in page_text:
                raise Exception("Google Account does not exist.")
            if "Account deleted" in page_text or "deletedaccount" in driver.current_url:
                raise Exception("Google Account has been deleted.")
            if "may not be secure" in page_text or "Couldn't sign you in" in page_text:
                raise Exception("Google blocked sign-in with security warning ('browser or app not secure').")

            try:
                btn = driver.find_element(By.XPATH, "//button[contains(., 'Try another way') or contains(., 'Next') or contains(., 'Continue')]")
                if btn.is_displayed():
                    btn.click()
                    time.sleep(2)
                    continue
            except:
                pass

            time.sleep(1)

        if not password_field:
            raise Exception(f"Google Sign-In failed or timed out waiting for password field. URL: {driver.current_url}")

        password_field.clear()
        password_field.send_keys(password)
        
        pass_next_btn = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//*[@id='passwordNext']//button | //button[contains(., 'Next')]"))
        )
        pass_next_btn.click()
        time.sleep(5)
        
        # 7.3 Poll and handle all Google interstitial pages until callback redirect
        print("[OAuth] Waiting for redirect back to local callback URL...")
        callback_url = None
        for _ in range(30):
            curr_url = driver.current_url

            if "/callback" in curr_url:
                callback_url = curr_url
                break

            # Checkboxes
            try:
                for cb in driver.find_elements(By.XPATH, "//input[@type='checkbox']"):
                    if not cb.is_selected():
                        cb.click()
                        time.sleep(0.3)
            except:
                pass

            # Any actionable button: Allow, Continue, I agree, Sign in, I understand
            try:
                btn = driver.find_element(By.XPATH, "//button[contains(., 'Allow') or contains(., 'I agree') or contains(., 'Sign in') or contains(., 'I understand') or contains(., 'Continue') or contains(., 'Login') or contains(., 'Masuk')]")
                print(f"[Google] Clicking button: {btn.text.strip()}")
                btn.click()
                time.sleep(3)
            except:
                pass

            # Scroll on terms pages to reveal hidden buttons
            try:
                if "termsofservice" in curr_url.lower() or "speedbump" in curr_url.lower():
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            except:
                pass

            time.sleep(1)

        if not callback_url:
            raise Exception(f"Failed to capture redirect callback URL. Current URL is: {driver.current_url}")
            
        print(f"[OAuth] Successfully captured callback URL: {callback_url[:80]}...")
        
        # 8. Submit Callback URL to 9Router to finish connection
        print("[9Router] Navigating back to Antigravity page...")
        driver.get(f"{ROUTER_URL}/dashboard/providers/antigravity")
        time.sleep(5)
        
        # Open credentials form again
        print("[9Router] Re-opening credentials form...")
        add_btn = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Add') and not(contains(., 'Model')) and not(contains(., 'Added'))]"))
        )
        add_btn.click()
        time.sleep(3)

        # Handle "I Understand, Continue" button if it appears (may not show second time)
        try:
            continue_btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'I Understand, Continue')]"))
            )
            continue_btn.click()
            time.sleep(3)
        except:
            pass
        
        # Paste captured callback URL in input field 2 (not readonly)
        print("[9Router] Pasting callback URL...")
        paste_input = WebDriverWait(driver, 30).until(
            EC.presence_of_element_located((By.XPATH, "//input[not(@readonly) and @type='text']"))
        )
        paste_input.clear()
        paste_input.send_keys(callback_url)
        
        # Click Connect
        connect_btn = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Connect')]"))
        )
        connect_btn.click()
        print("[9Router] Submitted callback URL. Waiting for backend validation...")
        time.sleep(5)
        
        # 9. Verify Connection Status in Database
        print("[DB] Verifying connection status in SQLite...")
        is_success = False
        for _ in range(10):
            if db_helper.is_connection_active(email):
                is_success = True
                break
            time.sleep(1)
            
        if not is_success:
            # Check what error is stored in DB
            conn_info = db_helper.get_connection(email)
            err_msg = "Unknown error"
            if conn_info and "lastError" in conn_info["data"]:
                err_msg = conn_info["data"]["lastError"]
            raise Exception(f"Account connection failed. Status in database remains inactive. Error: {err_msg}")
            
        print(f"[Success] Account {email} connected successfully!")
        
        # Retrieve session info
        session_info = db_helper.get_connection(email)
        return {
            "success": True,
            "email": email,
            "session_info": session_info,
            "error": None
        }
        
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        print(f"[Error] Failed to connect {email}: {type(e).__name__} - {e}\n{tb}", flush=True)
        return {
            "success": False,
            "email": email,
            "session_info": None,
            "error": f"{type(e).__name__}: {e}\n{tb}"
        }
    finally:
        if driver:
            try:
                driver.quit()
            except:
                pass
        if chrome_proc:
            try:
                chrome_proc.terminate()
                chrome_proc.wait(timeout=3)
            except:
                pass
