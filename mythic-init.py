#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import argparse
import os
import platform
import shutil
import subprocess
import sys

try:
    from git import Repo, GitCommandError
except ImportError:
    print("Please install GitPython: pip install gitpython")
    sys.exit(1)

RED = "\033[91m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"

MYTHIC_REPO_URL = 'https://github.com/its-a-feature/Mythic'

def print_env_table(effective_env):
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
        except FileNotFoundError:
            pass
    elif system == 'darwin':
        return 'darwin'
    return system

def ensure_mythic_cli(targetDir):
    cli_path = os.path.join(targetDir, 'mythic-cli')
    if not os.path.isfile(cli_path):
        print(f"{RED}'mythic-cli' not found in {targetDir}. Please build Mythic first (run 'make').{RESET}")
        return False
    return True

def cleanup_docker_orphans(targetDir):
    print(f"{BLUE}Removing orphaned Docker containers...{RESET}")
    compose_yml = os.path.join(targetDir, 'docker-compose.yml')
    if not os.path.exists(compose_yml):
        print(f"{YELLOW}docker-compose.yml not found in {targetDir}. Skipping orphan cleanup.{RESET}")
        return
    compose_cmd = "docker compose" if shutil.which("docker") else "docker-compose"
    os.system(f"{compose_cmd} -f {compose_yml} down --remove-orphans")

def cleanup_docker():
    print(f"{BLUE}Cleaning up Docker containers, volumes, and images...{RESET}")
    os.system("docker container prune -f")
    os.system("docker volume prune -f")
    os.system("docker system prune -af")

