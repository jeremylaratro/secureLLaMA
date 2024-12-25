# Airgapped AI for Enhanced Data Security
This project has been created as a part of my masters degree in cybersecurity. The project aims to create a simple, effective solution for countering the massive data privacy issues associated with the AIaaS model. It does this by simplifying the process for locally managed, private AI using a streamlined DevOps pipeline focused on deployment scripting and automation. The core component of the project is a custom-made LLAMA interface script which executes Meta's Llama model directly using Torchrun. Gradio is used for a locally hosted web server, with SSL implementation for secure web traffic.

![RiskReduction](https://github.com/jeremylaratro/secure_intelligence_masters/blob/master/diagrams/Screenshot_20-Dec_15-36-41_30408.png)


### Components
The project consists of three major components:
1. A central host server, using Fedora SilverBlue or SecureBlue
2. A Docker container running the LLM via Torchrun, with gradio to serve the app through a web UI locally
3. (Optional) A qemu/virt-manager VM to serve as a web proxy

![System Architecture](https://github.com/jeremylaratro/secure_intelligence_masters/blob/master/diagrams/Screenshot_19-Dec_18-29-19_7194.png)

This repository contains the following:
- LLM Python script to interface with the LLAMA model
- Dockerfile to deploy the application
- Deployment scripts used to:
  - Add logging and monitoring
  - Harden the server and container

The project is intended to serve as a replacement for AIaaS products in corporate settings, with strict ACL integration for extensive network segmentation between the AI server and other vLANS.

![vlAN/ACLs](https://github.com/jeremylaratro/secure_intelligence_masters/blob/master/diagrams/Screenshot_20-Dec_10-25-12_8371.png?raw=true)
