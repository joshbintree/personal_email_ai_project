import os
import time
import random
import json
import logging
from datetime import datetime
from dotenv import load_dotenv
from sentence_transformers import SentenceTransformer

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

mini_lm_model = SentenceTransformer("all-MiniLM-L6-v2")

CHECKPOINT_PATH = "chunks_embedded.jsonl"

def _get_already_embedded_count(path: str) -> int:
    if not os.path.exists(path):
        return 0
    with open(path, "r") as f:
        return sum(1 for _ in f)

def _embed_batch_with_retry(texts: list[str], max_retries: int = 5) -> list[list[float]]:
    for attempt in range(max_retries):
        try:
            embeddings = mini_lm_model.encode(texts)
            return [e.tolist() for e in embeddings]
        except Exception as e:
            if attempt == max_retries - 1:
                raise
            wait = (2 ** attempt) + random.uniform(0, 1)
            logger.warning(f"Embedding failed ({e}), retrying in {wait:.2f}s (attempt {attempt + 1}/{max_retries})")
            time.sleep(wait)

def embed_chunks(chunks: list[dict], batch_size: int = 100, checkpoint_path: str = CHECKPOINT_PATH) -> list[dict]:
    already_done = _get_already_embedded_count(checkpoint_path)
    total = len(chunks)

    if already_done >= total:
        logger.info("All chunks already embedded, loading from checkpoint.")
        return chunks

    if already_done > 0:
        logger.info(f"Resuming from chunk {already_done:,} / {total:,}")

    with open(checkpoint_path, "a", encoding="utf-8") as f:
        for i in range(already_done, total, batch_size):
            batch = chunks[i:i + batch_size]
            texts = [c["content"] for c in batch]

            embeddings = _embed_batch_with_retry(texts)

            for chunk, embedding in zip(batch, embeddings):
                chunk["embedding"] = embedding
                row = chunk.copy()
                if isinstance(row.get("received_at"), datetime):
                    row["received_at"] = row["received_at"].isoformat()
                f.write(json.dumps(row) + "\n")

            f.flush()
            logger.info(f"Checkpoint: {min(i + batch_size, total):,} / {total:,}")

    logger.info("Embedding complete.")
    return chunks

def embed_db_query(query: str) -> list[float]:
    return mini_lm_model.encode([query])[0].tolist()

def embed_llm_query(query: str) -> list[float]:
    return mini_lm_model.encode([query])[0].tolist()