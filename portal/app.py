"""
SakigakeAPP 統合ポータル
全機能を1つのFlaskサーバーで提供
"""
import os
import sys
import re
import json
import threading
import importlib.util

import logging
import subprocess
import time

from flask import Flask, Blueprint, render_template, send_from_directory, request, jsonify
from flask_cors import CORS
from jinja2 import ChoiceLoader, FileSystemLoader

# ベースディレクトリ（プロジェクトルート = portal/ の親）
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
logger = logging.getLogger(__name__)


def _atomic_json_write(filepath, data):
    """アトミック書き込み: 一時ファイルに書き込み後リネーム（クラッシュ安全）"""
    tmp = filepath + ".tmp"
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, filepath)

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
CORS(app, origins=["http://localhost:5000", "http://127.0.0.1:5000"])

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
# 給与・損益ロジック（importlibで明示的にインポート、sys.path汚染を回避）
# ---------------------------------------------------------------------------
def _import_from(module_name, file_path):
    """指定パスのPythonファイルをモジュールとしてインポート"""
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod

salary_logic = _import_from('salary_logic', os.path.join(BASE_DIR, '給与', 'salary_logic.py'))
pnl_logic = _import_from('pnl_logic', os.path.join(BASE_DIR, '損益', 'pnl_logic.py'))

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
# 給与API
# ---------------------------------------------------------------------------
@app.route('/api/folders')
def salary_folders():
    return jsonify(salary_logic.list_folders_data())


@app.route('/api/parse', methods=['POST'])
def salary_parse():
    result = salary_logic.parse_uploaded_files(request.files)
    if result is None:
        return jsonify({'error': 'ファイルが選択されていません'}), 400
    return jsonify(result)


@app.route('/api/parse_folder', methods=['POST'])
def salary_parse_folder():
    folder = request.json.get('folder', '')
    if not re.match(r'^\d+月$', folder):
        return jsonify({'error': '無効なフォルダ名'}), 400
    result = salary_logic.parse_folder_data(folder)
    if result is None:
        return jsonify({'error': f'フォルダが見つかりません: {folder}'}), 404
    return jsonify(result)


@app.route('/api/parse_all_folders', methods=['POST'])
def salary_parse_all():
    result = salary_logic.parse_all_folders_data()
    if result is None:
        return jsonify({'error': '月フォルダが見つかりません'}), 404
    return jsonify(result)


@app.route('/api/sheets_data')
def salary_sheets_data():
    data = salary_logic.get_sheets_json()
    if data is None:
        return jsonify({'error': 'R7支払いデータなし'}), 404
    return jsonify(data)

# ---------------------------------------------------------------------------
# 損益API
# ---------------------------------------------------------------------------
@app.route('/api/autoload')
def pnl_autoload():
    result = pnl_logic.load_all_data()
    if 'error' in result:
        return jsonify(result), 404
    return jsonify(result)


@app.route('/api/manual_inputs', methods=['POST'])
def pnl_manual_inputs():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data'}), 400
    pnl_logic.save_manual_inputs(data)
    return jsonify({'ok': True})


@app.route('/api/export_pdf', methods=['POST'])
def pnl_export_pdf():
    data = request.json
    if not data:
        return jsonify({'error': 'No data'}), 400
    ctx = pnl_logic.build_pdf_context(data)
    return render_template('pdf_summary.html', **ctx)

# ---------------------------------------------------------------------------
# 診療報酬API
# ---------------------------------------------------------------------------
@app.route('/api/shinryo_data')
def shinryo_data():
    """全月の薬剤JSON + 入院収益JSONを統合して返す"""
    shinryo_dir = os.path.join(BASE_DIR, 'shared', '診療')
    result = {'pharmacy': {}, 'inpatient': {}}

    # 薬剤月次データ（各月フォルダ内のJSON）
    if os.path.isdir(shinryo_dir):
        for entry in sorted(os.listdir(shinryo_dir)):
            if re.match(r'^\d{1,2}月$', entry):
                month_dir = os.path.join(shinryo_dir, entry)
                for f in os.listdir(month_dir):
                    if f.startswith('薬剤月次データ') and f.endswith('.json'):
                        fpath = os.path.join(month_dir, f)
                        with open(fpath, encoding='utf-8') as fp:
                            result['pharmacy'][entry] = json.load(fp)

    # 入院収益月次データ（診療/ルートのJSON）
    inpatient_path = os.path.join(shinryo_dir, '入院収益月次データ.json')
    if os.path.isfile(inpatient_path):
        with open(inpatient_path, encoding='utf-8') as fp:
            result['inpatient'] = json.load(fp)

    return jsonify(result)


