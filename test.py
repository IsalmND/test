import sys
import subprocess
import ctypes
import os
import json

# المكتبة الوحيدة المطلوبة (ستُثبّت تلقائياً)
REQUIRED_PACKAGES = ['requests']

def show_message_box(title, message, flags=0x4 | 0x20):
    """عرض رسالة منبثقة في Windows (نعم/لا)"""
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

def check_and_install_missing_packages():
    missing = [pkg for pkg in REQUIRED_PACKAGES if not is_package_installed(pkg)]
    if not missing:
        return True
    missing_list = "\n".join(f"• {pkg}" for pkg in missing)
    msg = (f"المكتبات التالية مطلوبة:\n\n{missing_list}\n\n"
           f"هل تريد تثبيتها الآن؟")
    result = show_message_box("مكتبات مفقودة", msg)
    if result == 6:  # Yes
        if install_packages(missing):
            show_message_box("تم التثبيت", "تم تثبيت المكتبات بنجاح.\nسيتم إعادة تشغيل السكربت.", 0x40)
            restart_script()
        else:
            show_message_box("خطأ", "فشل التثبيت. قم بتشغيل:\npip install " + " ".join(missing), 0x10)
            return False
    else:
        show_message_box("تنبيه", "لن تعمل الوظائف بدون المكتبات.", 0x30)
        return False

# بعد التأكد من وجود المكتبات، نستوردها
check_and_install_missing_packages()
import requests

def ask_token():
    """طلب التوكن من المستخدم عبر نافذة GUI أو الطرفية"""
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
        resp = requests.get(f'https://discord.com/api/v9/users/@me/username-check?username={username}',
                            headers={'Authorization': token})
        if resp.status_code == 200:
            return resp.json()
        else:
            return {'error': resp.json().get('message', 'API error')}
    except Exception as e:
        return {'error': str(e)}

def main():
    # طلب التوكن
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
    print(f"\n✅ تم الدخول كـ {user['username']}#{user.get('discriminator', '0')} (ID: {user['id']})")
    print("📌 الأوامر المتاحة:")
    print("   /check <اسم>  - فحص اسم مكون من 4 أحرف")
    print("   /exit         - إنهاء السكربت")
    while True:
        cmd = input("\n> ").strip()
        if cmd.lower() == '/exit':
            print("👋 مع السلامة!")
            break
        elif cmd.startswith('/check'):
            parts = cmd.split()
            if len(parts) != 2:
                print("⚠️ استخدم: /check <اسم>")
                continue
            username = parts[1]
            if len(username) != 4:
                print("⚠️ الاسم يجب أن يكون 4 أحرف بالضبط.")
                continue
            print(f"🔍 جاري فحص الاسم: {username}...")
            result = check_username(token, username)
            if 'error' in result:
                print(f"❌ خطأ: {result['error']}")
            else:
                taken = result.get('taken', False)
                if taken:
                    print(f"❌ الاسم {username} محجوز.")
                else:
                    print(f"✅ الاسم {username} متاح!")
        else:
            print("أمر غير معروف. استخدم /check أو /exit")

if __name__ == '__main__':
    main()
