"""
Módulo de embeddings com fallback determinístico.
"""

try:
    from sentence_transformers import SentenceTransformer
    _model = SentenceTransformer('all-MiniLM-L6-v2')
except ImportError:
    _model = None


class EmbeddingManager:
    """Manager para embeddings com fallback hash-based determinístico."""

    def __init__(self):
        self.model = _model

    def get_embedding(self, text: str) -> list[float]:
        """Retorna embedding real ou fallback hash-based determinístico."""
        if self.model is not None:
            return self.model.encode(text).tolist()
        # Fallback: hash-based deterministic embedding
        import hashlib
        h = hashlib.sha256(text.encode()).digest()
        # Expandir 32 bytes para 384 dimensões via hash cíclico
        embedding = []
        while len(embedding) < 384:
            h = hashlib.sha256(h).digest()
            embedding.extend([b / 255.0 for b in h])
        return embedding[:384]

    def similarity(self, text1: str, text2: str) -> float:
        """Calcula similaridade de cosseno entre dois textos."""
        emb1 = self.get_embedding(text1)
        emb2 = self.get_embedding(text2)
        # Similaridade de cosseno
        dot = sum(a * b for a, b in zip(emb1, emb2))
        norm1 = sum(a * a for a in emb1) ** 0.5
        norm2 = sum(b * b for b in emb2) ** 0.5
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot / (norm1 * norm2)