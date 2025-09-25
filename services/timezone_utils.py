from datetime import datetime, timezone, timedelta
from typing import Optional, Union
import pytz

# IST Timezone Constants
IST = timezone(timedelta(hours=5, minutes=30))
IST_PYTZ = pytz.timezone('Asia/Kolkata')

def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)

def ist_now() -> datetime:
    return datetime.now(IST).replace(tzinfo=None)

def utc_to_ist(utc_dt: Optional[datetime]) -> Optional[datetime]:
    if utc_dt is None:
        return None
    if utc_dt.tzinfo is None:
        utc_dt = utc_dt.replace(tzinfo=timezone.utc)
    return utc_dt.astimezone(IST).replace(tzinfo=None)

def ist_to_utc(ist_dt: Optional[datetime]) -> Optional[datetime]:
    if ist_dt is None:
        return None
    if ist_dt.tzinfo is None:
        ist_dt = ist_dt.replace(tzinfo=IST)
    return ist_dt.astimezone(timezone.utc).replace(tzinfo=None)

# API Response Formatters (for JSON serialization)
def format_ist_datetime(utc_dt: Optional[datetime]) -> Optional[str]:
    if utc_dt is None:
        return None
    ist_dt = utc_to_ist(utc_dt)
    return ist_dt.strftime("%Y-%m-%d %H:%M:%S")

def format_ist_date(utc_dt: Optional[datetime]) -> Optional[str]:
    if utc_dt is None:
        return None
    ist_dt = utc_to_ist(utc_dt)
    return ist_dt.strftime("%Y-%m-%d")

def format_ist_time_12h(utc_dt: Optional[datetime]) -> Optional[str]:
    if utc_dt is None:
        return None
    ist_dt = utc_to_ist(utc_dt)
    return ist_dt.strftime("%I:%M %p")

def format_ist_time_24h(utc_dt: Optional[datetime]) -> Optional[str]:
    if utc_dt is None:
        return None
    ist_dt = utc_to_ist(utc_dt)
    return ist_dt.strftime("%H:%M")

# Input Parsers (for API requests)
def parse_ist_datetime_input(ist_string: str) -> datetime:
    try:
        # Parse IST time from user input
        ist_dt = datetime.strptime(ist_string, "%Y-%m-%d %H:%M:%S")
        ist_dt = ist_dt.replace(tzinfo=IST)
        # Convert to UTC naive for database
        return ist_dt.astimezone(timezone.utc).replace(tzinfo=None)
    except ValueError as e:
        raise ValueError(f"Invalid IST datetime format: {ist_string}. Expected: YYYY-MM-DD HH:MM:SS")

def parse_ist_date_input(ist_date_string: str) -> datetime:
    try:
        # Parse IST date and assume midnight
        ist_dt = datetime.strptime(ist_date_string, "%Y-%m-%d")
        ist_dt = ist_dt.replace(tzinfo=IST)
        # Convert to UTC for database
        return ist_dt.astimezone(timezone.utc).replace(tzinfo=None)
    except ValueError as e:
        raise ValueError(f"Invalid IST date format: {ist_date_string}. Expected: YYYY-MM-DD")

# Validation Helpers
def is_same_ist_date(utc_dt1: Optional[datetime], utc_dt2: Optional[datetime]) -> bool:
    if utc_dt1 is None or utc_dt2 is None:
        return False
    ist_dt1 = utc_to_ist(utc_dt1)
    ist_dt2 = utc_to_ist(utc_dt2)
    return ist_dt1.date() == ist_dt2.date()

def ist_date_range(start_utc: datetime, end_utc: datetime) -> int:
    ist_start = utc_to_ist(start_utc)
    ist_end = utc_to_ist(end_utc)
    return (ist_end.date() - ist_start.date()).days + 1

# Debugging Helper
def debug_timezone_info(utc_dt: Optional[datetime]) -> dict:
    if utc_dt is None:
        return {"error": "None datetime provided"}
    
    ist_dt = utc_to_ist(utc_dt)
    return {
        "utc_input": utc_dt.isoformat() if utc_dt.tzinfo else f"{utc_dt.isoformat()} (naive)",
        "ist_converted": ist_dt.isoformat(),
        "ist_formatted": format_ist_datetime(utc_dt),
        "ist_date": format_ist_date(utc_dt),
        "ist_time_12h": format_ist_time_12h(utc_dt),
        "ist_time_24h": format_ist_time_24h(utc_dt)
    }


# def format_ist_datetime_debug(utc_dt: Optional[datetime]) -> Optional[str]:
#     if utc_dt is None:
#         return None
    
#     print(f"🔍 DEBUG: Input UTC: {utc_dt}")
#     print(f"🔍 DEBUG: Input type: {type(utc_dt)}")
    
#     ist_dt = utc_to_ist(utc_dt)
#     print(f"🔍 DEBUG: Converted IST: {ist_dt}")
    
#     formatted = ist_dt.strftime("%Y-%m-%d %H:%M:%S")
#     print(f"🔍 DEBUG: Formatted result: {formatted}")
    
#     return formatted
