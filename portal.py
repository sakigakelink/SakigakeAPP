"""
SakigakeAPP デスクトップポータル
pywebview でネイティブウィンドウ表示
"""
import webview
import subprocess
import os
import sys
import time
import urllib.request

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PYTHON = r"C:\Python314\python.exe"
URL = "http://localhost:5000/"


def kill_existing_server():
    """既存サーバープロセスを停止"""
    subprocess.run(
        'taskkill /f /fi "WINDOWTITLE eq SakigakeAPP-Server"',
        shell=True, capture_output=True
    )


def start_server():
    """Flaskサーバーをバックグラウンドで起動"""
    subprocess.Popen(
        f'title SakigakeAPP-Server && "{PYTHON}" app.py --no-browser',
        shell=True, cwd=BASE_DIR,
        creationflags=subprocess.CREATE_NO_WINDOW
    )


def wait_for_server(timeout=15):
    """サーバーが応答するまで待機"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(URL, timeout=1)
            return True
        except Exception:
            time.sleep(0.3)
    return False


if __name__ == '__main__':
    kill_existing_server()
    time.sleep(0.3)
    start_server()

    if not wait_for_server():
        print("サーバー起動タイムアウト")
        sys.exit(1)

    window = webview.create_window(
        'SakigakeAPP',
        URL,
        width=1280,
        height=900,
        maximized=True,
    )
    webview.start()
