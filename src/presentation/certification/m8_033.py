from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Callable

import yaml

from src.presentation.accessibility import AccessibilityRuntimeRegistry
from src.presentation.audience import AudiencePresentationPolicies
from src.presentation.golden_fixtures import GoldenFixtureLoader, GoldenFixtureSet, VisualBaselineManifest
from src.presentation.package import PresentationAudience
from src.presentation.routing import PropertyRoutingRegistry, StablePropertyRouter
from src.presentation.visual_regression import VisualRegressionRegistry
from src.shared.canonical_json import canonical_json


@dataclass(frozen=True)
class EvidenceRecord:
    key: str
    passed: bool
    details: tuple[str, ...]

    def canonical_payload(self) -> dict[str, object]:
        return {"key": self.key, "passed": self.passed, "details": list(self.details)}

    @property
    def fingerprint(self) -> str:
        return sha256(canonical_json(self.canonical_payload()).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class CertificationBundle:
    certification_id: str
    source_commit: str
    source_hashes: dict[str, str]
    layers: tuple[EvidenceRecord, ...]
    stage_gates: tuple[EvidenceRecord, ...]
    acceptance_criteria: tuple[EvidenceRecord, ...]
    open_defects: tuple[str, ...]
    waivers: tuple[str, ...]
    verdict: str

    def canonical_payload(self) -> dict[str, object]:
        return {
            "certification_id": self.certification_id,
            "source_commit": self.source_commit,
            "source_hashes": dict(sorted(self.source_hashes.items())),
            "layers": [item.canonical_payload() for item in self.layers],
            "stage_gates": [item.canonical_payload() for item in self.stage_gates],
            "acceptance_criteria": [item.canonical_payload() for item in self.acceptance_criteria],
            "open_defects": list(self.open_defects),
            "waivers": list(self.waivers),
            "verdict": self.verdict,
        }

    @property
    def evidence_hash(self) -> str:
        return sha256(canonical_json(self.canonical_payload()).encode("utf-8")).hexdigest()


class M8033CertificationRunner:
    """Frozen M8-033 A→J certification runner.

    This runner certifies the accepted M8-032 candidate. It does not repair,
    rewrite, waive, or add presentation capabilities. Missing required evidence
    is a certification failure owned by the upstream layer.
    """

    def __init__(self, repository_root: str | Path, manifest_path: str | Path) -> None:
        self.root = Path(repository_root)
        self.manifest_path = Path(manifest_path)
        self.manifest = yaml.safe_load(self.manifest_path.read_text())
        self._validate_manifest()

    def run(self, *, verify_source_commit: bool = True) -> CertificationBundle:
        source_hashes = self._source_hashes(verify_source_commit=verify_source_commit)
        fixture_set = self._fixtures()

        layers: list[EvidenceRecord] = []
        layers.append(self._layer_a(source_hashes, fixture_set))
        if not layers[-1].passed:
            return self._adjudicate(source_hashes, tuple(layers), fixture_set)

        layers.append(self._layer_b())
        if not layers[-1].passed:
            return self._adjudicate(source_hashes, tuple(layers), fixture_set)

        layers.append(self._audience_layer("C", PresentationAudience.AGENT, fixture_set))
        layers.append(self._audience_layer("D", PresentationAudience.SELLER, fixture_set))
        layers.append(self._audience_layer("E", PresentationAudience.PUBLIC, fixture_set))
        layers.append(self._layer_f(fixture_set))
        layers.append(self._layer_g(fixture_set))
        layers.append(self._layer_h(fixture_set))
        layers.append(self._layer_i(source_hashes, fixture_set, tuple(layers)))

        return self._adjudicate(source_hashes, tuple(layers), fixture_set)

    def _validate_manifest(self) -> None:
        if self.manifest.get("certification_id") != "STH-M8-033-PRESENTATION-INTEGRATION-v1.0":
            raise ValueError("unexpected M8-033 certification id")
        if str(self.manifest.get("version")) != "1.0.0":
            raise ValueError("unexpected M8-033 certification version")
        if self.manifest.get("status") != "LOCKED":
            raise ValueError("M8-033 certification manifest must be LOCKED")
        layers = self.manifest.get("layers") or {}
        if tuple(layers) != tuple("ABCDEFGHIJ"):
            raise ValueError("M8-033 certification layers must be exactly A through J")
        gates = self.manifest.get("stage_gates") or {}
        if tuple(gates) != tuple("ABCDEFGHIJKL"):
            raise ValueError("M8-033 stage gates must be exactly A through L")
        criteria = self.manifest.get("acceptance_criteria") or []
        if len(criteria) != 12 or len(set(criteria)) != 12:
            raise ValueError("M8-033 requires exactly 12 unique integration acceptance criteria")
        rules = self.manifest.get("final_rules") or {}
        if rules.get("allow_waivers") is not False or rules.get("allow_conditional_go") is not False:
            raise ValueError("M8-033 does not allow waivers or conditional GO")

    def _source_hashes(self, *, verify_source_commit: bool) -> dict[str, str]:
        source = self.manifest["source_candidate"]["commit_sha"]
        hashes: dict[str, str] = {}
        for path in self.manifest.get("required_source_paths") or ():
            current = (self.root / path).read_bytes()
            current_hash = sha256(current).hexdigest()
            if verify_source_commit:
                try:
                    frozen = subprocess.check_output(
                        ["git", "show", f"{source}:{path}"],
                        cwd=self.root,
                    )
                except (subprocess.CalledProcessError, FileNotFoundError) as exc:
                    raise ValueError(f"cannot load frozen M8-032 source path: {path}") from exc
                frozen_hash = sha256(frozen).hexdigest()
                if current_hash != frozen_hash:
                    raise ValueError(f"M8-032 source drift detected: {path}")
            hashes[path] = current_hash
        return hashes

    def _fixtures(self) -> GoldenFixtureSet:
        path = self.root / self.manifest["source_candidate"]["fixture_manifest"]
        return GoldenFixtureLoader(self.root).load(path)

    def _layer_a(self, source_hashes: dict[str, str], fixture_set: GoldenFixtureSet) -> EvidenceRecord:
        problems: list[str] = []
        for number in range(1, 33):
            path = self.root / "docs" / "implementation" / f"M8-{number:03d}.md"
            if not path.exists():
                problems.append(f"missing accepted implementation record M8-{number:03d}")
                continue
            if "Status: ACCEPTED" not in path.read_text():
                problems.append(f"M8-{number:03d} is not ACCEPTED")
        if len(source_hashes) != len(self.manifest.get("required_source_paths") or ()):
            problems.append("source hash coverage incomplete")
        if len(fixture_set.fixtures) != 16:
            problems.append("golden fixture membership is not exactly 16")
        details = (
            f"source_sha={self.manifest['source_candidate']['commit_sha']}",
            f"source_paths_hashed={len(source_hashes)}",
            f"fixture_count={len(fixture_set.fixtures)}",
            f"fixture_set_hash={fixture_set.fixture_set_fingerprint}",
        ) + tuple(problems)
        return EvidenceRecord("A", not problems, details)

    def _layer_b(self) -> EvidenceRecord:
        problems: list[str] = []
        first = self._fixtures()
        second = self._fixtures()
        if first.fixture_set_fingerprint != second.fixture_set_fingerprint:
            problems.append("clean baseline is not deterministic")

        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            self._copy_fixture_package(temp_root)
            manifest_path = temp_root / "manifest.yaml"
            manifest = yaml.safe_load(
                (self.root / self.manifest["source_candidate"]["fixture_manifest"]).read_text()
            )
            manifest.update(
                {
                    "schema": "schema.json",
                    "truth_set": "fixtures.json",
                    "expected_set": "expected.json",
                    "coverage_matrix": "coverage.yaml",
                }
            )
            manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False))

            truth_path = temp_root / "fixtures.json"
            truth = json.loads(truth_path.read_text())
            truth["fixtures"][0]["property"]["apn"] = "SYNTHETIC-BUT-PROHIBITED"
            truth_path.write_text(json.dumps(truth))
            try:
                GoldenFixtureLoader(temp_root).load(manifest_path)
                problems.append("corrupted fixture negative control did not fail")
            except ValueError:
                pass

            truth_path.write_text(
                (self.root / "tests/fixtures/presentation/golden/fixtures.json").read_text()
            )
            manifest["status"] = "UNLOCKED"
            manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False))
            try:
                GoldenFixtureLoader(temp_root).load(manifest_path)
                problems.append("failed-prerequisite negative control did not fail")
            except ValueError:
                pass

        return EvidenceRecord(
            "B",
            not problems,
            (
                f"baseline_hash={first.fixture_set_fingerprint}",
                "corrupted_fixture_negative_control=PASS" if not problems else "negative_control_problem",
                "failed_prerequisite_negative_control=PASS" if not problems else "negative_control_problem",
            )
            + tuple(problems),
        )

    def _copy_fixture_package(self, temp_root: Path) -> None:
        copies = {
            "schema.json": "schemas/presentation/golden-fixture-v1.0.schema.json",
            "fixtures.json": "tests/fixtures/presentation/golden/fixtures.json",
            "expected.json": "tests/fixtures/presentation/golden/expected.json",
            "coverage.yaml": "tests/fixtures/presentation/golden/coverage-matrix.yaml",
        }
        for dest, source in copies.items():
            shutil.copyfile(self.root / source, temp_root / dest)

    def _audience_layer(
        self,
        key: str,
        audience: PresentationAudience,
        fixture_set: GoldenFixtureSet,
    ) -> EvidenceRecord:
        policies = AudiencePresentationPolicies.from_repository(self.root)
        policy = policies.for_audience(audience)
        problems: list[str] = []
        for fixture in fixture_set.fixtures:
            projection = fixture.payload["audience_projection"][audience.value]
            if not policy.allows(
                classification=projection["classification"],
                publication_scope=projection["publication_scope"],
            ):
                problems.append(f"{fixture.fixture_id}: governed projection not allowed")
            expected = fixture.expected[audience.value]
            if audience in (PresentationAudience.SELLER, PresentationAudience.PUBLIC):
                if expected.get("diagnostics_visible") is not False:
                    problems.append(f"{fixture.fixture_id}: diagnostics leakage")
                if expected.get("private_lineage_visible") is not False:
                    problems.append(f"{fixture.fixture_id}: private lineage leakage")
        return EvidenceRecord(
            key,
            not problems,
            (f"audience={audience.value}", f"fixtures_certified={len(fixture_set.fixtures)}")
            + tuple(problems),
        )

    def _layer_f(self, fixture_set: GoldenFixtureSet) -> EvidenceRecord:
        problems: list[str] = []
        policies = AudiencePresentationPolicies.from_repository(self.root)
        seller = policies.for_audience(PresentationAudience.SELLER)
        public = policies.for_audience(PresentationAudience.PUBLIC)

        if seller.allows(classification="AGENT_INTERNAL", publication_scope="AGENT"):
            problems.append("Seller policy admits Agent-only content")
        if public.allows(classification="AGENT_INTERNAL", publication_scope="AGENT"):
            problems.append("Public policy admits Agent-only content")
        if public.allows(classification="SELLER_DATA", publication_scope="SELLER"):
            problems.append("Public policy admits Seller-only content")

        privacy = fixture_set.by_id("SYNTH-PRIVACY_ADVERSARIAL-001")
        public_forbidden = set(privacy.expected["PUBLIC"].get("forbidden_tokens") or ())
        seller_forbidden = set(privacy.expected["SELLER"].get("forbidden_tokens") or ())
        if not {"owner_name", "apn", "mls_number", "private_note"} <= public_forbidden:
            problems.append("Public privacy canary coverage incomplete")
        if not {"private_note", "agent_diagnostic"} <= seller_forbidden:
            problems.append("Seller privacy canary coverage incomplete")

        return EvidenceRecord(
            "F",
            not problems,
            (
                "agent_to_seller_isolation=checked",
                "agent_to_public_isolation=checked",
                "seller_to_public_isolation=checked",
                "privacy_canaries=checked",
            )
            + tuple(problems),
        )

    def _layer_g(self, fixture_set: GoldenFixtureSet) -> EvidenceRecord:
        problems: list[str] = []
        historical = fixture_set.by_id("SYNTH-HISTORICAL-001")
        changed = fixture_set.by_id("SYNTH-CHANGE-001")
        stale = fixture_set.by_id("SYNTH-STALE-001")
        if historical.expected["PUBLIC"].get("expected_report_designation") != "HISTORICAL":
            problems.append("historical replay designation missing")
        if changed.expected["PUBLIC"].get("what_changed_required") is not True:
            problems.append("change replay expectation missing")
        if stale.expected["PUBLIC"].get("expected_freshness_state") != "STALE":
            problems.append("stale replay expectation missing")
        replay = GoldenFixtureLoader(self.root).load(
            self.root / self.manifest["source_candidate"]["fixture_manifest"]
        )
        if replay.fixture_set_fingerprint != fixture_set.fixture_set_fingerprint:
            problems.append("fixture replay fingerprint drift")
        return EvidenceRecord(
            "G",
            not problems,
            (
                "historical_replay=checked",
                "what_changed_replay=checked",
                "stale_state_replay=checked",
                f"replay_hash={replay.fixture_set_fingerprint}",
            )
            + tuple(problems),
        )

    def _layer_h(self, fixture_set: GoldenFixtureSet) -> EvidenceRecord:
        problems: list[str] = []
        routing = StablePropertyRouter(
            PropertyRoutingRegistry.load(
                self.root / "registries/presentation/property-routing-v1.0.yaml"
            )
        )
        synthetic_uuid = "11111111-1111-1111-1111-111111111111"
        for audience in PresentationAudience:
            route = routing.build(synthetic_uuid, audience)
            if routing.resolve(route.path) != route:
                problems.append(f"{audience.value}: route round-trip mismatch")
            if "version" in route.path or "hash" in route.path:
                problems.append(f"{audience.value}: mutable data embedded in stable route")

        accessibility = AccessibilityRuntimeRegistry.load(
            self.root / "registries/presentation/accessibility-runtime-v1.0.yaml"
        )
        if accessibility.status != "LOCKED":
            problems.append("accessibility runtime is not locked")

        for fixture in fixture_set.fixtures:
            render = fixture.expected.get("render") or {}
            if not all(render.get(name) is True for name in ("web", "pdf", "print")):
                problems.append(f"{fixture.fixture_id}: cross-surface expectations incomplete")

        return EvidenceRecord(
            "H",
            not problems,
            (
                "stable_routes=AGENT,SELLER,PUBLIC",
                "web_pdf_print_expectations=checked",
                f"accessibility_registry={accessibility.fingerprint}",
            )
            + tuple(problems),
        )

    def _layer_i(
        self,
        source_hashes: dict[str, str],
        fixture_set: GoldenFixtureSet,
        prior_layers: tuple[EvidenceRecord, ...],
    ) -> EvidenceRecord:
        problems: list[str] = []
        first = self._replay_hash(source_hashes, fixture_set, prior_layers)
        replay_fixture_set = self._fixtures()
        second = self._replay_hash(source_hashes, replay_fixture_set, prior_layers)
        if first != second:
            problems.append("full-chain replay evidence hash drift")

        visual_root = self.root / self.manifest["visual_evidence"]["baseline_root"]
        baseline_path = visual_root / "m8-032" / "manifest.yaml"
        visual_registry = VisualRegressionRegistry.load(
            self.root / self.manifest["source_candidate"]["visual_registry"]
        )
        try:
            baseline = VisualBaselineManifest.load(
                baseline_path,
                fixture_set=fixture_set,
                visual_registry=visual_registry,
            )
        except (OSError, ValueError) as exc:
            baseline = None
            problems.append(f"visual baseline manifest validation failed: {exc}")

        required_targets = set(self.manifest["visual_evidence"]["required_targets"])
        if required_targets != set(visual_registry.targets):
            problems.append("visual target coverage does not match the locked M8-031 registry")
        if baseline is not None and required_targets != set(baseline.targets):
            problems.append("approved visual baseline target coverage mismatch")

        return EvidenceRecord(
            "I",
            not problems,
            (
                f"replay_hash_1={first}",
                f"replay_hash_2={second}",
                f"visual_baseline_fingerprint={baseline.fingerprint if baseline else 'INVALID'}",
                f"visual_runtime_fingerprint={visual_registry.fingerprint}",
            )
            + tuple(problems),
        )

    def _replay_hash(
        self,
        source_hashes: dict[str, str],
        fixture_set: GoldenFixtureSet,
        layers: tuple[EvidenceRecord, ...],
    ) -> str:
        payload = {
            "source_hashes": dict(sorted(source_hashes.items())),
            "fixture_set": fixture_set.fixture_set_fingerprint,
            "layers": [item.canonical_payload() for item in layers if item.key != "I"],
        }
        return sha256(canonical_json(payload).encode("utf-8")).hexdigest()

    def _adjudicate(
        self,
        source_hashes: dict[str, str],
        layers: tuple[EvidenceRecord, ...],
        fixture_set: GoldenFixtureSet,
    ) -> CertificationBundle:
        stage_gates = self._stage_gates(layers, fixture_set)
        criteria = self._acceptance_criteria(layers, stage_gates)
        defects = tuple(
            f"{item.key}: {detail}"
            for item in (*layers, *stage_gates, *criteria)
            if not item.passed
            for detail in item.details
            if "missing" in detail.lower()
            or "drift" in detail.lower()
            or "leak" in detail.lower()
            or "problem" in detail.lower()
            or "incomplete" in detail.lower()
            or "not " in detail.lower()
        )
        all_layers = {item.key: item for item in layers}
        required_layer_keys = tuple("ABCDEFGHI")
        layer_complete = all(key in all_layers and all_layers[key].passed for key in required_layer_keys)
        gate_complete = len(stage_gates) == 12 and all(item.passed for item in stage_gates)
        criteria_complete = len(criteria) == 12 and all(item.passed for item in criteria)
        verdict = (
            self.manifest["final_rules"]["verdicts"]["pass"]
            if layer_complete and gate_complete and criteria_complete and not defects
            else self.manifest["final_rules"]["verdicts"]["fail"]
        )
        j = EvidenceRecord(
            "J",
            verdict == self.manifest["final_rules"]["verdicts"]["pass"],
            (
                f"layers_passed={sum(item.passed for item in layers)}/{len(layers)}",
                f"stage_gates_passed={sum(item.passed for item in stage_gates)}/12",
                f"criteria_passed={sum(item.passed for item in criteria)}/12",
                f"open_defects={len(defects)}",
                f"verdict={verdict}",
            ),
        )
        return CertificationBundle(
            certification_id=self.manifest["certification_id"],
            source_commit=self.manifest["source_candidate"]["commit_sha"],
            source_hashes=source_hashes,
            layers=layers + (j,),
            stage_gates=stage_gates,
            acceptance_criteria=criteria,
            open_defects=defects,
            waivers=(),
            verdict=verdict,
        )

    def _stage_gates(
        self,
        layers: tuple[EvidenceRecord, ...],
        fixture_set: GoldenFixtureSet,
    ) -> tuple[EvidenceRecord, ...]:
        passed = {item.key: item.passed for item in layers}
        responsive = fixture_set.by_id("SYNTH-RESPONSIVE-001")
        required_viewports = responsive.expected["render"].get("required_viewports") or []
        accessibility = fixture_set.by_id("SYNTH-ACCESSIBILITY-001")
        visual_registry = VisualRegressionRegistry.load(
            self.root / self.manifest["source_candidate"]["visual_registry"]
        )
        try:
            baseline = VisualBaselineManifest.load(
                self.root / self.manifest["visual_evidence"]["baseline_root"] / "m8-032" / "manifest.yaml",
                fixture_set=fixture_set,
                visual_registry=visual_registry,
            )
            baseline_valid = True
        except (OSError, ValueError):
            baseline_valid = False

        gate_values = {
            "A": passed.get("A", False),
            "B": passed.get("C", False) and passed.get("D", False) and passed.get("E", False),
            "C": passed.get("C", False) and passed.get("D", False) and passed.get("E", False),
            "D": passed.get("F", False),
            "E": passed.get("H", False),
            "F": len(required_viewports) == 5,
            "G": accessibility.expected["accessibility"].get("semantic_order_required") is True,
            "H": all(
                all((fixture.expected.get("render") or {}).get(name) is True for name in ("pdf", "print"))
                for fixture in fixture_set.fixtures
            ),
            "I": passed.get("I", False) and baseline_valid,
            "J": passed.get("H", False) and passed.get("G", False),
            "K": passed.get("B", False) and passed.get("H", False),
            "L": all(passed.get(key, False) for key in tuple("ABCDEFGH")) and passed.get("I", False),
        }
        return tuple(
            EvidenceRecord(
                key,
                gate_values[key],
                (self.manifest["stage_gates"][key],),
            )
            for key in tuple("ABCDEFGHIJKL")
        )

    def _acceptance_criteria(
        self,
        layers: tuple[EvidenceRecord, ...],
        gates: tuple[EvidenceRecord, ...],
    ) -> tuple[EvidenceRecord, ...]:
        passed = {item.key: item.passed for item in layers}
        gate = {item.key: item.passed for item in gates}
        values = (
            passed.get("C", False) and passed.get("D", False) and passed.get("E", False),
            passed.get("F", False),
            gate.get("E", False),
            gate.get("C", False),
            passed.get("C", False) and passed.get("D", False) and passed.get("E", False),
            gate.get("H", False),
            passed.get("G", False),
            passed.get("H", False),
            gate.get("G", False),
            gate.get("I", False),
            passed.get("I", False),
            all(item.passed for item in gates),
        )
        return tuple(
            EvidenceRecord(criteria_id, bool(value), ())
            for criteria_id, value in zip(self.manifest["acceptance_criteria"], values, strict=True)
        )


def write_bundle(bundle: CertificationBundle, output: str | Path) -> None:
    path = Path(output)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = bundle.canonical_payload() | {"evidence_hash": bundle.evidence_hash}
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
