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
    CHROME_PATH, CHROMEDRIVER_PATH, CHROME_USER_DATA_DIR, DEBUG_PORT,
    ROUTER_URL, ROUTER_PASSWORD
)
import db_helper

def kill_dev_chrome():
    """Kill any existing Chrome and chromedriver processes completely."""
    # Kill chromedriver
    subprocess.run('powershell -NonInteractive -Command "Stop-Process -Name \'chromedriver\' -Force -ErrorAction SilentlyContinue"', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    
    # Kill Chrome
    cmd = 'powershell -NonInteractive -Command "Get-CimInstance Win32_Process -Filter \\"Name = \'chrome.exe\'\\" | Where-Object CommandLine -like \\"*chrome_dev_profile*\\" | ForEach-Object { Stop-Process $_.ProcessId -Force }"'
    try:
        subprocess.run(cmd, shell=True, timeout=5, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1)
    except:
        pass

def clean_user_data_dir():
    """Delete the temporary Chrome profile directory to start with a fresh session."""
    import shutil
    if os.path.exists(CHROME_USER_DATA_DIR):
        for _ in range(3):
            try:
                shutil.rmtree(CHROME_USER_DATA_DIR)
                break
            except:
                time.sleep(1)

def launch_chrome():
    """Launch Google Chrome with remote debugging and a clean profile."""
    print("[Chrome] Cleaning up stale Chrome processes and profile...")
    kill_dev_chrome()
    clean_user_data_dir()
    
    print(f"[Chrome] Launching Chrome with remote debugging on port {DEBUG_PORT}...")
    chrome_cmd = [
        CHROME_PATH,
        f"--remote-debugging-port={DEBUG_PORT}",
        f"--user-data-dir={CHROME_USER_DATA_DIR}",
        "--no-sandbox",
        "--disable-gpu",
        "--window-size=1280,800"
    ]
    
    proc = subprocess.Popen(chrome_cmd)
    time.sleep(5)  # Allow Chrome time to fully startup
    return proc

def get_driver():
    """Connect Selenium to the remote debugging Chrome instance."""
    options = Options()
    options.add_experimental_option("debuggerAddress", f"127.0.0.1:{DEBUG_PORT}")
    service = Service(executable_path=CHROMEDRIVER_PATH)
    driver = webdriver.Chrome(service=service, options=options)
    return driver

def login_to_router(driver):
    """Log in to 9Router if not already authenticated."""
    print("[9Router] Checking login status...")
    driver.get(f"{ROUTER_URL}/login")
    time.sleep(2)
    
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

def connect_kiro_account(email, password):
    """Run the entire automation flow for a single Kiro account."""
    chrome_proc = None
    driver = None
    try:
        # 1. Launch Chrome
        chrome_proc = launch_chrome()
        
        # 2. Get Driver
        driver = get_driver()
        wait = WebDriverWait(driver, 15)
        
        # 3. Login to Router
        login_to_router(driver)
        
        # 4. Navigate to Kiro Provider page
        print("[9Router] Navigating to Kiro page...")
        driver.get(f"{ROUTER_URL}/dashboard/providers/kiro")
        time.sleep(3)
        
        # 5. Open Credentials form (click Add)
        print("[9Router] Opening connection form...")
        add_btn = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Add') and not(contains(., 'Model'))]"))
        )
        add_btn.click()
        time.sleep(2)
        
        # 6. Click AWS Builder ID button
        print("[9Router] Selecting AWS Builder ID...")
        builder_id_btn = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'AWS Builder ID')]"))
        )
        builder_id_btn.click()
        time.sleep(3)
        
        # 7. Extract AWS SSO Login URL
        print("[9Router] Extracting AWS device login URL...")
        url_element = wait.until(
            EC.presence_of_element_located((By.XPATH, "//code[contains(text(), 'https://view.awsapps.com')]"))
        )
        login_url = url_element.text.strip()
        print(f"[OAuth] AWS SSO URL successfully extracted: {login_url[:80]}...")
        
        # 8. Open AWS SSO page in a new tab
        print("[AWS] Navigating to AWS SSO authorization page...")
        driver.execute_script("window.open('');")
        driver.switch_to.window(driver.window_handles[-1])
        driver.get(login_url)
        time.sleep(8)  # Allow AWS SSO page to fully render
        
        # Accept Cookies if present to prevent covering elements
        try:
            accept_btn = driver.find_element(By.XPATH, "//button[text()='Accept' or contains(@class, 'awsccc-u-btn-primary')]")
            accept_btn.click()
            time.sleep(1)
        except:
            pass
            
        # 9. Enter email robustly
        print(f"[AWS] Submitting email... (URL: {driver.current_url[:80]})", flush=True)
        email_field = wait.until(
            EC.visibility_of_element_located((By.XPATH, "//input[@type='email']"))
        )
        print("[AWS] Email field found.", flush=True)
        email_field.click()
        time.sleep(1)
        
        for attempt in range(3):
            email_field.clear()
            email_field.send_keys(email)
            time.sleep(0.5)
            if email_field.get_attribute("value") == email:
                break
            time.sleep(0.5)
            
        continue_btn = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Continue')]"))
        )
        continue_btn.click()
        time.sleep(8)  # Allow redirect to complete fully
        
        # Check for AWS signup redirect (account has no AWS Builder ID registered)
        curr_url_after_continue = driver.current_url
        print(f"[AWS] URL after Continue: {curr_url_after_continue[:120]}", flush=True)
        if "profile.aws.amazon.com" in curr_url_after_continue and "signup" in curr_url_after_continue:
            raise Exception(f"Account has no AWS Builder ID - redirected to AWS signup page: {curr_url_after_continue}")
        if "profile.aws.amazon.com" in curr_url_after_continue:
            raise Exception(f"Account has no AWS Builder ID - on AWS profile page: {curr_url_after_continue}")
        
        # 10. Perform Google Login (or standard password field if it didn't federate)
        print("[Google] Handling authentication redirect...")
        try:
            g_email_field = WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.XPATH, "//input[@type='email' or @id='identifierId' or @name='identifier']"))
            )
            # Enter Google email
            g_email_field.click()
            time.sleep(1)
            for attempt in range(3):
                g_email_field.clear()
                g_email_field.send_keys(email)
                time.sleep(0.5)
                if g_email_field.get_attribute("value") == email:
                    break
                time.sleep(0.5)
                
            g_next_btn = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//*[@id='identifierNext']//button | //button[contains(., 'Next')]"))
            )
            g_next_btn.click()
            time.sleep(4)
            
            # After clicking Next on Google email, check for deleted/non-existent account
            curr_url_after_g = driver.current_url
            if "deletedaccount" in curr_url_after_g or "Account deleted" in driver.title:
                raise Exception("Google Account has been deleted.")
            if "find your Google Account" in driver.page_source or "Couldn't find your" in driver.page_source:
                raise Exception("Google Account does not exist.")
                
        except Exception as e:
            # Rethrow our specific errors immediately
            if any(kw in str(e) for kw in ["no AWS Builder ID", "deleted", "does not exist"]):
                raise
            # Otherwise may be on AWS password screen - continue
            
        # Enter Password (either Google or AWS password screen)
        print("[Google/AWS] Entering password...")
        try:
            password_field = WebDriverWait(driver, 8).until(
                EC.visibility_of_element_located((By.XPATH, "//input[@type='password' or @name='password']"))
            )
        except Exception as e:
            # Check for error page safely
            try:
                page_text = driver.page_source
                curr_url = driver.current_url
                curr_title = driver.title
            except Exception as read_err:
                page_text = ""
                curr_url = ""
                curr_title = ""
                print(f"[Debug] Could not read page details: {read_err}", flush=True)

            if "find your Google Account" in page_text or "Couldn't find your" in page_text:
                raise Exception("Google Account does not exist.")
            if "deleted" in curr_url or "deletedaccount" in curr_url or "Account deleted" in curr_title or "Account deleted" in page_text:
                raise Exception("Google Account has been deleted.")
            if "rejected" in curr_url or "sign you in" in page_text.lower() or "Couldn't sign you in" in curr_title or "may not be secure" in page_text:
                raise Exception("Google blocked sign-in with security warning ('browser or app not secure').")
            if "profile.aws.amazon.com" in curr_url:
                raise Exception(f"Account has no AWS Builder ID - on AWS profile/signup page: {curr_url}")
            raise Exception(f"Failed or timed out waiting for password field. Error: {e}")

        password_field.clear()
        password_field.send_keys(password)
        
        # Click Next/Sign in
        submit_btn = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//*[@id='passwordNext']//button | //button[contains(., 'Next') or contains(., 'Sign in') or @type='submit']"))
        )
        submit_btn.click()
        time.sleep(10)
        
        # 11. Handle any Google Consent/Scopes (only if prompted)
        try:
            checkboxes = driver.find_elements(By.XPATH, "//input[@type='checkbox']")
            for cb in checkboxes:
                if not cb.is_selected():
                    cb.click()
                    time.sleep(0.5)
            allow_btn = driver.find_element(By.XPATH, "//button[contains(., 'Allow') or contains(., 'Continue') or contains(., 'I agree')]")
            allow_btn.click()
            time.sleep(5)
        except:
            pass
            
        # 12. Click "Allow" on AWS SSO Confirmation Screen
        print("[AWS] Clicking Allow on permission confirmation...")
        allow_btn = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.XPATH, "//button[text()='Allow' or contains(., 'Allow')]"))
        )
        allow_btn.click()
        time.sleep(5)
        
        # 13. Verify connection in SQLite database
        print("[DB] Verifying connection status in SQLite database...")
        is_success = False
        for _ in range(15):
            if db_helper.is_connection_active(email, provider='kiro'):
                is_success = True
                break
            time.sleep(1)
            
        if not is_success:
            conn_info = db_helper.get_connection(email, provider='kiro')
            err_msg = "Unknown error"
            if conn_info and "lastError" in conn_info["data"]:
                err_msg = conn_info["data"]["lastError"]
            raise Exception(f"Account connection failed. Status in database remains inactive. Error: {err_msg}")
            
        print(f"[Success] Account {email} connected to Kiro successfully!")
        
        # Retrieve session info
        session_info = db_helper.get_connection(email, provider='kiro')
        return {
            "success": True,
            "email": email,
            "session_info": session_info,
            "error": None
        }
        
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        if driver:
            try:
                os.makedirs("scratch/html", exist_ok=True)
                with open("scratch/html/kiro_fail_page.html", "w", encoding="utf-8") as f:
                    f.write(driver.page_source)
                print(f"[Debug] Saved failure page source to scratch/html/kiro_fail_page.html. URL: {driver.current_url}, Title: {driver.title}", flush=True)
            except Exception as save_err:
                print(f"[Debug] Failed to save failure page source: {save_err}", flush=True)
        print(f"[Error] Failed to connect Kiro for {email}: {type(e).__name__} - {e}\n{tb}", flush=True)
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

