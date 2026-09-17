from pathlib import Path

import pytest

from src.presentation.media import (
    MediaAssetDescriptor,
    MediaPipeline,
    MediaPolicyRegistry,
    MediaSlotComposer,
    MediaSlotRequest,
)

ROOT = Path(__file__).resolve().parents[3]
POLICY = ROOT / "registries" / "presentation" / "media-policy-v1.0.yaml"


def pipeline():
    return MediaPipeline(MediaPolicyRegistry.load(POLICY))


def asset(asset_id: str, kind: str, content_type: str, *, audiences=None, channels=None):
    return MediaAssetDescriptor(
        asset_id=asset_id,
        asset_kind=kind,
        content_type=content_type,
        content_sha256=(asset_id[0] * 64) if asset_id[0] in "abcdef" else ("a" * 64),
        source_reference=f"source-{asset_id}",
        accessibility_text=f"Accessible description for {asset_id}",
        audiences=frozenset(audiences or {"AGENT", "SELLER", "PUBLIC"}),
        channels=frozenset(channels or {"WEB", "PDF", "PRINT"}),
        caption=f"Caption for {asset_id}",
    )


def manifest():
    p = pipeline()
    return p, p.build_manifest(
        (
            asset("a-image", "IMAGE", "image/png"),
            asset("b-diagram", "DIAGRAM", "image/svg+xml"),
            asset("c-document", "DOCUMENT", "application/pdf", audiences={"AGENT"}),
        )
    )


def test_media_slots_bind_only_eligible_assets_and_preserve_accessibility_text():
    p, m = manifest()
    slots = MediaSlotComposer(p).compose(
        m,
        audience="PUBLIC",
        channel="WEB",
        requests=(
            MediaSlotRequest("hero", "HERO_IMAGE", "a-image"),
            MediaSlotRequest("lot-context", "CONTEXT_DIAGRAM", "b-diagram"),
        ),
    )
    assert [slot.slot_id for slot in slots.slots] == ["hero", "lot-context"]
    assert slots.slots[0].accessibility_text == "Accessible description for a-image"
    assert len(slots.fingerprint) == 64


def test_media_slots_reject_asset_outside_audience_scope():
    p, m = manifest()
    with pytest.raises(ValueError, match="not eligible"):
        MediaSlotComposer(p).compose(
            m,
            audience="PUBLIC",
            channel="WEB",
            requests=(MediaSlotRequest("document", "SUPPORTING_DOCUMENT", "c-document"),),
        )


def test_media_slots_reject_kind_mismatch():
    p, m = manifest()
    with pytest.raises(ValueError, match="requires DIAGRAM"):
        MediaSlotComposer(p).compose(
            m,
            audience="PUBLIC",
            channel="WEB",
            requests=(MediaSlotRequest("context", "CONTEXT_DIAGRAM", "a-image"),),
        )


def test_media_slots_reject_duplicate_slot_or_asset_binding():
    p, m = manifest()
    composer = MediaSlotComposer(p)
    with pytest.raises(ValueError, match="duplicate media slot_id"):
        composer.compose(
            m,
            audience="PUBLIC",
            channel="WEB",
            requests=(
                MediaSlotRequest("hero", "HERO_IMAGE", "a-image"),
                MediaSlotRequest("hero", "INLINE_IMAGE", "a-image"),
            ),
        )


def test_media_slot_fingerprint_is_deterministic():
    p, m = manifest()
    request = (MediaSlotRequest("hero", "HERO_IMAGE", "a-image"),)
    composer = MediaSlotComposer(p)
    assert composer.compose(m, audience="PUBLIC", channel="WEB", requests=request).fingerprint == composer.compose(
        m, audience="PUBLIC", channel="WEB", requests=request
    ).fingerprint
