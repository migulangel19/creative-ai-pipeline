import json
import logging
import base64  # Added for base64 encoding
import io
from PIL import Image
from typing import Dict
import tempfile
import os

from ontology_dc8f06af066e4a7880a5938933236037.config import ConfigClass
from ontology_dc8f06af066e4a7880a5938933236037.input import InputClass
from ontology_dc8f06af066e4a7880a5938933236037.output import OutputClass
from openfabric_pysdk.context import AppModel, State
from core.stub import Stub

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

    # Retrieve super-user config
    user_config: ConfigClass = configurations.get('super-user', None)
    logging.info(f"{configurations}")

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

        # Log the complete response structure
        #logging.info(f"Complete image_result: {image_result}")
        #logging.info(f"Image result type: {type(image_result)}")
        #logging.info(f"Image result keys: {list(image_result.keys()) if isinstance(image_result, dict) else 'Not a dict'}")

        # Get the raw image data (bytes)
        image_data = image_result.get("result")
        if not image_data:
            raise Exception("No image data returned from Text-to-Image app.")

        logging.info(f"Image data received: {type(image_data)}, size: {len(image_data)} bytes")

        # Save the image locally as output.png
        with open("output.png", "wb") as f:
            f.write(image_data)
        logging.info("Image generated and saved as output.png")

        # Step 2: Convert image to 3D model
        logging.info("Step 2: Converting image to 3D model...")

        # Let's try to understand what format the 3D API actually expects
        # Based on the schema, it wants a string, but let's try different interpretations
        
        # First, let's see if there's a resource ID or URL in the original response
        # that we should be passing instead of the binary data
        
        # Check if the original response contains resource information
        logging.info("Analyzing original image response for resource information...")
        
        # Try to find any resource identifiers in the response
        resource_info = None
        for key, value in image_result.items():
            if key != "result":
                logging.info(f"Additional field in image response: {key} = {value}")
                if "resource" in str(key).lower() or "id" in str(key).lower() or "url" in str(key).lower():
                    resource_info = value
                    logging.info(f"Potential resource info found: {key} = {value}")

        # Approach 1: Try to use resource information if available
        if resource_info:
            logging.info(f"Attempt 1: Using resource info: {resource_info}")
            try:
                three_d_result = stub.call(
                    image_to_3d_id,
                    {"input_image": str(resource_info)},
                    "super-user"
                )
                if three_d_result:
                    logging.info("Success with resource info approach!")
                else:
                    raise Exception("No response with resource info")
            except Exception as e:
                logging.warning(f"Resource info approach failed: {e}")
                three_d_result = None
        else:
            three_d_result = None

        # If resource approach didn't work, try the image data approaches
       # Después de validar y procesar la imagen:
            try:
                # Validar la imagen
                image = Image.open(io.BytesIO(image_data))
                logging.info(f"Image validation successful: {image.format}, size: {image.size}, mode: {image.mode}")
                
                # Convertir a RGB si es necesario
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
                
                # Redimensionar si es demasiado grande
                max_size = 1024
                if max(image.size) > max_size:
                    logging.info(f"Resizing image from {image.size} to fit {max_size}px")
                    image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
                
                # Guardar como PNG
                png_buffer = io.BytesIO()
                image.save(png_buffer, format='PNG')
                png_data = png_buffer.getvalue()
                logging.info(f"Processed image: PNG, {len(png_data)} bytes, size: {image.size}")

                # Convertir a base64 sin encabezado data URI
                image_base64 = base64.b64encode(png_data).decode('utf-8')

                # Enviar a la app 3D
                logging.info("Calling Image-to-3D service with PNG base64...")
                three_d_result = stub.call(
                    image_to_3d_id,
                    {"input_image": image_base64},
                    "super-user"
                )
                if not three_d_result:
                    raise Exception("3D conversion failed with PNG base64")

            except Exception as e:
                logging.error(f"Error in PNG base64 3D conversion: {e}")
                raise e

        if not three_d_result:
            raise Exception("All format attempts failed for 3D conversion service")
            
        #logging.info(f"3D service response: {three_d_result}")
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
            
            # Save the 3D model
            with open("output.glb", "wb") as f:
                f.write(model_bytes)
            logging.info(f"3D model saved as output.glb ({len(model_bytes)} bytes)")
        else:
            logging.warning("No 3D model data in response")
            
        

        # Set success response
        response: OutputClass = model.response
        response.message = f"Successfully generated image and 3D model from prompt: '{expanded_prompt}'"
        logging.info("Pipeline completed successfully!")

    except Exception as e:
        logging.error(f"Error in pipeline: {str(e)}", exc_info=True)
        response: OutputClass = model.response
        response.message = f"Pipeline failed: {str(e)}"
