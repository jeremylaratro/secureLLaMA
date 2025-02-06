# Airgapped AI for Enhanced Data Security
This project has been created as a part of my masters degree in cybersecurity. The project aims to create a simple, effective solution for countering the massive data privacy issues associated with the AIaaS model. It does this by simplifying the process for locally managed, private AI using a streamlined DevOps pipeline focused on deployment scripting and automation. The core component of the project is a custom-made LLAMA interface script which executes Meta's Llama model directly using Torchrun. Gradio is used for a locally hosted web server, with SSL implementation for secure web traffic.

Web UI using Gradio

![Interface](https://github.com/jeremylaratro/secure_intelligence_masters/blob/main/diagrams/Screenshot_21-Dec_16-00-49_18923.png?raw=true)

Risk reduction workflow

![RiskReduction](https://github.com/jeremylaratro/secure_intelligence_masters/blob/master/diagrams/Screenshot_20-Dec_15-36-41_30408.png)


## Components
### System
The project consists of three major components:
1. A central host server, using Fedora SilverBlue or SecureBlue
2. A Docker container (Ubuntu/CUDA base) running the LLM via Torchrun, with gradio to serve the app through a web UI locally
3. (Optional) A qemu/virt-manager VM to serve as a web proxy

![System Architecture](https://github.com/jeremylaratro/secure_intelligence_masters/blob/master/diagrams/Screenshot_19-Dec_18-29-19_7194.png)
### Software
This repository contains the following:
- LLM Python script to interface with the LLAMA model
- Dockerfile to deploy the application
- Deployment scripts used to:
  - Add logging and monitoring
  - Harden the server and container

The project is intended to serve as a replacement for AIaaS products in corporate settings, with strict ACL integration for extensive network segmentation between the AI server and other vLANS.

![vlAN/ACLs](https://github.com/jeremylaratro/secure_intelligence_masters/blob/master/diagrams/Screenshot_20-Dec_10-25-12_8371.png?raw=true)

## Usage
This repo consists of everything needed to run the Llama3-2.1B-Instruct model, minus the consolidated.00.pth file due to size constraints of github. Download the model via Huggingface or directly from Meta. The script should be compatible with all models, but all of the files in model minus the python script must be changed out if switching models (i.e., params.json, tokenizer, etc.)

First, clone the directory.
```bash
git clone https://github.com/jeremylaratro/secure_intelligence_masters.git
```
Execute the Dockerfile
```bash
sudo docker -t ai_container_v3_0_x build . 
```
Run the container
```bash
sudo docker run --privileged --runtime=nvidia --gpus all -it solution_container_v1_6 bash
```
Within the container, verify GPU passthrough with nvidia-smi command.
If successful, execute the model:
```bash
torchrun --nproc_per_node=1 ai_solution_v3_0_x.py --ckpt_dir ./ --tokenizer_path ./tokenizer.model --max_seq_len 8192 --max_batch_size 8
```
Note: The following switch is dependent upon the number of GPUs you have/want to use. 
--nproc_per_node={integer}
  - If you have one GPU, keep at 1. If two GPUs, set the number to 2, etc.

----

## Hardening

For hardening measures, the included scripts install and set up snort, auditd, ufw, collectd, and clamav.

- Script for hardening vanilla Fedora install. Adopted from https://github.com/RoyalOughtness/fedora-hardened/blob/main/harden.sh
```bash
./hardening.sh
```
- Script for installing core requirements for VM and containers on host.
```bash
./host.sh
```

- Script for installing snort.
Run on host:
```bash
./snort.sh
```
Run in container:
```
./snort_container.sh
```

- Script for running Snort3 in daemon mode, establishing ClamAV and Freshclam cronjobs, and enabling extended logging capabilities.
- Run on host and inside container.
```bash
./monitor_all.sh
```




