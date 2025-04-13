#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from git import Repo, GitCommandError
import argparse
import platform
import os
import subprocess
import shutil
import sys

RED    = "\033[91m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
BLUE   = "\033[94m"
RESET  = "\033[0m"

def print_env_table(effective_env):

    # Print the key-value pairs from effective_env in a nicely formatted table.
    rows = sorted(effective_env.items())
    key_width = max(len("Variable"), *(len(k) for k, _ in rows)) if rows else len("Variable")
    val_width = max(len("Value"), *(len(str(v)) for _, v in rows)) if rows else len("Value")
    horizontal_line = f"+{'-'*(key_width+2)}+{'-'*(val_width+2)}+"
    header = f"| {'Variable'.ljust(key_width)} | {'Value'.ljust(val_width)} |"
    print(horizontal_line)
    print(header)
    print(horizontal_line)
    for k, v in rows:
        print(f"| {k.ljust(key_width)} | {str(v).ljust(val_width)} |")
    print(horizontal_line)

def detect_os():
    system = platform.system().lower()
    if system == 'linux':
        try:
            with open('/etc/os-release', 'r') as f:
                os_info = {}
                for line in f:
                    if '=' in line:
                        key, value = line.strip().split('=', 1)
                        os_info[key] = value.strip('"\'')

            dist_id = os_info.get('ID', '').lower()
            if 'debian' in dist_id:
                return 'debian'
            elif 'ubuntu' in dist_id:
                return 'ubuntu'
            elif 'kali' in dist_id:
                return 'kali'
            else:
                try:
                    result = subprocess.run(['lsb_release', '-i'],
                                            capture_output=True,
                                            text=True,
                                            check=True)
                    output = result.stdout.lower()
                    if 'debian' in output:
                        return 'debian'
                    elif 'ubuntu' in output:
                        return 'ubuntu'
                    elif 'kali' in output:
                        return 'kali'
                except (subprocess.SubprocessError, FileNotFoundError):
                    pass
        except FileNotFoundError:
            pass
    elif system == 'darwin':
        return 'darwin'
    return system

def cloneAndBuild(targetLoc):
    repo_url = 'https://github.com/its-a-feature/Mythic'
    targetLoc = os.path.abspath(targetLoc)
    setup_successful = False

    try:
        repo = Repo.clone_from(repo_url, targetLoc)
        print(f"{GREEN}Cloned from {repo_url} to {targetLoc}{RESET}")
        setup_successful = True
    except GitCommandError as e:
        if "destination path" in str(e) and "already exists" in str(e):
            print(f"{YELLOW}Directory {targetLoc} already exists.{RESET}")
            if os.path.exists(os.path.join(targetLoc, '.git')):
                try:
                    repo = Repo(targetLoc)
                    remotes = [remote.url for remote in repo.remotes]
                    if repo_url in remotes:
                        print(f"{BLUE}Repository already exists. Pulling latest changes...{RESET}")
                        repo.git.pull('origin', 'master')
                        setup_successful = True
                    else:
                        print(f"{RED}Directory is a git repository but not for {repo_url}.{RESET}")
                        choice = input("Would you like to update the remote and continue? (y/n): ")
                        if choice.lower() == 'y':
                            if 'origin' in [remote.name for remote in repo.remotes]:
                                repo.delete_remote('origin')
                            origin = repo.create_remote('origin', repo_url)
                            origin.fetch()
                            repo.git.pull('origin', 'master')
                            setup_successful = True
                except Exception as repo_error:
                    print(f"{RED}Error examining existing repository: {repo_error}{RESET}")
            else:
                print(f"{YELLOW}Directory exists but is not a git repository.{RESET}")
                choice = input("Would you like to initialize it as a git repository for Mythic? (y/n): ")
                if choice.lower() == 'y':
                    try:
                        repo = Repo.init(targetLoc)
                        origin = repo.create_remote('origin', repo_url)
                        origin.fetch()
                        repo.create_head('master', origin.refs.master)
                        repo.heads.master.set_tracking_branch(origin.refs.master)
                        repo.heads.master.checkout()
                        repo.git.pull('origin', 'master')
                        setup_successful = True
                    except Exception as init_error:
                        print(f"{RED}Error initializing repository: {init_error}{RESET}")
        else:
            print(f"{RED}Git error: {e}{RESET}")

    if setup_successful:
        os_type = detect_os()
        print(f"{BLUE}Detected OS: {os_type}{RESET}")
        script_name = None

        if os_type == 'debian':
            script_name = 'install_docker_debian.sh'
        elif os_type == 'ubuntu':
            script_name = 'install_docker_ubuntu.sh'
        elif os_type == 'kali':
            script_name = 'install_docker_kali.sh'
        elif os_type == 'darwin':
            print(f"{YELLOW}Please install 'orbstack' instead of docker and consult the product documentation at: https://docs.mythic-c2.net/installation{RESET}")
            return
        else:
            print(f"{RED}Unsupported platform: {os_type}{RESET}")
            print(f"{RED}Please install Docker manually and run 'make' in the repository directory.{RESET}")
            return

        script_path = os.path.join(targetLoc, script_name)
        if os.path.exists(script_path):
            print(f"{BLUE}Running installation script: {script_name}{RESET}")
            try:
                os.chmod(script_path, 0o755)
                subprocess.run([script_path], cwd=targetLoc, check=True)
                print(f"{GREEN}Docker installed successfully!{RESET}")
                subprocess.run(['make'], cwd=targetLoc, check=True)
                print(f"{GREEN}Mythic build completed successfully!{RESET}")
            except subprocess.CalledProcessError as e:
                print(f"{RED}Error during installation: {e}{RESET}")
        else:
            print(f"{RED}Installation script not found: {script_path}{RESET}")
    else:
        print(f"{RED}Repository setup failed. Installation aborted.{RESET}")

