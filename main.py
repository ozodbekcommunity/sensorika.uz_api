# main.py

import requests
from bs4 import BeautifulSoup
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from typing import List, Dict, Any, Optional
from pathlib import Path

# --- Ilovalarni o'rnatish uchun ---
# pip install fastapi uvicorn requests beautifulsoup4 lxml

app = FastAPI(
    title="Sensorika.uz Scraper API",
    description="Sensorika.uz saytidan o'quvchilar, yangiliklar va frilanserlar haqida ma'lumotlarni olish uchun API.",
    version="1.0.0",
)

# Static files va templates sozlamasi
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

BASE_URL = "https://sensorika.uz"

# --- Helper funksiyalar ---

def get_soup(url: str ) -> BeautifulSoup:
    """Berilgan URL manzilidan HTMLni olib, BeautifulSoup obyektini qaytaradi."""
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        response.raise_for_status()
        return BeautifulSoup(response.content, "lxml")
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=503, detail=f"Saytga ulanishda xatolik: {e}")

def parse_student_card(item) -> Dict[str, Any]:
    """O'quvchi kartochkasini (short-item) tahlil qiladi."""
    link_tag = item.find("a", class_="short-link")
    img_tag = item.find("img")
    title_tag = item.find("div", class_="short-title")
    desc_tag = item.find("div", class_="short-desc")
    
    url = link_tag['href'] if link_tag else None
    
    # URL manzilidan ID ni ajratib olish
    student_id = None
    if url:
        try:
            student_id = int(url.split('/')[-1].split('-')[0])
        except (ValueError, IndexError):
            student_id = None

    return {
        "id": student_id,
        "name": title_tag.text.strip() if title_tag else "Noma'lum",
        "description": desc_tag.text.strip() if desc_tag else "Tavsif mavjud emas",
        "url": url,
        "image_url": BASE_URL + img_tag['src'] if img_tag and img_tag.get('src') else None,
    }

# --- API Endpoints ---

@app.get("/", tags=["Bosh sahifa"])
def read_root():
    """API haqida umumiy ma'lumot."""
    return {
        "message": "Sensorika.uz sayti uchun ma'lumotlarni yig'uvchi API",
        "docs_url": "/docs"
    }

@app.get("/students", tags=["O'quvchilar"], summary="Barcha o'quvchilar ro'yxatini olish")
def get_all_students() -> List[Dict[str, Any]]:
    """
    Bosh sahifadagi "TOP O'QUVCHILARIMIZ" va "BITIRUVCHILARIMIZ" bo'limlaridan
    barcha o'quvchilarning ro'yxatini oladi.
    """
    soup = get_soup(BASE_URL)
    students = []
    
    # "short-items" classiga ega bo'lgan barcha bo'limlarni topish
    student_sections = soup.find_all("div", class_="short-items")
    
    for section in student_sections:
        student_items = section.find_all("div", class_="short-item")
        for item in student_items:
            students.append(parse_student_card(item))
            
    if not students:
        raise HTTPException(status_code=404, detail="Hech qanday o'quvchi topilmadi.")
        
    return students

@app.get("/students/{student_id}", tags=["O'quvchilar"], summary="ID bo'yicha o'quvchi ma'lumotlarini olish")
def get_student_by_id(student_id: int, student_url: str) -> Dict[str, Any]:
    """
    Berilgan ID va URL orqali o'quvchining shaxsiy sahifasidan to'liq ma'lumotlarni oladi.
    
    Masalan: `student_id=2212`, `student_url=https://sensorika.uz/students/kompyuter-savodxonligi/2212-sevinova-jasmina.html`
    """
    soup = get_soup(student_url )
    
    full_article = soup.find("article", class_="full")
    if not full_article:
        raise HTTPException(status_code=404, detail=f"ID {student_id} ga ega o'quvchi topilmadi.")

    name = full_article.find("h1").text.strip() if full_article.find("h1") else "Noma'lum"
    
    info_items = full_article.find_all("div", recursive=False)
    
    details = {}
    for item in info_items:
        key_tag = item.find("div")
        value_tag = item.find("span")
        if key_tag and value_tag:
            key = key_tag.text.strip().lower().replace("'", "").replace(" ", "_")
            details[key] = value_tag.text.strip()

    images = [BASE_URL + img['src'] for img in full_article.find("div", class_="fdesc").find_all("img")]
    
    freelance_platform_tag = full_article.find("div", class_="fmessage")
    freelance_platform = None
    if freelance_platform_tag and freelance_platform_tag.find("a"):
        freelance_platform = freelance_platform_tag.find("a")['href']

    return {
        "id": student_id,
        "name": name,
        "details": details,
        "freelance_platform": freelance_platform,
        "images": images,
        "source_url": student_url
    }

