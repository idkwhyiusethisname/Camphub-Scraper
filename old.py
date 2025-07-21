import hashlib
from fastapi import BackgroundTasks
from fastapi import FastAPI, Query
import requests
from typing import List, Union
from pydantic import BaseModel
from datetime import datetime
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Query
import re
from urllib.parse import urlparse
import os
import json
from bs4 import BeautifulSoup
from pathlib import Path

SEEN_CONTESTS_FILE = Path("seen_contests.json")

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

seen_contests = load_seen_contests()


app = FastAPI(title="Camphub Scraper API",)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def validate_slug(slug: str):
    return slug

def is_valid_camphub_url(url: str) -> bool:
    parsed = urlparse(url)
    return parsed.netloc.endswith("camphub.in.th")


headers = {
    'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'accept-language': 'en-GB,en-US;q=0.9,en;q=0.8,th;q=0.7',
    'cache-control': 'no-cache',
    'pragma': 'no-cache',
    'priority': 'u=0, i',
    'referer': 'https://www.camphub.in.th/engineer/',
    'sec-ch-ua': '"Not)A;Brand";v="8", "Chromium";v="138", "Google Chrome";v="138"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'document',
    'sec-fetch-mode': 'navigate',
    'sec-fetch-site': 'same-origin',
    'sec-fetch-user': '?1',
    'upgrade-insecure-requests': '1',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
}

class Contest(BaseModel):
    title: str
    description: str
    url: str
    image: str
    status: str
    contest_details: Union[dict, None] = None


def hash_contest(contest: Contest) -> str:
    return hashlib.md5(contest.url.encode("utf-8")).hexdigest()

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

def fetch_contest_details(url: str) -> dict:
    response = requests.get(url, headers=headers)
    soup = BeautifulSoup(response.text, "html.parser")

    def safe_text(selector):
        el = soup.select_one(selector)
        return el.text.strip() if el else ""

    def safe_attr(selector, attr):
        el = soup.select_one(selector)
        return el[attr] if el and el.has_attr(attr) else ""

    return {
        "title": safe_text("h1.entry-title"),
        "categories": [a.text.strip() for a in soup.select(".meta-category a")],
        "closing_in_days": safe_text(".closedate"),
        "event_format": safe_text("h6:contains('รูปแบบกิจกรรม') + h4"),
        "event_date": safe_text("h6:contains('วันที่จัดกิจกรรม') + h4"),
        "application_deadline": safe_text("h6:contains('วันที่รับสมัครวันสุดท้าย') + h4"),
        "max_participants": safe_text("h6:contains('จำนวนที่รับ') + h4"),
        "fee": safe_text("h6:contains('ค่าใช้จ่าย') + h4"),
        "qualifications": safe_text("h6:contains('คุณสมบัติ') + h4"),
        "organizer": safe_text("h6:contains('กิจกรรมนี้จัดโดย') + h4"),
        "poster_image": safe_attr("img[data-src]", "data-src")
    }

def fetch_contests(category_slug: str) -> List[Contest]:
    page = 1
    contests = []
    found_closed = False

    while True:
        url = f"https://www.camphub.in.th/{category_slug.strip('/')}/"
        if page > 1:
            url += f"page/{page}/"

        print(f"Fetching: {url}")

        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            break

        soup = BeautifulSoup(response.text, "html.parser")
        articles = soup.find_all("article", class_="vce-post")

        if not articles:
            break

        for article in articles:
            title_tag = article.find("h2", class_="entry-title").find("a")
            title = title_tag.text.strip()
            post_url = title_tag["href"]
            desc = article.find("div", class_="entry-content").text.strip().replace("\n", " ").replace("  ", " ")
            img_tag = article.find("img")
            image = img_tag["data-src"] if img_tag and img_tag.has_attr("data-src") else ""
            status_tag = article.find("span", class_="closedate")
            status = status_tag.text.strip() if status_tag else "เปิดรับสมัคร"

            if status != "ปิดรับสมัครแล้ว":
                details = fetch_contest_details(post_url)
                contests.append(Contest(
                    title=title,
                    description=desc,
                    url=post_url,
                    image=image,
                    status=status,
                    contest_details=details
                ))
            else:
                found_closed = True

        if found_closed:
            break

        page += 1

    return contests

