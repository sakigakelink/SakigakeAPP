#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
給与分析 ビジネスロジック（Flask依存なし）
TKC PX2 一人別給与統計表 PDF解析
"""

import os
import re
import json
import tempfile
import pdfplumber

# ---------------------------------------------------------------------------
# パス
# ---------------------------------------------------------------------------
_DIR = os.path.dirname(os.path.abspath(__file__))

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
    '欠勤控除': 12,
    '時間外手当': 14,
    '深夜手当': 15,
    '休日手当': 16,
    '時間外計': 17,
    '通勤費': 19,
    '支給合計': 21,
    '健康保険料': 24,
    '介護保険料': 25,
    '厚生年金': 26,
    '雇用保険料': 27,
    '所得税': 29,
    '住民税': 30,
    '年末控除': 31,
    'その他控除': 33,
    '控除合計': 35,
    '差引支給額': 37,
    '出勤日数': 40,
    '時間外': 42,
}

CATEGORY_MAP = {
    '一般.pdf': '一般',
    '医師.pdf': '医師',
    '地域生活.pdf': '地域生活',
    '非常勤.pdf': '非常勤',
}

UPLOAD_CATEGORIES = {
    'ippan': '一般',
    'ishi': '医師',
    'chiiki': '地域生活',
    'hijoukin': '非常勤',
}


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
    v = parse_number(safe_cell(table, row, col))
    if v == 0:
        v2 = parse_number(safe_cell(table, row, col - 1))
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
    names = []
    for line in text.split('\n'):
        line = line.strip()
        m = re.match(r'^([^\d\s]{1,4})\s+([^\d\s]{1,4})$', line)
        if m:
            names.append(f"{m.group(1)} {m.group(2)}")
        if len(names) >= expected_count:
            break
    return names


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
        if code_clean.strip() and re.match(r'^\d+$', code_clean.strip()):
            cols.append(col_off)
    return cols


def parse_employee_page(table, page_text=''):
    employees = []
    active_cols = detect_employee_columns(table)
    if not active_cols:
        return employees

    names_from_text = extract_names_from_text(page_text, len(active_cols))

    for idx, col_off in enumerate(active_cols):
        name = extract_prefixed_cell(table, NAME_ROW, col_off)
        if not name and idx < len(names_from_text):
            name = names_from_text[idx]
        if not name:
            continue

        code_raw = extract_prefixed_cell(table, CODE_ROW, col_off)
        code_clean = re.sub(r'^[A-Z]', '', code_raw) if code_raw else ''

        dob_raw = extract_prefixed_cell(table, DOB_ROW, col_off)
        hire_raw = extract_prefixed_cell(table, HIRE_ROW, col_off)

        taikei, buka, shain_no, gender = '', '', '', ''
        age, tenure = 0, 0
        if code_clean:
            parts = re.findall(r'\d+', code_clean)
            if len(parts) >= 3:
                taikei = parts[0]
                buka = parts[1].zfill(3)
                shain_no = parts[2]

        def parse_era_date(s):
            if not s:
                return None, None
            m = re.search(r'([SHTRsht昭平令])\s*\.?\s*(\d+)\s*[./年]\s*(\d+)\s*[./月]\s*(\d+)', s)
            if m:
                era, y, mo, d = m.group(1).upper(), int(m.group(2)), int(m.group(3)), int(m.group(4))
                era_map = {'S': 1925, '昭': 1925, 'H': 1988, '平': 1988, 'T': 1911, 'R': 2018, '令': 2018}
                western = era_map.get(era, 2018) + y
                from datetime import date
                try:
                    return date(western, mo, d), era
                except ValueError:
                    pass
            return None, None

        dob_date, _ = parse_era_date(dob_raw)
        hire_date, _ = parse_era_date(hire_raw)

        from datetime import date
        today = date.today()
        if dob_date:
            age = (today - dob_date).days / 365.25
            gender = '女性' if dob_raw and ('2' in dob_raw[:3] or safe_cell(table, DOB_ROW, col_off + 1).strip() == '2') else '男性'
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
            'gender': gender,
            'age': round(age, 1),
            'tenure': round(tenure, 1),
            'salary': salary,
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
        jikangai = sum(e['salary'].get('時間外計', 0) for e in employees)

        category_summaries.append({
            'category': label,
            'headcount': headcount,
            '支給合計': total_pay,
            '一人当たり': round(total_pay / headcount) if headcount else 0,
            '基本給計': kihonkyu,
            '手当計': teate,
            '時間外計': jikangai,
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
                buka_data[buka] = {'buka': buka, 'headcount': 0, '基本給計': 0, '手当計': 0, '時間外計': 0, '支給合計': 0}
            b = buka_data[buka]
            b['headcount'] += 1
            sal = emp.get('salary', {})
            b['基本給計'] += sal.get('基本給', 0)
            b['手当計'] += (
                sal.get('役職手当', 0)
                + sal.get('調整手当', 0)
                + sal.get('その他固定', 0)
                + sal.get('その他変動', 0)
                + sal.get('通勤費', 0)
            )
            b['時間外計'] += sal.get('時間外計', 0)
            b['支給合計'] += sal.get('支給合計', 0)

    buka_list = sorted(buka_data.values(), key=lambda x: -x['支給合計'])
    for b in buka_list:
        b['一人当たり'] = round(b['支給合計'] / b['headcount']) if b['headcount'] else 0
    return buka_list


# ---------------------------------------------------------------------------
# サービス関数（ポータルから呼ばれる）
# ---------------------------------------------------------------------------

def list_folders_data():
    """月フォルダ一覧を返す"""
    folders = []
    for name in sorted(os.listdir(_DIR)):
        path = os.path.join(_DIR, name)
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
                    results[label] = {'error': str(e), 'category': label}
    if not results:
        return None
    combined = build_combined_summary(results)
    buka = build_buka_summary(results)
    return {'categories': results, 'combined': combined, 'buka_summary': buka}


def parse_folder_data(folder_name):
    """指定フォルダのPDFを解析"""
    folder_path = os.path.join(_DIR, folder_name)
    if not os.path.isdir(folder_path):
        return None
    results = {}
    for filename, label in CATEGORY_MAP.items():
        filepath = os.path.join(folder_path, filename)
        if os.path.exists(filepath):
            try:
                results[label] = parse_payroll_pdf_path(filepath, label)
            except Exception as e:
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
    """全月フォルダを一括解析し月別推移データを返す"""
    month_folders = []
    for name in os.listdir(_DIR):
        path = os.path.join(_DIR, name)
        if os.path.isdir(path) and re.match(r'^\d+月$', name):
            month_folders.append(name)
    month_folders.sort(key=_month_sort_key)

    if not month_folders:
        return None

    months = {}
    monthly_trend = []
    category_trend = []

    for folder_name in month_folders:
        folder_path = os.path.join(_DIR, folder_name)
        results = {}
        for filename, label in CATEGORY_MAP.items():
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

    return {
        'months': months,
        'monthly_trend': monthly_trend,
        'category_trend': category_trend,
    }


def get_sheets_json():
    """R7支払いデータを返す"""
    data_path = os.path.join(_DIR, 'data', 'r7_sheets.json')
    if not os.path.exists(data_path):
        return None
    with open(data_path, encoding='utf-8') as f:
        return json.load(f)