@app.get("/news", tags=["Yangiliklar"], summary="Barcha yangiliklar ro'yxatini olish")
def get_all_news() -> List[Dict[str, Any]]:
    """Bosh sahifadagi yangiliklar ro'yxatini oladi."""
    soup = get_soup(BASE_URL)
    news_list = []
    
    news_section = soup.find("div", class_="sect-title", string="YANGILIKLAR")
    if not news_section:
        raise HTTPException(status_code=404, detail="Yangiliklar bo'limi topilmadi.")
        
    news_items = news_section.find_parent("div", class_="sect-col").find_all("a", class_="top-item")

    for item in news_items:
        title_tag = item.find("div", class_="top-title")
        img_tag = item.find("img")
        
        url = item['href']
        news_id = None
        try:
            news_id = int(url.split('/')[-1].split('-')[0])
        except (ValueError, IndexError):
            news_id = None

        news_list.append({
            "id": news_id,
            "title": title_tag.text.strip() if title_tag else "Sarlavha mavjud emas",
            "url": url,
            "image_url": BASE_URL + img_tag['src'] if img_tag and img_tag.get('src') else None,
        })
        
    if not news_list:
        raise HTTPException(status_code=404, detail="Hech qanday yangilik topilmadi.")
        
    return news_list

@app.get("/news/{news_id}", tags=["Yangiliklar"], summary="ID bo'yicha yangilik ma'lumotlarini olish")
def get_news_by_id(news_id: int, news_url: str) -> Dict[str, Any]:
    """
    Berilgan ID va URL orqali yangilik sahifasidan to'liq ma'lumotlarni oladi.
    
    Masalan: `news_id=5049`, `news_url=https://sensorika.uz/yangiliklar/5049-manaviy-marifiy-tayyorgarlik-mashguloti.html`
    """
    soup = get_soup(news_url )
    
    article = soup.find("article", class_="full")
    if not article:
        raise HTTPException(status_code=404, detail=f"ID {news_id} ga ega yangilik topilmadi.")
        
    title = article.find("h1").text.strip() if article.find("h1") else "Sarlavha mavjud emas"
    content_div = article.find("div", class_="fdesc")
    
    content_text = ""
    if content_div:
        # Faqat matnli qismlarni olish
        text_parts = [p.text.strip() for p in content_div.find_all("div", recursive=False)]
        content_text = "\n".join(filter(None, text_parts))

    images = [BASE_URL + img['src'] for img in content_div.find_all("img")] if content_div else []
    
    return {
        "id": news_id,
        "title": title,
        "content": content_text,
        "images": images,
        "source_url": news_url
    }

@app.get("/freelancers", tags=["Frilanserlar"], summary="Frilanserlar ro'yxatini olish")
def get_freelancers() -> List[Dict[str, Any]]:
    """Bosh sahifadagi "BIZ FRILANSINGDA DAROMAD QILYAPMIZ!" bo'limidan o'quvchilar ro'yxatini oladi."""
    soup = get_soup(BASE_URL)
    freelancers = []
    
    freelancer_header = soup.find(lambda tag: tag.name == 'div' and "BIZ FRILANSINGDA DAROMAD QILYAPMIZ!" in tag.text)
    
    if not freelancer_header:
        raise HTTPException(status_code=404, detail="Frilanserlar bo'limi topilmadi.")
        
    freelancer_section = freelancer_header.find_parent("div", class_="sect")
    freelancer_items = freelancer_section.find_all("div", class_="short-item")
    
    for item in freelancer_items:
        freelancers.append(parse_student_card(item))
        
    if not freelancers:
        raise HTTPException(status_code=404, detail="Hech qanday frilanser topilmadi.")
        
    return freelancers

