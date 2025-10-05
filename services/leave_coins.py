from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from models import LeaveCoin, LeaveCoinTxn
from .timezone_utils import format_ist_datetime, format_ist_date

ROLLING_MONTHS = 12
CAP_COINS = 10

def _aware_utc(dt):
    if dt is None:
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)

def _naive(dt):
    if dt is None:
        return None
    return dt.replace(tzinfo=None)

def _rolling_window_start(as_of: datetime) -> datetime:
    try:
        from dateutil.relativedelta import relativedelta
        return as_of - relativedelta(months=ROLLING_MONTHS)
    except Exception:
        return as_of - timedelta(days=365)

def _expiry_from_grant(grant_date: datetime) -> datetime:
    try:
        from dateutil.relativedelta import relativedelta
        return grant_date + relativedelta(months=ROLLING_MONTHS)
    except Exception:
        return grant_date + timedelta(days=365)

def get_available_coins(db: Session, employee_id: int, as_of: datetime | None = None) -> dict:
    as_of = _aware_utc(as_of or datetime.now(timezone.utc))
    window_start = _rolling_window_start(as_of)
    as_of_naive = _naive(as_of)
    window_start_naive = _naive(window_start)

    coins = db.query(LeaveCoin).filter(
        LeaveCoin.employee_id == employee_id,
        LeaveCoin.grant_date >= window_start_naive,
        LeaveCoin.expiry_date > as_of_naive,
        LeaveCoin.remaining > 0
    ).all()

    raw_available = sum(c.remaining for c in coins)
    available = min(raw_available, CAP_COINS)

    # Expiring soon (next 60 days)
    soon_cutoff = as_of + timedelta(days=60)
    expiring: dict[datetime, int] = {}
    for c in coins:
        exp = _aware_utc(c.expiry_date)
        if exp <= soon_cutoff:
            expiring[exp] = expiring.get(exp, 0) + c.remaining
    expiring_soon = [
        {"expiry_date": format_ist_date(k), "amount": v} 
        for k, v in sorted(expiring.items(), key=lambda kv: kv)
    ]
    # Last 10 txns
    txns = (
        db.query(LeaveCoinTxn)
        .filter(LeaveCoinTxn.employee_id == employee_id)
        .order_by(LeaveCoinTxn.occurred_at.desc())
        .limit(10)
        .all()
    )
    recent_txns = [
        {"type": t.type, "amount": t.amount, "occurred_at": format_ist_datetime(t.occurred_at), "comment": t.comment}
        for t in txns
    ]

    return {
        "available_coins": available,
        "raw_available": raw_available,
        "expiring_soon": expiring_soon,
        "recent_txns": recent_txns,
    }

def grant_coins(db: Session, employee_id: int, amount: int = 1, source: str = "monthly_grant", now: datetime | None = None) -> int:
    now = _aware_utc(now or datetime.now(timezone.utc))
    # enforce cap BEFORE granting
    bal = get_available_coins(db, employee_id, now)
    if bal["available_coins"] >= CAP_COINS:
        return 0
    grant_amount = min(amount, CAP_COINS - bal["available_coins"])
    if grant_amount <= 0:
        return 0

    lc = LeaveCoin(
        employee_id=employee_id,
        grant_date=now,
        expiry_date=_expiry_from_grant(now),
        quantity=grant_amount,
        remaining=grant_amount,
        source=source,
    )
    db.add(lc)
    db.flush()  # to get lc.id

    txn = LeaveCoinTxn(
        employee_id=employee_id,
        coin_id=lc.id,
        type="grant",
        amount=grant_amount,
        occurred_at=now,
        comment=f"Grant {source}",
    )
    db.add(txn)
    return grant_amount

def expire_coins(db: Session, now: datetime | None = None) -> int:
    now = _aware_utc(now or datetime.now(timezone.utc))
    now_naive = _naive(now)
    coins = db.query(LeaveCoin).filter(
        LeaveCoin.expiry_date <= now_naive,
        LeaveCoin.remaining > 0
    ).all()

    total_expired = 0
    for c in coins:
        amt = c.remaining
        c.remaining = 0
        total_expired += amt
        db.add(LeaveCoinTxn(
            employee_id=c.employee_id,
            coin_id=c.id,
            type="expire",
            amount=amt,
            occurred_at=now,
            comment="Auto expiry at 12 months"
        ))
    return total_expired

def consume_coins(db: Session, employee_id: int, amount: int, ref_leave_request_id: int | None = None, now: datetime | None = None) -> int:
    """
    Consume 'amount' coins FIFO by expiry for the given employee.
    Returns the total consumed (0 if insufficient).
    Does not commit; caller should commit/rollback.
    """
    if amount <= 0:
        return 0

    now = _aware_utc(now or datetime.now(timezone.utc))
    now_naive = _naive(now)

    coins = (
        db.query(LeaveCoin)
        .filter(
            LeaveCoin.employee_id == employee_id,
            LeaveCoin.expiry_date > now_naive,
            LeaveCoin.remaining > 0
        )
        .order_by(LeaveCoin.expiry_date.asc(), LeaveCoin.id.asc())
        .all()
    )

    to_consume = amount
    consumed_total = 0
    for c in coins:
        if to_consume <= 0:
            break
        take = min(c.remaining, to_consume)
        if take > 0:
            c.remaining -= take
            consumed_total += take
            to_consume -= take
            db.add(LeaveCoinTxn(
                employee_id=employee_id,
                coin_id=c.id,
                type="consume",
                amount=take,
                ref_leave_request_id=ref_leave_request_id,
                occurred_at=now,
                comment="Consume for approved leave" if ref_leave_request_id else "Consume",
            ))

    if consumed_total < amount:
        # Caller must rollback to cancel partial deductions.
        return 0
    return consumed_total

def _duration_days(start_date: datetime, end_date: datetime) -> int:
    """
    Calculate the number of days between start and end dates (inclusive).
    Both dates should be UTC naive datetimes.
    """
    if not start_date or not end_date:
        return 0
    
    # Convert to dates to avoid time component issues
    start = start_date.date() if hasattr(start_date, 'date') else start_date
    end = end_date.date() if hasattr(end_date, 'date') else end_date
    
    # Calculate inclusive days (end - start + 1)
    return (end - start).days + 1
