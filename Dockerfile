# Use NVIDIA's base image with CUDA
FROM nvidia/cuda:12.2.0-runtime-ubuntu22.04

# Set environment variables for Python
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    python3 python3-pip wget git curl nano && \
    rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Create required directories
RUN mkdir -p /app/checkpoints

# Copy the model and script into the container
COPY ./checklist.chk /app/checkpoints/checklist.chk
COPY ./consolidated.00.pth /app/checkpoints/consolidated.00.pth
COPY ./config.json /app/checkpoints/config.json
COPY ./params.json /app/checkpoints/params.json
COPY ./tokenizer.model /app/checkpoints/tokenizer.model
COPY ./ai_solution_v3_0_1.py /app/checkpoints/ai_solution_v3_0_1.py
COPY ./llama3 /app/checkpoints/llama3/

# install basic tools
RUN apt update -y
#RUN apt install curl nano 

# install nvidia container toolkit
RUN curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
RUN curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
RUN apt update -y
RUN apt install -y nvidia-container-toolkit
#RUN nvidia-ctk

# Install Python dependencies
RUN pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118 && pip install transformers fire gradio

#install llama3
#RUN cd /app/checkpoints && git clone https://github.com/meta-llama/llama3.git
#RUN cd /app/checkpoints/llama3 && python3 setup.py install
# change to locally managed distro, due to edits required
RUN cd /app/checkpoints/llama3 && python3 setup.py install

# Set the default command to run the chatbot script
#CMD ["python3", "/app/checkpoints/gpt4.py", "--ckpt_dir", "/app/checkpoints/", "--tokenizer_path", "/app/checkpoints/tokenizer.model", "--max_seq_len", "512", "--temperature", "0.7", "--top_k", "50"]
#CMD ["torchrun", "--nproc_per_node", "1", "/app/checkpoints/ai_solution_v3_0_1.py", "--ckpt_dir", "/app/checkpoints/", "--tokenizer_path", "/app/checkpoints/tokenizer.model", "--max_seq_len", "8192", "--max_batch_size", "6"
