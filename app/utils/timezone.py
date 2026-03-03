"""
WENDRINK ERP - Almaty Timezone and Business Date Logic

LAW 4: ALMATY BUSINESS DATE WITH UTC+5 TIMEZONE

Business day starts at 06:00 AM Almaty time:
- 00:00 to 05:59 AM Almaty → PREVIOUS business day
- 06:00 to 23:59 PM Almaty → CURRENT business day

All timestamps stored in UTC.
Business date calculated in Almaty timezone.
"""

from datetime import date, datetime, time, timedelta, timezone
from typing import Final

# Almaty timezone: UTC+5 (no DST in Kazakhstan)
ALMATY_UTC_OFFSET: Final[int] = 5
ALMATY_TZ: Final[timezone] = timezone(timedelta(hours=ALMATY_UTC_OFFSET))

# Business day starts at 06:00 AM Almaty time
BUSINESS_DAY_START_HOUR: Final[int] = 6


def get_utc_now() -> datetime:
    """
    Get current UTC timestamp.
    
    Returns:
        Current datetime in UTC with timezone info.
    """
    return datetime.now(timezone.utc)


def utc_to_almaty(utc_dt: datetime) -> datetime:
    """
    Convert UTC datetime to Almaty timezone.
    
    Args:
        utc_dt: Datetime in UTC (must have timezone info).
        
    Returns:
        Datetime in Almaty timezone (UTC+5).
        
    Raises:
        ValueError: If datetime has no timezone info.
    """
    if utc_dt.tzinfo is None:
        raise ValueError("UTC datetime must have timezone info")
    
    return utc_dt.astimezone(ALMATY_TZ)


def almaty_to_utc(almaty_dt: datetime) -> datetime:
    """
    Convert Almaty datetime to UTC.
    
    Args:
        almaty_dt: Datetime in Almaty timezone.
        
    Returns:
        Datetime in UTC.
    """
    if almaty_dt.tzinfo is None:
        # Assume it's Almaty time if no timezone
        almaty_dt = almaty_dt.replace(tzinfo=ALMATY_TZ)
    
    return almaty_dt.astimezone(timezone.utc)


def get_business_date(utc_dt: datetime | None = None) -> date:
    """
    Calculate the business date for a given UTC timestamp.
    
    Business day rules (Almaty time):
    - 00:00 to 05:59 → PREVIOUS calendar day
    - 06:00 to 23:59 → CURRENT calendar day
    
    Args:
        utc_dt: UTC datetime to calculate business date for.
                If None, uses current UTC time.
                
    Returns:
        Business date in Almaty timezone.
        
    Examples:
        # 2026-01-27 03:00 Almaty → business date 2026-01-26
        # 2026-01-27 06:00 Almaty → business date 2026-01-27
        # 2026-01-27 23:59 Almaty → business date 2026-01-27
    """
    if utc_dt is None:
        utc_dt = get_utc_now()
    
    # Convert to Almaty time
    almaty_dt = utc_to_almaty(utc_dt)
    
    # If before 06:00, it belongs to the previous business day
    if almaty_dt.hour < BUSINESS_DAY_START_HOUR:
        return (almaty_dt - timedelta(days=1)).date()
    
    return almaty_dt.date()


def get_business_date_range(business_date: date) -> tuple[datetime, datetime]:
    """
    Get the UTC datetime range for a business date.
    
    A business day in Almaty:
    - Starts: 06:00:00 Almaty (01:00:00 UTC on the same day)
    - Ends: 05:59:59.999999 Almaty next day (00:59:59.999999 UTC next day)
    
    Args:
        business_date: The business date to get range for.
        
    Returns:
        Tuple of (start_utc, end_utc) datetimes.
        
    Example:
        For 2026-01-27:
        - Start: 2026-01-27 01:00:00 UTC (06:00 Almaty)
        - End: 2026-01-28 00:59:59.999999 UTC (05:59:59 Almaty)
    """
    # Business day starts at 06:00 Almaty on the business_date
    start_almaty = datetime.combine(
        business_date,
        time(hour=BUSINESS_DAY_START_HOUR, minute=0, second=0),
        tzinfo=ALMATY_TZ,
    )
    
    # Business day ends at 05:59:59.999999 Almaty the next day
    end_almaty = datetime.combine(
        business_date + timedelta(days=1),
        time(hour=BUSINESS_DAY_START_HOUR - 1, minute=59, second=59, microsecond=999999),
        tzinfo=ALMATY_TZ,
    )
    
    return almaty_to_utc(start_almaty), almaty_to_utc(end_almaty)


def is_same_business_day(dt1: datetime, dt2: datetime) -> bool:
    """
    Check if two UTC datetimes belong to the same business day.
    
    Args:
        dt1: First UTC datetime.
        dt2: Second UTC datetime.
        
    Returns:
        True if both datetimes are in the same Almaty business day.
    """
    return get_business_date(dt1) == get_business_date(dt2)
