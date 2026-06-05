import sys
import traceback
import os
import time

def run_local_script(file_path, tool_name):
    # رسالة عامة دون ذكر رابط
    print(f"جاري تحميل {tool_name} يرجى الانتظار...")
    time.sleep(1)  # محاكاة بسيطة للتحميل (اختياري)

    if not os.path.exists(file_path):
        print(f"[-] الملف غير موجود: {file_path}")
        input("\nاضغط Enter للعودة إلى القائمة...")
        return

    print(f"[+] تشغيل {tool_name} ...\n")
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            code = f.read()
        # تنفيذ الكود في نفس النطاق العام
        exec(code, globals())
    except Exception as e:
        print(f"\n[!] خطأ أثناء تشغيل {tool_name}:\n{e}")
        traceback.print_exc()
    finally:
        print(f"\n[+] انتهى تشغيل {tool_name}.")
        input("\nاضغط Enter للعودة إلى القائمة...")

def main():
    while True:
        print("\n" + "=" * 40)
        print("         أداة اختيار الأدوات")
        print("=" * 40)
        print("[1] تشغيل الأداة 1")
        print("[2] تشغيل الأداة 2")
        print("[0] خروج")
        choice = input("\nاختر (1/2/0): ").strip()

        if choice == "1":
            run_local_script("user.py", "الأداة 1")
        elif choice == "2":
            run_local_script("clone.py", "الأداة 2")
        elif choice == "0":
            print("خروج.")
            sys.exit(0)
        else:
            print("[-] اختيار غير صالح. الرجاء إدخال 1 أو 2 أو 0.")
            input("\nاضغط Enter للمتابعة...")

if __name__ == "__main__":
    main()
