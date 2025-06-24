import json
import sqlite3
import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import hashlib
import os

@dataclass
class MemoryEntry:
    """Represents a single memory entry in the system"""
    id: str
    timestamp: str
    original_prompt: str
    expanded_prompt: str
    image_path: str
    model_path: str
    tags: List[str]
    metadata: Dict[str, Any]

class MemorySystem:
    """
    AI Memory System - Remembers everything forever
    
    Features:
    - Short-term: Session context during interaction
    - Long-term: SQLite persistence across sessions
    - Smart search: Find similar prompts and creations
    - Tagging: Organize memories by themes
    """
    
    def __init__(self, db_path: str = "app/memory.db"):
        self.db_path = db_path
        self.session_memory: Dict[str, Any] = {}
        self.init_database()
        logging.info("Memory System initialized")
    
    def init_database(self):
        """Initialize SQLite database for long-term memory"""
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    original_prompt TEXT NOT NULL,
                    expanded_prompt TEXT NOT NULL,
                    image_path TEXT NOT NULL,
                    model_path TEXT NOT NULL,
                    tags TEXT NOT NULL,
                    metadata TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp ON memories(timestamp)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_tags ON memories(tags)
            """)
        logging.info("Long-term memory database ready")
    
    def generate_memory_id(self, prompt: str) -> str:
        """Generate unique ID for memory entry"""
        timestamp = datetime.now().isoformat()
        content = f"{prompt}_{timestamp}"
        return hashlib.md5(content.encode()).hexdigest()[:12]
    
    def store_memory(self, 
                    original_prompt: str,
                    expanded_prompt: str,
                    image_path: str,
                    model_path: str,
                    keywords: List[str] = None,
                    metadata: Dict[str, Any] = None) -> str:
        """
        Store a new memory entry
        
        Args:
            original_prompt: User's original input
            expanded_prompt: LLM-enhanced prompt
            image_path: Path to generated image
            model_path: Path to generated 3D model
            keywords: Optional keywords for categorization
            metadata: Additional metadata
            
        Returns:
            Memory ID
        """
        memory_id = self.generate_memory_id(original_prompt)
        timestamp = datetime.now().isoformat()
        
        if keywords is None:
            keywords = self.extract_keywords_with_llama(original_prompt)
        if metadata is None:
            metadata = {}
            
        memory = MemoryEntry(
            id=memory_id,
            timestamp=timestamp,
            original_prompt=original_prompt,
            expanded_prompt=expanded_prompt,
            image_path=image_path,
            model_path=model_path,
            tags=keywords,
            metadata=metadata
        )
        
        # Store in long-term memory (SQLite)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO memories 
                (id, timestamp, original_prompt, expanded_prompt, image_path, model_path, tags, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                memory.id,
                memory.timestamp,
                memory.original_prompt,
                memory.expanded_prompt,
                memory.image_path,
                memory.model_path,
                json.dumps(memory.tags),
                json.dumps(memory.metadata)
            ))
        
        # Store in short-term memory (session)
        self.session_memory[memory_id] = asdict(memory)
        
        logging.info(f"Memory stored: {memory_id} - '{original_prompt[:50]}...'")
        return memory_id
    
    def recall_memory(self, memory_id: str) -> Optional[MemoryEntry]:
        """Recall a specific memory by ID"""
        # Try session memory first (faster)
        if memory_id in self.session_memory:
            data = self.session_memory[memory_id]
            return MemoryEntry(**data)
        
        # Try long-term memory
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT * FROM memories WHERE id = ?
            """, (memory_id,))
            row = cursor.fetchone()
            
            if row:
                return MemoryEntry(
                    id=row[0],
                    timestamp=row[1],
                    original_prompt=row[2],
                    expanded_prompt=row[3],
                    image_path=row[4],
                    model_path=row[5],
                    tags=json.loads(row[6]),
                    metadata=json.loads(row[7])
                )
        return None
    
    def search_memories(self, 
                       query: str = None,
                       tags: List[str] = None,
                       limit: int = 10) -> List[MemoryEntry]:
        """
        Search memories by query or tags
        
        Args:
            query: Text to search in prompts
            tags: Tags to filter by
            limit: Maximum results to return
            
        Returns:
            List of matching memories
        """
        with sqlite3.connect(self.db_path) as conn:
            sql = "SELECT * FROM memories WHERE 1=1"
            params = []
            
            if query:
                sql += " AND (original_prompt LIKE ? OR expanded_prompt LIKE ?)"
                params.extend([f"%{query}%", f"%{query}%"])
            
            if tags:
                for tag in tags:
                    sql += " AND tags LIKE ?"
                    params.append(f"%{tag}%")
            
            sql += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            
            cursor = conn.execute(sql, params)
            results = []
            
            for row in cursor.fetchall():
                results.append(MemoryEntry(
                    id=row[0],
                    timestamp=row[1],
                    original_prompt=row[2],
                    expanded_prompt=row[3],
                    image_path=row[4],
                    model_path=row[5],
                    tags=json.loads(row[6]),
                    metadata=json.loads(row[7])
                ))
            
            return results
    
    def get_recent_memories(self, limit: int = 5) -> List[MemoryEntry]:
        """Get most recent memories"""
        return self.search_memories(limit=limit)
    
    def extract_keywords_with_llama(self, prompt: str) -> List[str]:
        """Extract keywords using LLaMA for better semantic understanding"""
        try:
            import requests
            
            llama_response = requests.post("http://ollama:11434/api/generate", json={
                "model": "llama3",
                "prompt": f"""Extract 5-8 relevant keywords from this prompt for categorization and search purposes. 
Return only the keywords separated by commas, no explanations.

Prompt: "{prompt}"

Keywords:""",
                "stream": False
            }, timeout=60)
            
            llama_response.raise_for_status()
            keywords_text = llama_response.json().get("response", "").strip()
            
            # Parse keywords from response
            keywords = [kw.strip().lower() for kw in keywords_text.split(',') if kw.strip()]
            
            # Fallback to simple extraction if LLaMA fails
            if not keywords:
                logging.warning("LLaMA keyword extraction failed, using fallback")
                return self.extract_tags_fallback(prompt)
            
            # Limit to 8 keywords max
            keywords = keywords[:8]
            logging.info(f"LLaMA extracted keywords: {keywords}")
            return keywords
            
        except Exception as e:
            logging.error(f"Error extracting keywords with LLaMA: {e}")
            return self.extract_tags_fallback(prompt)

    def extract_tags_fallback(self, prompt: str) -> List[str]:
        """Fallback keyword extraction method"""
        # Simple keyword-based tagging (original method)
        keywords = {
            'animal': ['cat', 'dog', 'dragon', 'bird', 'fish', 'lion', 'tiger'],
            'vehicle': ['car', 'truck', 'plane', 'ship', 'submarine', 'motorcycle'],
            'building': ['house', 'castle', 'tower', 'city', 'bridge'],
            'nature': ['forest', 'mountain', 'ocean', 'desert', 'jungle'],
            'fantasy': ['dragon', 'wizard', 'magic', 'fairy', 'unicorn'],
            'sci-fi': ['robot', 'spaceship', 'alien', 'cyberpunk', 'futuristic'],
            'color': ['red', 'blue', 'green', 'yellow', 'purple', 'black', 'white']
        }
        
        tags = []
        prompt_lower = prompt.lower()
        
        for category, words in keywords.items():
            if any(word in prompt_lower for word in words):
                tags.append(category)
        
        return tags[:5]  # Limit to 5 tags
    
    def extract_tags(self, prompt: str) -> List[str]:
        """Extract relevant tags from prompt"""
        return self.extract_keywords_with_llama(prompt)
    
    def get_memory_stats(self) -> Dict[str, Any]:
        """Get memory system statistics"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM memories")
            total_memories = cursor.fetchone()[0]
            
            cursor = conn.execute("""
                SELECT tags, COUNT(*) as count 
                FROM memories 
                GROUP BY tags 
                ORDER BY count DESC 
                LIMIT 10
            """)
            popular_tags = cursor.fetchall()
        
        return {
            'total_memories': total_memories,
            'session_memories': len(self.session_memory),
            'popular_tags': popular_tags
        }
    
    def save_prompt_to_folder(self, original_prompt: str, expanded_prompt: str, memory_id: str, folder_path: str = None) -> str:
        """Save prompts to organized folder structure by date"""
        # Use provided folder_path or create date-based folder structure
        if folder_path:
            os.makedirs(folder_path, exist_ok=True)
        else:
            today = datetime.now().strftime("%Y-%m-%d")
            folder_path = f"memories/{today}"
            os.makedirs(folder_path, exist_ok=True)
        
        # Generate filename with timestamp and memory ID
        timestamp = datetime.now().strftime("%H%M%S")
        filename = f"prompt_{timestamp}_{memory_id}.txt"
        file_path = os.path.join(folder_path, filename)
        
        # Save both prompts to file
        content = f"""MEMORY ID: {memory_id}
TIMESTAMP: {datetime.now().isoformat()}

ORIGINAL PROMPT:
{original_prompt}

EXPANDED PROMPT:
{expanded_prompt}
"""
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        logging.info(f"Prompt saved to: {file_path}")
        return file_path
    
    def find_similar(self, prompt: str, limit: int = 3) -> List[MemoryEntry]:
        """Find memories similar to given prompt"""
        # Simple similarity based on common words
        prompt_words = set(prompt.lower().split())
        memories = self.get_recent_memories(limit=50)  # Get more to compare
        
        scored_memories = []
        for memory in memories:
            memory_words = set(memory.original_prompt.lower().split())
            common_words = prompt_words.intersection(memory_words)
            score = len(common_words) / max(len(prompt_words), 1)
            
            if score > 0.1:  # Minimum similarity threshold
                scored_memories.append((score, memory))
        
        # Sort by score and return top results
        scored_memories.sort(key=lambda x: x[0], reverse=True)
        return [memory for score, memory in scored_memories[:limit]]

# Global memory system instance
memory_system = MemorySystem()
