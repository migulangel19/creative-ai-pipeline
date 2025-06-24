# 🧠 Creative AI Pipeline

This project is a local AI-powered creative pipeline that transforms simple text prompts into images and interactive 3D models using Openfabric and Ollama (LLaMA 3). It includes persistent memory and a visual interface built with Gradio.

## Project Documentation
The full technical report and memory of the project is available in the PDF document:
"Proyect memory.pdf"

---

## 🚀 How to Run This Project

### 1. Clone the repository

```bash
git clone https://github.com/migulangel19/creative-ai-pipeline.git
cd creative-ai-pipeline
```

### 2. Launch with Docker
Make sure you have Docker and Docker Compose installed.

```bash
docker pull ollama/ollama
docker compose up --build
```
Build the app container

Download and run the LLaMA 3 model using Ollama

Launch the Gradio interface and the Openfabric backend

📦 The first time you run it, it may take a few minutes to download the model (~4.7 GB).

### 3. Open the interface
Once everything is running, go to:

http://localhost:7860

You can enter a text prompt like:

"A glowing dragon on top of a cliff at sunset"

And it will generate both an image and a 3D model.



## 🛠 Stack
🐳 Docker & Docker Compose

🧠 LLaMA 3 via Ollama

🎨 Gradio

🔁 Openfabric SDK

💾 SQLite-based memory system
