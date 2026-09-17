from __future__ import annotations
from datetime import date, datetime
from decimal import Decimal
import json
from .normalization import normalize_datetime, normalize_number

def _path_string(path):
    return "/" + "/".join(str(p) for p in path) if path else "/"

def _canonical(value, path, set_like_paths):
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, datetime):
        return normalize_datetime(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, (int, float, Decimal)) and not isinstance(value, bool):
        return {"__canonical_number__": normalize_number(value)}
    if isinstance(value, dict):
        return {str(k): _canonical(value[k], path+(str(k),), set_like_paths) for k in sorted(value, key=lambda k: str(k))}
    if isinstance(value, (list, tuple)):
        items=[_canonical(v, path+(i,), set_like_paths) for i,v in enumerate(value)]
        if _path_string(path) in set_like_paths:
            items=sorted(items, key=lambda x: _encode(x))
        return items
    raise TypeError(f"Unsupported canonical JSON type: {type(value)!r}")

def _encode(value):
    if isinstance(value, dict):
        # Numeric marker is emitted as a raw JSON number, not a string/object.
        if set(value)=={"__canonical_number__"}:
            return value["__canonical_number__"]
        return "{" + ",".join(json.dumps(k, ensure_ascii=False, separators=(",",":")) + ":" + _encode(v) for k,v in value.items()) + "}"
    if isinstance(value, list):
        return "[" + ",".join(_encode(v) for v in value) + "]"
    return json.dumps(value, ensure_ascii=False, separators=(",",":"), allow_nan=False)

def canonical_json(value, *, set_like_paths=()) -> str:
    canonical=_canonical(value, (), frozenset(set_like_paths))
    return _encode(canonical)

def canonicalize(value, *, set_like_paths=()):
    """Return a JSON-compatible canonical structure. Numbers are represented as strings here; use canonical_json for hashing."""
    text=canonical_json(value, set_like_paths=set_like_paths)
    return json.loads(text, parse_float=Decimal, parse_int=int)
