import re
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "MurmurationWatchUK/1.0 (Kent & Sussex Regional Pipeline)"
}

url = "https://sussexwildlifetrust.org.uk/news/rye-harbour-nature-reserve-sightings-in-october-2026/"
res = requests.get(url, headers=HEADERS, timeout=15)
soup = BeautifulSoup(res.text, "html.parser")
text = " ".join(soup.get_text(" ").split())
hits = [m.start() for m in re.finditer(r"starling", text, re.IGNORECASE)]
print("Rye Harbour Oct 2026 Status:", res.status_code, "| Starling hits:", len(hits))
for idx in hits:
    print("  ->", text[max(0, idx - 80): min(len(text), idx + 160)])