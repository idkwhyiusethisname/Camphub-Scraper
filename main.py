from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Union
from datetime import datetime
from urllib.parse import urlparse
from bs4 import BeautifulSoup
from pathlib import Path
import warnings
import requests
import hashlib
import json
import os
import uvicorn

warnings.filterwarnings("ignore")
app = FastAPI(title="Camphub Scraper API")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

HEADERS = { ## For unflagging the request
    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'accept-language': 'en-GB,en-US;q=0.9,en;q=0.8,th;q=0.7',
    'cache-control': 'no-cache',
    'pragma': 'no-cache',
    'priority': 'u=0, i',
    'referer': 'https://www.camphub.in.th/',
    'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'iframe',
    'sec-fetch-mode': 'navigate',
    'sec-fetch-site': 'cross-site',
    'sec-fetch-storage-access': 'active',
    'upgrade-insecure-requests': '1',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
}


SEEN_CONTESTS_FILE = Path("seen_contests.json")


# ============================
# MODELS
# ============================

class Contest(BaseModel):
    title: str
    description: str
    url: str
    image: str
    status: str
    contest_details: Union[dict, None] = None
    
    
# ============================
# Alert
# ============================

def send_discord_notification(contest: Contest, discord_webhook: str):
    data = {
        "embeds": [
            {
                "title": contest.title,
                "description": contest.description[:200] + ("..." if len(contest.description) > 200 else ""),
                "url": contest.url,
                "thumbnail": {"url": contest.image},
                "fields": [
                    {"name": "สถานะ", "value": contest.status, "inline": True},
                    {"name": "วันปิดรับสมัคร", "value": contest.contest_details.get("application_deadline", "ไม่ระบุ"), "inline": True},
                    {"name": "จำนวนที่รับ", "value": contest.contest_details.get("max_participants", "ไม่ระบุ"), "inline": True},
                    {"name": "ค่าใช้จ่าย", "value": contest.contest_details.get("fee", "ไม่ระบุ"), "inline": True},
                    {"name": "ผู้จัดงาน", "value": contest.contest_details.get("organizer", "ไม่ระบุ"), "inline": True},
                    {"name": "รูปแบบกิจกรรม", "value": contest.contest_details.get("event_format", "ไม่ระบุ"), "inline": True},
                    {"name": "วันที่จัดกิจกรรม", "value": contest.contest_details.get("event_date", "ไม่ระบุ"), "inline": True},
                ],
                "footer": {"text": "ส่งจาก Camphub Scraper API"},
                "timestamp": datetime.utcnow().isoformat()
            }
        ]
    }

    try:
        response = requests.post(discord_webhook, json=data)
        
        if response.status_code != 204:
            return False
        else:
            return True
    
    except Exception as e:
        return False

# ============================
# UTILITIES
# ============================

def hash_contest(contest: Contest) -> str:
    return hashlib.md5(contest.url.encode("utf-8")).hexdigest()

def load_seen_contests() -> set:
    if SEEN_CONTESTS_FILE.exists():
        with open(SEEN_CONTESTS_FILE, "r", encoding="utf-8") as f:
            try:
                return set(json.load(f))
            except json.JSONDecodeError:
                return set()
    return set()

def save_seen_contests(seen: set):
    with open(SEEN_CONTESTS_FILE, "w", encoding="utf-8") as f:
        json.dump(list(seen), f, ensure_ascii=False, indent=2)

def is_valid_camphub_url(url: str) -> bool:
    return urlparse(url).netloc.endswith("camphub.in.th")


# ============================
# SCRAPER
# ============================

