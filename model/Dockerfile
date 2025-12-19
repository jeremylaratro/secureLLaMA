# Use NVIDIA's base image with CUDA 11.8 (matches PyTorch wheel)
FROM nvidia/cuda:11.8.0-runtime-ubuntu22.04

# Set environment variables
ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV LOG_LEVEL=INFO

# Install system dependencies (consolidated)
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    wget \
    git \
    curl \
    nano \
    auditd \
    clamav \
    ufw \
    ngrep \
    collectd \
    tcpdump \
    && rm -rf /var/lib/apt/lists/*

# Install NVIDIA container toolkit
RUN curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg \
    && curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
       sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
       tee /etc/apt/sources.list.d/nvidia-container-toolkit.list \
    && apt-get update \
    && apt-get install -y --no-install-recommends nvidia-container-toolkit \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip install --no-cache-dir \
    torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118 \
    && pip install --no-cache-dir transformers fire gradio

# Create non-root user for security
RUN useradd -m -s /bin/bash -u 1000 llama \
    && mkdir -p /app/checkpoints \
    && chown -R llama:llama /app

# Set the working directory
WORKDIR /app/checkpoints

# Copy model files and scripts (as root for permissions, then chown)
COPY --chown=llama:llama ./checklist.chk /app/checkpoints/checklist.chk
COPY --chown=llama:llama ./consolidated.00.pth /app/checkpoints/consolidated.00.pth
COPY --chown=llama:llama ./config.json /app/checkpoints/config.json
COPY --chown=llama:llama ./params.json /app/checkpoints/params.json
COPY --chown=llama:llama ./tokenizer.model /app/checkpoints/tokenizer.model
COPY --chown=llama:llama ./ai_solution_v3_0_6_prod.py /app/checkpoints/ai_solution_v3_0_6_prod.py
COPY --chown=llama:llama ./llama3 /app/checkpoints/llama3/

# Install local llama3 library
RUN cd /app/checkpoints/llama3 && python3 setup.py install

# Switch to non-root user
USER llama

# Expose Gradio port
EXPOSE 7860

# Health check for container orchestration
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD curl -f http://localhost:7860/ || exit 1

# Default command
ENTRYPOINT ["torchrun", "--nproc_per_node=1", "ai_solution_v3_0_6_prod.py"]
CMD ["--ckpt_dir", "./", "--tokenizer_path", "./tokenizer.model", "--max_seq_len", "8192", "--max_batch_size", "8"]
