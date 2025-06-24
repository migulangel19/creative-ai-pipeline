#!/bin/sh
ollama serve &
sleep 3
ollama run llama3
tail -f /dev/null
