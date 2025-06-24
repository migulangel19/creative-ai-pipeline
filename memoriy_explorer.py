import gradio as gr
import sqlite3
import json
import os
from datetime import datetime
from PIL import Image
import pandas as pd
from memory_system import memory_system

def get_all_memories():
    """Get all memories from the database"""
    try:
        with sqlite3.connect("app/memory.db") as conn:
            cursor = conn.execute("""
                SELECT id, timestamp, original_prompt, expanded_prompt, 
                       image_path, model_path, tags, metadata
                FROM memories 
                ORDER BY timestamp DESC
            """)
            
            memories = []
            for row in cursor.fetchall():
                memory = {
                    'id': row[0],
                    'timestamp': row[1],
                    'original_prompt': row[2],
                    'expanded_prompt': row[3],
                    'image_path': row[4],
                    'model_path': row[5],
                    'tags': json.loads(row[6]) if row[6] else [],
                    'metadata': json.loads(row[7]) if row[7] else {}
                }
                memories.append(memory)
            
            return memories
    except Exception as e:
        print(f"Error getting memories: {e}")
        return []

def search_memories(query="", tag_filter=""):
    """Search memories by text or tag"""
    memories = get_all_memories()
    
    if not query and not tag_filter:
        return memories
    
    filtered = []
    for memory in memories:
        # Search in prompts
        if query:
            if (query.lower() in memory['original_prompt'].lower() or 
                query.lower() in memory['expanded_prompt'].lower()):
                filtered.append(memory)
                continue
        
        # Filter by tag
        if tag_filter:
            if tag_filter.lower() in [tag.lower() for tag in memory['tags']]:
                filtered.append(memory)
    
    return filtered if (query or tag_filter) else memories

def format_memory_display(memories):
    """Format memories for display"""
    if not memories:
        return "No memories found"
    
    display_text = f"FOUND: {len(memories)} memories\n\n"
    
    for i, memory in enumerate(memories[:10]):  # Show only first 10
        timestamp = datetime.fromisoformat(memory['timestamp']).strftime('%Y-%m-%d %H:%M')
        
        display_text += f"""Memory #{i+1}
ID: {memory['id']}
Date: {timestamp}
Original Prompt: "{memory['original_prompt']}"
Expanded Prompt: "{memory['expanded_prompt'][:100]}..."
Tags: {', '.join(memory['tags'])}
Image: {os.path.basename(memory['image_path']) if memory['image_path'] != 'none' else 'Not available'}
3D Model: {os.path.basename(memory['model_path']) if memory['model_path'] != 'none' else 'Not available'}

---
"""
    
    if len(memories) > 10:
        display_text += f"\n... and {len(memories) - 10} more memories"
    
    return display_text

def get_memory_stats():
    """Get memory system statistics"""
    memories = get_all_memories()
    
    if not memories:
        return "No memories stored"
    
    # Basic statistics
    total = len(memories)
    with_images = len([m for m in memories if m['image_path'] != 'none'])
    with_models = len([m for m in memories if m['model_path'] != 'none'])
    
    # Most popular tags
    all_tags = []
    for memory in memories:
        all_tags.extend(memory['tags'])
    
    tag_counts = {}
    for tag in all_tags:
        tag_counts[tag] = tag_counts.get(tag, 0) + 1
    
    popular_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    
    # Dates
    dates = [datetime.fromisoformat(m['timestamp']).date() for m in memories]
    unique_dates = len(set(dates))
    
    stats_text = f"""MEMORY SYSTEM STATISTICS

Totals:
- Total memories: {total}
- With images: {with_images}
- With 3D models: {with_models}
- Active days: {unique_dates}

Most popular tags:
"""
    
    for tag, count in popular_tags:
        stats_text += f"- {tag}: {count} times\n"
    
    return stats_text

def load_memory_image(memory_id):
    """Load image from a specific memory"""
    memories = get_all_memories()
    
    for memory in memories:
        if memory['id'] == memory_id:
            if memory['image_path'] != 'none' and os.path.exists(memory['image_path']):
                try:
                    return Image.open(memory['image_path'])
                except Exception as e:
                    return None
    return None

def get_all_tags():
    """Get all unique tags"""
    memories = get_all_memories()
    all_tags = set()
    
    for memory in memories:
        all_tags.update(memory['tags'])
    
    return sorted(list(all_tags))

def create_memory_explorer():
    """Create memory exploration interface"""
    
    with gr.Blocks(title="Memory Explorer") as demo:
        gr.Markdown("# Memory System Explorer")
        gr.Markdown("Explore all your creations stored in the memory system")
        
        with gr.Tab("Search Memories"):
            with gr.Row():
                search_query = gr.Textbox(
                    label="Search by text",
                    placeholder="Ex: dragon, car, house..."
                )
                tag_dropdown = gr.Dropdown(
                    label="Filter by tag",
                    choices=get_all_tags(),
                    value=None
                )
            
            search_btn = gr.Button("Search", variant="primary")
            
            search_results = gr.Textbox(
                label="Search results",
                lines=20,
                max_lines=30
            )
            
            # Load all memories at startup
            demo.load(
                fn=lambda: format_memory_display(get_all_memories()),
                outputs=search_results
            )
            
            search_btn.click(
                fn=lambda q, t: format_memory_display(search_memories(q, t)),
                inputs=[search_query, tag_dropdown],
                outputs=search_results
            )
        
        with gr.Tab("Statistics"):
            stats_display = gr.Textbox(
                label="System Statistics",
                lines=15
            )
            
            refresh_stats_btn = gr.Button("Refresh Statistics")
            
            # Load statistics at startup
            demo.load(
                fn=get_memory_stats,
                outputs=stats_display
            )
            
            refresh_stats_btn.click(
                fn=get_memory_stats,
                outputs=stats_display
            )
        
        with gr.Tab("View Image"):
            memory_id_input = gr.Textbox(
                label="Memory ID",
                placeholder="Enter memory ID (ex: a1b2c3d4e5f6)"
            )
            
            load_image_btn = gr.Button("Load Image")
            
            memory_image = gr.Image(
                label="Memory Image",
                type="pil"
            )
            
            load_image_btn.click(
                fn=load_memory_image,
                inputs=memory_id_input,
                outputs=memory_image
            )
    
    return demo

if __name__ == "__main__":
    demo = create_memory_explorer()
    demo.launch(server_name="0.0.0.0", server_port=7861, share=False)
