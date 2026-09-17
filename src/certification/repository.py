import json
class CertificationRepository:
    def create_run(self,cur,*,run_id,candidate_version,contract_version,candidate_fingerprint):
        cur.execute('''INSERT INTO certification.runs(certification_run_id,candidate_version,contract_version,candidate_fingerprint,run_state) VALUES(%s,%s,%s,%s,'CREATED')''',(run_id,candidate_version,contract_version,candidate_fingerprint))
    def insert_scenario_result(self,cur,run_id,row):
        sid,status,evidence,detail=row
        cur.execute('''INSERT INTO certification.scenario_results(certification_run_id,scenario_id,status,evidence_hash,detail) VALUES(%s,%s,%s,%s,%s::jsonb)''',(run_id,sid,status,evidence,json.dumps(detail,sort_keys=True)))
    def insert_metric_result(self,cur,run_id,row):
        cur.execute('''INSERT INTO certification.metric_results(certification_run_id,metric_id,observed_value,maximum_allowed,status) VALUES(%s,%s,%s,%s,%s)''',(run_id,row.metric_id,row.observed_value,row.maximum_allowed,row.status))
    def finalize(self,cur,run_id,verdict):
        cur.execute("UPDATE certification.runs SET run_state=%s, verdict=%s, completed_at=now() WHERE certification_run_id=%s",('PASSED' if verdict=='GO' else 'FAILED',verdict,run_id))
