from datetime import datetime, timezone, timedelta
from decimal import Decimal
import pytest
from src.shared.canonical_json import canonical_json
from src.shared.hash import sha256_canonical

def test_key_order_does_not_change_hash():
    a={"b":2,"a":1}
    b={"a":1,"b":2}
    assert canonical_json(a) == '{"a":1,"b":2}'
    assert sha256_canonical(a) == sha256_canonical(b)

def test_semantic_change_changes_hash():
    assert sha256_canonical({"a":1}) != sha256_canonical({"a":2})

def test_timezone_equivalent_datetimes_match():
    a=datetime(2026,9,16,18,0,tzinfo=timezone.utc)
    b=datetime(2026,9,16,11,0,tzinfo=timezone(timedelta(hours=-7)))
    assert canonical_json(a) == canonical_json(b)

def test_decimal_normalization():
    assert canonical_json({"n":Decimal("1.2300")}) == '{"n":1.23}'
    assert canonical_json({"n":Decimal("-0.000")}) == '{"n":0}'

def test_nonfinite_numbers_rejected():
    with pytest.raises(ValueError):
        canonical_json({"n":float("nan")})

def test_set_like_path_sorting():
    value={"tags":["z","a"]}
    assert canonical_json(value,set_like_paths={"/tags"}) == '{"tags":["a","z"]}'
