import urllib.request
import sys

def download_and_execute(url, tool_name):
    print(f"[*] Downloading {tool_name} from {url} ...")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            code = resp.read().decode('utf-8')
        if not code.strip():
            print(f"[-] {tool_name} is empty.")
            return
        print(f"[+] Running {tool_name} ...\n")
        exec(code)
    except Exception as e:
        print(f"[-] Failed to load or execute {tool_name}: {e}")

def main():
    print("=" * 40)
    print("         TOOL SELECTOR")
    print("=" * 40)
    print("[1] Launch Tool 1")
    print("[2] Launch Tool 2")
    print("[0] Exit")
    choice = input("\nEnter your choice (1/2/0): ").strip()

    if choice == "1":
        download_and_execute(
            "https://raw.githubusercontent.com/IsalmND/test/refs/heads/main/test.py",
            "Tool 1"
        )
    elif choice == "2":
        download_and_execute(
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
