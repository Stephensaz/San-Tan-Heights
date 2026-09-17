from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED = [
    "README.md", "CHANGELOG.md", "VERSION", "ARCHITECTURE-LOCK.yaml",
    "CONTRACT-MANIFEST.yaml", "BUILD-MANIFEST.yaml", "contracts", "schemas",
    "registries", "database", "src", "workers", "web", "templates", "tests",
    "synthetic", "ops", "docs"
]


def test_required_repository_entries_exist():
    missing = [name for name in REQUIRED if not (ROOT / name).exists()]
    assert not missing, f"Missing repository entries: {missing}"


def test_version_is_valid_semver():
    version = (ROOT / "VERSION").read_text().strip()
    parts = version.split(".")
    assert len(parts) == 3
    assert all(part.isdigit() for part in parts)
