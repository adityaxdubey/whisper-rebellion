from sentence_transformers import SentenceTransformer
import numpy as np
from typing import List, Optional
import logging

class EmbeddingService:
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """Initialize the embedding model"""
        try:
            self.model = SentenceTransformer(model_name)
            self.dimension = self.model.get_sentence_embedding_dimension()
            logging.info(f"Loaded embedding model: {model_name} (dim: {self.dimension})")
        except Exception as e:
            logging.error(f"Failed to load embedding model: {e}")
            raise
    
    def embed_text(self, text: str) -> List[float]:
        """Convert text to embedding vector"""
        try:
            # Clean and preprocess text
            cleaned_text = text.strip().lower()
            if not cleaned_text:
                return [0.0] * self.dimension
            
            # Generate embedding
            embedding = self.model.encode(cleaned_text, convert_to_tensor=False)
            return embedding.tolist()
        except Exception as e:
            logging.error(f"Error generating embedding: {e}")
            return [0.0] * self.dimension
    
    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts efficiently"""
        try:
            cleaned_texts = [text.strip().lower() for text in texts]
            embeddings = self.model.encode(cleaned_texts, convert_to_tensor=False)
            return [emb.tolist() for emb in embeddings]
        except Exception as e:
            logging.error(f"Error generating batch embeddings: {e}")
            return [[0.0] * self.dimension] * len(texts)

# Global instance
embedding_service = EmbeddingService()
