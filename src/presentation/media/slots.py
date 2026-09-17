from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import re
from typing import Iterable

from src.presentation.media.pipeline import MediaManifest, MediaPipeline
from src.shared.canonical_json import canonical_json

_SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_SLOT_KIND = {
    "HERO_IMAGE": "IMAGE",
    "INLINE_IMAGE": "IMAGE",
    "CONTEXT_DIAGRAM": "DIAGRAM",
    "SUPPORTING_DOCUMENT": "DOCUMENT",
}


@dataclass(frozen=True)
class MediaSlotRequest:
    slot_id: str
    slot_type: str
    asset_id: str

    def __post_init__(self) -> None:
        if not _SLUG.fullmatch(self.slot_id):
            raise ValueError("media slot_id must be a lowercase slug")
        if self.slot_type not in _SLOT_KIND:
            raise ValueError(f"unsupported media slot type: {self.slot_type}")
        if not _SLUG.fullmatch(self.asset_id):
            raise ValueError("media slot asset_id must be a lowercase slug")


@dataclass(frozen=True)
class MediaSlotView:
    slot_id: str
    slot_type: str
    asset_id: str
    asset_kind: str
    content_type: str
    content_sha256: str
    accessibility_text: str
    caption: str | None


@dataclass(frozen=True)
class MediaSlotSet:
    audience: str
    channel: str
    media_manifest_fingerprint: str
    slots: tuple[MediaSlotView, ...]

    def canonical_payload(self) -> dict[str, object]:
        return {
            "audience": self.audience,
            "channel": self.channel,
            "media_manifest_fingerprint": self.media_manifest_fingerprint,
            "slots": [slot.__dict__ for slot in self.slots],
        }

    @property
    def fingerprint(self) -> str:
        return sha256(canonical_json(self.canonical_payload()).encode("utf-8")).hexdigest()


class MediaSlotComposer:
    """Binds governed eligible media into deterministic presentation slots."""

    def __init__(self, pipeline: MediaPipeline) -> None:
        self.pipeline = pipeline

    def compose(
        self,
        manifest: MediaManifest,
        *,
        audience: str,
        channel: str,
        requests: Iterable[MediaSlotRequest],
    ) -> MediaSlotSet:
        eligible = self.pipeline.eligible(manifest, audience=audience, channel=channel)
        assets = {asset.asset_id: asset for asset in eligible.assets}
        items = tuple(requests)

        seen_slots: set[str] = set()
        seen_assets: set[str] = set()
        views: list[MediaSlotView] = []
        for request in items:
            if request.slot_id in seen_slots:
                raise ValueError(f"duplicate media slot_id: {request.slot_id}")
            seen_slots.add(request.slot_id)
            if request.asset_id in seen_assets:
                raise ValueError(f"media asset cannot be bound to multiple slots: {request.asset_id}")
            seen_assets.add(request.asset_id)

            asset = assets.get(request.asset_id)
            if asset is None:
                raise ValueError(f"media asset is not eligible for requested audience/channel: {request.asset_id}")
            required_kind = _SLOT_KIND[request.slot_type]
            if asset.asset_kind != required_kind:
                raise ValueError(
                    f"media slot {request.slot_type} requires {required_kind}, got {asset.asset_kind}"
                )

            views.append(
                MediaSlotView(
                    slot_id=request.slot_id,
                    slot_type=request.slot_type,
                    asset_id=asset.asset_id,
                    asset_kind=asset.asset_kind,
                    content_type=asset.content_type,
                    content_sha256=asset.content_sha256,
                    accessibility_text=asset.accessibility_text,
                    caption=asset.caption,
                )
            )

        ordered = tuple(sorted(views, key=lambda item: item.slot_id))
        return MediaSlotSet(
            audience=audience,
            channel=channel,
            media_manifest_fingerprint=eligible.fingerprint,
            slots=ordered,
        )