def fetch_type_contests(category_slug: str) -> List[Contest]:
    page = 1
    contests = []
    found_closed = False

    while True:
        url = f"https://www.camphub.in.th/type/{category_slug.strip('/')}/"
        if page > 1:
            url += f"page/{page}/"

        print(f"Fetching: {url}")

        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            break

        soup = BeautifulSoup(response.text, "html.parser")
        articles = soup.find_all("article", class_="vce-post")

        if not articles:
            break

        for article in articles:
            title_tag = article.find("h2", class_="entry-title").find("a")
            title = title_tag.text.strip()
            post_url = title_tag["href"]
            desc = article.find("div", class_="entry-content").text.strip().replace("\n", " ").replace("  ", " ")
            img_tag = article.find("img")
            image = img_tag["data-src"] if img_tag and img_tag.has_attr("data-src") else ""
            status_tag = article.find("span", class_="closedate")
            status = status_tag.text.strip() if status_tag else "เปิดรับสมัคร"

            if status != "ปิดรับสมัครแล้ว":
                details = fetch_contest_details(post_url)
                contests.append(Contest(
                    title=title,
                    description=desc,
                    url=post_url,
                    image=image,
                    status=status,
                    contest_details=details
                ))
            else:
                found_closed = True

        if found_closed:
            break

        page += 1

    return contests

def fetch_tag_contests(category_slug: str) -> List[Contest]:
    page = 1
    contests = []
    found_closed = False

    while True:
        url = f"https://www.camphub.in.th/tag/{category_slug.strip('/')}/"
        if page > 1:
            url += f"page/{page}/"

        print(f"Fetching: {url}")

        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            break

        soup = BeautifulSoup(response.text, "html.parser")
        articles = soup.find_all("article", class_="vce-post")

        if not articles:
            break

        for article in articles:
            title_tag = article.find("h2", class_="entry-title").find("a")
            title = title_tag.text.strip()
            post_url = title_tag["href"]
            desc = article.find("div", class_="entry-content").text.strip().replace("\n", " ").replace("  ", " ")
            img_tag = article.find("img")
            image = img_tag["data-src"] if img_tag and img_tag.has_attr("data-src") else ""
            status_tag = article.find("span", class_="closedate")
            status = status_tag.text.strip() if status_tag else "เปิดรับสมัคร"

            if status != "ปิดรับสมัครแล้ว":
                details = fetch_contest_details(post_url)
                contests.append(Contest(
                    title=title,
                    description=desc,
                    url=post_url,
                    image=image,
                    status=status,
                    contest_details=details
                ))
            else:
                found_closed = True

        if found_closed:
            break

        page += 1

    return contests

def fetch_tag_private_university() -> List[Contest]:
    page = 1
    contests = []
    found_closed = False

    while True:
        url = f"https://www.camphub.in.th/private-university/"
        if page > 1:
            url += f"page/{page}/"

        print(f"Fetching: {url}")

        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            break

        soup = BeautifulSoup(response.text, "html.parser")
        articles = soup.find_all("article", class_="vce-post")

        if not articles:
            break

        for article in articles:
            title_tag = article.find("h2", class_="entry-title").find("a")
            title = title_tag.text.strip()
            post_url = title_tag["href"]
            desc = article.find("div", class_="entry-content").text.strip().replace("\n", " ").replace("  ", " ")
            img_tag = article.find("img")
            image = img_tag["data-src"] if img_tag and img_tag.has_attr("data-src") else ""
            status_tag = article.find("span", class_="closedate")
            status = status_tag.text.strip() if status_tag else "เปิดรับสมัคร"

            if status != "ปิดรับสมัครแล้ว":
                details = fetch_contest_details(post_url)
                contests.append(Contest(
                    title=title,
                    description=desc,
                    url=post_url,
                    image=image,
                    status=status,
                    contest_details=details
                ))
            else:
                found_closed = True

        if found_closed:
            break

        page += 1

    return contests

def fetch_medical_health_contests(contest_name: str) -> List[Contest]:
    page = 1
    contests = []
    found_closed = False

    while True:
        url = f"https://www.camphub.in.th/medical-health/{contest_name}/"
        if page > 1:
            url += f"page/{page}/"

        print(f"Fetching: {url}")

        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            break

        soup = BeautifulSoup(response.text, "html.parser")
        articles = soup.find_all("article", class_="vce-post")

        if not articles:
            break

        for article in articles:
            title_tag = article.find("h2", class_="entry-title").find("a")
            title = title_tag.text.strip()
            post_url = title_tag["href"]
            desc = article.find("div", class_="entry-content").text.strip().replace("\n", " ").replace("  ", " ")
            img_tag = article.find("img")
            image = img_tag["data-src"] if img_tag and img_tag.has_attr("data-src") else ""
            status_tag = article.find("span", class_="closedate")
            status = status_tag.text.strip() if status_tag else "เปิดรับสมัคร"

            if status != "ปิดรับสมัครแล้ว":
                details = fetch_contest_details(post_url)
                contests.append(Contest(
                    title=title,
                    description=desc,
                    url=post_url,
                    image=image,
                    status=status,
                    contest_details=details
                ))
            else:
                found_closed = True

        if found_closed:
            break

        page += 1

    return contests

