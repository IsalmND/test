import urllib.request
import sys
import traceback

def run_code_in_current_window(url, tool_name):
    print(f"[*] Downloading {tool_name} from {url} ...")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            code = resp.read().decode('utf-8')
        if not code.strip():
            print(f"[-] {tool_name} is empty.")
            input("\nPress Enter to return to menu...")
            return
        print(f"[+] Executing {tool_name} in current window...\n")
        try:
            exec(code)
        except Exception as exec_err:
            print(f"\n[!] Error while executing {tool_name}:\n{exec_err}")
            traceback.print_exc()
        finally:
            print(f"\n[+] Finished executing {tool_name}.")
            input("\nPress Enter to return to menu...")
    except Exception as e:
        print(f"[-] Failed to load {tool_name}: {e}")
        input("\nPress Enter to return to menu...")

def main():
    while True:
        print("\n" + "=" * 40)
        print("         TOOL SELECTOR")
        print("=" * 40)
        print("[1] Launch Tool 1")
        print("[2] Launch Tool 2")
        print("[0] Exit")
        choice = input("\nEnter your choice (1/2/0): ").strip()

        if choice == "1":
            run_code_in_current_window(
                "https://raw.githubusercontent.com/IsalmND/test/refs/heads/main/user.py",
                "Tool 1"
            )
        elif choice == "2":
            run_code_in_current_window(
                "https://raw.githubusercontent.com/IsalmND/test2/refs/heads/main/clone.py",
                "Tool 2"
            )
        elif choice == "0":
            print("Exiting.")
            sys.exit(0)
        else:
            print("[-] Invalid choice. Please enter 1, 2 or 0.")
            input("\nPress Enter to continue...")

if __name__ == "__main__":
    main()
