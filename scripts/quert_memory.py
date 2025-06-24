import sqlite3
import json
import os
from datetime import datetime

def simple_table(data, headers):
    """Simple table formatter without external dependencies"""
    if not data:
        return ""
    
    # Calculate column widths
    col_widths = [len(str(h)) for h in headers]
    for row in data:
        for i, cell in enumerate(row):
            col_widths[i] = max(col_widths[i], len(str(cell)))
    
    # Create separator
    separator = "+" + "+".join("-" * (w + 2) for w in col_widths) + "+"
    
    # Format header
    header_row = "|" + "|".join(f" {str(h).ljust(col_widths[i])} " for i, h in enumerate(headers)) + "|"
    
    # Format data rows
    data_rows = []
    for row in data:
        data_row = "|" + "|".join(f" {str(cell).ljust(col_widths[i])} " for i, cell in enumerate(row)) + "|"
        data_rows.append(data_row)
    
    # Combine all parts
    result = [separator, header_row, separator] + data_rows + [separator]
    return "\n".join(result)

def query_memory_database():
    """Query the memory database directly"""
    
    db_path = "app/memory.db"
    
    if not os.path.exists(db_path):
        print("Memory database not found")
        return
    
    try:
        with sqlite3.connect(db_path) as conn:
            # Get all memories
            cursor = conn.execute("""
                SELECT id, timestamp, original_prompt, expanded_prompt, 
                       image_path, model_path, tags, metadata
                FROM memories 
                ORDER BY timestamp DESC
            """)
            
            memories = cursor.fetchall()
            
            if not memories:
                print("No memories stored")
                return
            
            print(f"MEMORY SYSTEM - {len(memories)} memories found")
            print("=" * 80)
            
            # Show summary table
            table_data = []
            for memory in memories:
                timestamp = datetime.fromisoformat(memory[1]).strftime('%Y-%m-%d %H:%M')
                tags = json.loads(memory[6]) if memory[6] else []
                
                table_data.append([
                    memory[0][:8] + "...",  # Short ID
                    timestamp,
                    memory[2][:30] + "..." if len(memory[2]) > 30 else memory[2],  # Short prompt
                    ", ".join(tags[:3]),  # First 3 tags
                    "YES" if memory[4] != 'none' else "NO",  # Image
                    "YES" if memory[5] != 'none' else "NO"   # 3D Model
                ])
            
            headers = ["ID", "Date", "Prompt", "Tags", "Img", "3D"]
            print(simple_table(table_data, headers))
            
            print("\nSTATISTICS:")
            print(f"- Total memories: {len(memories)}")
            print(f"- With images: {len([m for m in memories if m[4] != 'none'])}")
            print(f"- With 3D models: {len([m for m in memories if m[5] != 'none'])}")
            
            # Most popular tags
            all_tags = []
            for memory in memories:
                tags = json.loads(memory[6]) if memory[6] else []
                all_tags.extend(tags)
            
            if all_tags:
                tag_counts = {}
                for tag in all_tags:
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1
                
                popular_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:5]
                print(f"\nMOST POPULAR TAGS:")
                for tag, count in popular_tags:
                    print(f"- {tag}: {count} times")
            
            # Show details of last 3 memories
            print(f"\nLAST 3 CREATIONS:")
            print("-" * 80)
            
            for i, memory in enumerate(memories[:3]):
                timestamp = datetime.fromisoformat(memory[1]).strftime('%Y-%m-%d %H:%M:%S')
                tags = json.loads(memory[6]) if memory[6] else []
                metadata = json.loads(memory[7]) if memory[7] else {}
                
                print(f"\n#{i+1} - ID: {memory[0]}")
                print(f"Date: {timestamp}")
                print(f"Original Prompt: {memory[2]}")
                print(f"Expanded Prompt: {memory[3][:100]}...")
                print(f"Tags: {', '.join(tags)}")
                print(f"Image: {os.path.basename(memory[4]) if memory[4] != 'none' else 'Not available'}")
                print(f"3D Model: {os.path.basename(memory[5]) if memory[5] != 'none' else 'Not available'}")
                
                if metadata:
                    print(f"Metadata: {metadata}")
    
    except Exception as e:
        print(f"Error querying database: {e}")

def search_memories_by_keyword(keyword):
    """Search memories by keyword"""
    db_path = "app/memory.db"
    
    if not os.path.exists(db_path):
        print("Memory database not found")
        return
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.execute("""
                SELECT id, timestamp, original_prompt, expanded_prompt, tags
                FROM memories 
                WHERE original_prompt LIKE ? OR expanded_prompt LIKE ? OR tags LIKE ?
                ORDER BY timestamp DESC
            """, (f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"))
            
            results = cursor.fetchall()
            
            if not results:
                print(f"No memories found with '{keyword}'")
                return
            
            print(f"SEARCH: '{keyword}' - {len(results)} results")
            print("=" * 60)
            
            for result in results:
                timestamp = datetime.fromisoformat(result[1]).strftime('%Y-%m-%d %H:%M')
                tags = json.loads(result[4]) if result[4] else []
                
                print(f"\nID: {result[0]}")
                print(f"Date: {timestamp}")
                print(f"Prompt: {result[2]}")
                print(f"Tags: {', '.join(tags)}")
                print("-" * 40)
    
    except Exception as e:
        print(f"Search error: {e}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        keyword = sys.argv[1]
        search_memories_by_keyword(keyword)
    else:
        query_memory_database()
