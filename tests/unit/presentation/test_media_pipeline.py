from pathlib import Path

import pytest

from src.presentation.media import MediaAssetDescriptor, MediaPipeline, MediaPolicyRegistry

ROOT = Path(__file__).resolve().parents[3]
POLICY = ROOT / "registries" / "presentation" / "media-policy-v1.0.yaml"


def pipeline():
    return MediaPipeline(MediaPolicyRegistry.load(POLICY))


def sample_assets():
    return (
        MediaAssetDescriptor(
            asset_id="public-diagram",
            asset_kind="DIAGRAM",
            content_type="image/svg+xml",
            content_sha256="a" * 64,
            source_reference="diagram:lot-context:1",
            accessibility_text="Schematic lot and context relationship diagram.",
            audiences=frozenset({"AGENT", "SELLER", "PUBLIC"}),
            channels=frozenset({"WEB", "PDF", "PRINT"}),
            caption="Lot and context relationships",
        ),
        MediaAssetDescriptor(
            asset_id="agent-photo",
            asset_kind="IMAGE",
            content_type="image/jpeg",
            content_sha256="b" * 64,
            source_reference="media:agent-photo:1",
            accessibility_text="Property reference photograph.",
            audiences=frozenset({"AGENT"}),
            channels=frozenset({"WEB", "PDF"}),
        ),
    )


def test_media_manifest_is_deterministic_and_policy_bound():
    media = pipeline()
    first = media.build_manifest(reversed(sample_assets()))
    second = media.build_manifest(sample_assets())
    assert [asset.asset_id for asset in first.assets] == ["agent-photo", "public-diagram"]
    assert first.fingerprint == second.fingerprint
    assert first.policy_fingerprint == media.policy.fingerprint


def test_media_eligibility_only_narrows_scope():
    media = pipeline()
    manifest = media.build_manifest(sample_assets())
    public_web = media.eligible(manifest, audience="PUBLIC", channel="WEB")
    assert [asset.asset_id for asset in public_web.assets] == ["public-diagram"]
    agent_web = media.eligible(manifest, audience="AGENT", channel="WEB")
    assert [asset.asset_id for asset in agent_web.assets] == ["agent-photo", "public-diagram"]


def test_media_pipeline_rejects_kind_content_type_mismatch():
    media = pipeline()
    bad = MediaAssetDescriptor(
        asset_id="bad-media",
        asset_kind="IMAGE",
        content_type="application/pdf",
        content_sha256="c" * 64,
        source_reference="media:bad:1",
        accessibility_text="Bad media",
        audiences=frozenset({"AGENT"}),
        channels=frozenset({"WEB"}),
    )
    with pytest.raises(ValueError, match="not allowed"):
        media.build_manifest([bad])


def test_media_pipeline_requires_accessibility_and_provenance():
    with pytest.raises(ValueError, match="source_reference"):
        MediaAssetDescriptor(
            asset_id="missing-source",
            asset_kind="IMAGE",
            content_type="image/png",
            content_sha256="d" * 64,
            source_reference="",
            accessibility_text="Description",
            audiences=frozenset({"AGENT"}),
            channels=frozenset({"WEB"}),
        )
    with pytest.raises(ValueError, match="accessibility_text"):
        MediaAssetDescriptor(
            asset_id="missing-alt",
            asset_kind="IMAGE",
            content_type="image/png",
            content_sha256="e" * 64,
            source_reference="media:missing-alt:1",
            accessibility_text="",
            audiences=frozenset({"AGENT"}),
            channels=frozenset({"WEB"}),
        )


def test_media_pipeline_rejects_duplicate_content_under_multiple_ids():
    media = pipeline()
    first = sample_assets()[0]
    duplicate = MediaAssetDescriptor(
        asset_id="duplicate-diagram",
        asset_kind="DIAGRAM",
        content_type="image/svg+xml",
        content_sha256=first.content_sha256,
        source_reference="diagram:lot-context:duplicate",
        accessibility_text="Duplicate content",
        audiences=frozenset({"AGENT"}),
        channels=frozenset({"WEB"}),
    )
    with pytest.raises(ValueError, match="same media content hash"):
        media.build_manifest([first, duplicate])


def test_media_policy_forbids_fetch_mutation_scope_broadening_and_inference():
    policy = MediaPolicyRegistry.load(POLICY)
    assert policy.rules["allow_remote_fetch"] is False
    assert policy.rules["allow_content_mutation"] is False
    assert policy.rules["allow_scope_broadening"] is False
    assert policy.rules["allow_semantic_inference"] is False
