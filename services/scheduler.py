from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime
import asyncio
from sqlalchemy.orm import Session
from services.quotes import fetch_and_store_quote
from db import get_db

class QuoteScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        
    def start(self):
        """Start the scheduler"""
        # Schedule daily quote fetch at 00:01 UTC
        self.scheduler.add_job(
            self.daily_quote_job,
            CronTrigger(hour=0, minute=1, timezone='UTC'),
            id='daily_quote_fetch',
            replace_existing=True
        )
        
        # Optional: Schedule backup fetch at 12:01 UTC
        self.scheduler.add_job(
            self.backup_quote_job,
            CronTrigger(hour=12, minute=1, timezone='UTC'),
            id='backup_quote_fetch',
            replace_existing=True
        )
        
        self.scheduler.start()
        print("Quote scheduler started successfully")
    
    def stop(self):
        """Stop the scheduler"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            print("Quote scheduler stopped")
    
    def daily_quote_job(self):
        """Fetch and store daily quote"""
        try:
            # Get database session
            db = next(get_db())
            
            # Fetch and store quote
            fetch_and_store_quote(db)
            
            print(f"Daily quote job completed: {datetime.now()}")
            
        except Exception as e:
            print(f"Daily quote job failed: {e}")
        finally:
            if 'db' in locals():
                db.close()
    
    def backup_quote_job(self):
        """Backup job in case morning job failed"""
        try:
            db = next(get_db())
            
            # Check if today's quote exists
            from services.quotes import _utc_midnight, DailyQuote
            key = _utc_midnight(datetime.now())
            
            existing = db.query(DailyQuote).filter(DailyQuote.date_utc == key).first()
            
            if not existing:
                print("No quote found for today, running backup job...")
                fetch_and_store_quote(db)
            else:
                print("Today's quote already exists, backup job skipped")
                
        except Exception as e:
            print(f"Backup quote job failed: {e}")
        finally:
            if 'db' in locals():
                db.close()

# Global scheduler instance
quote_scheduler = QuoteScheduler()
