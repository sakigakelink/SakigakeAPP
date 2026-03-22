#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""給与分析アプリ - TKC PX2 一人別給与統計表 PDF解析"""

import os
import re
import tempfile
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import pdfplumber

app = Flask(__name__)
CORS(app)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB
app.json.sort_keys = False

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------------------
# 部課コード → 名称マッピング
# ---------------------------------------------------------------------------
import json as _json
_dept_path = os.path.join(BASE_DIR, '..', 'データ', 'dept_codes.json')
try:
    with open(_dept_path, encoding='utf-8') as _f:
        DEPT_NAMES = _json.load(_f)
except (FileNotFoundError, ValueError):
    DEPT_NAMES = {}

# ---------------------------------------------------------------------------
# PDF テーブル定数
# ---------------------------------------------------------------------------
# 各ページ: 63行 × 32列、6名分の給与データを横並び
# 従業員データの当月値列インデックス
EMPLOYEE_COL_OFFSETS = [4, 9, 14, 19, 24, 29]

# ヘッダー行
NAME_ROW = 1
CODE_ROW = 2
DOB_ROW = 3
HIRE_ROW = 4

# 支給項目の行インデックス
SALARY_ROW_MAP = {
    '基本給': 6,
    '役職手当': 7,
    '調整手当': 8,
    'その他固定': 9,
    'その他変動': 10,
    '欠勤控除': 12,
    '深夜手当': 13,
    '準夜手当': 14,
    '遅出手当1': 15,
    '遅出手当2': 16,
    '早出手当': 17,
    '会費等': 18,
    '時間外手当': 19,
    '回数手当': 20,
    '課税通勤手当': 21,
    '課税支給額': 23,
    '非課税通勤手当': 24,
    '非課税当直手当': 25,
    '支給合計': 26,
}


# ---------------------------------------------------------------------------
# ユーティリティ
# ---------------------------------------------------------------------------
def parse_number(s):
    """'330,000' → 330000, 空/None → 0"""
    if not s or not str(s).strip():
        return 0
    try:
        return int(str(s).strip().replace(',', '').replace(' ', '').replace('\u3000', ''))
    except ValueError:
        return 0


def safe_cell(table, row, col):
    """テーブルのセルを安全に取得"""
    if row < len(table) and col < len(table[row]):
        return table[row][col]
    return None


def parse_value(table, row, col):
    """数値セルを取得。大きい値がcol-1とcolに分割されるケースを処理"""
    cell = safe_cell(table, row, col)
    val_str = str(cell).strip() if cell else ''
    if val_str.startswith(','):
        prefix = safe_cell(table, row, col - 1)
        if prefix:
            val_str = str(prefix).strip() + val_str
    return parse_number(val_str)


# ---------------------------------------------------------------------------
# PDF解析
# ---------------------------------------------------------------------------
def is_summary_page(table):
    """最終ページ（全社合計）かどうか判定"""
    if not table or len(table) < 2:
        return False
    for cell in table[NAME_ROW]:
        if cell and '合' in str(cell) and '計' in str(cell):
            return True
    return False


def extract_names_from_text(text, expected_count):
    """テキストから従業員名を抽出（テーブルのName行が不完全な場合のフォールバック）"""
    for line in text.split('\n'):
        if '氏' in line and '名' in line:
            parts = line.split('名', 1)
            if len(parts) < 2:
                continue
            words = parts[1].split()
            names = []
            for i in range(0, len(words) - 1, 2):
                names.append(words[i] + '\u3000' + words[i + 1])
                if len(names) >= expected_count:
                    break
            return names
    return []


def extract_prefixed_cell(table, row, col_offset):
    """先頭文字が col_offset-1 に分割されるセルを結合取得"""
    main = safe_cell(table, row, col_offset)
    prev = safe_cell(table, row, col_offset - 1) if col_offset > 0 else None

    parts = []
    if prev:
        p = str(prev).strip()
        if p and p in ('昭', '平', '令'):
            parts.append(p)
    if main:
        parts.append(str(main).strip())

    return ''.join(parts)


def detect_employee_columns(table):
    """社員番号行からデータ列のオフセットを動的検出"""
    offsets = []
    if CODE_ROW < len(table):
        for c in range(len(table[CODE_ROW])):
            cell = safe_cell(table, CODE_ROW, c)
            if cell and re.match(r'\d+\s*-\s*\d+\s*-\s*\d+', str(cell).strip()):
                offsets.append(c)
    return offsets


