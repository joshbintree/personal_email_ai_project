from utils.convert_mbox import get_emails_from_mbox, chunk_records
from utils.embed_text import _embed_batch_with_retry
from utils.db_queries import insert_chunks
import json
import os
from datetime import datetime
CHECKPOINT_PATH = "chunks_embedded.jsonl"
def save_chunks(chunks: list[dict], path: str = "chunks.jsonl"):
    with open(path, "w", encoding="utf-8") as f:
        for chunk in chunks:
            row = chunk.copy()
            if isinstance(row.get("received_at"), datetime):
                row["received_at"] = row["received_at"].isoformat()
            f.write(json.dumps(row) + "\n")
    print(f"Saved {len(chunks)} chunks to {path}")
def load_chunks(path: str = "chunks.jsonl") -> list[dict]:
    chunks = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            row = json.loads(line)
            if row.get("received_at"):
                row["received_at"] = datetime.fromisoformat(row["received_at"])
            chunks.append(row)
    print(f"Loaded {len(chunks)} chunks from {path}")
    return chunks
def get_already_embedded_count(path: str) -> int:
    """Count how many chunks are already saved so we can skip them."""
    if not os.path.exists(path):
        return 0
    with open(path, "r") as f:
        return sum(1 for _ in f)
def embed_with_checkpoints(chunks: list[dict], path: str = CHECKPOINT_PATH, batch_size: int = 100):
    already_done = get_already_embedded_count(path)
    if already_done > 0:
        print(f"Resuming from chunk {already_done} / {len(chunks)}")
    # open in append mode so we never overwrite completed work
    with open(path, "a", encoding="utf-8") as f:
        for i in range(already_done, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]
            texts = [c["content"] for c in batch]
            embeddings = _embed_batch_with_retry(texts)
            for chunk, embedding in zip(batch, embeddings):
                chunk["embedding"] = embedding
                row = chunk.copy()
                if isinstance(row.get("received_at"), datetime):
                    row["received_at"] = row["received_at"].isoformat()
                f.write(json.dumps(row) + "\n")
            f.flush()  # make sure it's written to disk after each batch
            print(f"Checkpoint: {min(i + batch_size, len(chunks))} / {len(chunks)}")
    print("Embedding complete.")
# --- Run ---
#chunks = get_emails_from_mbox()
#chunk_data = chunk_records(chunks)
#save_chunks(chunk_data, "chunks.jsonl")
chunk_data = load_chunks("chunks_embedded.jsonl")
insert_chunks(chunk_data)