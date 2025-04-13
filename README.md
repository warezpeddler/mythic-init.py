# Mythic Installer

- This script automates the installation and setup of a Mythic C2 server on a Nix VPS. 
- It clones the Mythic repository, builds the project, allows for configuration of environment variables, optionally installs stock agents/profiles, and provides a cleanup option. 
- It also provides an option to inject iptables rules to restrict access to the admin panel in an source IP allow listing approach.

## Prerequisites
- A Debian or Ubuntu server/VPS
-Python interpreter (> =3.6) installed.

## Getting Started

### 1. Set Up Your Environment

#### Create a Working Directory (Optional)
```sh
mkdir mythic-installer
cd mythic-installer
```
#### Create a Python Virtual Environment
```sh
python3 -m venv venv
```
#### Activate the Virtual Environment
```sh
source venv/bin/activate
```
#### Install Required Dependencies
```sh
pip install --upgrade pip
pip install GitPython
```
### 2. Clone the repository

#### Clone the project
```sh
git clone https://github.com/warezpeddler/mythic-init.py.git
```
#### Make the script executeable
```sh
chmod +x mythic-init.py
```
### 3. Running the script
#### Options:
- -d/–directory 
Specifies the target installation directory (default is the current working directory).
- -e/–env
Generates a custom .env file with the specified .env configuration options.
- -s/–source-ip
Provides a trusted source IP address or CIDR (e.g., -s 128.168.1.1/24) to inject iptables rules that restrict access to port 7443 (Mythic admin portal).
- -i/–install
Installs some of the stock agents and profiles after the Mythic installation.
- -c/–cleanup
Runs cleanup logic only (stops Mythic, uninstalls any agents/profiles, and then produces a prompt allowing the user to decide whether to delete the installation directory).
- -p/–print
Reads and prints the contents of the .env file from the target directory in a tabular format. If no .env file is present, the script will notify the user.
#### Examples:
-  Basic Installation in the Current Directory
``` python
sudo ./mythic-init.py
```
- Installation with a Custom Directory and Environment Overrides
``` python
sudo ./mythic-init.py -d /opt/mythic -e --debug-level verbose --compose-project-name "mythic_custom"
```
-  Restrict Access to Port 7443 by Trusted IP Range
``` python
sudo ./mythic-init.py -s 128.168.1.1/24
```
- Print the Contents of the .env File
``` python
sudo ./mythic-init.py -p
```
- Install Stock Agents and Profiles
``` python
sudo ./mythic-init.py -i
```
- Cleanup Only
``` python
sudo ./mythic-init.py -c
```

### Next steps
- Configure a domain for your VPS
- Configure TLS certs for domain and containers
- Configure redirectors for C2 domain and any additional Opsec considerations
- Strip IoC's from Mythic source code and rebuild

### Stock Agents and Profiles list and credits
#### C2:
- Mythic: https://github.com/its-a-feature/Mythic

#### Agents:
- Apfell: https://github.com/MythicAgents/apfell
- Athena: https://github.com/MythicAgents/Athena
- Hannibal: https://github.com/MythicAgents/Hannibal

#### Profiles:
- http: https://github.com/MythicC2Profiles/http
- dns: https://github.com/MythicC2Profiles/dns
- httpx: https://github.com/MythicC2Profiles/httpx
- websocket: https://github.com/MythicC2Profiles/websocket