def parse_employee_page(table, page_text=''):
    """1ページから最大6名の給与データを抽出"""
    active_offsets = detect_employee_columns(table)

    if not active_offsets:
        return []

    # テキストから名前を抽出（テーブルの名前行は列位置がずれるため）
    text_names = extract_names_from_text(page_text, len(active_offsets))

    employees = []
    for idx, col_offset in enumerate(active_offsets):
        # 名前: テキストから取得
        name = text_names[idx] if idx < len(text_names) else ''

        # 社員番号解析
        code_cell = safe_cell(table, CODE_ROW, col_offset)
        code = str(code_cell).strip() if code_cell else ''
        code_match = re.match(
            r'(\d+)\s*-\s*(\d+)\s*-\s*(\d+)\s*(男性|女性)?', code
        )
        taikei = code_match.group(1) if code_match else ''
        buka = code_match.group(2) if code_match else ''
        shain_no = code_match.group(3) if code_match else ''
        gender = code_match.group(4) if code_match else ''

        # 年齢
        dob_str = extract_prefixed_cell(table, DOB_ROW, col_offset)
        age_match = re.search(r'(\d+)\s*歳', dob_str)
        age = int(age_match.group(1)) if age_match else None

        # 勤続年数
        hire_str = extract_prefixed_cell(table, HIRE_ROW, col_offset)
        tenure_match = re.search(r'([\d.]+)\s*年', hire_str)
        tenure = float(tenure_match.group(1)) if tenure_match else None

        # 支給項目
        salary = {}
        for item_name, row_idx in SALARY_ROW_MAP.items():
            salary[item_name] = parse_value(table, row_idx, col_offset)

        employees.append({
            'name': name,
            'taikei': taikei,
            'buka': buka,
            'shain_no': shain_no,
            'gender': gender,
            'age': age,
            'tenure': tenure,
            'salary': salary,
        })

    return employees


def find_summary_data_col(table):
    """サマリーページのデータ列を特定（'X人' が含まれる列を探す）"""
    if CODE_ROW < len(table):
        for c in range(len(table[CODE_ROW])):
            cell = safe_cell(table, CODE_ROW, c)
            if cell and re.search(r'\d+\s*人', str(cell)):
                return c
    return EMPLOYEE_COL_OFFSETS[0]


def parse_summary_page(table):
    """最終ページ（全社合計）から集計値を抽出"""
    col = find_summary_data_col(table)

    # 人数
    count_cell = safe_cell(table, CODE_ROW, col)
    count_match = re.search(r'(\d+)\s*人', str(count_cell)) if count_cell else None
    headcount = int(count_match.group(1)) if count_match else 0

    # 平均年齢
    age_cell = safe_cell(table, DOB_ROW, col)
    age_match = re.search(r'([\d.]+)\s*歳', str(age_cell)) if age_cell else None
    avg_age = float(age_match.group(1)) if age_match else 0

    # 平均勤続
    tenure_cell = safe_cell(table, HIRE_ROW, col)
    tenure_match = re.search(r'([\d.]+)\s*年', str(tenure_cell)) if tenure_cell else None
    avg_tenure = float(tenure_match.group(1)) if tenure_match else 0

    # 支給合計 (Row 26) — 値が分割されるケースに対応
    shikyu = parse_value(table, SALARY_ROW_MAP['支給合計'], col)

    return {
        'headcount': headcount,
        'avg_age': avg_age,
        'avg_tenure': avg_tenure,
        '支給合計': shikyu,
    }


def parse_payroll_pdf_path(filepath, category):
    """ファイルパスからPDFを解析"""
    result = {
        'category': category,
        'employees': [],
        'summary': None,
        'period': '',
    }

    with pdfplumber.open(filepath) as pdf:
        for page_num, page in enumerate(pdf.pages):
            text = page.extract_text() or ''

            if page_num == 0:
                m = re.search(r'令和\s*(\d+)年\s*(\d+)月', text)
                if m:
                    result['period'] = f"{2018 + int(m.group(1))}年{int(m.group(2))}月"

            tables = page.extract_tables()
            if not tables:
                continue
            table = tables[0]

            if is_summary_page(table):
                result['summary'] = parse_summary_page(table)
            else:
                result['employees'].extend(parse_employee_page(table, text))

    return result


def parse_payroll_pdf_upload(file_storage, category):
    """アップロードファイルからPDFを解析"""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
    try:
        file_storage.save(tmp.name)
        tmp.close()
        return parse_payroll_pdf_path(tmp.name, category)
    finally:
        os.unlink(tmp.name)


