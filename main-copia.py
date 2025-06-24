import json
import logging
import base64
import io
from PIL import Image
from typing import Dict
import tempfile
import os
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
        logging.info(f"Saving new config for user with id: '{uid}'")
        configurations[uid] = conf

############################################################
# Execution callback function
############################################################
def execute(model: AppModel) -> None:
    """
    Main execution entry point for the AI Creative Pipeline
    
    Pipeline: Text -> LLM Enhancement -> Image Generation -> 3D Model -> Memory Storage
    
    Args:
        model: The model object containing request and response.
    """

    # Retrieve input prompt from the request
    request: InputClass = model.request
    logging.info(f"Starting creative pipeline with prompt: '{request.prompt}'")

    # Check for similar memories first
    similar_memories = memory_system.find_similar(request.prompt)
    if similar_memories:
        logging.info(f"Found {len(similar_memories)} similar memories:")
        for memory in similar_memories:
            logging.info(f"   - '{memory.original_prompt}' (ID: {memory.id})")

    # Retrieve super-user config
    user_config: ConfigClass = configurations.get('super-user', None)
    logging.info(f"Configuration loaded: {configurations}")

    # Initialize list of app IDs for Stub
    app_ids = user_config.app_ids if user_config else []

    # Ensure both app IDs are included
    text_to_image_id = "c25dcd829d134ea98f5ae4dd311d13bc.node3.openfabric.network"
    #image_to_3d_id = "166d2212647b4a44ac48edada6bff3d3.node3.openfabric.network"
    image_to_3d_id = "35666222571f43378da37a98104044dc.node3.openfabric.network"
    
    if text_to_image_id not in app_ids:
        app_ids.append(text_to_image_id)
    if image_to_3d_id not in app_ids:
        app_ids.append(image_to_3d_id)

    # Initialize Stub with the app IDs
    stub = Stub(app_ids)

    # STEP 0: PROMPT ENHANCEMENT
    try:
        logging.info("Step 0: Enhancing prompt with LLaMA...")
        logging.info(f"Original prompt: {request.prompt}")
        
        llama_response = requests.post("http://ollama:11434/api/generate", json={
            "model": "llama3",
            "prompt": f"""Expand this prompt to generate a detailed image description following this format:
'Wide angle camera shot of [subject] [action/pose] [location/setting] [style/quality descriptors], highly realistic, high quality'

Original prompt: {request.prompt}

Keep it under 60 words and end with 'highly realistic, high quality':""",
            "stream": False
        }, timeout=180)

        llama_response.raise_for_status()
        expanded_prompt = llama_response.json().get("response", "").strip()
        
        # Ensure prompt doesn't exceed 60 words
        words = expanded_prompt.split()
        if len(words) > 60:
            expanded_prompt = " ".join(words[:60])
            
        logging.info(f"Enhanced prompt ({len(expanded_prompt.split())} words): {expanded_prompt}")

    except Exception as e:
        logging.error(f"Error calling LLaMA: {e}")
        expanded_prompt = request.prompt
        logging.info(f"Using original prompt as fallback: {expanded_prompt}")

    # Abort if prompt expansion failed
    if not expanded_prompt:
        response: OutputClass = model.response
        response.message = "Prompt enhancement failed."
        return

    try:
        # Check connectivity to each app
        for app_id in app_ids:
            if app_id in stub._connections:
                logging.info(f"Connected to app: {app_id}")
            else:
                logging.warning(f"Not connected to app: {app_id}")

        # STEP 1: IMAGE GENERATION
        logging.info("Step 1: Generating image from enhanced prompt...")
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

        # Generate unique filenames with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        date_folder = datetime.now().strftime("%Y-%m-%d")
        memory_folder = f"memories/{date_folder}"
        os.makedirs(memory_folder, exist_ok=True)

        image_filename = f"{memory_folder}/output_{timestamp}.png"
        model_filename = f"{memory_folder}/output_{timestamp}.glb"

        # Save the image locally
        with open(image_filename, "wb") as f:
            f.write(image_data)
        logging.info(f"Image generated and saved as {image_filename}")

        # STEP 2: 3D MODEL CONVERSION
        logging.info("Step 2: Converting image to 3D model...")
        model_saved = False
        
        try:
            # Try different image formats for the 3D API
            # First, try with just base64 without data URI prefix
            encoded_image = base64.b64encode(image_data).decode('utf-8')
            
            # Try multiple payload formats
            payload_formats = [
                {"input_image": encoded_image},  # Just base64
                {"input_image": f"data:image/png;base64,{encoded_image}"},  # With data URI
            ]
            
            three_d_result = None
            for i, payload in enumerate(payload_formats):
                try:
                    logging.info(f"Trying 3D conversion format {i+1}/2...")
                    three_d_result = stub.call(
                        image_to_3d_id,
                        payload,
                        "super-user"
                    )
                    if three_d_result:
                        logging.info(f"3D conversion successful with format {i+1}")
                        break
                except Exception as e:
                    logging.warning(f"3D conversion format {i+1} failed: {e}")
                    continue
            
            if three_d_result:
                logging.info(f"3D service response keys: {list(three_d_result.keys())}")
                
                # Process the 3D model result
                model_data = three_d_result.get("generated_object")
                
                if model_data:
                    # Handle the 3D model data
                    if isinstance(model_data, str):
                        try:
                            model_bytes = base64.b64decode(model_data)
                        except:
                            model_bytes = model_data.encode() if isinstance(model_data, str) else model_data
                    else:
                        model_bytes = model_data
                    
                    # Save the 3D model
                    with open(model_filename, "wb") as f:
                        f.write(model_bytes)
                    logging.info(f"3D model saved as {model_filename} ({len(model_bytes)} bytes)")
                    model_saved = True
                else:
                    logging.warning("No 3D model data in response")
                    model_filename = "none"
            else:
                logging.warning("All 3D conversion attempts failed")
                model_filename = "none"
                
        except Exception as e:
            logging.error(f"3D conversion failed: {e}")
            model_filename = "none"

        # STEP 3: MEMORY STORAGE
        logging.info("Step 3: Storing memory...")
        
        memory_id = memory_system.store_memory(
            original_prompt=request.prompt,
            expanded_prompt=expanded_prompt,
            image_path=image_filename,
            model_path=model_filename,
            metadata={
                'image_size': len(image_data),
                'model_generated': model_saved,
                'timestamp': timestamp
            }
        )
        
        # Save prompts to organized folders (same folder as images)
        prompt_file_path = memory_system.save_prompt_to_folder(
            original_prompt=request.prompt,
            expanded_prompt=expanded_prompt,
            memory_id=memory_id,
            folder_path=memory_folder  # Pass the same folder
        )
        logging.info(f"Prompt file saved: {prompt_file_path}")
        
        logging.info(f"Memory stored with ID: {memory_id}")

        # Get memory stats for response
        stats = memory_system.get_memory_stats()
        
        # Set success response
        response: OutputClass = model.response
        if model_saved:
            response.message = f"""Creative pipeline completed successfully!

Original: "{request.prompt}"
Enhanced: "{expanded_prompt}"
Image: {image_filename}
3D Model: {model_filename}
Memory ID: {memory_id}

Memory Stats: {stats['total_memories']} total memories stored"""
        else:
            response.message = f"""Pipeline partially completed!

Original: "{request.prompt}"
Enhanced: "{expanded_prompt}"
Image: {image_filename}
3D conversion failed (external API issue)
Memory ID: {memory_id}

Memory Stats: {stats['total_memories']} total memories stored"""
        
        logging.info("Creative pipeline completed successfully!")

    except Exception as e:
        logging.error(f"Error in pipeline: {str(e)}", exc_info=True)
        response: OutputClass = model.response
        response.message = f"Pipeline failed: {str(e)}"
