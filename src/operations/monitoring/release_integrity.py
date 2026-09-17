from .models import IntegrityFinding
class ReleaseIntegritySweep:
    def evaluate(self, *, release, manifest, items):
        out=[]
        if len(items)!=release.total_item_count:
            out.append(IntegrityFinding('RELEASE_ITEM_COUNT_MATCH','release',release.release_id,'FAIL',f'expected {release.total_item_count} items, found {len(items)}'))
        if manifest is None or manifest.manifest_fingerprint!=release.manifest_fingerprint or manifest.membership_fingerprint!=release.membership_fingerprint:
            out.append(IntegrityFinding('RELEASE_MANIFEST_MATCH','release',release.release_id,'FAIL','frozen manifest fingerprints do not match release'))
        return tuple(out)
