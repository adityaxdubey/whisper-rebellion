import numpy as np
from typing import List, Dict
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_
from models import Message, User
import logging
import re

# Configure logging
logger = logging.getLogger(__name__)

class LocalSemanticSearch:
    def __init__(self):
        self.model = None
        self.use_embeddings = False
        
        # Try to load sentence-transformers
        try:
            from sentence_transformers import SentenceTransformer
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
                # Clean text
                cleaned_text = text.strip()
                if not cleaned_text:
                    return [0.0] * 384
                
                # Generate embedding
                embedding = self.model.encode(cleaned_text, convert_to_tensor=False)
                return embedding.tolist()
            except Exception as e:
                logger.error(f"Error generating embedding: {e}")
                return [0.0] * 384
        else:
            # Fallback: simple hash-based embedding
            import random
            hash_value = hash(text.lower())
            random.seed(hash_value)
            return [random.random() for _ in range(384)]
    
    def search_messages(self, user_id: int, query: str, db: Session, limit: int = 10, target_user_id: int = None):
        try:
            print(f" SEARCH DEBUG ===", flush=True)
            print(f"Searching for User ID: {user_id}, Query: '{query}', Target User: {target_user_id}", flush=True)
            
            # Build the base query
            if target_user_id:
                # Search messages between current user and target user
                messages_query = db.query(Message).filter(
                    or_(
                        and_(Message.sender_id == user_id, Message.receiver_id == target_user_id),
                        and_(Message.sender_id == target_user_id, Message.receiver_id == user_id)
                    )
                )
            else:
                # Search all messages involving the current user
                messages_query = db.query(Message).filter(
                    or_(Message.sender_id == user_id, Message.receiver_id == user_id)
                )
            
            messages = messages_query.all()
            print(f"Total messages in scope: {len(messages)}", flush=True)
            
            if not messages:
                print("No messages found in scope!", flush=True)
                return []
            
            # Clean query
            query_lower = query.lower().strip()
            if not query_lower:
                print("Empty query!", flush=True)
                return []
            
            # Generate query embedding if using embeddings
            query_embedding = None
            if self.use_embeddings and self.model:
                query_embedding = self.embed_text(query)
            
            results = []
            query_words = set(re.findall(r'\w+', query_lower))
            
            print(f"Query words: {query_words}", flush=True)
            
            for msg in messages:
                message_lower = msg.message.lower()
                message_words = set(re.findall(r'\w+', msg.message.lower()))
                
                print(f"Checking message: '{msg.message}' (words: {message_words})", flush=True)
                
                # Calculate similarity score
                score = 0
                
                if self.use_embeddings and query_embedding and msg.embedding:
                    # Use cosine similarity with embeddings
                    try:
                        cosine_sim = self.cosine_similarity(query_embedding, msg.embedding)
                        score = max(score, cosine_sim)
                        print(f"  Embedding similarity: {cosine_sim:.3f}", flush=True)
                    except Exception as e:
                        print(f"  Error calculating embedding similarity: {e}", flush=True)
                
                # Keyword-based scoring as fallback or supplement
                # 1. Exact phrase match (highest score)
                if query_lower in message_lower:
                    score = max(score, 1.0)
                    print(f"  Exact phrase match! Score: {score}", flush=True)
                
                # 2. All query words are present
                if query_words.issubset(message_words):
                    score = max(score, 0.9)
                    print(f"  All words match! Score: {score}", flush=True)
                
                # 3. Partial word match
                matched_words = 0
                for q_word in query_words:
                    for m_word in message_words:
                        if q_word in m_word or m_word in q_word:
                            matched_words += 1
                            print(f"  Partial match: '{q_word}' in '{m_word}'", flush=True)
                            break
                
                if matched_words > 0:
                    partial_score = 0.5 * (matched_words / len(query_words))
                    score = max(score, partial_score)
                    print(f"  Partial match score: {score}", flush=True)
                
                print(f"  Final score for message: {score}", flush=True)
                
                # Only include results with meaningful scores
                if score > 0.1:  # Lower threshold for better recall
                    sender = db.query(User).filter(User.id == msg.sender_id).first()
                    results.append({
                        "id": msg.id,
                        "message": msg.message,
                        "sender_name": sender.name if sender else "Unknown",
                        "sender_id": msg.sender_id,
                        "receiver_id": msg.receiver_id,
                        "created_at": msg.created_at.isoformat(),
                        "similarity_score": score
                    })
                    print(f"  ✅ Added to results: {msg.message}", flush=True)
                else:
                    print(f"  ❌ Score too low, not adding to results", flush=True)
            
            print(f"Found {len(results)} matching messages", flush=True)
            
            # Sort by score and limit results
            results.sort(key=lambda x: x['similarity_score'], reverse=True)
            return results[:limit]
            
        except Exception as e:
            print(f"Error in search: {e}", flush=True)
            logger.error(f"Error in search: {e}", exc_info=True)
            return []
    
    def index_message(self, message_text: str, message_id: int, db: Session):
        try:
            # Generate embedding
            embedding = self.embed_text(message_text)
            
            # Update message with embedding
            message = db.query(Message).filter(Message.id == message_id).first()
            if message:
                message.embedding = embedding
                db.commit()
                print(f"✅ Indexed message {message_id}: {message_text[:50]}...", flush=True)
            else:
                print(f"Message {message_id} not found for indexing", flush=True)
                
        except Exception as e:
            print(f"Error indexing message {message_id}: {e}", flush=True)
            logger.error(f"Error indexing message {message_id}: {e}")
    
    def cosine_similarity(self, a: List[float], b: List[float]) -> float:
        try:
            a_np = np.array(a)
            b_np = np.array(b)
            
            # Normalize vectors
            a_norm = np.linalg.norm(a_np)
            b_norm = np.linalg.norm(b_np)
            
            if a_norm == 0 or b_norm == 0:
                return 0.0
            
            return float(np.dot(a_np, b_np) / (a_norm * b_norm))
        except Exception as e:
            logger.error(f"Error calculating cosine similarity: {e}")
            return 0.0

# Global instance
semantic_service = LocalSemanticSearch()
