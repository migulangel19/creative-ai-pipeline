import os
from datetime import datetime
from PIL import Image

def explore_memory_files():
    """Explore physical memory system files"""
    
    memories_dir = "memories"
    
    if not os.path.exists(memories_dir):
        print("Memories directory does not exist")
        return
    
    print("MEMORY FILES EXPLORER")
    print("=" * 50)
    
    total_folders = 0
    total_images = 0
    total_models = 0
    total_size = 0
    
    # Browse by dates
    date_folders = sorted(os.listdir(memories_dir), reverse=True)
    
    for date_folder in date_folders:
        date_path = os.path.join(memories_dir, date_folder)
        
        if not os.path.isdir(date_path):
            continue
        
        print(f"\n{date_folder}")
        print("-" * 30)
        
        creation_folders = os.listdir(date_path)
        creation_folders.sort(key=lambda x: os.path.getmtime(os.path.join(date_path, x)), reverse=True)
        
        for creation_folder in creation_folders:
            creation_path = os.path.join(date_path, creation_folder)
            
            if not os.path.isdir(creation_path):
                continue
            
            total_folders += 1
            
            # Analyze folder content
            files = os.listdir(creation_path)
            
            has_image = any(f.endswith('.png') for f in files)
            has_model = any(f.endswith('.glb') for f in files)
            has_details = 'details.txt' in files
            
            if has_image:
                total_images += 1
            if has_model:
                total_models += 1
            
            # Calculate size
            folder_size = 0
            for file in files:
                file_path = os.path.join(creation_path, file)
                if os.path.isfile(file_path):
                    folder_size += os.path.getsize(file_path)
            
            total_size += folder_size
            
            # Show information
            mod_time = datetime.fromtimestamp(os.path.getmtime(creation_path))
            
            print(f"  {creation_folder}")
            print(f"     Time: {mod_time.strftime('%H:%M:%S')}")
            print(f"     Size: {folder_size/1024:.1f} KB")
            print(f"     Files: {'IMG' if has_image else 'NO'} {'3D' if has_model else 'NO'} {'TXT' if has_details else 'NO'}")
            
            # Read details.txt if exists
            details_path = os.path.join(creation_path, 'details.txt')
            if has_details:
                try:
                    with open(details_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                        # Extract original prompt
                        lines = content.split('\n')
                        for line in lines:
                            if line.startswith('ORIGINAL PROMPT:'):
                                next_line_idx = lines.index(line) + 1
                                if next_line_idx < len(lines):
                                    prompt = lines[next_line_idx].strip()
                                    print(f"     Prompt: {prompt[:50]}...")
                                break
                except:
                    pass
    
    print(f"\nTOTAL SUMMARY:")
    print(f"- Creation folders: {total_folders}")
    print(f"- Generated images: {total_images}")
    print(f"- Generated 3D models: {total_models}")
    print(f"- Total size: {total_size/1024/1024:.2f} MB")

def show_recent_creations(limit=5):
    """Show most recent creations"""
    memories_dir = "memories"
    
    if not os.path.exists(memories_dir):
        print("Memories directory does not exist")
        return
    
    # Find all creation folders
    all_creations = []
    
    for date_folder in os.listdir(memories_dir):
        date_path = os.path.join(memories_dir, date_folder)
        
        if not os.path.isdir(date_path):
            continue
        
        for creation_folder in os.listdir(date_path):
            creation_path = os.path.join(date_path, creation_folder)
            
            if os.path.isdir(creation_path):
                mod_time = os.path.getmtime(creation_path)
                all_creations.append((mod_time, creation_path, creation_folder))
    
    # Sort by modification date (most recent first)
    all_creations.sort(reverse=True)
    
    print(f"LAST {min(limit, len(all_creations))} CREATIONS:")
    print("=" * 60)
    
    for i, (mod_time, creation_path, creation_folder) in enumerate(all_creations[:limit]):
        timestamp = datetime.fromtimestamp(mod_time)
        
        print(f"\n#{i+1} - {creation_folder}")
        print(f"Date: {timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Show files
        files = os.listdir(creation_path)
        for file in files:
            file_path = os.path.join(creation_path, file)
            if os.path.isfile(file_path):
                size = os.path.getsize(file_path)
                if file.endswith('.png'):
                    print(f"IMAGE: {file} ({size/1024:.1f} KB)")
                elif file.endswith('.glb'):
                    print(f"3D MODEL: {file} ({size/1024:.1f} KB)")
                elif file.endswith('.txt'):
                    print(f"TEXT: {file}")
        
        # Read prompt from details.txt
        details_path = os.path.join(creation_path, 'details.txt')
        if os.path.exists(details_path):
            try:
                with open(details_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    lines = content.split('\n')
                    for line in lines:
                        if line.startswith('ORIGINAL PROMPT:'):
                            next_line_idx = lines.index(line) + 1
                            if next_line_idx < len(lines):
                                prompt = lines[next_line_idx].strip()
                                print(f"PROMPT: {prompt}")
                            break
            except:
                pass

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "recent":
        limit = int(sys.argv[2]) if len(sys.argv) > 2 else 5
        show_recent_creations(limit)
    else:
        explore_memory_files()
