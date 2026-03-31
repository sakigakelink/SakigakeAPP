"""
SakigakeAPP 統合ポータル
全機能を1つのFlaskサーバーで提供
"""
import os
import sys
import re
import json
import threading
import webbrowser
import importlib.util

import subprocess
import time

from flask import Flask, Blueprint, render_template, send_from_directory, request
from flask_cors import CORS
from jinja2 import ChoiceLoader, FileSystemLoader

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
app.jinja_loader = ChoiceLoader([
    FileSystemLoader(os.path.join(BASE_DIR, 'portal', 'templates')),
    FileSystemLoader(os.path.join(BASE_DIR, '損益', 'templates')),
])
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024
CORS(app)

# ---------------------------------------------------------------------------
# シフト管理（appに直接ルート登録、/はポータル側で定義するためスキップ）
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.join(BASE_DIR, 'シフト'))
os.makedirs(os.path.join(BASE_DIR, 'シフト', 'backup'), exist_ok=True)

from routes import register_routes as shift_register_routes, start_daily_backup
SHIFT_BACKUP_DIR = os.path.join(BASE_DIR, 'シフト', 'backup')
shift_register_routes(app, SHIFT_BACKUP_DIR, portal_mode=True)
start_daily_backup(SHIFT_BACKUP_DIR)

# ---------------------------------------------------------------------------
# 給与分析（モジュール読み込み — プロキシルートで配信）
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.join(BASE_DIR, '給与'))
_salary_spec = importlib.util.spec_from_file_location(
    'salary_app', os.path.join(BASE_DIR, '給与', 'app.py'))
_salary_mod = importlib.util.module_from_spec(_salary_spec)
_salary_spec.loader.exec_module(_salary_mod)

# ---------------------------------------------------------------------------
# 損益計算（モジュール読み込み — プロキシルートで配信）
# ---------------------------------------------------------------------------
sys.path.insert(0, os.path.join(BASE_DIR, '損益'))
_pnl_spec = importlib.util.spec_from_file_location(
    'pnl_app', os.path.join(BASE_DIR, '損益', 'app.py'))
_pnl_mod = importlib.util.module_from_spec(_pnl_spec)
_pnl_spec.loader.exec_module(_pnl_mod)

# ---------------------------------------------------------------------------
# ポータル ルート
# ---------------------------------------------------------------------------
VALID_PAGES = {'shift', 'salary', 'pnl', 'data', 'master'}


@app.route('/')
def portal_home():
    return render_template('dashboard.html')


@app.route('/reports')
def portal_reports():
    return render_template('reports.html')


@app.route('/<page>')
def portal_page(page):
    if page in VALID_PAGES:
        return render_template('iframe_wrapper.html', page=page)
    return 'Not Found', 404

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


@app.route('/legacy/master/')
def legacy_master():
    return send_from_directory(
        os.path.join(BASE_DIR, '給与'), 'master.html')


@app.route('/legacy/pnl/')
def legacy_pnl():
    return send_from_directory(
        os.path.join(BASE_DIR, '損益', 'templates'), 'index.html')


@app.route('/legacy/data/<tool>')
def legacy_data(tool):
    if tool == 'kintai':
        return send_from_directory(
            os.path.join(BASE_DIR, 'portal', 'templates'), '勤怠変換.html')
    return 'Not Found', 404

# ---------------------------------------------------------------------------
# 給与API プロキシ（iframe内の /api/* 呼び出しを中継）
# ---------------------------------------------------------------------------
@app.route('/api/folders')
def salary_folders():
    return _salary_mod.list_folders()


@app.route('/api/parse', methods=['POST'])
def salary_parse():
    return _salary_mod.parse_pdfs()


@app.route('/api/parse_folder', methods=['POST'])
def salary_parse_folder():
    return _salary_mod.parse_folder()


@app.route('/api/parse_all_folders', methods=['POST'])
def salary_parse_all():
    return _salary_mod.parse_all_folders()


@app.route('/api/sheets_data')
def salary_sheets_data():
    return _salary_mod.get_sheets_data()

# ---------------------------------------------------------------------------
# 損益API プロキシ
# ---------------------------------------------------------------------------
@app.route('/api/autoload')
def pnl_autoload():
    return _pnl_mod.autoload_data()


