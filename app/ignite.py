import subprocess
import threading
import time
import logging
import socket
from openfabric_pysdk.starter import Starter

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def find_free_port(start_port=7860, max_attempts=100):
    """Find a free port starting from start_port"""
    for port in range(start_port, start_port + max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('', port))
                logging.info(f"Found free port for Gradio: {port}")
                return port
        except OSError:
            continue
    raise RuntimeError(f"Could not find free port in range {start_port}-{start_port + max_attempts}")

def start_gradio_ui():
    """Start Gradio UI in a separate thread"""
    try:
        free_port = find_free_port(7860)
        logging.info(f"🚀 Starting Gradio UI on port {free_port}...")
        subprocess.run([
            "python", "gradio_ui.py"
        ])
    except Exception as e:
        logging.error(f"Failed to start Gradio UI: {e}")

if __name__ == '__main__':
    PORT = 8888
    
    # Start Gradio UI in background thread
    ui_thread = threading.Thread(target=start_gradio_ui, daemon=True)
    ui_thread.start()
    
    # Small delay to let Gradio start
    time.sleep(2)
    
    # Start main OpenFabric server
    logging.info(f"Starting OpenFabric server on port {PORT}...")
    Starter.ignite(debug="False", host="0.0.0.0", port=PORT)
