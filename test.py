import sys
import traceback
import os

def run_local_script(file_path, tool_name):
    if not os.path.exists(file_path):
        print(f"[-] File not found: {file_path}")
        input("\nPress Enter to return to menu...")
        return
    print(f"[+] Executing {tool_name} from {file_path} ...\n")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            code = f.read()
        # تنفيذ الكود في نفس النطاق العام لضمان رؤية الدوال
        exec(code, globals())
    except Exception as e:
        print(f"\n[!] Error while executing {tool_name}:\n{e}")
        traceback.print_exc()
    finally:
        print(f"\n[+] Finished executing {tool_name}.")
        input("\nPress Enter to return to menu...")

def main():
    while True:
        print("\n" + "=" * 40)
        print("         TOOL SELECTOR")
        print("=" * 40)
        print("[1] Launch Tool 1 (user.py)")
        print("[2] Launch Tool 2 (clone.py)")
        print("[0] Exit")
        choice = input("\nEnter your choice (1/2/0): ").strip()

        if choice == "1":
            run_local_script("user.py", "Tool 1")
        elif choice == "2":
            run_local_script("clone.py", "Tool 2")
        elif choice == "0":
            print("Exiting.")
            sys.exit(0)
        else:
            print("[-] Invalid choice. Please enter 1, 2 or 0.")
            input("\nPress Enter to continue...")

if __name__ == "__main__":
    main()
