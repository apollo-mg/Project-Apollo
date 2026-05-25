from modules.vdb import get_vector_store
vector_store = get_vector_store()
res = vector_store._collection.query(query_texts=["test"], n_results=2)
print(res)
