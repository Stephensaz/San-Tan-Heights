class DependencyBatchWorker:
    def __init__(self,evaluator,chunk_size=250): self.evaluator=evaluator; self.chunk_size=chunk_size
    def run_chunk(self,cursor,*,batch_id,dependency_type,correlation_id):
        return self.evaluator.evaluate_claimed(cursor,batch_id=batch_id,dependency_type=dependency_type,correlation_id=correlation_id,limit=self.chunk_size)
