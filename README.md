# 9Router Provider Connection Automation

Selenium automation for connecting multiple accounts to 9Router providers, then reading connection status and session data from 9Router's local SQLite database.

Supported flows:

- `main.py`: Antigravity provider with Google OAuth.
- `main_kiro.py`: Kiro provider with AWS Builder ID / AWS SSO.

## Features

- Launches Chrome with remote debugging so OAuth flows run in a normal browser session.
- Logs in to local 9Router at `http://localhost:20128`.
- Checks 9Router's SQLite database before browser automation and skips accounts already marked active.
- Deletes stale or broken provider connections before retrying.
- Saves progress after each account so interrupted runs can resume.
- Keeps browser dumps and one-off probes under `scratch/`.

## Setup

1. Install Python dependency:

   ```powershell
   py -3.13 -m pip install selenium
   ```

2. Create or update `accounts.json`:

   ```json
   [
     {
       "email": "your_account_1@gmail.com",
       "password": "your_password_1"
     },
     {
       "email": "your_account_2@gmail.com",
       "password": "your_password_2"
     }
   ]
   ```

3. Check `config.py`:

   - `CHROME_PATH`: Chrome executable path.
   - `CHROMEDRIVER_PATH`: matching ChromeDriver path.
   - `CHROME_USER_DATA_DIR`: temporary Chrome profile used by automation.
   - `ROUTER_URL`: local 9Router URL.
   - `ROUTER_PASSWORD`: local 9Router password.
   - `DB_PATH`: 9Router SQLite database path.
   - `RESULTS_FILE`: Antigravity output file.

## Run

Start 9Router first, then run one provider flow.

Antigravity:

```powershell
py -3.13 main.py
```

Kiro:

```powershell
py -3.13 main_kiro.py
```

## Outputs

- `results.json`: Antigravity run results.
- `results_kiro.json`: Kiro run results.
- `scratch/html/`: captured browser pages for debugging.
- `scratch/text/`: extracted page text and details.
- `scratch/scripts/`: temporary probe scripts used during debugging.

`accounts.json`, `results*.json`, `scratch/`, and Python cache files are ignored by Git.

## Flow

1. Load accounts from `accounts.json`.
2. Check existing provider connection in SQLite.
3. Skip active accounts and record current session data.
4. Delete stale inactive connections before reconnecting.
5. Launch Chrome with remote debugging.
6. Complete the provider OAuth or SSO flow.
7. Verify `testStatus == "active"` in SQLite.
8. Save result JSON and continue to the next account.

## Notes

- This project expects local 9Router to be running and unlocked.
- ChromeDriver must match installed Chrome.
- Automation can fail when Google or AWS shows extra security challenges, missing accounts, deleted accounts, or accounts without AWS Builder ID.
- The scripts read and delete records from the configured 9Router database. Confirm `DB_PATH` before running against important data.