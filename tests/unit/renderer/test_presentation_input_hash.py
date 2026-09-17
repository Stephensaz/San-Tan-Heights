import pytest
from src.renderer.hashing import PresentationDependency, PresentationInputHashEngine, PresentationInputHashError


def dep(kind='TEMPLATE', ident='PROPERTY_REPORT', fp='c'*64, version='1.0.0', slot=None):
    return PresentationDependency(kind,ident,fp,version,slot)

def calculate(**overrides):
    values=dict(
        report_id='11111111-1111-1111-1111-111111111111', render_type='WEB',
        canonical_report_payload_hash='a'*64, report_input_hash='b'*64,
        render_contract_version='1.0.0', template_id='PROPERTY_REPORT',
        template_version='1.0.0', renderer_version='1.0.0', dependencies=[dep()],
    )
    values.update(overrides)
    return PresentationInputHashEngine().calculate(**values)

def test_equivalent_inputs_hash_identically_regardless_dependency_order():
    a=dep('BRANDING','DEFAULT','d'*64,'1.0.0')
    b=dep('TEMPLATE','PROPERTY_REPORT','c'*64,'1.0.0')
    assert calculate(dependencies=[a,b]).presentation_input_hash == calculate(dependencies=[b,a]).presentation_input_hash

def test_template_or_renderer_change_changes_presentation_hash():
    base=calculate().presentation_input_hash
    assert calculate(template_version='1.0.1').presentation_input_hash != base
    assert calculate(renderer_version='1.0.1').presentation_input_hash != base

def test_render_type_changes_hash_without_changing_report_semantic_identity():
    web=calculate(render_type='WEB')
    pdf=calculate(render_type='PDF')
    assert web.presentation_input_hash != pdf.presentation_input_hash
    assert web.semantic_projection['report_input_hash'] == pdf.semantic_projection['report_input_hash'] == 'b'*64

def test_dependency_fingerprint_change_changes_hash():
    assert calculate(dependencies=[dep(fp='c'*64)]).presentation_input_hash != calculate(dependencies=[dep(fp='d'*64)]).presentation_input_hash

def test_operational_metadata_is_not_accepted_or_projected():
    identity=calculate()
    assert 'created_at' not in identity.semantic_projection
    assert 'worker_id' not in identity.semantic_projection
    assert 'render_version' not in identity.semantic_projection

def test_duplicate_dependency_key_fails_closed():
    with pytest.raises(PresentationInputHashError): calculate(dependencies=[dep(),dep(fp='d'*64)])

def test_bad_hash_fails_closed():
    with pytest.raises(PresentationInputHashError): calculate(report_input_hash='bad')