# --- Web Sahifalar (HTML) ---

@app.get("/web", response_class=HTMLResponse, tags=["Web Sahifalar"])
async def web_home(request: Request):
    """Bosh sahifa - barcha bo'limlarni ko'rsatadi."""
    try:
        students = get_all_students()
        news = get_all_news()
        freelancers = get_freelancers()
        return templates.TemplateResponse("index.html", {
            "request": request,
            "students": students[:6],  # Faqat 6 ta ko'rsatish
            "news": news[:6],
            "freelancers": freelancers[:6]
        })
    except HTTPException:
        return templates.TemplateResponse("index.html", {
            "request": request,
            "students": [],
            "news": [],
            "freelancers": [],
            "error": "Ma'lumotlarni yuklashda xatolik yuz berdi."
        })

@app.get("/web/students", response_class=HTMLResponse, tags=["Web Sahifalar"])
async def web_students(request: Request):
    """Barcha o'quvchilar ro'yxati."""
    try:
        students = get_all_students()
        return templates.TemplateResponse("students.html", {
            "request": request,
            "students": students
        })
    except HTTPException as e:
        return templates.TemplateResponse("students.html", {
            "request": request,
            "students": [],
            "error": str(e.detail)
        })

@app.get("/web/students/{student_id}", response_class=HTMLResponse, tags=["Web Sahifalar"])
async def web_student_detail(request: Request, student_id: int, student_url: str):
    """O'quvchining batafsil ma'lumotlari."""
    try:
        student = get_student_by_id(student_id, student_url)
        return templates.TemplateResponse("student_detail.html", {
            "request": request,
            "student": student
        })
    except HTTPException as e:
        return templates.TemplateResponse("student_detail.html", {
            "request": request,
            "student": None,
            "error": str(e.detail)
        })

@app.get("/web/news", response_class=HTMLResponse, tags=["Web Sahifalar"])
async def web_news(request: Request):
    """Barcha yangiliklar ro'yxati."""
    try:
        news = get_all_news()
        return templates.TemplateResponse("news.html", {
            "request": request,
            "news": news
        })
    except HTTPException as e:
        return templates.TemplateResponse("news.html", {
            "request": request,
            "news": [],
            "error": str(e.detail)
        })

@app.get("/web/news/{news_id}", response_class=HTMLResponse, tags=["Web Sahifalar"])
async def web_news_detail(request: Request, news_id: int, news_url: str):
    """Yangilikning batafsil ma'lumotlari."""
    try:
        news_item = get_news_by_id(news_id, news_url)
        return templates.TemplateResponse("news_detail.html", {
            "request": request,
            "news": news_item
        })
    except HTTPException as e:
        return templates.TemplateResponse("news_detail.html", {
            "request": request,
            "news": None,
            "error": str(e.detail)
        })

@app.get("/web/freelancers", response_class=HTMLResponse, tags=["Web Sahifalar"])
async def web_freelancers(request: Request):
    """Barcha frilanserlar ro'yxati."""
    try:
        freelancers = get_freelancers()
        return templates.TemplateResponse("freelancers.html", {
            "request": request,
            "freelancers": freelancers
        })
    except HTTPException as e:
        return templates.TemplateResponse("freelancers.html", {
            "request": request,
            "freelancers": [],
            "error": str(e.detail)
        })

# --- Ilovani ishga tushirish uchun ---
# Terminalda quyidagi buyruqni yozing:
# uvicorn main:app --reload