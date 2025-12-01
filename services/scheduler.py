# from apscheduler.schedulers.asyncio import AsyncIOScheduler
# from apscheduler.triggers.cron import CronTrigger
# from datetime import datetime, date, timedelta
# import asyncio
# from sqlalchemy.orm import Session

# # Existing imports
# from services.quotes import fetch_and_store_quote
# from db import get_db

# # imports for attendance aggregation
# from services.attendance_aggregation_service import (
#     aggregate_daily_attendance,
#     archive_old_attendance,
#     delete_old_archived_attendance
# )


# class QuoteScheduler:
#     def __init__(self):
#         self.scheduler = AsyncIOScheduler()
    
#     def start(self):
#         """Start the scheduler"""
        
#         # Schedule daily quote fetch at 00:01 UTC
#         self.scheduler.add_job(
#             self.daily_quote_job,
#             CronTrigger(hour=0, minute=1, timezone='UTC'),
#             id='daily_quote_fetch',
#             replace_existing=True
#         )
        
#         # Optional: Schedule backup fetch at 12:01 UTC
#         self.scheduler.add_job(
#             self.backup_quote_job,
#             CronTrigger(hour=12, minute=1, timezone='UTC'),
#             id='backup_quote_fetch',
#             replace_existing=True
#         )
        
#         # these three jobs for attendance automation
        
#         # JOB 1: Daily attendance aggregation at 2:00 AM IST (20:30 UTC previous day)
#         # Runs every day at 2:00 AM IST to aggregate previous day's attendance
#         self.scheduler.add_job(
#             self.daily_attendance_aggregation_job,
#             CronTrigger(hour=20, minute=30, timezone='UTC'),  # 2:00 AM IST
#             id='daily_attendance_aggregation',
#             replace_existing=True
#         )
        
#         # JOB 2: Archive old daily_attendance records at 2:45 AM IST (21:15 UTC previous day)
#         # Runs after aggregation to move records >30 days to archive
#         self.scheduler.add_job(
#             self.daily_attendance_archive_job,
#             CronTrigger(hour=21, minute=15, timezone='UTC'),  # 2:45 AM IST
#             id='daily_attendance_archive',
#             replace_existing=True
#         )
        
#         # JOB 3: Monthly cleanup of old archived records at 3:00 AM IST on 1st of month
#         # Deletes archived records >1 year old
#         self.scheduler.add_job(
#             self.monthly_archive_cleanup_job,
#             CronTrigger(day=1, hour=21, minute=30, timezone='UTC'),  # 3:00 AM IST on 1st
#             id='monthly_archive_cleanup',
#             replace_existing=True
#         )
        
#         self.scheduler.start()
#         print("Scheduler started successfully")
#         print("Daily attendance aggregation: Every day at 2:00 AM IST")
#         print("Daily attendance archival: Every day at 2:45 AM IST")
#         print("Monthly archive cleanup: 1st of month at 3:00 AM IST")
    
#     def stop(self):
#         """Stop the scheduler"""
#         if self.scheduler.running:
#             self.scheduler.shutdown()
#             print("Scheduler stopped")
    
    
#     def daily_quote_job(self):
#         """Fetch and store daily quote"""
#         try:
#             # Get database session
#             db = next(get_db())
            
#             # Fetch and store quote
#             fetch_and_store_quote(db)
#             print(f"Daily quote job completed: {datetime.now()}")
        
#         except Exception as e:
#             print(f"Daily quote job failed: {e}")
        
#         finally:
#             if 'db' in locals():
#                 db.close()
    
#     def backup_quote_job(self):
#         """Backup job in case morning job failed"""
#         try:
#             db = next(get_db())
            
#             # Check if today's quote exists
#             from services.quotes import _utc_midnight, DailyQuote
#             key = _utc_midnight(datetime.now())
#             existing = db.query(DailyQuote).filter(DailyQuote.date_utc == key).first()
            
