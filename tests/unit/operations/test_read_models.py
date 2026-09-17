from src.operations.read_models.repository import OperationsReadModelRepository
class C:
    def __init__(self):self.calls=[]
    def execute(self,*a):self.calls.append(a)
    def fetchone(self):return ('ok',)
def test_read_model_queries_explicit_views():
    c=C(); r=OperationsReadModelRepository(); assert r.get_fleet_health(c)==('ok',); assert 'operations.fleet_health_current' in c.calls[-1][0]