@app.route('/api/reports/months')
def reports_months():
    shinryo_dir = os.path.join(BASE_DIR, 'shared', '診療')
    if not os.path.isdir(shinryo_dir):
        return jsonify([])
    months = []
    for entry in os.listdir(shinryo_dir):
        if re.match(r'^\d{1,2}月$', entry):
            month_dir = os.path.join(shinryo_dir, entry)
            if os.path.isdir(month_dir):
                files = [f for f in os.listdir(month_dir) if f.endswith('.html')]
                if files:
                    months.append({'month': entry, 'files': sorted(files)})
    months.sort(key=lambda m: int(m['month'].replace('月', '')))
    return jsonify(months)


_GOOGLE_FONTS_LINK = re.compile(
    r'<link[^>]+fonts\.googleapis\.com[^>]*>',
    re.IGNORECASE,
)
_REPORT_FONT_STYLE = '<style>body{font-family:"Segoe UI","Meiryo","Noto Sans JP",sans-serif}</style>'


def _safe_read_html(base_dir, filename):
    """パストラバーサル防止付きHTML読み込み。安全でなければNoneを返す"""
    real_base = os.path.realpath(base_dir)
    safe_path = os.path.realpath(os.path.join(base_dir, filename))
    try:
        if os.path.commonpath([real_base, safe_path]) != real_base:
            return None
    except ValueError:
        return None
    if not os.path.isfile(safe_path):
        return None
    with open(safe_path, 'r', encoding='utf-8') as f:
        return f.read()


@app.route('/api/shinryo_annual')
def reports_annual():
    """診療/直下の年度レポート一覧"""
    shinryo_dir = os.path.join(BASE_DIR, 'shared', '診療')
    if not os.path.isdir(shinryo_dir):
        return jsonify([])
    files = sorted(f for f in os.listdir(shinryo_dir) if f.endswith('.html'))
    return jsonify(files)


@app.route('/api/shinryo_annual/<path:filename>')
def reports_annual_file(filename):
    """診療/直下の年度レポートを配信"""
    if not filename.endswith('.html'):
        return 'Not Found', 404
    html = _safe_read_html(os.path.join(BASE_DIR, 'shared', '診療'), filename)
    if html is None:
        return 'Not Found', 404
    html = _GOOGLE_FONTS_LINK.sub(_REPORT_FONT_STYLE, html)
    return html, 200, {'Content-Type': 'text/html; charset=utf-8'}


@app.route('/api/reports/<month>/<path:filename>')
def reports_file(month, filename):
    if not re.match(r'^\d{1,2}月$', month):
        return 'Not Found', 404
    if not filename.endswith('.html'):
        return 'Not Found', 404
    month_dir = os.path.join(BASE_DIR, 'shared', '診療', month)
    if not os.path.isdir(month_dir):
        return 'Not Found', 404
    html = _safe_read_html(month_dir, filename)
    if html is None:
        return 'Not Found', 404
    html = _GOOGLE_FONTS_LINK.sub(_REPORT_FONT_STYLE, html)
    return html, 200, {'Content-Type': 'text/html; charset=utf-8'}

# ---------------------------------------------------------------------------
# 共通マスタAPI
# ---------------------------------------------------------------------------
# 非常勤部課コード（master.htmlから除外）
_NON_REGULAR_BUKA = {'024', '025', '026', '027', '028', '033', '034', '041', '045', '046'}


def _is_master_target(emp):
    """一般(001)・地域生活(004)の常勤職員のみ"""
    eid = emp.get('id', '')
    if len(eid) != 12:
        return False
    taikei, buka = eid[:3], eid[3:6]
    return taikei in ('001', '004') and buka not in _NON_REGULAR_BUKA


@app.route('/api/master/employees')
def master_employees():
    path = os.path.join(BASE_DIR, 'shared', 'employees.json')
    if not os.path.isfile(path):
        return jsonify([]), 404
    with open(path, encoding='utf-8') as f:
        all_emps = json.load(f)
    return jsonify([e for e in all_emps if _is_master_target(e)])


@app.route('/api/master/employees', methods=['PUT'])
def master_employees_save():
    path = os.path.join(BASE_DIR, 'shared', 'employees.json')
    master_data = request.get_json(force=True)
    # master対象外の職員を保持してマージ
    with open(path, encoding='utf-8') as f:
        all_emps = json.load(f)
    non_master = [e for e in all_emps if not _is_master_target(e)]
    _atomic_json_write(path, master_data + non_master)
    return 'OK'


@app.route('/api/master/bonus')
def master_bonus():
    path = os.path.join(BASE_DIR, 'shared', 'bonus_contributions.json')
    if not os.path.isfile(path):
        return jsonify({}), 200
    with open(path, encoding='utf-8') as f:
        return jsonify(json.load(f))


@app.route('/api/master/bonus', methods=['PUT'])
def master_bonus_save():
    path = os.path.join(BASE_DIR, 'shared', 'bonus_contributions.json')
    data = request.get_json(force=True)
    _atomic_json_write(path, data)
    return 'OK'


@app.route('/api/master/dept-codes')
def master_dept_codes():
    path = os.path.join(BASE_DIR, '給与', 'dept_codes.json')
    if not os.path.isfile(path):
        return jsonify({}), 404
    with open(path, encoding='utf-8') as f:
        return jsonify(json.load(f))