@app.route('/api/manual_inputs', methods=['POST'])
def pnl_manual_inputs():
    return _pnl_mod.save_manual_inputs()


@app.route('/api/export_pdf', methods=['POST'])
def pnl_export_pdf():
    return _pnl_mod.export_pdf()

# ---------------------------------------------------------------------------
# 診療報酬API
# ---------------------------------------------------------------------------
@app.route('/api/reports/months')
def reports_months():
    shinryo_dir = os.path.join(BASE_DIR, '診療')
    if not os.path.isdir(shinryo_dir):
        return json.dumps([], ensure_ascii=False)
    months = []
    for entry in os.listdir(shinryo_dir):
        if re.match(r'^\d{1,2}月$', entry):
            month_dir = os.path.join(shinryo_dir, entry)
            if os.path.isdir(month_dir):
                files = [f for f in os.listdir(month_dir) if f.endswith('.html')]
                if files:
                    months.append({'month': entry, 'files': sorted(files)})
    months.sort(key=lambda m: int(m['month'].replace('月', '')))
    return json.dumps(months, ensure_ascii=False)


_GOOGLE_FONTS_LINK = re.compile(
    r'<link[^>]+fonts\.googleapis\.com[^>]*>',
    re.IGNORECASE,
)
_REPORT_FONT_STYLE = '<style>body{font-family:"Segoe UI","Meiryo","Noto Sans JP",sans-serif}</style>'


@app.route('/api/shinryo_annual')
def reports_annual():
    """診療/直下の年度レポート一覧"""
    shinryo_dir = os.path.join(BASE_DIR, '診療')
    if not os.path.isdir(shinryo_dir):
        return json.dumps([], ensure_ascii=False)
    files = sorted(f for f in os.listdir(shinryo_dir) if f.endswith('.html'))
    return json.dumps(files, ensure_ascii=False)


@app.route('/api/shinryo_annual/<path:filename>')
def reports_annual_file(filename):
    """診療/直下の年度レポートを配信"""
    if not filename.endswith('.html'):
        return 'Not Found', 404
    filepath = os.path.join(BASE_DIR, '診療', filename)
    if not os.path.isfile(filepath):
        return 'Not Found', 404
    with open(filepath, 'r', encoding='utf-8') as f:
        html = f.read()
    html = _GOOGLE_FONTS_LINK.sub(_REPORT_FONT_STYLE, html)
    return html, 200, {'Content-Type': 'text/html; charset=utf-8'}


@app.route('/api/reports/<month>/<path:filename>')
def reports_file(month, filename):
    if not re.match(r'^\d{1,2}月$', month):
        return 'Not Found', 404
    if not filename.endswith('.html'):
        return 'Not Found', 404
    month_dir = os.path.join(BASE_DIR, '診療', month)
    if not os.path.isdir(month_dir):
        return 'Not Found', 404
    filepath = os.path.join(month_dir, filename)
    if not os.path.isfile(filepath):
        return 'Not Found', 404
    with open(filepath, 'r', encoding='utf-8') as f:
        html = f.read()
    html = _GOOGLE_FONTS_LINK.sub(_REPORT_FONT_STYLE, html)
    return html, 200, {'Content-Type': 'text/html; charset=utf-8'}

# ---------------------------------------------------------------------------
# 共通マスタAPI
# ---------------------------------------------------------------------------
@app.route('/api/master/employees')
def master_employees():
    path = os.path.join(BASE_DIR, 'shared', 'employees.json')
    if not os.path.isfile(path):
        return json.dumps([], ensure_ascii=False), 404
    with open(path, encoding='utf-8') as f:
        return json.load(f)


