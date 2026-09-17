from __future__ import annotations
from hashlib import sha256
from .canonical_json import canonical_json

def sha256_bytes(value: bytes) -> str:
    return sha256(value).hexdigest()

def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))

def sha256_canonical(value, *, set_like_paths=()) -> str:
    return sha256_text(canonical_json(value, set_like_paths=set_like_paths))
