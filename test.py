import sys
import subprocess
import importlib
import ctypes
import os
import time

# قائمة المكتبات الإضافية التي يحتاجها السكربت
REQUIRED_PACKAGES = ['requests', 'Pillow', 'pynput']  # استبدلها بالمكتبات التي تحتاجها

def show_message_box(title, message, flags=0x4 | 0x20):  # 0x4 = Yes/No, 0x20 = Question mark
    return ctypes.windll.user32.MessageBoxW(0, message, title, flags)

def is_package_installed(package_name):
    """التحقق من تثبيت حزمة معينة باستخدام pip"""
    try:
        subprocess.run([sys.executable, "-m", "pip", "show", package_name], 
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
        return True
    except subprocess.CalledProcessError:
        return False

def install_packages(packages):
    """تثبيت الحزم المفقودة"""
    for pkg in packages:
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", pkg, "--quiet"], check=True)
        except subprocess.CalledProcessError:
            return False
    return True

def restart_script():
    """إعادة تشغيل السكربت الحالي"""
    os.execv(sys.executable, [sys.executable] + sys.argv)

def check_and_install_missing_packages():
    missing = [pkg for pkg in REQUIRED_PACKAGES if not is_package_installed(pkg)]
    if not missing:
        return True
    
    missing_list = "\n".join(f"• {pkg}" for pkg in missing)
    msg = (f"السكربت يحتاج إلى المكتبات التالية لتشغيل الوظائف المتقدمة:\n\n{missing_list}\n\n"
           f"هل تريد تثبيتها الآن؟")
    
    result = show_message_box("مكتبات مفقودة", msg)
    
    if result == 6:  # IDYES = 6
        if install_packages(missing):
            show_message_box("تم التثبيت", "تم تثبيت المكتبات بنجاح.\nسيتم إعادة تشغيل السكربت.", 0x40)
            restart_script()
        else:
            show_message_box("خطأ", "حدث خطأ أثناء تثبيت المكتبات. حاول يدوياً:\npip install " + " ".join(missing), 0x10)
            return False
    else:
        show_message_box("تنبيه", "لن تعمل بعض الوظائف بسبب عدم تثبيت المكتبات المطلوبة.", 0x30)
        return False

def main():
    # التحقق من المكتبات أولاً
    if not check_and_install_missing_packages():
        return
    
    # --- هنا اكتب الكود الأساسي للسكربت الذي يعتمد على تلك المكتبات ---
    # مثال:
    # import requests
    # response = requests.get('https://api.example.com')
    # print(response.json())
    
    ctypes.windll.user32.MessageBoxW(0, "مرحبا! السكربت يعمل الآن بجميع مكتباته.", "تم التشغيل", 0)

if __name__ == "__main__":
    main()
