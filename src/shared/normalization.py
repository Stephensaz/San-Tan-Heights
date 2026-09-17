from __future__ import annotations
from datetime import date, datetime, timezone
from decimal import Decimal
import math

def normalize_datetime(value: datetime) -> str:
    if value.tzinfo is None:
        raise ValueError("Naive datetimes are not canonical")
    utc=value.astimezone(timezone.utc)
    text=utc.isoformat(timespec="microseconds").replace("+00:00", "Z")
    text=text.replace(".000000Z", "Z")
    if "." in text:
        head, tail=text.split(".",1)
        frac=tail[:-1].rstrip("0")
        text=head + (("."+frac) if frac else "") + "Z"
    return text

def normalize_number(value) -> str:
    if isinstance(value, bool):
        raise TypeError("Boolean is not a numeric canonicalization input")
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("Non-finite floats are not canonical")
        value=Decimal(str(value))
    elif not isinstance(value, Decimal):
        raise TypeError(f"Unsupported numeric type: {type(value)!r}")
    if not value.is_finite():
        raise ValueError("Non-finite decimals are not canonical")
    if value == 0:
        return "0"
    normalized=value.normalize()
    text=format(normalized, "f")
    if "." in text:
        text=text.rstrip("0").rstrip(".")
    return text

def normalize_scalar(value):
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, datetime):
        return normalize_datetime(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, (int, float, Decimal)):
        return value
    raise TypeError(f"Unsupported scalar type: {type(value)!r}")
