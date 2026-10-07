"""Export the rule embeddings from the local Chroma database into data/embeddings.npz.
That small file is committed to GitHub so a server (e.g. Render) can search without Chroma
and without re-embedding anything. Run once after ingest.py:  python export_embeddings.py"""
import numpy as np
import chromadb

col = chromadb.PersistentClient(path="data/chroma").get_collection("psr")
data = col.get(include=["embeddings"])
ids = np.array(data["ids"])
vectors = np.array(data["embeddings"], dtype=np.float32)
np.savez_compressed("data/embeddings.npz", ids=ids, vectors=vectors)
print(f"exported {len(ids)} rules, {vectors.shape[1]} dimensions -> data/embeddings.npz")
