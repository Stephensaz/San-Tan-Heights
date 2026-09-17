from dataclasses import replace
import pytest
from src.snapshot.dependencies import DependencyManifestBuilder, DependencyManifestError
from tests.unit.snapshot._fixtures import dep

def test_manifest_deduplicates_identical_dependencies_and_sorts_scope():
    d=replace(dep('PROPERTY_IDENTITY','x'),variant_scope=('PUBLIC','AGENT','PUBLIC'))
    out=DependencyManifestBuilder().build((d,d)); assert len(out)==1 and out[0].variant_scope==('AGENT','PUBLIC')

def test_manifest_rejects_conflicting_duplicate():
    a=dep('PROPERTY_IDENTITY','x'); b=replace(a,semantic_fingerprint='c'*64)
    with pytest.raises(DependencyManifestError,match='conflicting duplicate'): DependencyManifestBuilder().build((a,b))

def test_manifest_rejects_unknown_type():
    with pytest.raises(DependencyManifestError,match='unknown dependency type'): DependencyManifestBuilder().build((dep('MAGIC','x'),))