def fetch_contests_cornjob(category_slug: str) -> List[Contest]:
    page = 1
    contests = []
    found_closed = False

    while True:
        url = f"https://www.camphub.in.th/{category_slug.strip('/')}/"
        if page > 1:
            url += f"page/{page}/"

        print(f"Fetching: {url}")

        response = requests.get(url, headers=headers)
        if response.status_code != 200:
            break

        soup = BeautifulSoup(response.text, "html.parser")
        articles = soup.find_all("article", class_="vce-post")

        if not articles:
            break

        for article in articles:
            title_tag = article.find("h2", class_="entry-title").find("a")
            title = title_tag.text.strip()
            post_url = title_tag["href"]
            desc = article.find("div", class_="entry-content").text.strip().replace("\n", " ").replace("  ", " ")
            img_tag = article.find("img")
            image = img_tag["data-src"] if img_tag and img_tag.has_attr("data-src") else ""
            status_tag = article.find("span", class_="closedate")
            status = status_tag.text.strip() if status_tag else "เปิดรับสมัคร"

            if status != "ปิดรับสมัครแล้ว":
                contests.append(Contest(
                    title=title,
                    description=desc,
                    url=post_url,
                    image=image,
                    status=status
                ))
            else:
                found_closed = True

        if found_closed:
            break

        page += 1

    return contests


@app.get("/contests")
def get_contests(category: str = Query("contest", description="สำหรับค้นแบบทั่วไป")) -> dict:
    category = validate_slug(category)
    try:
        fetch_data = fetch_contests(category)
        return {
            "status": "success",
            "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "category": category,
            "total": len(fetch_data),
            "data": fetch_data
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "category": category,
            "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

@app.get("/type/contests")
def get_contests_type(category: str = Query("tutor", description="สำหรับค้นแบบ type")) -> dict:
    try:
        fetch_data = fetch_type_contests(category)
        return {
            "status": "success",
            "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "category": category,
            "total": len(fetch_data),
            "data": fetch_data
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "category": category,
            "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

@app.get("/tag/contests")
def get_contests_tag(category: str = Query("khon-kaen-university", description="สำหรับค้นตามมหาวิทยาลัย")) -> dict:
    try:
        fetch_data = fetch_tag_contests(category)
        return {
            "status": "success",
            "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "category": category,
            "total": len(fetch_data),
            "data": fetch_data
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "category": category,
            "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
@app.get("/tag/private-university")
def get_contests_tag_private() -> dict:
    try:
        fetch_data = fetch_tag_private_university()
        return {
            "status": "success",
            "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "category": "private-university",
            "total": len(fetch_data),
            "data": fetch_data
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "category": "private-university",
            "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
@app.get("/medical-health/")
def get_medical_health(category: str = Query("vet", description="สำหรับค้นค่ายเกี่ยวกับแพทย์หมอหมาปูเปา")) -> dict:
    category = validate_slug(category)
    try:
        fetch_data = fetch_medical_health_contests(category)
        return {
            "status": "success",
            "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "category": category,
            "total": len(fetch_data),
            "data": fetch_data
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "category": category,
            "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    
@app.get("/contest/details")
def get_contest_details(url: str = Query(..., description="URL of the contest detail page")) -> dict:
    if not is_valid_camphub_url(url):
        return {
            "status": "error",
            "message": "Invalid Camphub URL",
            "url": url,
            "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
    else:
        try:
            data = fetch_contest_details(url)
            return {
                "status": "success",
                "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "url": url,
                "data": data
            }
        except Exception as e:
            return {
                "status": "error",
                "message": str(e),
                "url": url,
                "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

@app.get("/cron/notify-discord")
def cron_notify_contest_discord(
    category: str = Query("contest", description="Category slug Cornjob"),
    discord_webhook: str = Query(..., description="Discord webhook URL")
) -> dict:
    category = validate_slug(category)
    try:
        seen_contests = load_seen_contests()
        contests = fetch_contests_cornjob(category)
        new_contests = []
        updated_seen = seen_contests.copy()
        notify_results = []

        for contest in contests:
            contest_id = hash_contest(contest)
            if contest_id not in seen_contests:
                updated_seen.add(contest_id)
                new_contests.append(contest)
                
                contest_detail = fetch_contest_details(contest.url)
                contest.contest_details = contest_detail

                success = send_discord_notification(contest, discord_webhook)
                notify_results.append({
                    "title": contest.title,
                    "success": success
                })

        if new_contests:
            save_seen_contests(updated_seen)
            seen_contests.update(updated_seen)

        return {
            "status": "success",
            "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "new_contests_count": len(new_contests),
            "notified": notify_results,
        }

    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "category": category,
            "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
