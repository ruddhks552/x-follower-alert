import json
import requests
import os
from bs4 import BeautifulSoup
from datetime import datetime, timezone

TG_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

NITTER_INSTANCES = [
    "https://nitter.net",
    "https://nitter.privacydev.net",
    "https://nitter.poast.org",
    "https://nitter.1d4.us",
]

def get_username(url):
    return url.rstrip("/").split("/")[-1]

def get_followers(username):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    for instance in NITTER_INSTANCES:
        try:
            r = requests.get(f"{instance}/{username}", headers=headers, timeout=10)
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.text, "html.parser")
            for stat in soup.select(".profile-stat"):
                if "followers" in stat.get_text().lower():
                    num = stat.select_one(".profile-stat-num")
                    if not num:
                        continue
                    text = num.get_text(strip=True).replace(",", "")
                    if "M" in text:
                        return int(float(text.replace("M", "")) * 1_000_000)
                    elif "K" in text:
                        return int(float(text.replace("K", "")) * 1_000)
                    return int(text)
        except Exception as e:
            print(f"  [{instance}] failed: {e}")
            continue
    return None

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    r = requests.post(url, json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"})
    return r.ok

with open("targets.json") as f:
    targets = json.load(f)

now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

for t in targets:
    username = get_username(t["url"])
    target = t["target_followers"]
    label = t.get("label", f"@{username}")
    print(f"Checking @{username}...")
    count = get_followers(username)
    if count is None:
        print(f"  -> crawl failed")
        continue
    pct = count / target * 100
    print(f"  -> {count:,} / {target:,} ({pct:.2f}%)")
    if count >= target:
        msg = (
            f"\U0001F3AF <b>목표 달성!</b>\n\n"
            f"<b>{label}</b>\n\n"
            f"@{username} 현재 팔로워: <b>{count:,}명</b>\n"
            f"목표: {target:,}명\n"
            f"시각: {now}"
        )
        ok = send_telegram(msg)
        print(f"  -> ALERT SENT (ok={ok})")
    else:
        print(f"  -> not reached ({pct:.1f}%)")
