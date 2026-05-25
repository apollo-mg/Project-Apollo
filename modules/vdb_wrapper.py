import time
from modules.vdb import query_vdb, get_vector_store

class VDBSession:
    """
    High-speed interface for the Vector DB to minimize 'Recall' injection latency.
    Acts as a lightweight companion server interface.
    """
    def __init__(self):
        self.start_time = time.time()
        # Pre-warm the vector store to avoid cold-start latency during first query
        self._vector_store = get_vector_store()
        print("[VDB_WRAPPER] Vector Store warmed and ready.")

    def fast_query(self, query: str, n_results: int = 5, filter_dict: dict = None):
        """
        Executes a query with high-precision timing to monitor 'Recall' latency.
        """
        start_query = time.perf_counter()
        
        # Execute the core query
        result = query_vdb(query, n_results=n_results, filter_dict=filter_dict)
        
        end_query = time.perf_counter()
        latency_ms = (end_query - start_query) * 1000
        
        # Log latency for the 'Recall' metric
        print(f"[METRIC] Recall Latency: {latency_ms:.2f}ms | Query: '{query[:30]}...'")
        
        return result, latency_ms

if __name__ == "__main__":
    # Quick test of the wrapper
    wrapper = VDBSession()
    res, lat = wrapper.fast_query("test query")
    print(f"Result: {res}\nLatency: {lat}ms")
