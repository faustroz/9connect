import os

# Chrome Configuration
CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
# Cached chrome driver matching chrome v149
CHROMEDRIVER_PATH = r"C:\Users\Asus\.cache\selenium\chromedriver\win64\150.0.7871.124\chromedriver.exe"
CHROME_USER_DATA_DIR = r"C:\Users\Asus\AppData\Local\Temp\chrome_dev_profile"
DEBUG_PORTS = [9222]

# 9Router Configuration
ROUTER_URL = "http://localhost:20128"
ROUTER_PASSWORD = os.environ.get("ROUTER_PASSWORD", "")

# Database Configuration
DB_PATH = r"C:\Users\Asus\AppData\Roaming\9router\db\data.sqlite"

# Output Configuration
RESULTS_FILE = "results.json"