def build_combined_summary(results):
    """全カテゴリ横断の集計"""
    category_summaries = []
    total_shikyu = 0
    total_headcount = 0
    total_age_w = 0
    total_tenure_w = 0

    for label, data in results.items():
        if 'error' in data:
            continue
        summary = data.get('summary')
        if not summary:
            continue

        hc = summary.get('headcount', 0)
        shikyu = summary.get('支給合計', 0)

        # 個人データから支給内訳を集計
        emp_list = data.get('employees', [])
        kihon_total = sum(e['salary'].get('基本給', 0) for e in emp_list)
        teate_total = sum(
            e['salary'].get('役職手当', 0) +
            e['salary'].get('調整手当', 0) +
            e['salary'].get('その他固定', 0) +
            e['salary'].get('その他変動', 0) +
            e['salary'].get('深夜手当', 0) +
            e['salary'].get('準夜手当', 0) +
            e['salary'].get('遅出手当1', 0) +
            e['salary'].get('遅出手当2', 0) +
            e['salary'].get('早出手当', 0) +
            e['salary'].get('回数手当', 0)
            for e in emp_list
        )
        jikangai_total = sum(e['salary'].get('時間外手当', 0) for e in emp_list)

        cat = {
            'category': label,
            'headcount': hc,
            'avg_age': summary.get('avg_age', 0),
            'avg_tenure': summary.get('avg_tenure', 0),
            '支給合計': shikyu,
            '基本給計': kihon_total,
            '手当計': teate_total,
            '時間外計': jikangai_total,
            '一人当たり': round(shikyu / hc) if hc else 0,
        }
        category_summaries.append(cat)

        total_shikyu += shikyu
        total_headcount += hc
        total_age_w += summary.get('avg_age', 0) * hc
        total_tenure_w += summary.get('avg_tenure', 0) * hc

    return {
        'category_summaries': category_summaries,
        'totals': {
            'headcount': total_headcount,
            'avg_age': round(total_age_w / total_headcount, 1) if total_headcount else 0,
            'avg_tenure': round(total_tenure_w / total_headcount, 1) if total_headcount else 0,
            '支給合計': total_shikyu,
            '一人当たり': round(total_shikyu / total_headcount) if total_headcount else 0,
        },
    }


def build_buka_summary(results):
    """部課コード別の集計（全カテゴリ横断）"""
    from collections import defaultdict
    buka_map = defaultdict(list)

    for label, data in results.items():
        if 'error' in data:
            continue
        for e in data.get('employees', []):
            buka_map[e['buka']].append(e)

    buka_summaries = []
    for buka in sorted(buka_map.keys()):
        emps = buka_map[buka]
        hc = len(emps)
        kihon = sum(e['salary'].get('基本給', 0) for e in emps)
        teate = sum(
            e['salary'].get('役職手当', 0) +
            e['salary'].get('調整手当', 0) +
            e['salary'].get('その他固定', 0) +
            e['salary'].get('その他変動', 0) +
            e['salary'].get('深夜手当', 0) +
            e['salary'].get('準夜手当', 0) +
            e['salary'].get('遅出手当1', 0) +
            e['salary'].get('遅出手当2', 0) +
            e['salary'].get('早出手当', 0) +
            e['salary'].get('回数手当', 0)
            for e in emps
        )
        jikangai = sum(e['salary'].get('時間外手当', 0) for e in emps)
        shikyu = sum(e['salary'].get('支給合計', 0) for e in emps)
        ages = [e['age'] for e in emps if e.get('age') is not None]
        tenures = [e['tenure'] for e in emps if e.get('tenure') is not None]

        buka_label = DEPT_NAMES.get(buka.lstrip('0').zfill(3), buka) if buka else buka
        buka_summaries.append({
            'buka': buka_label,
            'headcount': hc,
            'avg_age': round(sum(ages) / len(ages), 1) if ages else 0,
            'avg_tenure': round(sum(tenures) / len(tenures), 1) if tenures else 0,
            '基本給計': kihon,
            '手当計': teate,
            '時間外計': jikangai,
            '支給合計': shikyu,
            '一人当たり': round(shikyu / hc) if hc else 0,
        })

    return buka_summaries


# ---------------------------------------------------------------------------
# Flask ルート
# ---------------------------------------------------------------------------
@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/parse', methods=['POST'])
def parse_pdfs():
    """PDFアップロード解析"""
    categories = {
        'ippan': '一般',
        'ishi': '医師',
        'chiiki': '地域生活',
        'hijoukin': '非常勤',
    }

    results = {}
    for key, label in categories.items():
        if key in request.files:
            f = request.files[key]
            if f.filename:
                try:
                    results[label] = parse_payroll_pdf_upload(f, label)
                except Exception as e:
                    results[label] = {'error': str(e), 'category': label}

    if not results:
        return jsonify({'error': 'ファイルが選択されていません'}), 400

    combined = build_combined_summary(results)
    buka = build_buka_summary(results)
    return jsonify({'categories': results, 'combined': combined, 'buka_summary': buka})