def configureMythic(targetLoc, **env_vars):
    # Merge built-in values (generated by Mythic CLI) with any custom command-line overrides.
    effective_env = {}
    for k, v in env_vars.items():
        if v is not None:
            effective_env[k.upper()] = v
    # If any custom overrides were provided, generate a .env file with those values.
    if effective_env:
        conf_lines = [f'{key}="{value}"' for key, value in effective_env.items()]
        conf = "\n".join(conf_lines)
        env_file_path = os.path.join(targetLoc, ".env")
        with open(env_file_path, "w") as f:
            f.write(conf)
        print(f"{GREEN}Created custom .env file with the following content:{RESET}")
        print(conf)
    else:
        print(f"{YELLOW}No custom env variables provided; Mythic CLI will use its default .env settings.{RESET}")
    # Start Mythic CLI; any unset values will be provided internally.
    subprocess.run(['./mythic-cli', 'start'], cwd=targetLoc, check=True)

def configureRules(trustedIps):
    if not trustedIps:
        print(f"{YELLOW}No trusted source IP provided; skipping iptables rules injection.{RESET}")
        return

    print(f"{BLUE}Injecting iptables rules to restrict port 7443 to trusted source(s): {trustedIps}{RESET}")
    try:
        # Drop all TCP traffic on port 7443 (mythic admin portal) at the container level. This helps to ensure the admin portal is not exposed by mistake.
        subprocess.run(['iptables', '-I', 'DOCKER-USER', '-p', 'tcp', '--dport', '7443', '-j', 'DROP'], check=True)
        # Accept traffic from the specified trusted IP address or range on port 7443.
        subprocess.run(['iptables', '-I', 'DOCKER-USER', '-p', 'tcp', '--dport', '7443', '-s', trustedIps, '-j', 'ACCEPT'], check=True)
        print(f"{GREEN}iptables rules injected successfully.{RESET}")
    except subprocess.CalledProcessError as e:
        print(f"{RED}Error injecting iptables rules: {e}{RESET}")

def stockAgentsAndProfiles(targetDir):
    print(f"{BLUE}Installing stock agents and profiles...{RESET}")
    items = [
        "github https://github.com/MythicAgents/apfell",
        "github https://github.com/MythicAgents/Hannibal",
        "github https://github.com/MythicAgents/Athena",
        "github https://github.com/MythicC2Profiles/http",
        "github https://github.com/MythicC2Profiles/httpx",
        "github https://github.com/MythicC2Profiles/dns",
        "github https://github.com/MythicC2Profiles/websocket",
    ]
    for item in items:
        try:
            cmd = ['./mythic-cli', 'install'] + item.split()
            subprocess.run(cmd, cwd=targetDir, check=True)
            print(f"{GREEN}Installed {item}{RESET}")
        except subprocess.CalledProcessError as e:
            print(f"{RED}Error installing {item}: {e}{RESET}")

