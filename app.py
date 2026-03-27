"""
SakigakeAPP 統合ポータル
全機能を1つのFlaskサーバーで提供
"""
import os
import sys
import threading
import webbrowser

from flask import Flask, render_template, send_from_directory
from flask_cors import CORS

# ベースディレクトリ
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# Flask初期化
# ---------------------------------------------------------------------------
app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, 'portal', 'templates'),
    static_folder=os.path.join(BASE_DIR, 'portal', 'static'),
    static_url_path='/static',
)
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024
CORS(app)

# ---------------------------------------------------------------------------
# シフト管理 Blueprint
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.join(BASE_DIR, 'シフト'))
os.makedirs(os.path.join(BASE_DIR, 'シフト', 'backup'), exist_ok=True)

from flask import Blueprint
shift_bp = Blueprint('shift', __name__, url_prefix='/api/shift',
                     template_folder=os.path.join(BASE_DIR, 'シフト', 'templates'),
                     static_folder=os.path.join(BASE_DIR, 'シフト', 'static'),
                     static_url_path='/shift-static')

# シフトのregister_routesをBlueprint用に適用
from routes import register_routes as shift_register_routes, start_daily_backup
SHIFT_BACKUP_DIR = os.path.join(BASE_DIR, 'シフト', 'backup')
shift_register_routes(shift_bp, SHIFT_BACKUP_DIR)
app.register_blueprint(shift_bp)

# 日次バックアップ
start_daily_backup(SHIFT_BACKUP_DIR)

# ---------------------------------------------------------------------------
# 給与分析 Blueprint（既存app.pyのルートを取り込み）
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.join(BASE_DIR, '給与'))
salary_bp = Blueprint('salary', __name__, url_prefix='/api/salary',
                      template_folder=os.path.join(BASE_DIR, '給与', 'templates'))

import importlib.util
_salary_spec = importlib.util.spec_from_file_location(
    'salary_app', os.path.join(BASE_DIR, '給与', 'app.py'))
_salary_mod = importlib.util.module_from_spec(_salary_spec)
_salary_spec.loader.exec_module(_salary_mod)

# 給与アプリのルートをBlueprintにコピー
for rule in _salary_mod.app.url_map.iter_rules():
    if rule.endpoint == 'static':
        continue
    view_func = _salary_mod.app.view_functions[rule.endpoint]
    endpoint = f'salary_{rule.endpoint}'
    salary_bp.add_url_rule(rule.rule, endpoint=endpoint,
                           view_func=view_func, methods=rule.methods)

app.register_blueprint(salary_bp)

# ---------------------------------------------------------------------------
# 損益計算 Blueprint（同様に取り込み）
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.join(BASE_DIR, '損益'))
pnl_bp = Blueprint('pnl', __name__, url_prefix='/api/pnl',
                    template_folder=os.path.join(BASE_DIR, '損益', 'templates'))

_pnl_spec = importlib.util.spec_from_file_location(
    'pnl_app', os.path.join(BASE_DIR, '損益', 'app.py'))
_pnl_mod = importlib.util.module_from_spec(_pnl_spec)
_pnl_spec.loader.exec_module(_pnl_mod)

for rule in _pnl_mod.app.url_map.iter_rules():
    if rule.endpoint == 'static':
        continue
    view_func = _pnl_mod.app.view_functions[rule.endpoint]
    endpoint = f'pnl_{rule.endpoint}'
    pnl_bp.add_url_rule(rule.rule, endpoint=endpoint,
                         view_func=view_func, methods=rule.methods)

app.register_blueprint(pnl_bp)

# ---------------------------------------------------------------------------
# ポータル ルート
# ---------------------------------------------------------------------------
@app.route('/')
def portal_dashboard():
    return render_template('dashboard.html')

@app.route('/reports')
def portal_reports():
    return render_template('reports.html')

