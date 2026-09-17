from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
required = [
    "README.md", "CHANGELOG.md", "VERSION", "ARCHITECTURE-LOCK.yaml",
    "CONTRACT-MANIFEST.yaml", "BUILD-MANIFEST.yaml", "IMPLEMENTATION-BACKLOG.yaml",
    "contracts", "schemas", "registries", "database", "src", "workers",
    "web", "templates", "tests", "synthetic", "ops", "docs"
]
missing = [p for p in required if not (ROOT / p).exists()]
if missing:
    print("FAIL: missing", missing)
    sys.exit(1)
print("PASS: repository bootstrap structure is present")