# ---------------------------------------------------------------------------
# サーバー制御API（localhost限定）
# ---------------------------------------------------------------------------
def _is_localhost(req):
    return req.remote_addr in ('127.0.0.1', '::1')


def _safe_exit():
    """atexit/logging を実行してからプロセス終了（os._exitの安全なラッパー）"""
    import atexit
    atexit._run_exitfuncs()
    logging.shutdown()
    os._exit(0)


@app.route('/api/shutdown', methods=['POST'])
def api_shutdown():
    if not _is_localhost(request):
        return 'Forbidden', 403

    def _shutdown():
        time.sleep(0.5)
        _safe_exit()

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
        _safe_exit()

    threading.Thread(target=_restart).start()
    return 'サーバーを再起動します', 200


# ---------------------------------------------------------------------------
# 起動
# ---------------------------------------------------------------------------
def _shinryo_month_stale(month_dir, source_dir):
    """薬剤JSONのsourcesと元データPDFのmtimeを照合。不一致ならTrue"""
    # 薬剤JSONを探す
    json_files = [f for f in os.listdir(month_dir)
                  if f.startswith('薬剤月次データ') and f.endswith('.json')]
    if not json_files:
        return True
    try:
        with open(os.path.join(month_dir, json_files[0]), encoding='utf-8') as f:
            cached = json.load(f)
    except (OSError, json.JSONDecodeError):
        return True
    cached_sources = cached.get('sources', {})
    if not cached_sources:
        return True
    # 元データPDFのmtimeと照合
    for rel_path, cached_mtime in cached_sources.items():
        full_path = os.path.join(month_dir, rel_path)
        if not os.path.isfile(full_path):
            return True
        if round(os.path.getmtime(full_path), 2) != cached_mtime:
            return True
    # 新しいPDFが追加されていないかチェック
    source_pdfs = {f for f in os.listdir(source_dir) if f.lower().endswith('.pdf')}
    cached_basenames = {os.path.basename(p) for p in cached_sources}
    if source_pdfs != cached_basenames:
        return True
    return False


def generate_shinryo_reports():
    """診療/N月/ 内の元データPDFからHTMLレポートを自動生成（JSON sources照合）"""
    shinryo_data_dir = os.path.join(BASE_DIR, 'shared', '診療')
    shinryo_code_dir = os.path.join(BASE_DIR, '診療')
    if not os.path.isdir(shinryo_data_dir):
        return
    python = sys.executable
    needs_inpatient = False
    for entry in os.listdir(shinryo_data_dir):
        if not re.match(r'^\d{1,2}月$', entry):
            continue
        month_dir = os.path.join(shinryo_data_dir, entry)
        source_dir = os.path.join(month_dir, '元データ')
        if not os.path.isdir(source_dir):
            continue
        source_pdfs = [f for f in os.listdir(source_dir) if f.lower().endswith('.pdf')]
        if not source_pdfs:
            continue
        if not _shinryo_month_stale(month_dir, source_dir):
            continue
        needs_inpatient = True
        logger.info("薬剤レポート生成: %s", entry)
        try:
            subprocess.run(
                [python, os.path.join(shinryo_code_dir, 'pharmacy_report.py'), entry],
                cwd=shinryo_code_dir, timeout=120, capture_output=True,
            )
        except Exception as e:
            logger.exception("薬剤レポートエラー (%s): %s", entry, e)
    if needs_inpatient:
        logger.info("入院レポート生成（全月一括）")
        try:
            subprocess.run(
                [python, os.path.join(shinryo_code_dir, 'inpatient_report.py')],
                cwd=shinryo_code_dir, timeout=180, capture_output=True,
            )
        except Exception as e:
            logger.exception("入院レポートエラー: %s", e)
    logger.info("診療レポート生成完了")


def _hide_console():
    """コンソールウィンドウを非表示にする"""
    import ctypes
    ctypes.windll.user32.ShowWindow(
        ctypes.windll.kernel32.GetConsoleWindow(), 0
    )


def _start_flask():
    """Flaskサーバーをバックグラウンドスレッドで起動"""
    # 3モジュールのキャッシュ照合（差分なければ解析スキップ → 高速起動）
    salary_logic.ensure_cache()
    pnl_logic.ensure_cache()
    generate_shinryo_reports()
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)


if __name__ == '__main__':
    _hide_console()

    # Flaskをバックグラウンドスレッドで起動
    server_thread = threading.Thread(target=_start_flask, daemon=True)
    server_thread.start()

    # サーバーの応答を待機
    import urllib.request
    url = "http://localhost:5000/"
    for _ in range(50):
        try:
            urllib.request.urlopen(url, timeout=1)
            break
        except Exception:
            time.sleep(0.3)

    # pywebviewでネイティブウィンドウ表示
    import webview
    webview.create_window(
        'SakigakeAPP',
        url,
        width=1280,
        height=900,
        maximized=True,
    )
    webview.start(private_mode=True)
