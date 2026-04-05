#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
給与分析 ビジネスロジック（Flask依存なし）
TKC PX2 一人別給与統計表 PDF解析
"""

import os
import re
import json
import logging
import tempfile
from datetime import date
import pdfplumber

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# パス
# ---------------------------------------------------------------------------
_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_DIR)
_DATA_ROOT = os.path.join(_PROJECT_ROOT, 'shared', '給与')
_CACHE_PATH = os.path.join(_DATA_ROOT, 'data', 'salary_cache.json')

# 共通キャッシュユーティリティ（プロジェクトルートから importlib で読み込み）
import importlib.util as _imputil
_cu_spec = _imputil.spec_from_file_location('cache_utils', os.path.join(os.path.dirname(_DIR), 'cache_utils.py'))
_cu = _imputil.module_from_spec(_cu_spec)
_cu_spec.loader.exec_module(_cu)
_load_cache_util, _save_cache_util = _cu.load_cache, _cu.save_cache


# ---------------------------------------------------------------------------
# キャッシュ（元PDFのmtimeと照合し、差分なければ再解析スキップ）
# ---------------------------------------------------------------------------
def _build_source_map():
    """全月フォルダの全PDFの {relative_path: mtime} を構築"""
    sources = {}
    if not os.path.isdir(_DATA_ROOT):
        return sources
    for name in os.listdir(_DATA_ROOT):
        if not os.path.isdir(os.path.join(_DATA_ROOT, name)) or not re.match(r'^\d+月$', name):
            continue
        for f in os.listdir(os.path.join(_DATA_ROOT, name)):
            if f.endswith('.pdf'):
                rel = f'{name}/{f}'
                sources[rel] = os.path.getmtime(os.path.join(_DATA_ROOT, name, f))
    return sources


def ensure_cache():
    """起動時呼び出し: キャッシュが古ければ再生成"""
    parse_all_folders_data()


# ---------------------------------------------------------------------------
# 部課コード → 名称マッピング
# ---------------------------------------------------------------------------
_dept_path = os.path.join(_DIR, 'dept_codes.json')
try:
    with open(_dept_path, encoding='utf-8') as _f:
        DEPT_NAMES = json.load(_f)
except (FileNotFoundError, ValueError):
    DEPT_NAMES = {}

# ---------------------------------------------------------------------------
# PDF テーブル定数
# ---------------------------------------------------------------------------
EMPLOYEE_COL_OFFSETS = [4, 9, 14, 19, 24, 29]
NAME_COL_OFFSETS = [4, 7, 12, 17, 22, 27]

NAME_ROW = 1
CODE_ROW = 2
DOB_ROW = 3
HIRE_ROW = 4

SALARY_ROW_MAP = {
    '基本給': 6,
    '役職手当': 7,
    '調整手当': 8,
    'その他固定': 9,
    'その他変動': 10,
    '基本給パート': 11,
    '欠勤控除': 12,
    '準夜手当': 13,
    '深夜手当': 14,
    '夜手当': 15,
    '明手当': 16,
    '遅出手当': 17,
    '準深手当': 18,
    '時間外手当': 19,
    '回数手当': 20,
    '課税通勤手当': 21,
    '課税支給額': 23,
    '通勤費': 24,
    '非課税当直手当': 25,
    '支給合計': 26,
    '健保介護': 27,
    '健保一般': 28,
    '厚生年金': 30,
    '雇用保険料': 31,
    '社会保険料計': 32,
    '所得税': 34,
    '住民税': 35,
    '控除合計': 46,
    '差引支給額': 49,
}

CATEGORIES = [
    ('ippan', '一般.pdf', '一般'),
    ('ishi', '医師.pdf', '医師'),
    ('chiiki', '地域生活.pdf', '地域生活'),
    ('hijoukin', '非常勤.pdf', '非常勤'),
]
CATEGORY_MAP = {pdf: label for _, pdf, label in CATEGORIES}
UPLOAD_CATEGORIES = {key: label for key, _, label in CATEGORIES}


# ---------------------------------------------------------------------------
# PDF解析ヘルパー
# ---------------------------------------------------------------------------

def parse_number(s):
    if not s or not isinstance(s, str):
        return 0
    s = s.strip().replace(',', '').replace('△', '-').replace('▲', '-')
    s = re.sub(r'[^\d.\-]', '', s)
    try:
        return int(float(s)) if s else 0
    except ValueError:
        return 0


def safe_cell(table, row, col):
    try:
        return (table[row][col] or '').strip()
    except (IndexError, TypeError):
        return ''


def parse_value(table, row, col):
    raw = safe_cell(table, row, col)
    prev = safe_cell(table, row, col - 1) if col > 0 else ''
    # 桁あふれで前列に先頭桁が入るケースを結合して解析
    if prev and prev.strip().isdigit() and raw and raw.startswith(','):
        combined = prev.strip() + raw
        return parse_number(combined)
    v = parse_number(raw)
    if v == 0 and prev:
        v2 = parse_number(prev)
        if v2 != 0:
            return v2
    return v


def is_summary_page(table):
    for row in range(min(3, len(table))):
        for col in range(min(5, len(table[row]) if row < len(table) else 0)):
            cell = safe_cell(table, row, col)
            if '全社合計' in cell or '合計' in cell:
                return True
    return False


def extract_names_from_text(text, expected_count):
    """ページテキストの「氏 名 ...」行から職員名を抽出する"""
    for line in text.split('\n'):
        line = line.strip()
        if not re.match(r'^氏\s*名\s+', line):
            continue
        # 「氏 名」プレフィックスを除去
        rest = re.sub(r'^氏\s*名\s+', '', line)
        # 非数字・非空白の塊（姓/名）を抽出し、2つずつペアにする
        parts = re.findall(r'[^\d\s]+', rest)
        names = []
        i = 0
        while i < len(parts) - 1 and len(names) < expected_count:
            names.append(f"{parts[i]}\u3000{parts[i+1]}")
            i += 2
        return names
    return []


def extract_prefixed_cell(table, row, col_offset):
    raw = safe_cell(table, row, col_offset)
    if raw and re.match(r'^[A-Z0-9]', raw):
        return raw[1:].strip() if len(raw) > 1 else ''
    return raw


def detect_employee_columns(table):
    if len(table) <= CODE_ROW:
        return []
    cols = []
    for col_off in EMPLOYEE_COL_OFFSETS:
        code_val = safe_cell(table, CODE_ROW, col_off)
        code_clean = re.sub(r'^[A-Z]', '', code_val)
        if code_clean.strip() and re.match(r'^[\d\s\-]+', code_clean.strip()):
            cols.append(col_off)
    return cols


def parse_era_date(s):
    """和暦文字列をdateオブジェクトに変換。(date, era_char) or (None, None)を返す"""
    if not s:
        return None, None
    m = re.search(r'(昭和|平成|令和|大正|[SHTRsht昭平令])\s*\.?\s*(\d+)\s*[./年]\s*(\d+)\s*[./月]\s*(\d+)', s)
    if m:
        era_raw = m.group(1)
        era = era_raw[0].upper() if len(era_raw) == 1 else era_raw[0]
        y, mo, d = int(m.group(2)), int(m.group(3)), int(m.group(4))
        era_map = {'S': 1925, '昭': 1925, 'H': 1988, '平': 1988, 'T': 1911, 'R': 2018, '令': 2018}
        western = era_map.get(era, 2018) + y
        try:
            return date(western, mo, d), era
        except ValueError:
            pass
    return None, None


def parse_employee_page(table, page_text=''):
    employees = []
    active_cols = detect_employee_columns(table)
    if not active_cols:
        return employees

    names_from_text = extract_names_from_text(page_text, len(active_cols))

    for idx, col_off in enumerate(active_cols):
        # テキスト抽出名を優先（テーブル抽出は先頭文字欠落の問題あり）
        name = names_from_text[idx] if idx < len(names_from_text) else None
        if not name:
            name_col = NAME_COL_OFFSETS[idx] if idx < len(NAME_COL_OFFSETS) else col_off
            name = extract_prefixed_cell(table, NAME_ROW, name_col)
        if not name:
            continue

        code_raw = extract_prefixed_cell(table, CODE_ROW, col_off)
        code_clean = re.sub(r'^[A-Z]', '', code_raw) if code_raw else ''

        # 生年月日・入職日は元号が前列(col_off-1)に分離している
        dob_era = safe_cell(table, DOB_ROW, col_off - 1)
        dob_body = safe_cell(table, DOB_ROW, col_off)
        dob_raw = (dob_era + dob_body) if dob_era else dob_body
        hire_era = safe_cell(table, HIRE_ROW, col_off - 1)
        hire_body = safe_cell(table, HIRE_ROW, col_off)
        hire_raw = (hire_era + hire_body) if hire_era else hire_body

        taikei, buka, shain_no = '', '', ''
        age, tenure = 0, 0
        if code_clean:
            parts = re.findall(r'\d+', code_clean)
            if len(parts) >= 3:
                taikei = parts[0]
                buka = parts[1].zfill(3)
                shain_no = parts[2]

        # 有効な職員コードがない場合はスキップ（合計行等）
        if not shain_no:
            continue

        dob_date, _ = parse_era_date(dob_raw)
        hire_date, _ = parse_era_date(hire_raw)

        today = date.today()
        if dob_date:
            age = (today - dob_date).days / 365.25
        if hire_date:
            tenure = (today - hire_date).days / 365.25

        salary = {}
        for item_name, row_idx in SALARY_ROW_MAP.items():
            salary[item_name] = parse_value(table, row_idx, col_off)

        buka_name = DEPT_NAMES.get(buka, buka)
        employees.append({
            'name': name,
            'taikei': taikei,
            'buka': buka_name,
            'buka_code': buka,
            'shain_no': shain_no,
            'age': round(age, 1),
            'tenure': round(tenure, 1),
            'salary': salary,
            'id': taikei.zfill(3) + buka + shain_no.zfill(6),
        })

    return employees


def find_summary_data_col(table):
    for col in [4, 3, 5, 2]:
        for test_row in [21, 35, 37]:
            val = parse_number(safe_cell(table, test_row, col))
            if val != 0:
                return col
    return 4


def parse_summary_page(table):
    data_col = find_summary_data_col(table)
    headcount = parse_number(safe_cell(table, 40, data_col))
    avg_age = 0
    avg_tenure = 0

    avg_raw = safe_cell(table, 41, data_col)
    m = re.search(r'(\d+)[歳年]\s*(\d+)', avg_raw)
    if m:
        avg_age = int(m.group(1)) + int(m.group(2)) / 12
    else:
        avg_age = parse_number(avg_raw)

    tenure_raw = safe_cell(table, 42, data_col)
    m2 = re.search(r'(\d+)[年]\s*(\d+)', tenure_raw)
    if m2:
        avg_tenure = int(m2.group(1)) + int(m2.group(2)) / 12
    else:
        avg_tenure = parse_number(tenure_raw)

    summary_salary = {}
    for item_name, row_idx in SALARY_ROW_MAP.items():
        summary_salary[item_name] = parse_value(table, row_idx, data_col)

    return {
        'headcount': headcount,
        'avg_age': round(avg_age, 1),
        'avg_tenure': round(avg_tenure, 1),
        'total_pay': summary_salary.get('支給合計', 0),
        'salary': summary_salary,
    }


def parse_payroll_pdf_path(filepath, category):
    result = {'category': category, 'period': '', 'employees': [], 'summary': None}
    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables()
            if not tables:
                continue
            table = tables[0]
            if is_summary_page(table):
                result['summary'] = parse_summary_page(table)
            else:
                page_text = page.extract_text() or ''
                emps = parse_employee_page(table, page_text)
                result['employees'].extend(emps)
                if not result['period']:
                    for row in range(min(3, len(table))):
                        for col in range(min(5, len(table[row]) if row < len(table) else 0)):
                            cell = safe_cell(table, row, col)
                            m = re.search(r'(\d{4})年\s*(\d+)月', cell)
                            if m:
                                result['period'] = f"{m.group(1)}年{m.group(2)}月"
                                break

    if not result['summary'] and result['employees']:
        headcount = len(result['employees'])
        total_pay = sum(e['salary'].get('支給合計', 0) for e in result['employees'])
        ages = [e['age'] for e in result['employees'] if e['age'] > 0]
        tenures = [e['tenure'] for e in result['employees'] if e['tenure'] > 0]
        result['summary'] = {
            'headcount': headcount,
            'avg_age': round(sum(ages) / len(ages), 1) if ages else 0,
            'avg_tenure': round(sum(tenures) / len(tenures), 1) if tenures else 0,
            'total_pay': total_pay,
        }
    return result


def parse_payroll_pdf_upload(file_storage, category):
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
        file_storage.save(tmp.name)
        try:
            return parse_payroll_pdf_path(tmp.name, category)
        finally:
            os.unlink(tmp.name)


def build_combined_summary(results):
    category_summaries = []
    for label, data in results.items():
        if 'error' in data:
            continue
        summary = data.get('summary') or {}
        employees = data.get('employees', [])
        headcount = summary.get('headcount', 0) or len(employees)
        total_pay = summary.get('total_pay', 0) or sum(e['salary'].get('支給合計', 0) for e in employees)
        kihonkyu = sum(e['salary'].get('基本給', 0) for e in employees)
        teate = sum(
            e['salary'].get('役職手当', 0)
            + e['salary'].get('調整手当', 0)
            + e['salary'].get('その他固定', 0)
            + e['salary'].get('その他変動', 0)
            + e['salary'].get('通勤費', 0)
            for e in employees
        )
        jikangai = sum(e['salary'].get('時間外手当', 0) for e in employees)
        tsuukin = sum(e['salary'].get('通勤費', 0) for e in employees)

        category_summaries.append({
            'category': label,
            'headcount': headcount,
            '支給合計': total_pay,
            '一人当たり': round(total_pay / headcount) if headcount else 0,
            '基本給計': kihonkyu,
            '手当計': teate,
            '時間外計': jikangai,
            '通勤費計': tsuukin,
            'avg_age': summary.get('avg_age', 0),
            'avg_tenure': summary.get('avg_tenure', 0),
        })

    total_headcount = sum(c['headcount'] for c in category_summaries)
    total_pay = sum(c['支給合計'] for c in category_summaries)

    return {
        'category_summaries': category_summaries,
        'totals': {
            'headcount': total_headcount,
            '支給合計': total_pay,
            '一人当たり': round(total_pay / total_headcount) if total_headcount else 0,
            'avg_age': round(sum(c['avg_age'] * c['headcount'] for c in category_summaries) / total_headcount, 1) if total_headcount else 0,
            'avg_tenure': round(sum(c['avg_tenure'] * c['headcount'] for c in category_summaries) / total_headcount, 1) if total_headcount else 0,
        },
    }


def build_buka_summary(results):
    buka_data = {}
    for label, data in results.items():
        if 'error' in data:
            continue
        for emp in data.get('employees', []):
            buka = emp.get('buka', '不明')
            if buka not in buka_data:
                buka_data[buka] = {'buka': buka, 'headcount': 0, '基本給計': 0, '手当計': 0, '時間外計': 0, '通勤費計': 0, '支給合計': 0, '_ages': [], '_tenures': []}
            b = buka_data[buka]
            b['headcount'] += 1
            if emp.get('age', 0) > 0:
                b['_ages'].append(emp['age'])
            if emp.get('tenure', 0) > 0:
                b['_tenures'].append(emp['tenure'])
            sal = emp.get('salary', {})
            b['基本給計'] += sal.get('基本給', 0)
            b['手当計'] += (
                sal.get('役職手当', 0)
                + sal.get('調整手当', 0)
                + sal.get('その他固定', 0)
                + sal.get('その他変動', 0)
                + sal.get('通勤費', 0)
            )
            b['時間外計'] += sal.get('時間外手当', 0)
            b['通勤費計'] += sal.get('通勤費', 0)
            b['支給合計'] += sal.get('支給合計', 0)

    buka_list = sorted(buka_data.values(), key=lambda x: -x['支給合計'])
    for b in buka_list:
        b['一人当たり'] = round(b['支給合計'] / b['headcount']) if b['headcount'] else 0
        b['avg_age'] = round(sum(b['_ages']) / len(b['_ages']), 1) if b['_ages'] else 0
        b['avg_tenure'] = round(sum(b['_tenures']) / len(b['_tenures']), 1) if b['_tenures'] else 0
        del b['_ages'], b['_tenures']
    return buka_list


# ---------------------------------------------------------------------------
# サービス関数（ポータルから呼ばれる）
# ---------------------------------------------------------------------------

def list_folders_data():
    """月フォルダ一覧を返す"""
    folders = []
    if not os.path.isdir(_DATA_ROOT):
        return folders
    for name in sorted(os.listdir(_DATA_ROOT)):
        path = os.path.join(_DATA_ROOT, name)
        if os.path.isdir(path) and re.match(r'^\d+月$', name):
            pdfs = [f for f in os.listdir(path) if f.endswith('.pdf')]
            folders.append({'name': name, 'pdf_count': len(pdfs)})
    return folders


def parse_uploaded_files(files_dict):
    """アップロードされたPDFを解析。files_dict: {key: file_storage}"""
    results = {}
    for key, label in UPLOAD_CATEGORIES.items():
        if key in files_dict:
            f = files_dict[key]
            if f.filename:
                try:
                    results[label] = parse_payroll_pdf_upload(f, label)
                except Exception as e:
                    logger.exception("PDF解析エラー [%s]: %s", label, e)
                    results[label] = {'error': str(e), 'category': label}
    if not results:
        return None
    combined = build_combined_summary(results)
    buka = build_buka_summary(results)
    return {'categories': results, 'combined': combined, 'buka_summary': buka}


def parse_folder_data(folder_name):
    """指定フォルダのPDFを解析"""
    if not re.match(r'^\d+月$', folder_name):
        logger.warning("不正なフォルダ名: %s", folder_name)
        return None
    folder_path = os.path.join(_DATA_ROOT, folder_name)
    if not os.path.isdir(folder_path):
        return None
    results = {}
    for filename, label in CATEGORY_MAP.items():
        filepath = os.path.join(folder_path, filename)
        if os.path.exists(filepath):
            try:
                results[label] = parse_payroll_pdf_path(filepath, label)
            except Exception as e:
                logger.exception("PDF解析エラー [%s/%s]: %s", folder_name, label, e)
                results[label] = {'error': str(e), 'category': label}
    if not results:
        return None
    combined = build_combined_summary(results)
    buka = build_buka_summary(results)
    return {'categories': results, 'combined': combined, 'buka_summary': buka}


def _month_sort_key(name):
    m = re.match(r'(\d+)月', name)
    return int(m.group(1)) if m else 0


def parse_all_folders_data():
    """全月フォルダを一括解析し月別推移データを返す（キャッシュ優先）"""
    cached = _load_cache_util(_CACHE_PATH, _build_source_map())
    if cached is not None:
        logger.info("給与キャッシュ有効 — PDF解析スキップ")
        return cached

    month_folders = []
    if not os.path.isdir(_DATA_ROOT):
        return None
    for name in os.listdir(_DATA_ROOT):
        path = os.path.join(_DATA_ROOT, name)
        if os.path.isdir(path) and re.match(r'^\d+月$', name):
            month_folders.append(name)
    month_folders.sort(key=_month_sort_key)

    if not month_folders:
        return None

    months = {}
    monthly_trend = []
    category_trend = []

    for folder_name in month_folders:
        folder_path = os.path.join(_DATA_ROOT, folder_name)
        results = {}
        for filename, label in CATEGORY_MAP.items():
            filepath = os.path.join(folder_path, filename)
            if os.path.exists(filepath):
                try:
                    results[label] = parse_payroll_pdf_path(filepath, label)
                except Exception as e:
                    logger.exception("PDF解析エラー [%s/%s]: %s", folder_name, label, e)
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

        for cs in cat_sums:
            category_trend.append({
                'month': folder_name,
                'category': cs['category'],
                'headcount': cs['headcount'],
                '支給合計': cs['支給合計'],
                '一人当たり': cs['一人当たり'],
            })

    data = {
        'months': months,
        'monthly_trend': monthly_trend,
        'category_trend': category_trend,
    }
    _save_cache_util(_CACHE_PATH, data, _build_source_map())
    logger.info("給与キャッシュ生成完了")
    return data


def get_sheets_json():
    """R7支払いデータを返す"""
    data_path = os.path.join(_DATA_ROOT, 'data', 'r7_sheets.json')
    if not os.path.exists(data_path):
        return None
    with open(data_path, encoding='utf-8') as f:
        return json.load(f)
