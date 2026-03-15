"""
Sakigake Shift - メインアプリケーション
Flaskアプリの初期化と起動
"""
import os
import sys
import threading
import webbrowser
from flask import Flask
from flask_cors import CORS

# pythonw.exe 起動時もカレントディレクトリをスクリプト位置に合わせる
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from routes import register_routes

# Flaskアプリ初期化
app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
CORS(app, origins=["http://localhost:5000", "http://127.0.0.1:5000"])

# バックアップディレクトリ
BACKUP_DIR = os.path.join(os.path.dirname(__file__), "backup")
os.makedirs(BACKUP_DIR, exist_ok=True)

# ルート登録
register_routes(app, BACKUP_DIR)


def open_browser():
    import subprocess
    url = "http://localhost:5000/"

    # Chrome/Edgeをアプリモードで起動（タブなし、単独ウィンドウ）
    chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    edge_paths = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]

    # Chromeを優先
    for path in chrome_paths + edge_paths:
        if os.path.exists(path):
            try:
                subprocess.Popen([path, f"--app={url}"])
                return
            except Exception:
                pass

    # 見つからない場合は通常のブラウザで開く
    webbrowser.open(url)


if __name__ == "__main__":
    print("=" * 40)
    print("  Sakigake Shift")
    print("  http://localhost:5000/")
    print("=" * 40)
    # --no-browser 指定時はブラウザを開かない（テスト用）
    if "--no-browser" not in sys.argv:
        threading.Timer(1.0, open_browser).start()
    app.run(host="127.0.0.1", port=5000, debug=False, threaded=True)
