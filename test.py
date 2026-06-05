import urllib.request
import subprocess
import tempfile
import os
import time
import sys

def run_script_in_cmd(url, tool_name):
    print(f"[*] Downloading {tool_name} from {url} ...")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            code = resp.read().decode('utf-8')
        if not code.strip():
            print(f"[-] {tool_name} is empty.")
            return

        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            f.write(code)
            tmp_path = f.name

        print(f"[+] Launching {tool_name} in a new CMD window...")
        subprocess.Popen(f'cmd.exe /c python "{tmp_path}"', creationflags=subprocess.CREATE_NEW_CONSOLE)

        time.sleep(5)
        try:
            os.remove(tmp_path)
        except:
            pass

    except Exception as e:
        print(f"[-] Failed: {e}")

def main():
    print("=" * 40)
    print("         TOOL SELECTOR")
    print("=" * 40)
    print("[1] Launch Tool 1")
    print("[2] Launch Tool 2")
    print("[0] Exit")
    choice = input("\nEnter your choice (1/2/0): ").strip()

    if choice == "1":
        run_script_in_cmd(
            "https://raw.githubusercontent.com/IsalmND/test/refs/heads/main/test.py",
            "Tool 1"
        )
    elif choice == "2":
        run_script_in_cmd(
            "https://raw.githubusercontent.com/IsalmND/test2/refs/heads/main/test2.py",
            "Tool 2"
        )
    elif choice == "0":
        print("Exiting.")
        sys.exit(0)
    else:
        print("[-] Invalid choice. Please enter 1, 2 or 0.")

if __name__ == "__main__":
    main()
