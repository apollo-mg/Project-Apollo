import os
import sys
import hashlib
from vdb import get_vector_store, get_text_splitter, Document
from uuid import uuid5, NAMESPACE_DNS

vault_dir = "vault/skills"
store = get_vector_store()
files = [f for f in os.listdir(vault_dir) if f.endswith(".md")]

print(f"Ingesting {len(files)} skills into ChromaDB...")

documents = []
for file in files:
    file_path = os.path.join(vault_dir, file)
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Generate deterministic UUID5 based on filepath
    doc_id = str(uuid5(NAMESPACE_DNS, file_path))
    
    # We don't chunk skills, we ingest them whole since they are usually small
    doc = Document(
        page_content=content,
        metadata={"source": file_path, "type": "skill", "id": doc_id}
    )
    documents.append(doc)

if documents:
    store.add_documents(documents)
    print("Ingestion complete!")
