from datetime import datetime, timezone, timedelta
import requests
import random
from sqlalchemy.orm import Session
from models import DailyQuote

# Multiple API endpoints for redundancy
QUOTE_APIS = [
    {"url": "https://api.quotable.io/random", "type": "quotable"},
    {"url": "https://api.realinspire.live/v1/quotes/random", "type": "inspire"},
    {"url": "https://zenquotes.io/api/random", "type": "zen"}
]

# Curated fallback quotes for reliability
FALLBACK_QUOTES = [
    ("Success is not final, failure is not fatal: it is the courage to continue that counts.", "Winston Churchill"),
    ("The only way to do great work is to love what you do.", "Steve Jobs"),
    ("Innovation distinguishes between a leader and a follower.", "Steve Jobs"),
    ("Your time is limited, don't waste it living someone else's life.", "Steve Jobs"),
    ("The future belongs to those who believe in the beauty of their dreams.", "Eleanor Roosevelt"),
    ("Excellence is never an accident. It is always the result of high intention, sincere effort, and intelligent execution.", "Aristotle"),
    ("The only impossible journey is the one you never begin.", "Tony Robbins"),
    ("Believe you can and you're halfway there.", "Theodore Roosevelt"),
]

def _utc_midnight(dt: datetime) -> datetime:
    """Convert datetime to UTC midnight"""
    d = dt.astimezone(timezone.utc)
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc).replace(tzinfo=None)

def validate_quote_quality(text: str, author: str) -> bool:
    """Ensure quotes meet quality standards"""
    if not text or len(text) < 20 or len(text) > 300:
        return False
    if not author or author.lower() in ["unknown", "", "null"]:
        return False
    
    # Check for inappropriate content
    blocked_words = ["hate", "violence", "discrimination", "stupid", "idiot"]
    if any(word in text.lower() for word in blocked_words):
        return False
    
    return True

def fetch_quote_from_api(api_config: dict) -> tuple:
    """Fetch quote from specific API"""
    try:
        params = {}
        if api_config["type"] == "quotable":
            params = {
                "maxLength": 250,
                "tags": "motivational|inspirational|wisdom|success"
            }
        
        r = requests.get(api_config["url"], timeout=10, params=params)
        r.raise_for_status()
        
        if api_config["type"] == "quotable":
            data = r.json()
            text = data.get("content", "")
            author = data.get("author", "")
            
        elif api_config["type"] == "inspire":
            data = r.json()[0] if isinstance(r.json(), list) else r.json()
            text = data.get("content", "")
            author = data.get("author", "")
            
        elif api_config["type"] == "zen":
            data = r.json()[0] if isinstance(r.json(), list) else r.json()
            text = data.get("q", "")
            author = data.get("a", "")
        
        return text, author
        
    except Exception as e:
        print(f"API {api_config['url']} failed: {e}")
        return "", ""

def fetch_and_store_quote(db: Session):
    """Enhanced quote fetching with multiple API fallbacks"""
    text, author = "", ""
    
    # Try different APIs
    for api_config in QUOTE_APIS:
        text, author = fetch_quote_from_api(api_config)
        
        if validate_quote_quality(text, author):
            print(f"Successfully fetched quote from {api_config['type']}")
            break
        else:
            print(f"Quote from {api_config['type']} failed validation")
    
    # Use fallback if all APIs failed
    if not validate_quote_quality(text, author):
        text, author = random.choice(FALLBACK_QUOTES)
        print("Using fallback quote")
    
    # Store in database
    key = _utc_midnight(datetime.now(timezone.utc))
    existing = db.query(DailyQuote).filter(DailyQuote.date_utc == key).first()
    
    if existing:
        existing.text = text
        existing.author = author
        print(f"Updated existing quote for {key}")
    else:
        new_quote = DailyQuote(date_utc=key, text=text, author=author)
        db.add(new_quote)
        print(f"Added new quote for {key}")
    
    try:
        db.commit()
        print("Quote successfully saved to database")
    except Exception as e:
        print(f"Database error: {e}")
        db.rollback()

def get_today_quote(db: Session) -> dict:
    """Get today's quote from database"""
    key = _utc_midnight(datetime.now(timezone.utc))
    
    quote = db.query(DailyQuote).filter(DailyQuote.date_utc == key).first()
    
    if not quote:
        # No quote for today, fetch one
        print("No quote found for today, fetching...")
        fetch_and_store_quote(db)
        quote = db.query(DailyQuote).filter(DailyQuote.date_utc == key).first()
    
    if quote:
        return {"text": quote.text, "author": quote.author}
    else:
        # Ultimate fallback
        fallback = random.choice(FALLBACK_QUOTES)
        return {"text": fallback[0], "author": fallback[1]}

def get_quote_history(db: Session, days: int = 7) -> list:
    """Get last N days of quotes"""
    start_date = datetime.now(timezone.utc) - timedelta(days=days)
    
    quotes = (
        db.query(DailyQuote)
        .filter(DailyQuote.date_utc >= start_date.replace(tzinfo=None))
        .order_by(DailyQuote.date_utc.desc())
        .limit(days)
        .all()
    )
    
    return [
        {
            "text": q.text, 
            "author": q.author, 
            "date": q.date_utc.strftime("%Y-%m-%d")
        } 
        for q in quotes
    ]