#             if not existing:
#                 print("No quote found for today, running backup job...")
#                 fetch_and_store_quote(db)
#             else:
#                 print("Today's quote already exists, backup job skipped")
        
#         except Exception as e:
#             print(f"❌ Backup quote job failed: {e}")
        
#         finally:
#             if 'db' in locals():
#                 db.close()
    
#     # NEW: these three job functions for attendance automation
    
#     def daily_attendance_aggregation_job(self):
#         """
#         Aggregate yesterday's attendance data into daily_attendance table.
#         Runs daily at 2:00 AM IST (20:30 UTC previous day).
        
#         What it does:
#         - Gets yesterday's date (in IST)
#         - Aggregates all work_sessions for each employee
#         - Creates/updates daily_attendance records
#         - Links work_sessions to daily_attendance
#         """
#         try:
#             print(f"\n{'='*70}")
#             print(f"ATTENDANCE AGGREGATION JOB STARTED")
#             print(f"Time: {datetime.now()}")
#             print(f"{'='*70}")
            
#             # Get database session
#             db = next(get_db())
            
#             # Calculate yesterday's date (the day we're aggregating)
#             yesterday = date.today() - timedelta(days=1)
            
#             print(f"📅 Aggregating attendance for: {yesterday}")
            
#             # Run aggregation
#             records_created = aggregate_daily_attendance(
#                 db=db,
#                 target_date=yesterday,
#                 employee_id=None  # Aggregate all employees
#             )
            
#             print(f"Aggregation complete!")
#             print(f"Records created/updated: {records_created}")
#             print(f"{'='*70}\n")
        
#         except Exception as e:
#             print(f"ATTENDANCE AGGREGATION FAILED: {e}")
#             print(f"{'='*70}\n")
#             # Log error for monitoring (you can add email/slack notification here)
        
#         finally:
#             if 'db' in locals():
#                 db.close()
    
#     def daily_attendance_archive_job(self):
#         """
#         Archive daily_attendance records older than 30 days.
#         Runs daily at 2:45 AM IST (21:15 UTC previous day), 45 minutes after aggregation.
        
#         What it does:
#         - Finds daily_attendance records older than 30 days
#         - Copies them to archived_attendance table
#         - Deletes from daily_attendance table
#         """
#         try:
#             print(f"\n{'='*70}")
#             print(f"📦 ATTENDANCE ARCHIVE JOB STARTED")
#             print(f"⏰ Time: {datetime.now()}")
#             print(f"{'='*70}")
            
#             # Get database session
#             db = next(get_db())
            
#             # Archive records older than 30 days
#             retention_days = 30
            
#             print(f"📅 Archiving records older than {retention_days} days")
            
#             # Run archive
#             archived_count = archive_old_attendance(
#                 db=db,
#                 retention_days=retention_days
#             )
            
#             if archived_count > 0:
#                 print(f"Archive complete!")
#                 print(f"Records archived: {archived_count}")
#             else:
#                 print(f"No records to archive (all within {retention_days} days)")
            
#             print(f"{'='*70}\n")
        
#         except Exception as e:
#             print(f"ATTENDANCE ARCHIVE FAILED: {e}")
#             print(f"{'='*70}\n")
#             # Log error for monitoring
        
#         finally:
#             if 'db' in locals():
#                 db.close()
    
#     def monthly_archive_cleanup_job(self):
#         """
#         Delete archived_attendance records older than 1 year.
#         Runs monthly on the 1st at 3:00 AM IST (21:30 UTC on last day of previous month).
        
#         What it does:
#         - Finds archived_attendance records older than 365 days
#         - Permanently deletes them
#         - Keeps database size manageable
#         """
#         try:
#             print(f"\n{'='*70}")
#             print(f"MONTHLY ARCHIVE CLEANUP JOB STARTED")
#             print(f"Time: {datetime.now()}")
#             print(f"{'='*70}")
            
