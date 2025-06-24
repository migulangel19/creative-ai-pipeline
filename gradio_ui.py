import gradio as gr
import os
import socket
from datetime import datetime
import logging
from PIL import Image
import threading
import time
from memory_system import memory_system  # New import
import json

# Import the main execution function
from main import execute
from ontology_dc8f06af066e4a7880a5938933236037.input import InputClass
from ontology_dc8f06af066e4a7880a5938933236037.output import OutputClass
from openfabric_pysdk.context import AppModel

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global session state
session_state = {
    'generation_in_progress': False
}

def find_free_port(start_port=7860, max_attempts=100):
    """Find a free port starting from start_port"""
    for port in range(start_port, start_port + max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(('0.0.0.0', port))
                logger.info(f"Found free port: {port}")
                return port
        except OSError as e:
            logger.debug(f"Port {port} is busy: {e}")
            continue
    
    # If no port found in range, try some alternative ports
    alternative_ports = [8080, 8000, 8888, 9000, 9090, 5000, 3000]
    for port in alternative_ports:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(('0.0.0.0', port))
                logger.info(f"Found alternative free port: {port}")
                return port
        except OSError:
            continue
    
    raise RuntimeError(f"Could not find free port in range {start_port}-{start_port + max_attempts} or alternative ports")

def call_main_execute(prompt):
    """Call the main execute function and wait for completion"""
    try:
        # Create a mock AppModel with the prompt
        class MockModel:
            def __init__(self, prompt):
                self.request = InputClass()
                self.request.prompt = prompt
                self.response = OutputClass()
                self.expanded_prompt = ""  # Add this to store expanded prompt
        
        # Create model instance
        model = MockModel(prompt)
        
        # Call the main execute function (this handles everything)
        logger.info(f"Starting main execute with prompt: {prompt}")
        execute(model)
        
        logger.info("Main execute completed")
        
        # Try to extract expanded prompt from the response message
        expanded_prompt = ""
        if hasattr(model.response, 'message') and model.response.message:
            # Look for expanded prompt in the response message
            lines = model.response.message.split('\n')
            for line in lines:
                if 'expanded prompt' in line.lower() or 'detailed image description' in line.lower():
                    # Try to extract the expanded prompt
                    if ':' in line:
                        expanded_prompt = line.split(':', 1)[1].strip().strip("'\"")
                        break
        
        return (model.response.message if hasattr(model.response, 'message') else "Generation completed", 
                expanded_prompt)
        
    except Exception as e:
        logger.error(f"Error calling main execute: {e}")
        return f"Error: {str(e)}", ""

def find_latest_generated_image():
    """Find the most recently generated image"""
    try:
        latest_image = None
        latest_time = 0
        
        # Check current directory first
        # for img_name in ["output.png", "image.png", "generated.png"]:
        #     if os.path.exists(img_name):
        #         mod_time = os.path.getmtime(img_name)
        #         if mod_time > latest_time:
        #             latest_time = mod_time
        #             latest_image = img_name
        
        # Check memories directory
        memories_dir = "memories"
        if os.path.exists(memories_dir):
            # Get today's folder first
            today = datetime.now().strftime("%Y-%m-%d")
            today_path = os.path.join(memories_dir, today)
            
            folders_to_check = []
            if os.path.exists(today_path):
                folders_to_check.append(today_path)
            
            # Add other date folders
            for date_folder in os.listdir(memories_dir):
                date_path = os.path.join(memories_dir, date_folder)
                if os.path.isdir(date_path) and date_path != today_path:
                    folders_to_check.append(date_path)
            
            for date_path in folders_to_check:
                # Sort creation folders by modification time (newest first)
                creation_folders = []
                for creation_folder in os.listdir(date_path):
                    creation_path = os.path.join(date_path, creation_folder)
                    if os.path.isdir(creation_path):
                        creation_folders.append((creation_path, os.path.getmtime(creation_path)))
                
                creation_folders.sort(key=lambda x: x[1], reverse=True)
                
                for creation_path, _ in creation_folders:
                    for img_name in ["image.png", "output.png", "generated.png"]:
                        img_path = os.path.join(creation_path, img_name)
                        if os.path.exists(img_path):
                            mod_time = os.path.getmtime(img_path)
                            if mod_time > latest_time:
                                latest_time = mod_time
                                latest_image = img_path
        
        return latest_image
        
    except Exception as e:
        logger.error(f"Error finding latest image: {e}")
        return None

def find_latest_generated_glb():
    """Find the most recently generated GLB file"""
    try:
        latest_glb = None
        latest_time = 0
        
        # Check current directory first
        # for glb_name in ["output.glb", "model.glb", "generated.glb"]:
        #     if os.path.exists(glb_name):
        #         mod_time = os.path.getmtime(glb_name)
        #         if mod_time > latest_time:
        #             latest_time = mod_time
        #             latest_glb = glb_name
        
        # Check memories directory
        memories_dir = "memories"
        if os.path.exists(memories_dir):
            for date_folder in os.listdir(memories_dir):
                date_path = os.path.join(memories_dir, date_folder)
                if os.path.isdir(date_path):
                    for creation_folder in os.listdir(date_path):
                        creation_path = os.path.join(date_path, creation_folder)
                        if os.path.isdir(creation_path):
                            for glb_name in ["model.glb", "output.glb", "generated.glb"]:
                                glb_path = os.path.join(creation_path, glb_name)
                                if os.path.exists(glb_path):
                                    mod_time = os.path.getmtime(glb_path)
                                    if mod_time > latest_time:
                                        latest_time = mod_time
                                        latest_glb = glb_path
        
        return latest_glb
        
    except Exception as e:
        logger.error(f"Error finding latest GLB: {e}")
        return None

def generate_content(prompt):
    """Generate content and return all results at once"""
    if not prompt.strip():
        return "Please enter a prompt", None, "No generation started", None, ""
    
    if session_state['generation_in_progress']:
        return "Generation already in progress", None, "Please wait for current generation to complete", None, ""
    
    # Set generation flag
    session_state['generation_in_progress'] = True
    
    try:
        # Call main execute and wait for completion
        result_message, expanded_prompt = call_main_execute(prompt)
        
        # If we didn't get expanded prompt from response, try to find it in details file
        if not expanded_prompt:
            expanded_prompt = find_expanded_prompt_in_files()
        
        # Create prompt comparison display
        prompt_comparison = f"""ORIGINAL PROMPT:
{prompt}

EXPANDED PROMPT:
{expanded_prompt if expanded_prompt else 'Not available - check details.txt file'}"""
        
        # After completion, find the generated files
        image = None
        image_path = find_latest_generated_image()
        if image_path:
            try:
                image = Image.open(image_path)
                logger.info(f"Loaded image: {image_path}")
            except Exception as e:
                logger.error(f"Error loading image: {e}")
        
        # Find GLB and create info
        glb_info = "No 3D model generated"
        glb_file = None
        
        glb_path = find_latest_generated_glb()
        if glb_path:
            try:
                file_size = os.path.getsize(glb_path)
                mod_time = datetime.fromtimestamp(os.path.getmtime(glb_path))
                
                glb_info = f"""3D MODEL GENERATED:
File: {os.path.basename(glb_path)}
Size: {file_size:,} bytes ({file_size/1024:.1f} KB)
Created: {mod_time.strftime('%Y-%m-%d %H:%M:%S')}
Status: Ready for viewing

CONTROLS:
• Click and drag to rotate
• Scroll to zoom in/out
• Shift + drag to pan"""
                
                # Return the GLB file path for Gradio's Model3D component
                glb_file = glb_path
                logger.info(f"Loaded GLB: {glb_path}")
                
            except Exception as e:
                logger.error(f"Error processing GLB: {e}")
                glb_info = f"Error processing 3D model: {e}"
        
        return result_message, image, glb_info, glb_file, prompt_comparison
        
    except Exception as e:
        logger.error(f"Error in generation: {e}")
        return f"Generation failed: {str(e)}", None, "Generation failed", None, ""
    
    finally:
        session_state['generation_in_progress'] = False

def find_expanded_prompt_in_files():
    """Find the expanded prompt in the most recent details.txt file"""
    try:
        memories_dir = "memories"
        if not os.path.exists(memories_dir):
            return ""
        
        # Get today's folder first
        today = datetime.now().strftime("%Y-%m-%d")
        today_path = os.path.join(memories_dir, today)
        
        folders_to_check = []
        if os.path.exists(today_path):
            folders_to_check.append(today_path)
        
        # Add other recent date folders
        for date_folder in sorted(os.listdir(memories_dir), reverse=True)[:3]:  # Check last 3 days
            date_path = os.path.join(memories_dir, date_folder)
            if os.path.isdir(date_path) and date_path != today_path:
                folders_to_check.append(date_path)
        
        for date_path in folders_to_check:
            # Get most recent creation folder
            creation_folders = []
            for creation_folder in os.listdir(date_path):
                creation_path = os.path.join(date_path, creation_folder)
                if os.path.isdir(creation_path):
                    creation_folders.append((creation_path, os.path.getmtime(creation_path)))
            
            if creation_folders:
                creation_folders.sort(key=lambda x: x[1], reverse=True)
                most_recent_folder = creation_folders[0][0]
                
                details_file = os.path.join(most_recent_folder, "details.txt")
                if os.path.exists(details_file):
                    with open(details_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                        
                    # Extract expanded prompt from details file
                    lines = content.split('\n')
                    in_expanded_section = False
                    expanded_lines = []
                    
                    for line in lines:
                        if line.strip() == "EXPANDED PROMPT:":
                            in_expanded_section = True
                            continue
                        elif line.strip() == "KEYWORDS:" or line.strip() == "FILES:":
                            in_expanded_section = False
                            break
                        elif in_expanded_section and line.strip():
                            expanded_lines.append(line.strip())
                    
                    if expanded_lines:
                        return ' '.join(expanded_lines)
        
        return ""
        
    except Exception as e:
        logger.error(f"Error finding expanded prompt in files: {e}")
        return ""

def load_recent_creations():
    """Load recent creations from memory system"""
    try:
        recent_memories = memory_system.get_recent_memories(limit=20)
        if not recent_memories:
            return [], "No recent creations found"
        
        creation_options = []
        for memory in recent_memories:
            # Format: "2025-06-23 18:45 - create a dragon (ID: abc123)"
            timestamp = datetime.fromisoformat(memory.timestamp).strftime("%Y-%m-%d %H:%M")
            prompt_preview = memory.original_prompt[:50] + "..." if len(memory.original_prompt) > 50 else memory.original_prompt
            option_text = f"{timestamp} - {prompt_preview} (ID: {memory.id[:8]})"
            creation_options.append((option_text, memory.id))
        
        return creation_options, f"Found {len(recent_memories)} recent creations"
    except Exception as e:
        logger.error(f"Error loading recent creations: {e}")
        return [], f"Error loading creations: {str(e)}"

def load_creation_details(creation_id):
    """Load details for a specific creation"""
    if not creation_id:
        return None, "No creation selected", "", "", None
    
    try:
        memory = memory_system.recall_memory(creation_id)
        if not memory:
            return None, "Creation not found", "", "", None
        
        # Try to load the image
        image = None
        if memory.image_path and os.path.exists(memory.image_path):
            try:
                image = Image.open(memory.image_path)
            except Exception as e:
                logger.error(f"Error loading image: {e}")
        
        # Check for 3D model
        glb_file = None
        if memory.model_path and os.path.exists(memory.model_path):
            glb_file = memory.model_path
        
        # Create detailed info
        timestamp = datetime.fromisoformat(memory.timestamp).strftime("%Y-%m-%d %H:%M:%S")
        
        creation_info = f"""CREATION DETAILS:
ID: {memory.id}
Created: {timestamp}
Tags: {', '.join(memory.tags) if memory.tags else 'None'}

FILES:
Image: {'✓ Available' if image else '✗ Not found'} ({memory.image_path})
3D Model: {'✓ Available' if glb_file else '✗ Not found'} ({memory.model_path})

METADATA:
{json.dumps(memory.metadata, indent=2) if memory.metadata else 'None'}"""
        
        # Create prompt comparison
        prompt_comparison = f"""ORIGINAL PROMPT:
{memory.original_prompt}

EXPANDED PROMPT:
{memory.expanded_prompt}"""
        
        return image, creation_info, prompt_comparison, memory.id, glb_file
        
    except Exception as e:
        logger.error(f"Error loading creation details: {e}")
        return None, f"Error: {str(e)}", "", "", None

def refresh_recent_creations():
    """Refresh the recent creations list"""
    creation_options, status = load_recent_creations()
    if creation_options:
        return gr.Dropdown.update(choices=creation_options, value=creation_options[0][1]), status
    else:
        return gr.Dropdown.update(choices=[], value=None), status

def navigate_creation(current_id, direction):
    """Navigate to previous or next creation"""
    try:
        creation_options, _ = load_recent_creations()
        if not creation_options:
            return current_id
        
        # Find current index
        current_index = -1
        for i, (_, creation_id) in enumerate(creation_options):
            if creation_id == current_id:
                current_index = i
                break
        
        if current_index == -1:
            return creation_options[0][1] if creation_options else current_id
        
        # Navigate
        if direction == "prev" and current_index > 0:
            return creation_options[current_index - 1][1]
        elif direction == "next" and current_index < len(creation_options) - 1:
            return creation_options[current_index + 1][1]
        else:
            return current_id
            
    except Exception as e:
        logger.error(f"Error navigating creation: {e}")
        return current_id

def reset_session():
    """Reset the current session"""
    session_state['generation_in_progress'] = False
    return "Session reset!", None, "Session reset - no files loaded", None, ""

def create_interface():
    with gr.Blocks(title="AI Creative Studio") as demo:
        gr.Markdown("# AI Creative Studio")
        gr.Markdown("Create stunning 3D objects and images using AI")
        
        with gr.Tabs():
            # Main Generation Tab
            with gr.TabItem("Generate"):
                with gr.Row():
                    with gr.Column(scale=2):
                        prompt_input = gr.Textbox(
                            label="Enter your prompt",
                            placeholder="e.g., 'create a majestic lion'",
                            lines=3
                        )
                        
                        with gr.Row():
                            generate_btn = gr.Button("Generate", variant="primary", size="lg")
                            reset_btn = gr.Button("Reset", size="lg")
                        
                        status_display = gr.Textbox(
                            label="Status",
                            interactive=False,
                            lines=4
                        )
                        
                        prompt_comparison = gr.Textbox(
                            label="Prompt Comparison (Original vs Expanded)",
                            interactive=False,
                            lines=6,
                            value="Enter a prompt and generate to see the comparison..."
                        )

                with gr.Row():
                    with gr.Column():
                        generated_image = gr.Image(
                            label="Generated Image",
                            type="pil",
                            height=400
                        )
                    
                    with gr.Column():
                        glb_info_display = gr.Textbox(
                            label="3D Model Information",
                            interactive=False,
                            lines=10
                        )
                
                with gr.Row():
                    glb_viewer = gr.Model3D(
                        label="3D Model Viewer - Interactive GLB Display",
                        height=500,
                        camera_position=(3, 3, 3),
                        zoom_speed=0.5
                    )
            
            # Recent Creations Tab
            with gr.TabItem("Recent Creations"):
                with gr.Row():
                    with gr.Column(scale=3):
                        with gr.Row():
                            creation_dropdown = gr.Dropdown(
                                label="Select Creation",
                                choices=[],
                                value=None,
                                interactive=True
                            )
                            refresh_btn = gr.Button("Refresh", size="sm")
                        
                        with gr.Row():
                            prev_btn = gr.Button("← Previous", size="sm")
                            next_btn = gr.Button("Next →", size="sm")
                        
                        recent_status = gr.Textbox(
                            label="Status",
                            interactive=False,
                            lines=2
                        )
                    
                    with gr.Column(scale=2):
                        creation_info_display = gr.Textbox(
                            label="Creation Information",
                            interactive=False,
                            lines=15
                        )
                
                with gr.Row():
                    with gr.Column():
                        recent_image_display = gr.Image(
                            label="Creation Image",
                            type="pil",
                            height=400
                        )
                    
                    with gr.Column():
                        recent_prompt_comparison = gr.Textbox(
                            label="Prompt Details",
                            interactive=False,
                            lines=15
                        )
                
                # Add 3D Model viewer for recent creations
                with gr.Row():
                    recent_glb_viewer = gr.Model3D(
                        label="3D Model Viewer - Recent Creation",
                        height=500,
                        camera_position=(3, 3, 3),
                        zoom_speed=0.5
                    )
                
                # Hidden state to track current creation ID
                current_creation_id = gr.State(value="")
        
        # Event handlers for main generation
        generate_btn.click(
            fn=generate_content,
            inputs=[prompt_input],
            outputs=[status_display, generated_image, glb_info_display, glb_viewer, prompt_comparison]
        )
        
        reset_btn.click(
            fn=reset_session,
            outputs=[status_display, generated_image, glb_info_display, glb_viewer, prompt_comparison]
        )
        
        # Event handlers for recent creations
        refresh_btn.click(
            fn=refresh_recent_creations,
            outputs=[creation_dropdown, recent_status]
        )
        
        creation_dropdown.change(
            fn=load_creation_details,
            inputs=[creation_dropdown],
            outputs=[recent_image_display, creation_info_display, recent_prompt_comparison, current_creation_id, recent_glb_viewer]
        )
        
        prev_btn.click(
            fn=lambda current_id: navigate_creation(current_id, "prev"),
            inputs=[current_creation_id],
            outputs=[creation_dropdown]
        ).then(
            fn=load_creation_details,
            inputs=[creation_dropdown],
            outputs=[recent_image_display, creation_info_display, recent_prompt_comparison, current_creation_id, recent_glb_viewer]
        )
        
        next_btn.click(
            fn=lambda current_id: navigate_creation(current_id, "next"),
            inputs=[current_creation_id],
            outputs=[creation_dropdown]
        ).then(
            fn=load_creation_details,
            inputs=[creation_dropdown],
            outputs=[recent_image_display, creation_info_display, recent_prompt_comparison, current_creation_id, recent_glb_viewer]
        )
        
        # Load recent creations on startup
        demo.load(
            fn=refresh_recent_creations,
            outputs=[creation_dropdown, recent_status]
        )
    
    return demo

if __name__ == "__main__":
    try:
        # Check for environment variable first
        port = int(os.environ.get('GRADIO_SERVER_PORT', 7860))
        logger.info(f"Trying to use port from environment: {port}")
        
        # Try to find a free port
        free_port = find_free_port(port)
        logger.info(f"Starting Gradio UI on port {free_port}")
        
        demo = create_interface()
        demo.launch(
            server_name="0.0.0.0",
            server_port=free_port,
            share=False,
            show_error=True,
            quiet=False
        )
        
    except Exception as e:
        logger.error(f"Failed to start Gradio UI: {e}")
        logger.info("Trying with automatic port selection...")
        
        # Fallback: let Gradio choose the port automatically
        demo = create_interface()
        demo.launch(
            server_name="0.0.0.0",
            share=False,
            show_error=True,
            quiet=False
        )