def get_mythic_repo_file_list():
    import tempfile
    import requests
    import zipfile
    # Download the repo as a zip and list its top-level files
    api_url = "https://github.com/its-a-feature/Mythic/archive/refs/heads/master.zip"
    with tempfile.TemporaryDirectory() as tmpdir:
        zip_path = os.path.join(tmpdir, "mythic.zip")
        with requests.get(api_url, stream=True) as r:
            with open(zip_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
        with zipfile.ZipFile(zip_path, 'r') as z:
            namelist = z.namelist()
            # Only get files at the root of the repo
            prefix = namelist[0]
            root_files = [n[len(prefix):] for n in namelist if n.startswith(prefix) and '/' not in n[len(prefix):] and n != prefix]
            return set(root_files)

def check_for_conflicts(targetLoc):
    # Returns a set of conflicting files
    mythic_files = get_mythic_repo_file_list()
    local_files = set(os.listdir(targetLoc))
    conflicts = mythic_files.intersection(local_files)
    # Don't count .git itself as a conflict (handled separately)
    conflicts.discard('.git')
    return conflicts

def force_git_reinit(targetLoc, repo_url):
    os.chdir(targetLoc)
    os.system('rm -rf .git')
    os.system('git init')
    os.system(f'git remote add origin {repo_url}')
    os.system('git fetch origin')
    os.system('git checkout -t origin/master || git checkout -b master')
    os.system('git pull origin master')

def build_mythic(targetDir):
    try:
        subprocess.run(['make'], cwd=targetDir, check=True)
        print(f"{GREEN}Mythic build completed successfully!{RESET}")
    except subprocess.CalledProcessError as e:
        print(f"{RED}Error during Mythic build: {e}{RESET}")
        sys.exit(1)

def cloneAndBuild(targetLoc):
    repo_url = MYTHIC_REPO_URL
    targetLoc = os.path.abspath(targetLoc)
    setup_successful = False

    # .git directory edge case handling
    git_dir = os.path.join(targetLoc, '.git')
    if os.path.exists(git_dir):
        print(f"{YELLOW}A .git directory already exists in {targetLoc}.{RESET}")
        print(f"{YELLOW}This may indicate you are running this script inside another git repository, which can cause conflicts with Mythic's own repository.{RESET}")
        while True:
            user_choice = input(f"{BLUE}Do you want to delete the existing .git directory and proceed with Mythic installation? (y/n): {RESET}").strip().lower()
            if user_choice == "y":
                try:
                    shutil.rmtree(git_dir)
                    print(f"{GREEN}Deleted existing .git directory. Proceeding with Mythic installation...{RESET}")
                    break
                except Exception as e:
                    print(f"{RED}Failed to delete .git directory: {e}{RESET}")
                    sys.exit(1)
            elif user_choice == "n":
                print(f"{YELLOW}Exiting without making changes.{RESET}")
                print(f"{YELLOW}Recommendation: Copy mythic-init.py to a new, empty folder and run it there if you want to keep your current repository and also be able to update mythic-init.py from its own repository.{RESET}")
                sys.exit(0)
            else:
                print(f"{YELLOW}Please type 'y' or 'n'.{RESET}")

    # Check for file conflicts
    conflicts = check_for_conflicts(targetLoc)
    if conflicts:
        print(f"{RED}The following files in {targetLoc} would be overwritten by Mythic installation:{RESET}")
        for c in conflicts:
            print(f"  {c}")
        while True:
            user_choice = input(f"{BLUE}Do you want to delete these files and proceed? (y/n): {RESET}").strip().lower()
            if user_choice == "y":
                try:
                    for c in conflicts:
                        full_path = os.path.join(targetLoc, c)
                        if os.path.isdir(full_path):
                            shutil.rmtree(full_path)
                        else:
                            os.remove(full_path)
                    print(f"{GREEN}Conflicting files deleted. Proceeding with Mythic installation...{RESET}")
                    break
                except Exception as e:
                    print(f"{RED}Failed to delete conflicting files: {e}{RESET}")
                    sys.exit(1)
            elif user_choice == "n":
                print(f"{YELLOW}Exiting without making changes.{RESET}")
                print(f"{YELLOW}Recommendation: Use a clean directory for Mythic installation to avoid file conflicts.{RESET}")
                sys.exit(0)
            else:
                print(f"{YELLOW}Please type 'y' or 'n'.{RESET}")

    try:
        repo = Repo.clone_from(repo_url, targetLoc)
        print(f"{GREEN}Cloned from {repo_url} to {targetLoc}{RESET}")
        setup_successful = True

    except GitCommandError as e:
        if "destination path" in str(e) and "already exists" in str(e):
            print(f"{YELLOW}Directory {targetLoc} already exists.{RESET}")
            if not os.path.exists(git_dir):
                print(f"{YELLOW}Directory exists but is not a git repository. Forcibly initializing...{RESET}")
                force_git_reinit(targetLoc, repo_url)
                setup_successful = True
            else:
                repo = Repo(targetLoc)
                remotes = [remote.url for remote in repo.remotes]
                if repo_url in remotes:
                    print(f"{BLUE}Repository already exists. Pulling latest changes...{RESET}")
                    repo.git.pull('origin', 'master')
                    setup_successful = True
                else:
                    print(f"{YELLOW}Updating remote to Mythic repo...{RESET}")
                    force_git_reinit(targetLoc, repo_url)
                    setup_successful = True
        else:
            print(f"{RED}Git error: {e}{RESET}")

    if setup_successful:
        build_mythic(targetLoc)
    else:
        print(f"{RED}Repository setup failed. Installation aborted.{RESET}")
        sys.exit(1)

def configureMythic(targetLoc, **env_vars):
    effective_env = {}
    for k, v in env_vars.items():
        if v is not None:
            effective_env[k.upper()] = v
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
    if ensure_mythic_cli(targetLoc):
        subprocess.run(['./mythic-cli', 'start'], cwd=targetLoc, check=True)

def configureRules(trustedIps):
    if not trustedIps:
        print(f"{YELLOW}No trusted source IP provided; skipping iptables rules injection.{RESET}")
        return
    print(f"{BLUE}Injecting iptables rules to restrict port 7443 to trusted source(s): {trustedIps}{RESET}")
    try:
        subprocess.run(['iptables', '-I', 'DOCKER-USER', '-p', 'tcp', '--dport', '7443', '-j', 'DROP'], check=True)
        subprocess.run(['iptables', '-I', 'DOCKER-USER', '-p', 'tcp', '--dport', '7443', '-s', trustedIps, '-j', 'ACCEPT'], check=True)
        print(f"{GREEN}iptables rules injected successfully.{RESET}")
    except subprocess.CalledProcessError as e:
        print(f"{RED}Error injecting iptables rules: {e}{RESET}")

def stockAgentsAndProfiles(targetDir):
    if not ensure_mythic_cli(targetDir):
        return
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
            print(f"{YELLOW}Warning: Could not install {item} (may already be installed).{RESET}")

def cleanAndDestroy(targetDir, no_docker_cleanup=False):
    print(f"{BLUE}Tearing down Mythic configuration...{RESET}")
    if not ensure_mythic_cli(targetDir):
        print(f"{YELLOW}Skipping CLI teardown; mythic-cli not found.{RESET}")
    else:
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
                print(f"{YELLOW}Warning: Could not uninstall {item} (may not be installed).{RESET}")

    home_dir = os.path.expanduser("~")
    if os.path.abspath(targetDir) == os.path.abspath(home_dir):
        print(f"{RED}Refusing to delete user's home directory: {targetDir}{RESET}")
        return

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

    cleanup_docker_orphans(targetDir)
    if not no_docker_cleanup:
        cleanup_docker()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Turn a Nix VPS into a Mythic C2 Server")
    parser.add_argument('-d', '--directory', default=os.getcwd(), help="Target installation directory (default: current directory)")
    parser.add_argument('-e', '--env', action='store_true', help="Generate a .env file with custom configuration options")
    parser.add_argument('-s', '--source-ip', default=None, help="Trusted source IP address or range for restricting port 7443 (e.g., 128.168.1.1 or 128.168.1.1/24)")
    parser.add_argument('-i', '--install', action='store_true', help="Install stock agents and profiles")
    parser.add_argument('-c', '--cleanup', action='store_true', help="Clean up Mythic configuration and optionally delete the installation directory")
    parser.add_argument('-p', '--print', action='store_true', help="Print the contents of the .env file if it exists, otherwise show a message")
    parser.add_argument('--no-docker-cleanup', action='store_true', help="Skip Docker cleanup during cleanup")
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
        if args.cleanup:
            cleanAndDestroy(targetDir, no_docker_cleanup=args.no_docker_cleanup)
            sys.exit(0)

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

        cloneAndBuild(targetDir)

        cleanup_docker_orphans(targetDir)

        if args.env:
            configureMythic(targetDir, **env_options)
        else:
            print(f"{YELLOW}Using default .env variables. The './mythic-cli start' command will use its built-in defaults.{RESET}")
            if ensure_mythic_cli(targetDir):
                subprocess.run(['./mythic-cli', 'start'], cwd=targetDir, check=True)

        configureRules(args.source_ip)

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