#             # Get database session
#             db = next(get_db())
            
#             # Delete archived records older than 1 year (365 days)
#             retention_days = 365
            
#             print(f"Deleting archived records older than {retention_days} days (1 year)")
            
#             # Run cleanup
#             deleted_count = delete_old_archived_attendance(
#                 db=db,
#                 retention_days=retention_days
#             )
            
#             if deleted_count > 0:
#                 print(f"Cleanup complete!")
#                 print(f"Records deleted: {deleted_count}")
#             else:
#                 print(f"No old records to delete (all within {retention_days} days)")
            
#             print(f"{'='*70}\n")
        
#         except Exception as e:
#             print(f"MONTHLY ARCHIVE CLEANUP FAILED: {e}")
#             print(f"{'='*70}\n")
#             # Log error for monitoring
        
#         finally:
#             if 'db' in locals():
#                 db.close()


# # Global scheduler instance
# quote_scheduler = QuoteScheduler()

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from datetime import datetime, date, timedelta
import asyncio
from sqlalchemy.orm import Session

# Existing imports
from services.quotes import fetch_and_store_quote
from db import get_db

# ✅ NEW: Add these imports for attendance aggregation
from services.attendance_aggregation_service import (
    aggregate_daily_attendance,
    archive_old_attendance,
    delete_old_archived_attendance
)


