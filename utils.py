# utils.py
from datetime import timezone
from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")

def to_ist(dt):
    # Convert any datetime (naive=assumed UTC; aware=converted) to IST
    if not dt:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(IST)

def ensure_utc_naive(dt):
    # Ensure DB writes are stored as naive UTC (consistent with existing code)
    # Accepts naive (assumed UTC) or aware; returns naive UTC
    if dt is None:
        return None
    if dt.tzinfo is None:
        # Already naive: assume UTC by convention
        return dt
    
    if isinstance(dt_in, str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}', dt_in):
        ist_dt = datetime.strptime(dt_in, '%Y-%m-%d').replace(tzinfo=IST)
        return ist_dt.astimezone(timezone.utc).replace(tzinfo=None)

    # Convert to UTC then drop tzinfo
    return dt.astimezone(timezone.utc).replace(tzinfo=None)