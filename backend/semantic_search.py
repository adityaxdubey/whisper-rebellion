import logging
import random
import re
from typing import List, Dict, Optional
import numpy as np
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from models import Message, User
from database import engine

USING_PGVECTOR = engine.url.get_backend_name().startswith("postgresql")

logger = logging.getLogger(__name__)

class LocalSemanticSearch:
    def __init__(self):
        self.model = None
        self.use_embeddings = False
        try:
            from sentence_transformers import SentenceTransformer
            # Small, fast model
            self.model = SentenceTransformer('all-MiniLM-L6-v2')
            self.use_embeddings = True
            logger.info("✅ Loaded sentence-transformers model successfully")
        except ImportError:
            logger.warning("⚠️ sentence-transformers not available, using keyword search")
        except Exception as e:
            logger.error(f"❌ Error loading model: {e}")

    def embed_text(self, text: str) -> List[float]:
        if self.use_embeddings and self.model:
            try:
                vec = self.model.encode([text], normalize_embeddings=True)[0]
                return vec.tolist()
            except Exception as e:
                logger.warning(f"Embed error, falling back: {e}")
        # Fallback: deterministic pseudo-embedding
        hash_value = hash(text.lower())
        random.seed(hash_value)
        return [random.random() for _ in range(384)]

    def search_messages(self, user_id: int, query: str, db: Session, limit: int = 10, target_user_id: Optional[int] = None):
        try:
            print(f" SEARCH DEBUG ===", flush=True)
            print(f"Searching for User ID: {user_id}, Query: '{query}', Target User: {target_user_id}", flush=True)

            # Scope messages
            if target_user_id:
                messages_query = db.query(Message).filter(
                    or_(
                        and_(Message.sender_id == user_id, Message.receiver_id == target_user_id),
                        and_(Message.sender_id == target_user_id, Message.receiver_id == user_id)
                    )
                )
            else:
                messages_query = db.query(Message).filter(
                    or_(Message.sender_id == user_id, Message.receiver_id == user_id)
                )

            query_lower = (query or "").lower().strip()
            if not query_lower:
                return []

            query_embedding = None
            if self.use_embeddings and self.model:
                query_embedding = self.embed_text(query)

            # Fast path: DB-side vector search when pgvector is available
            if USING_PGVECTOR and self.use_embeddings and query_embedding:
                try:
                    rows = (
                        db.query(
                            Message,
                            Message.embedding.cosine_distance(query_embedding).label("distance")
                        )
                        .filter(Message.embedding.isnot(None))
                        .filter(messages_query.subquery().c.id == Message.id if target_user_id else or_(Message.sender_id == user_id, Message.receiver_id == user_id))
                        .order_by("distance")
                        .limit(limit)
                        .all()
                    )

                    results = []
                    for msg, distance in rows:
                        sender = db.query(User).filter(User.id == msg.sender_id).first()
                        similarity = max(0.0, 1.0 - float(distance))
                        results.append({
                            "id": msg.id,
                            "message": msg.message,
                            "sender_name": sender.name if sender else "Unknown",
                            "sender_id": msg.sender_id,
                            "receiver_id": msg.receiver_id,
                            "created_at": msg.created_at.isoformat(),
                            "similarity_score": similarity
                        })
                    print(f"Found {len(results)} matching messages (pgvector path)", flush=True)
                    return results[:limit]
                except Exception as e:
                    print(f"pgvector path failed, fallback to Python scoring: {e}", flush=True)

            # Fallback: Python scoring
            messages = messages_query.all()
            print(f"Total messages in scope: {len(messages)}", flush=True)
            if not messages:
                return []

            results = []
            query_words = set(re.findall(r'\w+', query_lower))
            print(f"Query words: {query_words}", flush=True)

            for msg in messages:
                text_lower = (msg.message or "").lower()
                message_words = set(re.findall(r'\w+', text_lower))
                score = 0.0

                # Embedding similarity if available
                if self.use_embeddings and query_embedding and msg.embedding:
                    try:
                        score = max(score, self.cosine_similarity(query_embedding, msg.embedding))
                    except Exception:
                        pass

                # Exact/keyword heuristics
                if query_lower in text_lower:
                    score = max(score, 1.0)
                if query_words and query_words.issubset(message_words):
                    score = max(score, 0.9)

                # Partial word overlap
                if query_words:
                    matched_words = 0
                    for q in query_words:
                        for w in message_words:
                            if q in w or w in q:
                                matched_words += 1
                                break
                    if matched_words > 0:
                        score = max(score, 0.5 * (matched_words / len(query_words)))

                if score > 0.1:
                    sender = db.query(User).filter(User.id == msg.sender_id).first()
                    results.append({
                        "id": msg.id,
                        "message": msg.message,
                        "sender_name": sender.name if sender else "Unknown",
                        "sender_id": msg.sender_id,
                        "receiver_id": msg.receiver_id,
                        "created_at": msg.created_at.isoformat(),
                        "similarity_score": float(score),
                    })

            results.sort(key=lambda x: x["similarity_score"], reverse=True)
            return results[:limit]
        except Exception as e:
            logger.error(f"search_messages error: {e}")
            return []

    def index_message(self, message_text: str, message_id: int, db: Session):
        try:
            embedding = self.embed_text(message_text)
            msg = db.query(Message).filter(Message.id == message_id).first()
            if not msg:
                return
            msg.embedding = embedding
            db.add(msg)
            db.commit()
            print(f"✅ Indexed message {message_id}: {message_text[:20]}...", flush=True)
        except Exception as e:
            logger.warning(f"index_message error: {e}")

    def cosine_similarity(self, a: List[float], b: List[float]) -> float:
        try:
            va = np.array(a, dtype=np.float32)
            vb = np.array(b, dtype=np.float32)
            denom = (np.linalg.norm(va) * np.linalg.norm(vb))
            if denom == 0:
                return 0.0
            return float(np.dot(va, vb) / denom)
        except Exception:
            return 0.0

semantic_service = LocalSemanticSearch()