class QuoteScheduler:
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
    
    def start(self):
        """Start the scheduler"""
        # ======================================================================
        # EXISTING JOBS (Keep these)
        # ======================================================================
        
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
        
        # ======================================================================
        # ✅ NEW: Add these three jobs for attendance automation
        # ======================================================================
        
        # JOB 1: Daily attendance aggregation at 2:00 AM IST (20:30 UTC previous day)
        self.scheduler.add_job(
            self.daily_attendance_aggregation_job,
            CronTrigger(hour=20, minute=30, timezone='UTC'),
            id='daily_attendance_aggregation',
            replace_existing=True
        )
        
        # JOB 2: Archive old daily_attendance records at 2:45 AM IST (21:15 UTC previous day)
        self.scheduler.add_job(
            self.daily_attendance_archive_job,
            CronTrigger(hour=21, minute=15, timezone='UTC'),
            id='daily_attendance_archive',
            replace_existing=True
        )
        
        # JOB 3: Monthly cleanup of old archived records at 3:00 AM IST on 1st
        self.scheduler.add_job(
            self.monthly_archive_cleanup_job,
            CronTrigger(day=1, hour=21, minute=30, timezone='UTC'),
            id='monthly_archive_cleanup',
            replace_existing=True
        )
        
        self.scheduler.start()
        print("✅ Scheduler started successfully")
        print("📅 Daily attendance aggregation: Every day at 2:00 AM IST")
        print("📦 Daily attendance archival: Every day at 2:45 AM IST")
        print("🗑️  Monthly archive cleanup: 1st of month at 3:00 AM IST")
    
    def stop(self):
        """Stop the scheduler"""
        if self.scheduler.running:
            self.scheduler.shutdown()
            print("Scheduler stopped")
    
    # ==========================================================================
    # EXISTING JOBS (Keep these as-is)
    # ==========================================================================
    
    def daily_quote_job(self):
        """Fetch and store daily quote"""
        try:
            db = next(get_db())
            fetch_and_store_quote(db)
            print(f"✅ Daily quote job completed: {datetime.now()}")
        except Exception as e:
            print(f"❌ Daily quote job failed: {e}")
        finally:
            if 'db' in locals():
                db.close()
    
    def backup_quote_job(self):
        """Backup job in case morning job failed"""
        try:
            db = next(get_db())
            from services.quotes import _utc_midnight, DailyQuote
            key = _utc_midnight(datetime.now())
            existing = db.query(DailyQuote).filter(DailyQuote.date_utc == key).first()
            
            if not existing:
                print("No quote found for today, running backup job...")
                fetch_and_store_quote(db)
            else:
                print("Today's quote already exists, backup job skipped")
        except Exception as e:
            print(f"❌ Backup quote job failed: {e}")
        finally:
            if 'db' in locals():
                db.close()
    
    # ==========================================================================
    # ✅ NEW: Add these three job functions for attendance automation
    # ==========================================================================
    
    def daily_attendance_aggregation_job(self):
        """
        Aggregate yesterday's attendance data into daily_attendance table.
        Runs daily at 2:00 AM IST (20:30 UTC previous day).
        """
        try:
            print(f"\n{'='*70}")
            print(f"🔄 ATTENDANCE AGGREGATION JOB STARTED")
            print(f"⏰ Time: {datetime.now()}")
            print(f"{'='*70}")
            
            db = next(get_db())
            yesterday = date.today() - timedelta(days=1)
            
            print(f"📅 Aggregating attendance for: {yesterday}")
            
            records_created = aggregate_daily_attendance(
                db=db,
                target_date=yesterday,
                employee_id=None
            )
            
            print(f"✅ Aggregation complete!")
            print(f"📊 Records created/updated: {records_created}")
            print(f"{'='*70}\n")
        
        except Exception as e:
            print(f"❌ ATTENDANCE AGGREGATION FAILED: {e}")
            print(f"{'='*70}\n")
        
        finally:
            if 'db' in locals():
                db.close()
    
    def daily_attendance_archive_job(self):
        """
        Archive daily_attendance records older than 30 days.
        Runs daily at 2:45 AM IST (21:15 UTC previous day), 45 minutes after aggregation.
        """
        try:
            print(f"\n{'='*70}")
            print(f"📦 ATTENDANCE ARCHIVE JOB STARTED")
            print(f"⏰ Time: {datetime.now()}")
            print(f"{'='*70}")
            
            db = next(get_db())
            retention_days = 30
            
            print(f"📅 Archiving records older than {retention_days} days")
            
            archived_count = archive_old_attendance(
                db=db,
                retention_days=retention_days
            )
            
            if archived_count > 0:
                print(f"✅ Archive complete!")
                print(f"📊 Records archived: {archived_count}")
            else:
                print(f"ℹ️  No records to archive (all within {retention_days} days)")
            
            print(f"{'='*70}\n")
        
        except Exception as e:
            print(f"❌ ATTENDANCE ARCHIVE FAILED: {e}")
            print(f"{'='*70}\n")
        
        finally:
            if 'db' in locals():
                db.close()
    
    def monthly_archive_cleanup_job(self):
        """
        Delete archived_attendance records older than 1 year.
        Runs monthly on the 1st at 3:00 AM IST (21:30 UTC on last day of previous month).
        """
        try:
            print(f"\n{'='*70}")
            print(f"🗑️  MONTHLY ARCHIVE CLEANUP JOB STARTED")
            print(f"⏰ Time: {datetime.now()}")
            print(f"{'='*70}")
            
            db = next(get_db())
            retention_days = 365
            
            print(f"📅 Deleting archived records older than {retention_days} days (1 year)")
            
            deleted_count = delete_old_archived_attendance(
                db=db,
                retention_days=retention_days
            )
            
            if deleted_count > 0:
                print(f"✅ Cleanup complete!")
                print(f"📊 Records deleted: {deleted_count}")
            else:
                print(f"ℹ️  No old records to delete (all within {retention_days} days)")
            
            print(f"{'='*70}\n")
        
        except Exception as e:
            print(f"❌ MONTHLY ARCHIVE CLEANUP FAILED: {e}")
            print(f"{'='*70}\n")
        
        finally:
            if 'db' in locals():
                db.close()


# Global scheduler instance
quote_scheduler = QuoteScheduler()

