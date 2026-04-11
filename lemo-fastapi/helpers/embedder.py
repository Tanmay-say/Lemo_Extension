from sentence_transformers import SentenceTransformer
import numpy as np

# Load a lightweight embedding model (384-dimensional)
model = SentenceTransformer('all-MiniLM-L6-v2')

def generate_embedding(text_chunk: str) -> np.ndarray:
    if not text_chunk or len(text_chunk.strip()) == 0:
        raise ValueError("Input text chunk is empty.")
    
    if len(text_chunk) > 1000:
        text_chunk = text_chunk[:1000]  # truncate safely

    embedding = model.encode(text_chunk, normalize_embeddings=True)
    embedding = np.array(embedding, dtype=np.float32)

    if embedding.shape[0] != 384:
        raise ValueError(f"Expected embedding dimension 384, got {embedding.shape[0]}")

    return embedding.tolist()