def fetch_contest_details(url: str) -> dict:
    res = requests.get(url, headers=HEADERS)
    soup = BeautifulSoup(res.text, "html.parser")

    def sel_text(sel): el = soup.select_one(sel); return el.text.strip() if el else ""
    def sel_attr(sel, attr): el = soup.select_one(sel); return el[attr] if el and el.has_attr(attr) else ""

    return {
        "title": sel_text("h1.entry-title"),
        "categories": [a.text.strip() for a in soup.select(".meta-category a")],
        "closing_in_days": sel_text(".closedate"),
        "event_format": sel_text("h6:contains('รูปแบบกิจกรรม') + h4"),
        "event_date": sel_text("h6:contains('วันที่จัดกิจกรรม') + h4"),
        "application_deadline": sel_text("h6:contains('วันที่รับสมัครวันสุดท้าย') + h4"),
        "max_participants": sel_text("h6:contains('จำนวนที่รับ') + h4"),
        "fee": sel_text("h6:contains('ค่าใช้จ่าย') + h4"),
        "qualifications": sel_text("h6:contains('คุณสมบัติ') + h4"),
        "organizer": sel_text("h6:contains('กิจกรรมนี้จัดโดย') + h4"),
        "poster_image": sel_attr("img[data-src]", "data-src")
    }

def scrape_contests(url_generator: callable, stop_on_closed=True) -> List[Contest]:
    contests = []
    page = 1
    while True:
        url = url_generator(page)
        print(f"[Scraping] {url}")
        r = requests.get(url, headers=HEADERS)
        if r.status_code != 200:
            break

        soup = BeautifulSoup(r.text, "html.parser")
        articles = soup.find_all("article", class_="vce-post")
        if not articles:
            break

        for a in articles:
            title_tag = a.find("h2", class_="entry-title").find("a")
            desc = a.find("div", class_="entry-content").text.strip().replace("\n", " ")
            img = a.find("img")
            image = img["data-src"] if img and img.has_attr("data-src") else ""
            status = a.find("span", class_="closedate")
            status_text = status.text.strip() if status else "เปิดรับสมัคร"

            if stop_on_closed and status_text == "ปิดรับสมัครแล้ว":
                return contests

            contest = Contest(
                title=title_tag.text.strip(),
                description=desc,
                url=title_tag["href"],
                image=image,
                status=status_text,
                contest_details=fetch_contest_details(title_tag["href"])
            )
            contests.append(contest)

        page += 1
    return contests


# ============================
# API ROUTES
# ============================

@app.get("/contests")
def get_contests(category: str = Query("contest"), type: str = Query("default")):
    try:
        def make_url(page):
            base = f"https://www.camphub.in.th/"
            if type == "type":
                return f"{base}type/{category}/" + (f"page/{page}/" if page > 1 else "")
            elif type == "tag":
                return f"{base}tag/{category}/" + (f"page/{page}/" if page > 1 else "")
            elif type == "medical":
                return f"{base}medical-health/{category}/" + (f"page/{page}/" if page > 1 else "")
            elif type == "private":
                return f"{base}private-university/" + (f"page/{page}/" if page > 1 else "")
            else:
                return f"{base}{category}/" + (f"page/{page}/" if page > 1 else "")

        contests = scrape_contests(make_url)
        return {
            "status": "success",
            "category": category,
            "type": type,
            "total": len(contests),
            "datetime": datetime.now().isoformat(),
            "data": contests
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/contest/details")
def get_details(url: str = Query(...)):
    if not is_valid_camphub_url(url):
        return {"status": "error", "message": "Invalid Camphub URL"}
    try:
        data = fetch_contest_details(url)
        return {"status": "success", "url": url, "data": data}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/cron/notify")
def cron_notify(category: str = Query("contest"), webhook: str = Query(...)):
    try:
        seen = load_seen_contests()
        new_seen = seen.copy()

        def make_url(page): return f"https://www.camphub.in.th/{category}/" + (f"page/{page}/" if page > 1 else "")
        contests = scrape_contests(make_url)

        new_contests = []
        for c in contests:
            cid = hash_contest(c)
            if cid not in seen:
                new_seen.add(cid)
                new_contests.append(c)

        status_send = []
        for c in new_contests:
            if send_discord_notification(c, webhook):
                status_send.append({"title": c.title, "status": "sent"})
            else:
                status_send.append({"title": c.title, "status": "failed"})

        if new_contests:
            save_seen_contests(new_seen)

        return {
            "status": "success",
            "messsage": "Notifications sent",
            "new_count": len(new_contests),
            "datetime": datetime.now().isoformat(),
            "notifications": status_send
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
    
# === Run the app with Uvicorn ===
if __name__ == "__main__":
    uvicorn.run("main:app", port=1372, reload=True)
