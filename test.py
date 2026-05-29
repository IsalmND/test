import sys
import subprocess
import ctypes
import os

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
            subprocess.run([sys.executable, "-m", "pip", "install", pkg], check=True)
        except subprocess.CalledProcessError:
            return False
    return True

def check_and_install():
    missing = [pkg for pkg in REQUIRED_PACKAGES if not is_package_installed(pkg)]
    if missing:
        print(f"[!] المكتبات المطلوبة غير موجودة: {', '.join(missing)}")
        choice = input("هل تريد تثبيتها الآن؟ (y/n): ").strip().lower()
        if choice == 'y':
            if install_packages(missing):
                print("[+] تم التثبيت. أعد تشغيل السكربت.")
                input("اضغط Enter للخروج...")
                sys.exit(0)
            else:
                print("[!] فشل التثبيت. قم بالتثبيت يدوياً.")
                input("اضغط Enter للخروج...")
                sys.exit(1)
        else:
            print("[!] لن تعمل الوظائف. قم بتثبيت المكتبات لاحقاً.")
            input("اضغط Enter للخروج...")
            sys.exit(1)

check_and_install()
import requests

def ask_token():
    return input("🔑 أدخل توكن حسابك في Discord: ").strip()

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
    print("\n=== Discord Username Checker ===\n")
    token = ask_token()
    if not token:
        print("[!] لم يتم إدخال أي توكن.")
        return
    print("🔄 جاري التحقق من التوكن...")
    verification = verify_token(token)
    if not verification['valid']:
        print(f"❌ توكن غير صالح: {verification['error']}")
        return
    user = verification['user']
    print(f"✅ تم الدخول كـ {user['username']}#{user.get('discriminator', '0')} (ID: {user['id']})")
    print("\n📌 الأوامر المتاحة:")
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