# SCHEDULE SUMMARY (for reference)
"""
DAILY JOBS:
-----------
00:01 UTC (5:31 AM IST)    - Fetch daily inspirational quote
12:01 UTC (5:31 PM IST)    - Backup quote fetch (if morning failed)
20:30 UTC (2:00 AM IST)    - Aggregate yesterday's attendance ← NEW
21:15 UTC (2:45 AM IST)    - Archive records >30 days old    ← NEW

MONTHLY JOBS:
-------------
1st of month at 21:30 UTC (3:00 AM IST) - Delete archived records >1 year ← NEW

RETENTION POLICY:
-----------------
- work_sessions: Forever (raw data)
- daily_attendance: Last 30 days (hot storage, fast queries)
- archived_attendance: 31 days - 1 year (cold storage, compliance)
- Deleted: Older than 1 year (GDPR compliance)

DATA LIFECYCLE:
---------------
Day 0:  User clocks in/out → work_sessions
Day 1:  Aggregated → daily_attendance
Day 31: Moved → archived_attendance
Day 396: Deleted (1 year + 31 days)
"""

# TIMEZONE CONVERSIONS (for reference)
"""
IST (India Standard Time) = UTC + 5:30

Desired IST Time    →    UTC Time (for CronTrigger)
----------------         ------------------------
2:00 AM IST        →    20:30 UTC (previous day)
2:45 AM IST        →    21:15 UTC (previous day)
3:00 AM IST        →    21:30 UTC (previous day)

Example: 2:00 AM IST on Nov 13 = 20:30 UTC on Nov 12
"""
# OLD SCHEDULER CODE

# from apscheduler.schedulers.asyncio import AsyncIOScheduler
# from apscheduler.triggers.cron import CronTrigger
# from datetime import datetime
# import asyncio
# from sqlalchemy.orm import Session
# from services.quotes import fetch_and_store_quote
# from db import get_db

# class QuoteScheduler:
#     def __init__(self):
#         self.scheduler = AsyncIOScheduler()
        
#     def start(self):
#         """Start the scheduler"""
#         # Schedule daily quote fetch at 00:01 UTC
#         self.scheduler.add_job(
#             self.daily_quote_job,
#             CronTrigger(hour=0, minute=1, timezone='UTC'),
#             id='daily_quote_fetch',
#             replace_existing=True
#         )
        
#         # Optional: Schedule backup fetch at 12:01 UTC
#         self.scheduler.add_job(
#             self.backup_quote_job,
#             CronTrigger(hour=12, minute=1, timezone='UTC'),
#             id='backup_quote_fetch',
#             replace_existing=True
#         )
        
#         self.scheduler.start()
#         print("Quote scheduler started successfully")
    
#     def stop(self):
#         """Stop the scheduler"""
#         if self.scheduler.running:
#             self.scheduler.shutdown()
#             print("Quote scheduler stopped")
    
#     def daily_quote_job(self):
#         """Fetch and store daily quote"""
#         try:
#             # Get database session
#             db = next(get_db())
            
#             # Fetch and store quote
#             fetch_and_store_quote(db)
            
#             print(f"Daily quote job completed: {datetime.now()}")
            
#         except Exception as e:
#             print(f"Daily quote job failed: {e}")
#         finally:
#             if 'db' in locals():
#                 db.close()
    
#     def backup_quote_job(self):
#         """Backup job in case morning job failed"""
#         try:
#             db = next(get_db())
            
#             # Check if today's quote exists
#             from services.quotes import _utc_midnight, DailyQuote
#             key = _utc_midnight(datetime.now())
            
#             existing = db.query(DailyQuote).filter(DailyQuote.date_utc == key).first()
            
#             if not existing:
#                 print("No quote found for today, running backup job...")
#                 fetch_and_store_quote(db)
#             else:
#                 print("Today's quote already exists, backup job skipped")
                
#         except Exception as e:
#             print(f"Backup quote job failed: {e}")
#         finally:
#             if 'db' in locals():
#                 db.close()

# # Global scheduler instance
# quote_scheduler = QuoteScheduler()
