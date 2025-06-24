
FROM openfabric/tee-python-cpu:dev


WORKDIR /app


COPY pyproject.toml poetry.lock* ./

RUN python3 -m pip install --upgrade pip && \
    python3 -m pip install poetry && \
    poetry config virtualenvs.create false && \
    poetry install --only main --no-root && \
    rm -rf ~/.cache/pypoetry/{cache,artifacts}


COPY . .


RUN chmod +x start.sh


EXPOSE 8888  
EXPOSE 7860  

CMD ["bash", "start.sh"]
