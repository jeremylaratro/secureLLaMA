# Airgapped AI for Enhanced Data Security
This project has been created as a part of my masters degree in cybersecurity. The project aims to create a simple, effective solution for countering the massive data privacy issues associated with the AIaaS model. It does this by simplifying the process for locally managed, private AI - executing Meta's Llama model directly with Torchrun, using Gradio for a locally hosted web server, and includes several host and container-hardening scripts to streamline deployment.

![RiskReduction](https://github.com/jeremylaratro/secure_intelligence_masters/blob/master/diagrams/Screenshot_20-Dec_15-36-41_30408.png)


### Overview
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
