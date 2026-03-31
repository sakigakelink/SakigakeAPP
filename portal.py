"""
SakigakeAPP デスクトップポータル
pywebview でネイティブウィンドウ表示
"""
import webview
import subprocess
import os
import sys
import time
import threading
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


def monitor_server(window):
    """サーバー停止を検知してウィンドウを閉じる"""
    time.sleep(3)  # 初回は待機
    while True:
        time.sleep(2)
        try:
            urllib.request.urlopen(URL, timeout=2)
        except Exception:
            # サーバーが応答しない → 終了ボタンが押された
            # 再起動の場合は数秒で復帰するので少し待つ
            time.sleep(5)
            try:
                urllib.request.urlopen(URL, timeout=2)
            except Exception:
                # 5秒待っても復帰しない → 本当に終了
                try:
                    window.destroy()
                except Exception:
                    pass
                return


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

    # サーバー停止検知スレッド開始
    threading.Thread(target=monitor_server, args=(window,), daemon=True).start()

    webview.start()

    # ウィンドウが閉じられたらサーバーも停止
    kill_existing_server()
