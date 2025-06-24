import json
import logging
import base64
import io
from PIL import Image
from typing import Dict
import tempfile
import os
import re
from datetime import datetime

from ontology_dc8f06af066e4a7880a5938933236037.config import ConfigClass
from ontology_dc8f06af066e4a7880a5938933236037.input import InputClass
from ontology_dc8f06af066e4a7880a5938933236037.output import OutputClass
from openfabric_pysdk.context import AppModel, State
from core.stub import Stub
from memory_system import memory_system

import requests

# Configurations dictionary for storing user configs
configurations: Dict[str, ConfigClass] = dict()

def create_short_folder_name(keywords: list, max_length: int = 15) -> str:
    """Create a short folder name from keywords"""
    if not keywords:
        return "creation"
    
    # Take first 2-3 keywords and clean them
    selected_keywords = keywords[:3]
    safe_keywords = []
    
    for kw in selected_keywords:
        # Clean keyword
        clean_kw = re.sub(r'[^\w]', '', kw.lower())
        if clean_kw and len(clean_kw) > 2:  # Only meaningful keywords
            safe_keywords.append(clean_kw)
    
    if not safe_keywords:
        return "creation"
    
    # Join with hyphens and limit length
    folder_name = '-'.join(safe_keywords)
    if len(folder_name) > max_length:
        folder_name = folder_name[:max_length]
    
    return folder_name.strip('-')

############################################################
# Config callback function
############################################################
def config(configuration: Dict[str, ConfigClass], state: State) -> None:
    """
    Stores user-specific configuration data.

    Args:
        configuration: Mapping of user IDs to configuration objects.
        state: Current application state (not used here).
    """
    for uid, conf in configuration.items():
        logging.info(f"Saving new config for user with id:'{uid}'")
        configurations[uid] = conf

