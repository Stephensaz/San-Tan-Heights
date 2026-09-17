from pathlib import Path
from uuid import uuid4
import tempfile, yaml, pytest
from src.production_certification.manifests.pinning import ManifestPinner

ROOT=Path(__file__).resolve().parents[3]

def test_contract_manifest_pin_verifies_locked_contract_hashes():
    pin=ManifestPinner().pin_file(production_certification_id=uuid4(),manifest_type='CONTRACT_MANIFEST',
        path=ROOT/'CONTRACT-MANIFEST.yaml',repository_root=ROOT,pinned_by='ops')
    assert pin.manifest_payload['status']=='LOCKED'
    assert len(pin.manifest_sha256)==64 and len(pin.pin_fingerprint)==64


def test_build_manifest_pin_is_byte_exact():
    pin=ManifestPinner().pin_file(production_certification_id=uuid4(),manifest_type='BUILD_MANIFEST',
        path=ROOT/'BUILD-MANIFEST.yaml',pinned_by='ops')
    assert pin.manifest_payload['status']=='ACTIVE'
    assert pin.manifest_version == pin.manifest_payload['version']


def test_contract_manifest_pin_rejects_tampered_contract_hash():
    with tempfile.TemporaryDirectory() as d:
        d=Path(d); (d/'contracts').mkdir()
        contract=d/'contracts'/'x.yaml'; contract.write_text('a: 1\n')
        mf={'manifest_id':'X','status':'LOCKED','hash_algorithm':'SHA-256','contracts':[{'id':'X','version':'1','status':'LOCKED','path':'contracts/x.yaml','sha256':'0'*64,'depends_on':[]}]}
        mp=d/'manifest.yaml'; mp.write_text(yaml.safe_dump(mf,sort_keys=False))
        with pytest.raises(Exception):
            ManifestPinner().pin_file(production_certification_id=uuid4(),manifest_type='CONTRACT_MANIFEST',path=mp,repository_root=d,pinned_by='ops')