@app.route('/api/master/employees', methods=['PUT'])
def master_employees_save():
    path = os.path.join(BASE_DIR, 'shared', 'employees.json')
    data = request.get_json(force=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return 'OK'


@app.route('/api/master/bonus')
def master_bonus():
    path = os.path.join(BASE_DIR, 'shared', 'bonus_contributions.json')
    if not os.path.isfile(path):
        return json.dumps({}, ensure_ascii=False), 200
    with open(path, encoding='utf-8') as f:
        return json.load(f)


@app.route('/api/master/bonus', methods=['PUT'])
def master_bonus_save():
    path = os.path.join(BASE_DIR, 'shared', 'bonus_contributions.json')
    data = request.get_json(force=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return 'OK'


@app.route('/api/master/dept-codes')
def master_dept_codes():
    path = os.path.join(BASE_DIR, '給与', 'dept_codes.json')
    if not os.path.isfile(path):
        return json.dumps({}, ensure_ascii=False), 404
    with open(path, encoding='utf-8') as f:
        return json.load(f)

# ---------------------------------------------------------------------------
# サーバー制御API（localhost限定）
# ---------------------------------------------------------------------------
def _is_localhost(req):
    return req.remote_addr in ('127.0.0.1', '::1')


@app.route('/api/shutdown', methods=['POST'])
def api_shutdown():
    if not _is_localhost(request):
        return 'Forbidden', 403

    def _shutdown():
        time.sleep(0.5)
        os._exit(0)

    threading.Thread(target=_shutdown).start()
    return 'サーバーを停止します', 200


@app.route('/api/restart', methods=['POST'])
def api_restart():
    if not _is_localhost(request):
        return 'Forbidden', 403

    def _restart():
        time.sleep(0.5)
        # --no-browser を維持して再起動（新ウインドウを開かない）
        args = list(sys.argv)
        if '--no-browser' not in args:
            args.append('--no-browser')
        subprocess.Popen([sys.executable] + args, cwd=BASE_DIR)
        time.sleep(0.3)
        os._exit(0)

    threading.Thread(target=_restart).start()
    return 'サーバーを再起動します', 200


# ---------------------------------------------------------------------------
# 起動
# ---------------------------------------------------------------------------
def open_browser():
    import subprocess
    url = "http://localhost:5000/"
    browser_paths = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    ]
    for path in browser_paths:
        if os.path.exists(path):
            try:
                subprocess.Popen([path, f"--app={url}"])
                return
            except Exception:
                pass
    webbrowser.open(url)


def generate_shinryo_reports():
    """診療/N月/ 内の元データPDFからHTMLレポートを自動生成（未生成 or 古い場合のみ）"""
    import subprocess
    shinryo_dir = os.path.join(BASE_DIR, '診療')
    if not os.path.isdir(shinryo_dir):
        return
    python = sys.executable
    needs_inpatient = False
    for entry in os.listdir(shinryo_dir):
        if not re.match(r'^\d{1,2}月$', entry):
            continue
        month_dir = os.path.join(shinryo_dir, entry)
        source_dir = os.path.join(month_dir, '元データ')
        if not os.path.isdir(source_dir):
            continue
        source_pdfs = [f for f in os.listdir(source_dir) if f.lower().endswith('.pdf')]
        if not source_pdfs:
            continue
        latest_src = max(
            os.path.getmtime(os.path.join(source_dir, f)) for f in source_pdfs
        )
        existing_htmls = [f for f in os.listdir(month_dir) if f.endswith('.html')]
        if existing_htmls:
            oldest_html = min(
                os.path.getmtime(os.path.join(month_dir, f)) for f in existing_htmls
            )
            if oldest_html > latest_src:
                continue
        needs_inpatient = True
        # 薬剤レポート（月ごと）
        print(f"  薬剤レポート生成: {entry} ...")
        try:
            subprocess.run(
                [python, os.path.join(shinryo_dir, 'pharmacy_report.py'), entry],
                cwd=shinryo_dir, timeout=120, capture_output=True,
            )
        except Exception as e:
            print(f"    薬剤レポートエラー ({entry}): {e}")
    # 入院レポート（全月一括、引数なし）
    if needs_inpatient:
        print("  入院レポート生成（全月一括）...")
        try:
            subprocess.run(
                [python, os.path.join(shinryo_dir, 'inpatient_report.py')],
                cwd=shinryo_dir, timeout=180, capture_output=True,
            )
        except Exception as e:
            print(f"    入院レポートエラー: {e}")
    print("  診療レポート生成完了")


if __name__ == '__main__':
    print("=" * 40)
    print("  SakigakeAPP 統合ポータル")
    print("  http://localhost:5000/")
    print("=" * 40)
    generate_shinryo_reports()
    if "--no-browser" not in sys.argv:
        threading.Timer(1.0, open_browser).start()
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
