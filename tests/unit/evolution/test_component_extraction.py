from pathlib import Path
import hashlib
import pytest
from src.evolution.component_extraction import (
    load_extraction_registry,classify_path,inventory_repository,require_clean_inventory,assert_baseline_preserved
)
from src.platform_config.community import load_community_config

R="registries/evolution/m10-002-core-config-extraction-v1.0.yaml"
C="config/communities/san_tan_heights-v1.0.yaml"
B="certification-evidence/m10-001/san-tan-heights-production-baseline-v1.0.0.json"

def registry(): return load_extraction_registry(R)

def test_explicit_san_tan_heights_config_loads():
    c=load_community_config(C)
    assert c.community_id=="SAN_TAN_HEIGHTS"
    assert c.county=="Pinal"
    assert c.listing_service=="ARMLS"
    assert c.property_id_prefix=="STH-"

def test_known_paths_classify_deterministically():
    r=registry()
    assert classify_path("src/shared/hash.py",r)[0]=="CORE_REUSABLE"
    assert classify_path("src/activation/corpus.py",r)[0]=="COMMUNITY_SPECIFIC"
    assert classify_path("registries/activation/m9-001-source-candidates-v1.0.yaml",r)[0]=="COMMUNITY_SPECIFIC"
    assert classify_path("templates/example.html",r)[0]=="COMMUNITY_CONFIGURABLE"

def test_residual_san_tan_heights_runtime_files_are_explicitly_community_specific():
    r=registry()
    expected=(
        "src/presentation/branding/runtime.py",
        "src/presentation/golden_fixtures/loader.py",
        "src/renderer/adapters/pdf.py",
        "src/report_builder/payload/builder.py",
    )
    for path in expected:
        assert classify_path(path,r)[0]=="COMMUNITY_SPECIFIC"

def test_unclassified_path_fails_closed():
    with pytest.raises(ValueError,match="unclassified"): classify_path("src/mystery/x.py",registry())

def test_core_marker_violation_is_detected(tmp_path):
    (tmp_path/"src/shared").mkdir(parents=True)
    (tmp_path/"src/shared/x.py").write_text('COMMUNITY = "SAN_TAN_HEIGHTS"')
    r=registry(); r["declared_scope"]=["src"]
    audit=inventory_repository(tmp_path,r)
    assert audit.core_marker_violations==("src/shared/x.py",)
    with pytest.raises(ValueError,match="hidden in reusable core"): require_clean_inventory(audit)

def test_community_specific_marker_is_allowed(tmp_path):
    (tmp_path/"src/activation").mkdir(parents=True)
    (tmp_path/"src/activation/x.py").write_text('COMMUNITY = "SAN_TAN_HEIGHTS"')
    r=registry(); r["declared_scope"]=["src"]
    audit=inventory_repository(tmp_path,r)
    assert not audit.core_marker_violations

def test_inventory_fingerprint_is_deterministic(tmp_path):
    (tmp_path/"src/shared").mkdir(parents=True)
    (tmp_path/"src/shared/x.py").write_text("VALUE = 1")
    r=registry(); r["declared_scope"]=["src"]
    assert inventory_repository(tmp_path,r).inventory_fingerprint==inventory_repository(tmp_path,r).inventory_fingerprint

def test_baseline_is_preserved():
    fp=hashlib.sha256(Path(B).read_bytes()).hexdigest()
    assert_baseline_preserved(frozen_fingerprint=fp,current_baseline_path=B)

def test_mutated_baseline_fails(tmp_path):
    raw=Path(B).read_bytes(); p=tmp_path/"baseline.json"; p.write_bytes(raw+b" ")
    fp=hashlib.sha256(raw).hexdigest()
    with pytest.raises(ValueError,match="baseline changed"): assert_baseline_preserved(frozen_fingerprint=fp,current_baseline_path=p)

def test_actual_repository_declared_scope_is_fully_classified():
    audit=inventory_repository(
        ".",
        registry(),
        exclude_prefixes=(
            "src/seller_intelligence/",
            "contracts/seller_intelligence/",
            "registries/seller_intelligence/",
        ),
    )
    assert audit.unclassified==()
    assert audit.ambiguous==()
    assert audit.core_marker_violations==()
    assert len(audit.classified)>0


def test_post_release_scope_exclusion_is_explicit_and_narrow(tmp_path):
    (tmp_path/"src/seller_intelligence").mkdir(parents=True)
    (tmp_path/"src/seller_intelligence/new.py").write_text("VALUE = 1")
    (tmp_path/"src/mystery").mkdir(parents=True)
    (tmp_path/"src/mystery/x.py").write_text("VALUE = 2")
    r=registry()
    r["declared_scope"]=["src"]
    audit=inventory_repository(
        tmp_path,
        r,
        exclude_prefixes=("src/seller_intelligence/",),
    )
    assert audit.unclassified==("src/mystery/x.py",)
