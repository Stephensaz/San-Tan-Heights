from src.operations.dashboard import OperationsDashboardProjector
class C:
    def execute(self,q):self.q=q
    def fetchone(self):return ('HEALTHY',10,9,1,0,0,2,1,0,0,True,'VERIFIED','VERIFIED')
def test_dashboard_is_read_only_projection_over_authoritative_view():
    c=C(); d=OperationsDashboardProjector().read(c); assert d.total_properties==10 and d.active_global_publication_freeze is True and 'operations.operations_dashboard_current' in c.q
