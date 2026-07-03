Stop-Process -Name 'chromedriver' -Force -ErrorAction SilentlyContinue
Stop-Process -Name 'python3' -Force -ErrorAction SilentlyContinue
Stop-Process -Name 'python' -Force -ErrorAction SilentlyContinue
Get-CimInstance Win32_Process -Filter "Name = 'chrome.exe'" | Where-Object { $_.CommandLine -like '*chrome_dev_profile*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Write-Host "All processes killed."
