import os
import urllib.request

url = os.getenv("AIOS_URL", "http://127.0.0.1:8000").rstrip("/")
url += "/api/budget/scan-reminders"
request = urllib.request.Request(url, data=b"{}", method="POST")
with urllib.request.urlopen(request, timeout=30) as response:
    print(response.read().decode("utf-8"))
