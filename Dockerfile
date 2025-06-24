FROM openfabric/tee-python-cpu:dev

# Copy only necessary files for Poetry installation
COPY pyproject.toml ./

# Install dependencies using Poetry
RUN python3 -m pip install --upgrade pip && \
    python3 -m pip install --upgrade poetry && \
    python3 -m poetry add "gradio==3.50.2" && \
    python3 -m poetry install --only main && \
    rm -rf ~/.cache/pypoetry/{cache,artifacts}

# Copy the rest of the source code into the container
COPY . .
RUN chmod +x start.sh

# Expose port 8888 for OpenFabric API
EXPOSE 8888
# Expose port 7860 for Gradio UI
EXPOSE 7860

# Start the Flask app using the start.sh script
CMD ["sh","start.sh"]