@app.route('/api/parse_folder', methods=['POST'])
def parse_folder():
    """ローカルフォルダのPDFを解析"""
    folder = request.json.get('folder', '')
    folder_path = os.path.join(BASE_DIR, folder)

    if not os.path.isdir(folder_path):
        return jsonify({'error': f'フォルダが見つかりません: {folder}'}), 404

    category_map = {
        '一般.pdf': '一般',
        '医師.pdf': '医師',
        '地域生活.pdf': '地域生活',
        '非常勤.pdf': '非常勤',
    }

    results = {}
    for filename, label in category_map.items():
        filepath = os.path.join(folder_path, filename)
        if os.path.exists(filepath):
            try:
                results[label] = parse_payroll_pdf_path(filepath, label)
            except Exception as e:
                results[label] = {'error': str(e), 'category': label}

    if not results:
        return jsonify({'error': 'PDFが見つかりません'}), 404

    combined = build_combined_summary(results)
    buka = build_buka_summary(results)
    return jsonify({'categories': results, 'combined': combined, 'buka_summary': buka})


@app.route('/api/folders', methods=['GET'])
def list_folders():
    """月フォルダ一覧を返す"""
    folders = []
    for name in sorted(os.listdir(BASE_DIR)):
        path = os.path.join(BASE_DIR, name)
        if os.path.isdir(path) and re.match(r'^\d+月$', name):
            pdfs = [f for f in os.listdir(path) if f.endswith('.pdf')]
            folders.append({'name': name, 'pdf_count': len(pdfs)})
    return jsonify(folders)


def _month_sort_key(name):
    """'1月' → 1, '12月' → 12 でソート用"""
    m = re.match(r'(\d+)月', name)
    return int(m.group(1)) if m else 0


@app.route('/api/parse_all_folders', methods=['POST'])
def parse_all_folders():
    """全月フォルダを一括解析し月別推移データを返す"""
    category_map = {
        '一般.pdf': '一般',
        '医師.pdf': '医師',
        '地域生活.pdf': '地域生活',
        '非常勤.pdf': '非常勤',
    }

    # 月フォルダ検出
    month_folders = []
    for name in os.listdir(BASE_DIR):
        path = os.path.join(BASE_DIR, name)
        if os.path.isdir(path) and re.match(r'^\d+月$', name):
            month_folders.append(name)
    month_folders.sort(key=_month_sort_key)

    if not month_folders:
        return jsonify({'error': '月フォルダが見つかりません'}), 404

    months = {}
    monthly_trend = []
    category_trend = []

    for folder_name in month_folders:
        folder_path = os.path.join(BASE_DIR, folder_name)
        results = {}
        for filename, label in category_map.items():
            filepath = os.path.join(folder_path, filename)
            if os.path.exists(filepath):
                try:
                    results[label] = parse_payroll_pdf_path(filepath, label)
                except Exception as e:
                    results[label] = {'error': str(e), 'category': label}

        if not results:
            continue

        combined = build_combined_summary(results)
        buka = build_buka_summary(results)
        months[folder_name] = {
            'categories': results,
            'combined': combined,
            'buka_summary': buka,
        }

        # 月別推移データ（総合）
        t = combined['totals']
        cat_sums = combined['category_summaries']
        trend_row = {
            'month': folder_name,
            'headcount': t['headcount'],
            '支給合計': t['支給合計'],
            '一人当たり': t['一人当たり'],
            '基本給計': sum(c.get('基本給計', 0) for c in cat_sums),
            '手当計': sum(c.get('手当計', 0) for c in cat_sums),
            '時間外計': sum(c.get('時間外計', 0) for c in cat_sums),
        }
        monthly_trend.append(trend_row)

        # 部門別月別推移データ
        for cs in cat_sums:
            category_trend.append({
                'month': folder_name,
                'category': cs['category'],
                'headcount': cs['headcount'],
                '支給合計': cs['支給合計'],
                '一人当たり': cs['一人当たり'],
            })

    return jsonify({
        'months': months,
        'monthly_trend': monthly_trend,
        'category_trend': category_trend,
    })


# ---------------------------------------------------------------------------
# R7支払いタブ JSON データ提供
# ---------------------------------------------------------------------------
@app.route('/api/sheets_data')
def get_sheets_data():
    data_path = os.path.join(BASE_DIR, 'data', 'r7_sheets.json')
    if not os.path.exists(data_path):
        return jsonify({'error': 'R7支払いデータなし'}), 404
    with open(data_path, encoding='utf-8') as f:
        return jsonify(_json.load(f))


# ---------------------------------------------------------------------------
if __name__ == '__main__':
    import webbrowser
    import threading
    port = 5001
    threading.Timer(1.5, lambda: webbrowser.open(f'http://localhost:{port}')).start()
    app.run(debug=False, host='0.0.0.0', port=port)