############################################################
# Execution callback function
############################################################
def execute(model: AppModel) -> None:
    """
    Main execution entry point for handling a model pass.

    Args:
        model: The model object containing request and response.
    """

    # Retrieve input prompt from the request
    request: InputClass = model.request
    logging.info(f"Starting creative pipeline with prompt: '{request.prompt}'")

    # MEMORY: Check for similar memories first
    similar_memories = memory_system.find_similar(request.prompt)
    if similar_memories:
        logging.info(f"Found {len(similar_memories)} similar memories:")
        for memory in similar_memories:
            logging.info(f"   - '{memory.original_prompt}' (ID: {memory.id})")

    # Retrieve super-user config
    user_config: ConfigClass = configurations.get('super-user', None)
    logging.info(f"{configurations}")

    # Initialize list of app IDs for Stub
    app_ids = user_config.app_ids if user_config else []

    # Ensure both app IDs are included - USING THE WORKING API IDs
    text_to_image_id = "c25dcd829d134ea98f5ae4dd311d13bc.node3.openfabric.network"
    image_to_3d_id_1 = "35666222571f43378da37a98104044dc.node3.openfabric.network"   # THE ONE THAT WORKS!
    image_to_3d_id_2 = "166d2212647b4a44ac48edada6bff3d3.node3.openfabric.network"  # Backup
    
    # List of 3D APIs to try in order of preference (working one first)
    image_to_3d_apis = [
        {"id": image_to_3d_id_1, "name": "3D API v2 (Working)"},
        {"id": image_to_3d_id_2, "name": "3D API v1 (Backup)"}
    ]
    
    if text_to_image_id not in app_ids:
        app_ids.append(text_to_image_id)
    if image_to_3d_id_1 not in app_ids:
        app_ids.append(image_to_3d_id_1)
    if image_to_3d_id_2 not in app_ids:
        app_ids.append(image_to_3d_id_2)

    # Initialize Stub with the app IDs
    stub = Stub(app_ids)

    # Add this right after initializing the stub
    logging.info(f"Stub initialized with apps: {app_ids}")
    logging.info(f"Available connections: {list(stub._connections.keys()) if hasattr(stub, '_connections') else 'No connections attribute'}")

    # Test connectivity
    for app_id in app_ids:
        try:
            # You might want to add a simple connectivity test here
            logging.info(f"App {app_id} - attempting connection test")
        except Exception as conn_error:
            logging.error(f"Connection issue with {app_id}: {conn_error}")

    # MEMORY: Extract keywords in parallel with prompt expansion
    logging.info("Extracting keywords for memory system...")
    extracted_keywords = []
    try:
        keywords_response = requests.post("http://ollama:11434/api/generate", json={
            "model": "llama3",
            "prompt": f"""Extract 3-5 simple keywords from this prompt. Return ONLY the keywords separated by commas, nothing else.

Prompt: "{request.prompt}"

Keywords:""",
            "stream": False
        }, timeout=60)
        
        keywords_response.raise_for_status()
        keywords_text = keywords_response.json().get("response", "").strip()
        
        # Parse keywords from response - be more aggressive in cleaning
        raw_keywords = [kw.strip().lower() for kw in keywords_text.split(',') if kw.strip()]
        extracted_keywords = []
        
        for kw in raw_keywords:
            # Clean up keywords - remove common words and artifacts
            clean_kw = re.sub(r'[^\w\s]', '', kw)  # Remove punctuation
            clean_kw = clean_kw.strip()
            
            # Skip common words and artifacts
            skip_words = ['objects', 'actions', 'styles', 'colors', 'settings', 'emotions', 'returned', 'keywords']
            if clean_kw and len(clean_kw) > 2 and clean_kw not in skip_words:
                extracted_keywords.append(clean_kw)
        
        extracted_keywords = extracted_keywords[:5]  # Limit to 5 keywords
        
        logging.info(f"Extracted keywords: {extracted_keywords}")
        
    except Exception as e:
        logging.error(f"Error extracting keywords: {e}")
        extracted_keywords = []

    # ------------------------------
    # TODO : add your magic here
    # ------------------------------
    try:
        # Call LLaMA to expand the prompt
        logging.info(f"Original prompt: {request.prompt}")
        llama_response = requests.post("http://ollama:11434/api/generate", json={
            "model": "llama3",
            "prompt": f"Expand this prompt to generate a detailed image description (max 60 words): {request.prompt}",
            "stream": False
        }, timeout=180)

        llama_response.raise_for_status()
        expanded_prompt = llama_response.json().get("response", "").strip()
        
        # Ensure prompt doesn't exceed 60 words
        words = expanded_prompt.split()
        if len(words) > 60:
            expanded_prompt = " ".join(words[:60])
            
        logging.info(f"Expanded prompt ({len(expanded_prompt.split())} words): {expanded_prompt}")

    except Exception as e:
        logging.error(f"Error calling LLaMA: {e}")
        # Use original prompt as fallback
        expanded_prompt = request.prompt

    # Abort if prompt expansion failed
    if not expanded_prompt:
        response: OutputClass = model.response
        response.message = "Prompt expansion failed."
        return

    try:
        # Check connectivity to each app
        for app_id in app_ids:
            if app_id in stub._connections:
                logging.info(f"Connected to app: {app_id}")
            else:
                logging.warning(f"Not connected to app: {app_id}")

        # Step 1: Call the Text-to-Image app
        logging.info("Step 1: Generating image from text...")
        image_result = stub.call(
            text_to_image_id,
            {"prompt": expanded_prompt},
            "super-user"
        )

        # Get the raw image data (bytes)
        image_data = image_result.get("result")
        if not image_data:
            raise Exception("No image data returned from Text-to-Image app.")

        logging.info(f"Image data received: {type(image_data)}, size: {len(image_data)} bytes")

        # MEMORY: Create improved folder structure with SHORT names
        timestamp = datetime.now().strftime("%H%M%S")
        date_folder = datetime.now().strftime("%Y-%m-%d")
        memory_id = memory_system.generate_memory_id(request.prompt)
        
        # Create SHORT descriptive folder name from keywords
        short_name = create_short_folder_name(extracted_keywords)
        creation_folder_name = f"{short_name}_{timestamp}_{memory_id[:6]}"
        creation_folder_path = f"memories/{date_folder}/{creation_folder_name}"
        os.makedirs(creation_folder_path, exist_ok=True)
        
        logging.info(f"Created creation folder: {creation_folder_path}")

        # Save the image locally as output.png AND in organized memory folder
        with open("output.png", "wb") as f:
            f.write(image_data)
        
        image_filename = f"{creation_folder_path}/image.png"
        with open(image_filename, "wb") as f:
            f.write(image_data)
        logging.info(f"Image generated and saved as output.png and {image_filename}")

        # Step 2: Convert image to 3D model - USING YOUR WORKING APPROACH
        logging.info("Step 2: Converting image to 3D model...")
        model_saved = False
        model_filename = f"{creation_folder_path}/model.glb"
        successful_api = None

        # Process image using YOUR WORKING METHOD
        try:
            # Validate the image
            image = Image.open(io.BytesIO(image_data))
            logging.info(f"Image validation successful: {image.format}, size: {image.size}, mode: {image.mode}")
            
            # Convert to RGB if necessary
            if image.mode in ('RGBA', 'LA'):
                logging.info(f"Converting image from {image.mode} to RGB")
                background = Image.new('RGB', image.size, (255, 255, 255))
                if image.mode == 'RGBA':
                    background.paste(image, mask=image.split()[-1])
                else:
                    background.paste(image)
                image = background
            elif image.mode != 'RGB':
                logging.info(f"Converting image from {image.mode} to RGB")
                image = image.convert('RGB')
            
            # Resize if too large
            max_size = 1024
            if max(image.size) > max_size:
                logging.info(f"Resizing image from {image.size} to fit {max_size}px")
                image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            
            # Save as PNG (YOUR WORKING FORMAT)
            png_buffer = io.BytesIO()
            image.save(png_buffer, format='PNG')
            png_data = png_buffer.getvalue()
            logging.info(f"Processed image: PNG, {len(png_data)} bytes, size: {image.size}")

            # Convert to base64 WITHOUT data URI prefix (YOUR WORKING METHOD)
            image_base64 = base64.b64encode(png_data).decode('utf-8')

        except Exception as img_error:
            logging.error(f"Error processing image: {img_error}")
            # Fallback to original data
            image_base64 = base64.b64encode(image_data).decode('utf-8')

        # Try each 3D API with YOUR WORKING METHOD
        for api_info in image_to_3d_apis:
            api_id = api_info["id"]
            api_name = api_info["name"]
            
            # Check if this API is connected
            if api_id not in stub._connections:
                logging.warning(f"Skipping {api_name} - not connected")
                continue
                
            logging.info(f"Trying {api_name}...")
            
            try:
                # Use YOUR WORKING METHOD: Pure base64 without data URI
                logging.info(f"Calling {api_name} with PNG base64...")
                three_d_result = stub.call(
                    api_id,
                    {"input_image": image_base64},
                    "super-user"
                )
                
                if three_d_result:
                    logging.info(f"Success with {api_name}!")
                    successful_api = api_name
                    break
                else:
                    logging.warning(f"{api_name} returned no result")
                    
            except Exception as api_error:
                logging.warning(f"{api_name} failed: {str(api_error)}")
                continue

        # Process the 3D result if we got one
        if three_d_result:
            logging.info(f"3D service response keys: {list(three_d_result.keys()) if isinstance(three_d_result, dict) else 'Not a dict'}")
            
            # Process the 3D model result
            model_data = three_d_result.get("generated_object")
            
            if model_data:
                try:
                    if isinstance(model_data, str):
                        model_bytes = base64.b64decode(model_data)
                    else:
                        model_bytes = model_data
                except Exception as decode_error:
                    logging.warning(f"Could not decode model data as base64: {decode_error}")
                    model_bytes = model_data.encode() if isinstance(model_data, str) else model_data
                
                # Save the 3D model in both locations
                with open("output.glb", "wb") as f:
                    f.write(model_bytes)
                with open(model_filename, "wb") as f:
                    f.write(model_bytes)
                logging.info(f"3D model saved as output.glb and {model_filename} ({len(model_bytes)} bytes)")
                logging.info(f"3D conversion successful using: {successful_api}")
                model_saved = True
            else:
                logging.warning("No 3D model data in response")
                model_filename = "none"
        else:
            logging.warning("All 3D APIs failed")
            model_filename = "none"

        # MEMORY: Store everything in memory system
        logging.info("Storing memory...")
        
        memory_id = memory_system.store_memory(
            original_prompt=request.prompt,
            expanded_prompt=expanded_prompt,
            image_path=image_filename,
            model_path=model_filename,
            keywords=extracted_keywords,
            metadata={
                'image_size': len(image_data),
                'model_generated': model_saved,
                'timestamp': timestamp,
                'keywords_source': 'llama' if extracted_keywords else 'fallback',
                'creation_folder': creation_folder_path,
                'successful_3d_api': successful_api if model_saved else None
            }
        )
        
        # Save detailed information file
        details_file_path = f"{creation_folder_path}/details.txt"
        details_content = f"""CREATION DETAILS
================

Memory ID: {memory_id}
Timestamp: {datetime.now().isoformat()}
Creation Folder: {creation_folder_path}

ORIGINAL PROMPT:
{request.prompt}

EXPANDED PROMPT:
{expanded_prompt}

KEYWORDS:
{', '.join(extracted_keywords)}

FILES:
- Image: image.png
- 3D Model: {'model.glb' if model_saved else 'FAILED'}

METADATA:
- Image Size: {len(image_data)} bytes
- Model Generated: {model_saved}
- Keywords Source: {'LLaMA' if extracted_keywords else 'Fallback'}
- Successful 3D API: {successful_api if model_saved else 'None'}
"""
        
        with open(details_file_path, 'w', encoding='utf-8') as f:
            f.write(details_content)
        
        logging.info(f"Details file saved: {details_file_path}")
        logging.info(f"Memory stored with ID: {memory_id}")

        # Get memory stats for response
        stats = memory_system.get_memory_stats()

        # Set success response
        response: OutputClass = model.response
        if model_saved:
            response.message = f"""Successfully generated image and 3D model from prompt: '{expanded_prompt}'

Creation saved in: {creation_folder_path}
Files:
- image.png
- model.glb  
- details.txt

Memory ID: {memory_id}
Keywords: {', '.join(extracted_keywords)}
3D API Used: {successful_api}

Memory Stats: {stats['total_memories']} total memories stored"""
        else:
            response.message = f"""Successfully generated image from prompt: '{expanded_prompt}'

Creation saved in: {creation_folder_path}
Files:
- image.png
- details.txt
- 3D conversion failed (tried both APIs)

Memory ID: {memory_id}
Keywords: {', '.join(extracted_keywords)}

Memory Stats: {stats['total_memories']} total memories stored"""
        
        logging.info("Pipeline completed successfully!")

    except Exception as e:
        logging.error(f"Error in pipeline: {str(e)}", exc_info=True)
        response: OutputClass = model.response
        response.message = f"Pipeline failed: {str(e)}"