@app.route('/<page>')
def portal_page(page):
    valid_pages = ['shift', 'salary', 'pnl', 'documents', 'data']
    if page in valid_pages:
        return render_template('iframe_wrapper.html', page=page)
    return render_template('dashboard.html')

# ---------------------------------------------------------------------------
# レガシーUI配信（iframe用）
# ---------------------------------------------------------------------------
@app.route('/legacy/shift/')
def legacy_shift():
    return send_from_directory(
        os.path.join(BASE_DIR, 'シフト', 'templates'), 'index.html')

@app.route('/legacy/shift/static/<path:filename>')
def legacy_shift_static(filename):
    return send_from_directory(
        os.path.join(BASE_DIR, 'シフト', 'static'), filename)

@app.route('/legacy/salary/')
def legacy_salary():
    return send_from_directory(
        os.path.join(BASE_DIR, '給与', 'templates'), 'index.html')

@app.route('/legacy/pnl/')
def legacy_pnl():
    return send_from_directory(
        os.path.join(BASE_DIR, '損益', 'templates'), 'index.html')

@app.route('/api/autoload')
def pnl_autoload():
    """損益/data/ 内のPDF・TXTを自動読み込み（iframe用プロキシ）"""
    return _pnl_mod.autoload_data()

@app.route('/legacy/data/<tool>')
def legacy_data(tool):
    if tool == 'kintai':
        return send_from_directory(
            os.path.join(BASE_DIR, 'portal', 'templates'), '勤怠変換.html')
    return 'Not Found', 404

# ---------------------------------------------------------------------------
# 診療報酬API
# ---------------------------------------------------------------------------
import re as _re
import json as _json

@app.route('/api/reports/months')
def reports_months():
    """利用可能な月とレポートファイル一覧を返す"""
    shinryo_dir = os.path.join(BASE_DIR, '診療')
    months = []
    for entry in sorted(os.listdir(shinryo_dir)):
        if _re.match(r'^\d{1,2}月$', entry):
            month_dir = os.path.join(shinryo_dir, entry)
            if os.path.isdir(month_dir):
                files = [f for f in os.listdir(month_dir)
                         if f.endswith('.html')]
                if files:
                    months.append({'month': entry, 'files': sorted(files)})
    return _json.dumps(months, ensure_ascii=False)

@app.route('/api/reports/<month>/<path:filename>')
def reports_file(month, filename):
    """月別HTMLサマリーファイルを配信"""
    if not _re.match(r'^\d{1,2}月$', month):
        return 'Not Found', 404
    if not filename.endswith('.html'):
        return 'Not Found', 404
    month_dir = os.path.join(BASE_DIR, '診療', month)
    if not os.path.isdir(month_dir):
        return 'Not Found', 404
    return send_from_directory(month_dir, filename)

# ---------------------------------------------------------------------------
# 共通マスタAPI
# ---------------------------------------------------------------------------

@app.route('/api/master/employees')
def master_employees():
    path = os.path.join(BASE_DIR, 'shared', 'employees.json')
    with open(path, encoding='utf-8') as f:
        return _json.load(f)

@app.route('/api/master/dept-codes')
def master_dept_codes():
    path = os.path.join(BASE_DIR, '給与', 'dept_codes.json')
    with open(path, encoding='utf-8') as f:
        return _json.load(f)

# ---------------------------------------------------------------------------
# 起動
# ---------------------------------------------------------------------------
def open_browser():
    import subprocess
    url = "http://localhost:5000/"
    chrome_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    ]
    edge_paths = [
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    for path in chrome_paths + edge_paths:
        if os.path.exists(path):
            try:
                subprocess.Popen([path, f"--app={url}"])
                return
            except Exception:
                pass
    webbrowser.open(url)


if __name__ == '__main__':
    print("=" * 40)
    print("  SakigakeAPP 統合ポータル")
    print("  http://localhost:5000/")
    print("=" * 40)
    if "--no-browser" not in sys.argv:
        threading.Timer(1.0, open_browser).start()
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
