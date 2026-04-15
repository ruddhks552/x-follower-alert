import json
import requests
import os
from bs4 import BeautifulSoup
from datetime import datetime, timezone

TG_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

NITTER_INSTANCES = [
    "https://nitter.poast.org",
    "https://nitter.cz",
    "https://nitter.lucahammer.com",
    "https://nitter.esmailelbob.xyz",
    "https://nitter.rawbit.ninja",
]

# CZ 새 회사 설립 관련 키워드
CZ_COMPANY_KEYWORDS = [
    "new company", "new firm", "founded", "establishing", "launch",
    "incorporated", "registered", "new venture", "startup", "새 회사",
    "설립", "창업", "announce", "official"
]

# 주요 뉴스 매체
NEWS_SOURCES = ["bloomberg", "reuters", "coindesk", "wsj", "wall street journal"]

def get_username(url):
    return url.rstrip("/").split("/")[-1]

def get_followers(username):
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
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

def get_cz_recent_tweets():
    """CZ 최근 트윗 가져오기"""
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    for instance in NITTER_INSTANCES:
        try:
            r = requests.get(f"{instance}/cz_binance", headers=headers, timeout=10)
            if r.status_code != 200:
                continue
            soup = BeautifulSoup(r.text, "html.parser")
            tweets = []
            for tweet in soup.select(".tweet-content")[:10]:
                tweets.append(tweet.get_text(strip=True))
            if tweets:
                return tweets
        except Exception as e:
            print(f"  [{instance}] tweet fetch failed: {e}")
            continue
    return []

def check_cz_company_news():
    """Google News에서 CZ 새 회사 관련 뉴스 체크"""
    query = "CZ Binance new company 2026"
    url = f"https://news.google.com/rss/search?q={query.replace(' ', '+')}&hl=en&gl=US&ceid=US:en"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        r = requests.get(url, headers=headers, timeout=10)
        if r.status_code != 200:
            return []
        soup = BeautifulSoup(r.content, "xml")
        results = []
        for item in soup.find_all("item")[:10]:
            title = item.find("title")
            source = item.find("source")
            link = item.find("link")
            if title and source:
                results.append({
                    "title": title.get_text(),
                    "source": source.get_text().lower(),
                    "link": link.get_text() if link else ""
                })
        return results
    except Exception as e:
        print(f"  Google News fetch failed: {e}")
        return []

def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    r = requests.post(url, json={"chat_id": CHAT_ID, "text": msg, "parse_mode": "HTML"})
    return r.ok

now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

# ─────────────────────────────────────────
# 1. 팔로워 수 모니터링
# ─────────────────────────────────────────
with open("targets.json") as f:
    targets = json.load(f)

for t in targets:
    username = get_username(t["url"])
    target = t["target_followers"]
    label = t.get("label", f"@{username}")
    print(f"[Followers] Checking @{username}...")
    count = get_followers(username)
    if count is None:
        print(f"  -> crawl failed")
        continue
    pct = count / target * 100
    print(f"  -> {count:,} / {target:,} ({pct:.2f}%)")
    if count >= target:
        msg = (
            f"\U0001F3AF <b>팔로워 목표 달성!</b>\n\n"
            f"<b>{label}</b>\n\n"
            f"@{username} 현재 팔로워: <b>{count:,}명</b>\n"
            f"목표: {target:,}명 \u2705\n"
            f"시각: {now}"
        )
        ok = send_telegram(msg)
        print(f"  -> ALERT SENT (ok={ok})")
    else:
        print(f"  -> not reached ({pct:.1f}%)")

# ─────────────────────────────────────────
# 2. CZ 새 회사 설립 트윗 감지
# ─────────────────────────────────────────
print("\n[Tweet] Checking @cz_binance recent tweets...")
tweets = get_cz_recent_tweets()
if tweets:
    for tweet in tweets:
        tweet_lower = tweet.lower()
        matched = [kw for kw in CZ_COMPANY_KEYWORDS if kw in tweet_lower]
        if matched:
            print(f"  -> KEYWORD MATCH: {matched}")
            msg = (
                f"\U0001F6A8 <b>CZ 새 회사 관련 트윗 감지!</b>\n\n"
                f"<b>매칭 키워드:</b> {', '.join(matched)}\n\n"
                f"<b>트윗 내용:</b>\n{tweet[:500]}\n\n"
                f"\U0001F517 https://x.com/cz_binance\n"
                f"시각: {now}"
            )
            send_telegram(msg)
            print(f"  -> TWEET ALERT SENT")
            break
    else:
        print(f"  -> {len(tweets)} tweets checked, no keyword match")
else:
    print("  -> failed to fetch tweets")

# ─────────────────────────────────────────
# 3. 주요 뉴스 매체 보도 감지
# ─────────────────────────────────────────
print("\n[News] Checking Google News for CZ company announcements...")
news_items = check_cz_company_news()
if news_items:
    matched_news = [
        n for n in news_items
        if any(src in n["source"] for src in NEWS_SOURCES)
        and any(kw in n["title"].lower() for kw in ["company", "firm", "launch", "founded", "establish", "venture"])
    ]
    if matched_news:
        for n in matched_news[:3]:
            print(f"  -> NEWS MATCH: {n['source']} - {n['title']}")
            msg = (
                f"\U0001F4F0 <b>CZ 새 회사 관련 뉴스 감지!</b>\n\n"
                f"<b>출처:</b> {n['source']}\n"
                f"<b>제목:</b> {n['title']}\n\n"
                f"\U0001F517 {n['link']}\n"
                f"시각: {now}"
            )
            send_telegram(msg)
            print(f"  -> NEWS ALERT SENT")
    else:
        print(f"  -> {len(news_items)} articles checked, no major source match")
else:
    print("  -> no news found")

print("\nDone.")