def cleanAndDestroy(targetDir):
    print(f"{BLUE}Tearing down Mythic configuration...{RESET}")
    try:
        subprocess.run(['./mythic-cli', 'stop'], cwd=targetDir, check=True)
    except subprocess.CalledProcessError as e:
        print(f"{RED}Error stopping Mythic CLI: {e}{RESET}")

    print(f"{BLUE}Uninstalling stock agents and profiles...{RESET}")
    items = [
        "github https://github.com/MythicAgents/apfell",
        "github https://github.com/MythicAgents/Hannibal",
        "github https://github.com/MythicAgents/Athena",
        "github https://github.com/MythicC2Profiles/http",
        "github https://github.com/MythicC2Profiles/httpx",
        "github https://github.com/MythicC2Profiles/dns",
        "github https://github.com/MythicC2Profiles/websocket",
    ]
    for item in items:
        try:
            cmd = ['./mythic-cli', 'uninstall'] + item.split()
            subprocess.run(cmd, cwd=targetDir, check=True)
            print(f"{GREEN}Uninstalled {item}{RESET}")
        except subprocess.CalledProcessError as e:
            if "Failed to find any service folder" in str(e):
                print(f"{YELLOW}Service not installed: {item}{RESET}")
            else:
                print(f"{RED}Error uninstalling {item}: {e}{RESET}")

    choice = input(f"{BLUE}Would you like to delete the entire Mythic installation directory? (y/n): {RESET}")
    if choice.lower() == 'y':
        try:
            running_script = os.path.basename(os.path.abspath(__file__))
            for entry in os.listdir(targetDir):
                if entry == running_script:
                    continue
                full_path = os.path.join(targetDir, entry)
                try:
                    if os.path.isdir(full_path):
                        shutil.rmtree(full_path)
                    else:
                        os.remove(full_path)
                except Exception as inner_e:
                    print(f"{RED}Error deleting {full_path}: {inner_e}{RESET}")
            print(f"{GREEN}Deleted contents of {targetDir}.{RESET}")
        except Exception as e:
            print(f"{RED}Error during directory cleanup: {e}{RESET}")
    else:
        print(f"{YELLOW}Mythic installation directory retained.{RESET}")

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Turn a Nix VPS into a Mythic C2 Server")
    parser.add_argument('-d', '--directory', default=os.getcwd(), help="Target installation directory (default: current directory)")
    parser.add_argument('-e', '--env', action='store_true', help="Generate a .env file with custom configuration options")
    parser.add_argument('-s', '--source-ip', default=None, help="Trusted source IP address or range for restricting port 7443 (e.g., 128.168.1.1 or 128.168.1.1/24)")
    parser.add_argument('-i', '--install', action='store_true', help="Install stock agents and profiles")
    parser.add_argument('-c', '--cleanup', action='store_true', help="Clean up Mythic configuration and optionally delete the installation directory")
    parser.add_argument('-p', '--print', action='store_true', help="Print the contents of the .env file if it exists, otherwise show a message")

    env_group = parser.add_argument_group("Environment configuration options (omit to use CLI defaults)")
    env_group.add_argument("--allowed-ip-blocks", default=None, help="Allowed IP blocks")
    env_group.add_argument("--compose-project-name", default=None, help="Compose project name")
    env_group.add_argument("--debug-level", default=None, help="Debug level")
    env_group.add_argument("--default-operation-name", default=None, help="Default operation name")
    env_group.add_argument("--default-operation-webhook-channel", default=None, help="Default operation webhook channel")
    env_group.add_argument("--default-operation-webhook-url", default=None, help="Default operation webhook URL")
    env_group.add_argument("--documentation-bind-localhost-only", default=None, help="Documentation bind localhost only")
    env_group.add_argument("--documentation-host", default=None, help="Documentation host")
    env_group.add_argument("--documentation-port", default=None, help="Documentation port")
    env_group.add_argument("--documentation-use-build-context", default=None, help="Documentation use build context")
    env_group.add_argument("--documentation-use-volume", default=None, help="Documentation use volume")
    env_group.add_argument("--global-docker-latest", default=None, help="Global docker latest version")
    env_group.add_argument("--global-manager", default=None, help="Global manager")
    env_group.add_argument("--global-server-name", default=None, help="Global server name")
    env_group.add_argument("--hasura-bind-localhost-only", default=None, help="Hasura bind localhost only")
    env_group.add_argument("--hasura-cpus", default=None, help="Hasura CPUs")
    env_group.add_argument("--hasura-experimental-features", default=None, help="Hasura experimental features")
    env_group.add_argument("--hasura-host", default=None, help="Hasura host")
    env_group.add_argument("--hasura-mem-limit", default=None, help="Hasura memory limit")
    env_group.add_argument("--hasura-port", default=None, help="Hasura port")
    env_group.add_argument("--hasura-secret", default=None, help="Hasura secret")
    env_group.add_argument("--hasura-use-build-context", default=None, help="Hasura use build context")
    env_group.add_argument("--hasura-use-volume", default=None, help="Hasura use volume")

    args = parser.parse_args()
    targetDir = os.path.abspath(args.directory)

    # Prepare a dictionary of environment overrides from command-line options.
    env_options = {
        "allowed_ip_blocks": args.allowed_ip_blocks,
        "compose_project_name": args.compose_project_name,
        "debug_level": args.debug_level,
        "default_operation_name": args.default_operation_name,
        "default_operation_webhook_channel": args.default_operation_webhook_channel,
        "default_operation_webhook_url": args.default_operation_webhook_url,
        "documentation_bind_localhost_only": args.documentation_bind_localhost_only,
        "documentation_host": args.documentation_host,
        "documentation_port": args.documentation_port,
        "documentation_use_build_context": args.documentation_use_build_context,
        "documentation_use_volume": args.documentation_use_volume,
        "global_docker_latest": args.global_docker_latest,
        "global_manager": args.global_manager,
        "global_server_name": args.global_server_name,
        "hasura_bind_localhost_only": args.hasura_bind_localhost_only,
        "hasura_cpus": args.hasura_cpus,
        "hasura_experimental_features": args.hasura_experimental_features,
        "hasura_host": args.hasura_host,
        "hasura_mem_limit": args.hasura_mem_limit,
        "hasura_port": args.hasura_port,
        "hasura_secret": args.hasura_secret,
        "hasura_use_build_context": args.hasura_use_build_context,
        "hasura_use_volume": args.hasura_use_volume
    }

    try:
        # If cleanup flag is specified, only run cleanup logic and exit.
        if args.cleanup:
            cleanAndDestroy(targetDir)
            sys.exit(0)

        # If print flag is specified, attempt to read and display the .env file
        if args.print:
            env_file = os.path.join(targetDir, ".env")
            if os.path.exists(env_file):
                with open(env_file, "r") as f:
                    lines = f.read().splitlines()
                effective_env = {}
                for line in lines:
                    line = line.strip()
                    if line and "=" in line:
                        key, val = line.split("=", 1)
                        effective_env[key.strip()] = val.strip().strip('"')
                print(f"{GREEN}Contents of .env file in {targetDir}:{RESET}")
                print_env_table(effective_env)
            else:
                print(f"{YELLOW}No .env file found in {targetDir}.{RESET}")

        # Stage 1: Clone and build the Mythic repository
        cloneAndBuild(targetDir)

        # Stage 2: Configure Mythic
        if args.env:
            configureMythic(targetDir, **env_options)
        else:
            print(f"{YELLOW}Using default .env variables. The './mythic-cli start' command will use its built-in defaults.{RESET}")
            subprocess.run(['./mythic-cli', 'start'], cwd=targetDir, check=True)

        # Stage 3: Configure Docker rules for port 7443, if a trusted source IP was provided.
        configureRules(args.source_ip)

        # Stage 4: Install stock agents and profiles if requested.
        if args.install:
            stockAgentsAndProfiles(targetDir)
        else:
            print(f"{YELLOW}Skipping stock agent and profile installation...{RESET}")

    except KeyboardInterrupt:
        print(f"\n{RED}Keyboard interrupt detected. Exiting gracefully.{RESET}")
        sys.exit(1)
    except Exception as ex:
        print(f"{RED}An unexpected error occurred: {ex}{RESET}")
        sys.exit(1)

    print(f"{GREEN}Mythic installation complete!{RESET}")
    sys.exit(0)