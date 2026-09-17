from uuid import uuid4
import pytest
from src.renderer.repository import RenderDependency, RenderRepository, RenderVersion


class Cursor:
    def __init__(self, rows=None):
        self.calls = []
        self.rows = list(rows or [])
    def execute(self, sql, params=None):
        self.calls.append((sql, params))
    def fetchone(self):
        return self.rows.pop(0) if self.rows else None


def render(**overrides):
    values = dict(
        render_id=uuid4(), report_id=uuid4(), render_type='WEB', render_version=1,
        render_contract_version='1.0.0', template_id='PROPERTY_REPORT', template_version='1.0.0',
        renderer_version='1.0.0', presentation_input_hash='a'*64,
    )
    values.update(overrides)
    return RenderVersion(**values)


def test_insert_render_targets_render_versions():
    c = Cursor()
    RenderRepository().insert_render(c, render())
    assert 'INSERT INTO reporting.render_versions' in c.calls[0][0]


def test_render_requires_supported_type_and_hash():
    repo = RenderRepository()
    with pytest.raises(ValueError): repo.insert_render(Cursor(), render(render_type='RAW_HTML'))
    with pytest.raises(ValueError): repo.insert_render(Cursor(), render(presentation_input_hash='bad'))


def test_artifact_can_be_absent_while_building():
    c = Cursor()
    RenderRepository().insert_render(c, render(artifact_hash=None, storage_uri=None, mime_type=None))
    assert c.calls


def test_insert_render_dependency_preserves_exact_lineage():
    c = Cursor(); rid = uuid4()
    dep = RenderDependency(uuid4(), rid, 'TEMPLATE', 'PROPERTY_REPORT', 'b'*64, '1.0.0')
    RenderRepository().insert_dependency(c, dep)
    assert 'INSERT INTO reporting.render_dependencies' in c.calls[0][0]
    assert c.calls[0][1][4] == 'b'*64


def test_find_equivalent_is_scoped_to_report_and_render_type():
    found = uuid4(); c = Cursor([(found,)])
    got = RenderRepository().find_equivalent(c, uuid4(), 'PDF', 'c'*64)
    assert got == found
    sql, params = c.calls[0]
    assert 'report_id=%s AND render_type=%s AND presentation_input_hash=%s' in sql
    assert params[1] == 'PDF'
