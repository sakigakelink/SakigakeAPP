#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
損益計算表 重点項目ビューア
TKC月次合算試算表PDFから重点項目を抽出し見やすく表示
"""

import os
import re
import json
import calendar
from datetime import datetime
from flask import Flask, render_template, request, jsonify
import pdfplumber

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

YAKUIN_TAISHOKUKIN_MONTHLY = 248700  # 役員退職金 月額積立額

REVENUE_DISPLAY_ITEMS = [
    {'type': 'single', 'code': None, 'name': '入院診療収益計', 'label': '入院診療収益計'},
    {'type': 'single', 'code': None, 'name': '外来診療収益計', 'label': '外来診療収益計'},
    {'type': 'single', 'code': '4271', 'name': '売店・弁当', 'label': '売店・弁当・加工品・手数'},
    {'type': 'single', 'code': '4279', 'name': '文書収入', 'label': '文書収入'},
    {'type': 'single', 'code': '4191', 'name': '査定減', 'label': '保険等査定減'},
    {'type': 'single', 'code': None, 'name': '医業収益合計', 'label': '医業収益合計'},
]

EXPENSE_DISPLAY_ITEMS = [
    {'type': 'single', 'code': '5211', 'name': None, 'label': '医薬品費'},
    {'type': 'single', 'code': '5212', 'name': None, 'label': '診療材料費'},
    {'type': 'single', 'code': '5214', 'name': None, 'label': '給食用材料費'},
    {'type': 'single', 'code': '5221', 'name': None, 'label': '売店仕入高'},
    {'type': 'single', 'code': None, 'name': '材料費計', 'label': '材料費計'},
    {'type': 'single', 'code': '5411', 'name': None, 'label': '医師給与'},
    {'type': 'calc', 'formula': '常勤職員給与小計-5411+5435', 'label': '一般職員給与'},
    {'type': 'single', 'code': None, 'name': '非常勤職員給与小計', 'label': '非常勤職員給与小計'},
    {'type': 'single', 'code': '5437', 'name': None, 'label': '法定福利費'},
    {'type': 'calc', 'formula': '給与費計-5431-5436', 'label': '給与費計'},
    {'type': 'single', 'code': None, 'name': '委託費計', 'label': '委託費計'},
    {'type': 'single', 'code': '6114', 'name': None, 'label': '修繕費'},
    {'type': 'single', 'code': None, 'name': '設備関係費計', 'label': '設備関係費計'},
    {'type': 'single', 'code': '6317', 'name': None, 'label': '消耗品費'},
    {'type': 'single', 'code': '6335', 'name': None, 'label': '採用関連費'},
    {'type': 'keihi_kei', 'label': '経費計'},
    {'type': 'igyou_hiyo', 'label': '医業（事業）費用合計'},
]

PROFIT_DISPLAY_ITEMS = [
    {'type': 'igyou_rieki', 'label': '医業（事業）利益'},
    {'type': 'keiri2_plus_chutaikyo', 'name': '経常利益', 'label': 'たいようの丘経常利益'},
    {'type': 'keijo_houjin', 'label': '経常利益（法人）'},
    {'type': 'taishokukin', 'formula': '5436', 'fixed_add': YAKUIN_TAISHOKUKIN_MONTHLY, 'label': '退職金'},
]

OUTPUT_DISPLAY_ITEMS = [
    {'type': 'single', 'code': None, 'name': '医業収益合計', 'label': '医業収益'},
    {'type': 'daily_revenue', 'label': '一日当たり収入'},
    {'type': 'manual_input', 'label': '平均入院患者数'},
    {'type': 'calc_fixed', 'formula': '医業（事業）費用合計-CHUTAIKYO-5436', 'fixed_add': -YAKUIN_TAISHOKUKIN_MONTHLY, 'label': '医業費用'},
    {'type': 'single', 'code': None, 'name': '材料費計', 'label': '材料費'},
    {'type': 'calc', 'formula': '給与費計-5431-5436', 'label': '人件費'},
    {'type': 'calc', 'formula': '常勤職員給与小計+5435', 'label': '　常勤・賞与'},
    {'type': 'single', 'code': None, 'name': '非常勤職員給与小計', 'label': '　非常勤'},
    {'type': 'single', 'code': '5437', 'name': None, 'label': '　法定福利'},
    {'type': 'single', 'code': None, 'name': '委託費計', 'label': '委託費'},
    {'type': 'single', 'code': None, 'name': '設備関係費計', 'label': '設備費'},
    {'type': 'single', 'code': '6114', 'name': None, 'label': '　修繕費'},
    {'type': 'keihi_kei', 'label': '経費'},
    {'type': 'single', 'code': '6335', 'name': None, 'label': '　採用費'},
    {'type': 'igyou_rieki', 'label': '医業利益'},
    {'type': 'keiri2_plus_chutaikyo', 'name': '経常利益', 'label': 'たいようの丘経常利益'},
    {'type': 'keijo_houjin', 'label': '経常利益（法人）'},
    {'type': 'taishokukin', 'formula': '5436', 'fixed_add': YAKUIN_TAISHOKUKIN_MONTHLY, 'label': '退職金'},
]


def parse_chutaikyo_txt(txt_path):
    debit_data, credit_data, debug_lines = {}, {}, []
    content = None
    for enc in ['shift_jis', 'cp932', 'utf-8']:
        try:
            with open(txt_path, 'r', encoding=enc) as f:
                content = f.read()
            break
        except (UnicodeDecodeError, LookupError):
            continue
    if not content:
        return {'debit': debit_data, 'credit': credit_data, 'debug': debug_lines}
    for line in content.split('\n'):
        if '中退共' in line or '退職金共済' in line or '退職金掛金' in line:
            parts = line.split('\t')
            if len(parts) >= 15:
                date_str = parts[2].strip() if len(parts) > 2 else ''
                month_match = re.search(r'\*?\s*(\d+)\.', date_str)
                if month_match:
                    month_key = f"{int(month_match.group(1))}月"
                    debit_str = parts[12].strip().replace(',', '') if len(parts) > 12 else '0'
                    credit_str = parts[13].strip().replace(',', '') if len(parts) > 13 else '0'
                    try:
                        debit = float(debit_str) if debit_str else 0
                        credit = float(credit_str) if credit_str else 0
                        debit_data[month_key] = debit_data.get(month_key, 0) + debit
                        credit_data[month_key] = credit_data.get(month_key, 0) + credit
                        debug_lines.append({'month': month_key, 'date_str': date_str, 'debit': debit, 'credit': credit})
                    except ValueError:
                        pass
    return {'debit': debit_data, 'credit': credit_data, 'debug': debug_lines}


def parse_tkc_pdf(pdf_path):
    result = {'filename': os.path.basename(pdf_path), 'organization': '', 'period': '', 'period_month': 0, 'period_year': 0, 'keiri_kubun': '', 'accounts': [], 'keiri2_accounts': [], 'keiri1_keijo': None}
    def parse_number(s):
        try:
            return float(s.replace(',', '').replace(' ', ''))
        except (ValueError, AttributeError):
            return 0
    with pdfplumber.open(pdf_path) as pdf:
        all_lines = []
        for page in pdf.pages:
            text = page.extract_text()
            if text:
                all_lines.extend(text.split('\n'))
        full_text = '\n'.join(all_lines)
        period_match = re.search(r'令和\s*(\d+)年\s*(\d+)月\s*(\d+)日[〜～]令和\s*(\d+)年\s*(\d+)月\s*(\d+)日', full_text)
        if period_match:
            result['period'] = f"{2018+int(period_match.group(1))}年{int(period_match.group(2))}月〜{2018+int(period_match.group(4))}年{int(period_match.group(5))}月"
            result['period_month'] = int(period_match.group(5))
            result['period_year'] = 2018 + int(period_match.group(4))
        keiri_match = re.search(r'経理区分[：:]\s*(\d+)\s*(\S+)', full_text)
        if keiri_match:
            result['keiri_kubun'] = f"{keiri_match.group(1)} {keiri_match.group(2)}"
        org_match = re.search(r'医療法人\s*(\S+)', full_text)
        if org_match:
            result['organization'] = f"医療法人 {org_match.group(1)}"
        current_keiri, keiri1_keijo_found, keiri2_keijo_found = '01', False, False
        for i, line in enumerate(all_lines):
            keiri_change = re.search(r'経理区分[：:]\s*(\d+)\s*(\S*)', line)
            if keiri_change:
                current_keiri = keiri_change.group(1)
            match = re.match(r'^(\d{4})\s+(.+?)\s+([\d,.-]+)\s+([\d,.-]+)\s+([\d,.-]+)\s+([\d,.-]+)\s+([\d,.-]+)', line)
            if match:
                code, name = match.group(1), match.group(2).strip()
                prev_month_balance, debit, credit = parse_number(match.group(3)), parse_number(match.group(4)), parse_number(match.group(5))
                current_balance, prev_year_balance = parse_number(match.group(6)), parse_number(match.group(7))
                monthly_amount = credit - debit if code.startswith('4') or code.startswith('71') else debit - credit
                account = {'code': code, 'name': name, 'prev_month_balance': prev_month_balance, 'debit': debit, 'credit': credit, 'current_balance': current_balance, 'prev_year_balance': prev_year_balance, 'monthly_amount': monthly_amount, 'is_subtotal': False}
                if current_keiri in ['01', '1']:
                    result['accounts'].append(account)
                elif current_keiri == '2':
                    result['keiri2_accounts'].append(account)
                continue
            subtotal_match = re.search(r'([\u4e00-\u9fa5（）\uff08\uff09]+[計合]+)\s+([\d,.-]+)\s+([\d,.-]+)\s+([\d,.-]+)\s+([\d,.-]+)\s+([\d,.-]+)', line)
            if subtotal_match and not re.match(r'^\d{4}', line):
                name = subtotal_match.group(1).strip()
                prev_month_balance, debit, credit = parse_number(subtotal_match.group(2)), parse_number(subtotal_match.group(3)), parse_number(subtotal_match.group(4))
                current_balance, prev_year_balance = parse_number(subtotal_match.group(5)), parse_number(subtotal_match.group(6))
                is_revenue = '収益' in name or (('医業' in name or '事業' in name) and '費用' not in name)
                monthly_amount = credit - debit if is_revenue else debit - credit
                account = {'code': 'SUBTOTAL', 'name': name, 'prev_month_balance': prev_month_balance, 'debit': debit, 'credit': credit, 'current_balance': current_balance, 'prev_year_balance': prev_year_balance, 'monthly_amount': monthly_amount, 'is_subtotal': True, 'is_revenue': is_revenue}
                if current_keiri in ['01', '1']:
                    result['accounts'].append(account)
                elif current_keiri == '2':
                    result['keiri2_accounts'].append(account)
                continue
            if current_keiri in ['01', '1'] and not keiri1_keijo_found:
                next_line = all_lines[i + 1] if i + 1 < len(all_lines) else ''
                if re.match(r'^8111\s', next_line):
                    keijo_match = re.search(r'(-?[\d,]+)\s+([-]?[\d,]+)\s+([-]?[\d,]+)\s+([-]?[\d,]+)\s+([-]?[\d,]+)\s*(?:[\d.]+\s*\*?)?\s*$', line)
                    if keijo_match:
                        val1, val2, val3, val4, val5 = [parse_number(keijo_match.group(j)) for j in range(1, 6)]
                        result['keiri1_keijo'] = {'code': 'KEIJO', 'name': '経常利益', 'prev_month_balance': val1, 'debit': val2, 'credit': val3, 'current_balance': val4, 'prev_year_balance': val5, 'monthly_amount': val3 - val2}
                        keiri1_keijo_found = True
            if current_keiri == '2' and not keiri2_keijo_found:
                next_line = all_lines[i + 1] if i + 1 < len(all_lines) else ''
                if re.match(r'^8111\s', next_line):
                    keijo_match = re.search(r'(-?[\d,]+)\s+([-]?[\d,]+)\s+([-]?[\d,]+)\s+([-]?[\d,]+)\s+([-]?[\d,]+)\s*(?:[\d.]+\s*\*?)?\s*$', line)
                    if keijo_match:
                        val1, val2, val3, val4, val5 = [parse_number(keijo_match.group(j)) for j in range(1, 6)]
                        result['keiri2_accounts'].append({'code': 'KEIJO', 'name': '経常利益', 'prev_month_balance': val1, 'debit': val2, 'credit': val3, 'current_balance': val4, 'prev_year_balance': val5, 'monthly_amount': val3 - val2, 'is_subtotal': True, 'is_revenue': False})
                        keiri2_keijo_found = True
    return result


def _make_month_key(year, month):
    """例: (2025, 4) → "25/4月" """
    return f"{str(year)[2:]}/{month}月" if year else f"{month}月"


def parse_month_from_filename(fname):
    """ファイル名 YYMM.pdf から (西暦year, month) を返す。例: 0704.pdf → (2025, 4)"""
    base = os.path.splitext(fname)[0]
    m = re.match(r'^(\d{2})(\d{2})$', base)
    if m:
        reiwa, month = int(m.group(1)), int(m.group(2))
        if 1 <= reiwa <= 99 and 1 <= month <= 12:
            return 2018 + reiwa, month
    return None, None


def merge_all_monthly_data(pdf_results, chutaikyo_data=None):
    sorted_results = sorted(pdf_results, key=lambda x: (x.get('period_year', 0), x.get('period_month', 0)))
    months, all_accounts, keiri2_accounts = [], {}, {}
    month_years = {}
    for result in sorted_results:
        year = result.get('period_year', 0)
        month = result.get('period_month', 0)
        month_key = _make_month_key(year, month)
        if month_key not in months and month:
            months.append(month_key)
        if month and year:
            month_years[month_key] = year
        for acc in result.get('accounts', []):
            key = f"{acc['code']}_{acc['name']}"
            if key not in all_accounts:
                all_accounts[key] = {'code': acc['code'], 'name': acc['name'], 'is_subtotal': acc.get('is_subtotal', False), 'is_revenue': acc.get('is_revenue', acc['code'].startswith('4') if acc['code'] != 'SUBTOTAL' else False), 'monthly_data': {}, 'current_balance': 0, 'prev_year_balance': 0}
            all_accounts[key]['monthly_data'][month_key] = acc.get('monthly_amount', 0)
            all_accounts[key]['current_balance'] = acc.get('current_balance', 0)
            all_accounts[key]['prev_year_balance'] = acc.get('prev_year_balance', 0)
        for acc in result.get('keiri2_accounts', []):
            key = f"KEIRI2_{acc['code']}_{acc['name']}"
            if key not in keiri2_accounts:
                keiri2_accounts[key] = {'code': acc['code'], 'name': acc['name'], 'is_subtotal': acc.get('is_subtotal', False), 'is_revenue': acc.get('is_revenue', False), 'monthly_data': {}, 'current_balance': 0, 'prev_year_balance': 0}
            keiri2_accounts[key]['monthly_data'][month_key] = acc.get('monthly_amount', 0)
            keiri2_accounts[key]['current_balance'] = acc.get('current_balance', 0)
            keiri2_accounts[key]['prev_year_balance'] = acc.get('prev_year_balance', 0)
    keiri1_keijo_data = {}
    for result in sorted_results:
        month_key = _make_month_key(result.get('period_year', 0), result.get('period_month', 0))
        if result.get('keiri1_keijo'):
            keiri1_keijo_data[month_key] = result['keiri1_keijo'].get('monthly_amount', 0)
    txt_debit_data = chutaikyo_data.get('debit', {}) if chutaikyo_data else {}
    txt_credit_data = chutaikyo_data.get('credit', {}) if chutaikyo_data else {}
    if txt_debit_data:
        all_accounts['CHUTAIKYO_中退共'] = {'code': 'CHUTAIKYO', 'name': '中退共', 'is_subtotal': False, 'is_revenue': False, 'monthly_data': txt_debit_data.copy(), 'current_balance': 0, 'prev_year_balance': 0}
    return {'months': months, 'accounts': list(all_accounts.values()), 'txt_debit_data': txt_debit_data, 'txt_credit_data': txt_credit_data, 'keiri1_keijo_data': keiri1_keijo_data, 'keiri2_accounts': list(keiri2_accounts.values()), 'organization': sorted_results[0].get('organization', '') if sorted_results else '', 'keiri_kubun': sorted_results[0].get('keiri_kubun', '') if sorted_results else '', 'chutaikyo_data': chutaikyo_data or {}, 'month_years': month_years}


def find_account(accounts, code=None, name=None):
    for acc in accounts:
        if code and acc['code'] == code:
            return acc
        if name and acc.get('name', '') == name:
            return acc
    return None


def calculate_formula(accounts, formula, months):
    parts = re.split(r'([+-])', formula)
    result_monthly = {m: 0 for m in months}
    operation = '+'
    for part in parts:
        part = part.strip()
        if part == '+':
            operation = '+'
        elif part == '-':
            operation = '-'
        elif part:
            acc = find_account(accounts, code=part) if re.match(r'^\d{4}$', part) else (find_account(accounts, code='CHUTAIKYO') if part == 'CHUTAIKYO' else find_account(accounts, name=part))
            if acc:
                for m in months:
                    val = acc.get('monthly_data', {}).get(m, 0)
                    result_monthly[m] = result_monthly[m] + val if operation == '+' else result_monthly[m] - val
    return result_monthly


def create_display_data(all_data, display_items):
    months, accounts = all_data['months'], all_data['accounts']
    display_accounts = []
    for item in display_items:
        if item['type'] == 'single':
            found = find_account(accounts, code=item.get('code'), name=item.get('name'))
            if found:
                display_accounts.append({'code': found['code'] if found['code'] != 'SUBTOTAL' else '', 'name': item['label'], 'monthly_data': found['monthly_data'], 'is_subtotal': found.get('is_subtotal', False)})
            else:
                display_accounts.append({'code': item.get('code', ''), 'name': item['label'], 'monthly_data': {m: 0 for m in months}, 'is_subtotal': False})
        elif item['type'] == 'calc':
            display_accounts.append({'code': '', 'name': item['label'], 'monthly_data': calculate_formula(accounts, item['formula'], months), 'is_subtotal': False, 'is_calculated': True})
        elif item['type'] == 'calc_fixed':
            monthly_data = calculate_formula(accounts, item['formula'], months)
            for m in months:
                monthly_data[m] = monthly_data.get(m, 0) + item.get('fixed_add', 0)
            display_accounts.append({'code': '', 'name': item['label'], 'monthly_data': monthly_data, 'is_subtotal': False, 'is_calculated': True})
        elif item['type'] == 'daily_revenue':
            found = find_account(accounts, name='医業収益合計')
            month_years = all_data.get('month_years', {})
            monthly_data = {}
            for m in months:
                month_num = int(m.replace('月', ''))
                year = month_years.get(m, datetime.now().year)
                days = calendar.monthrange(year, month_num)[1]
                val = found.get('monthly_data', {}).get(m, 0) if found else 0
                monthly_data[m] = round(val / days) if days > 0 else 0
            display_accounts.append({'code': '', 'name': item['label'], 'monthly_data': monthly_data, 'is_subtotal': False, 'is_calculated': True})
        elif item['type'] == 'manual_input':
            display_accounts.append({'code': '', 'name': item['label'], 'monthly_data': {m: 0 for m in months}, 'is_subtotal': False, 'is_manual': True})
        elif item['type'] == 'keiri2_plus_chutaikyo':
            keiri2_accounts = all_data.get('keiri2_accounts', [])
            found = find_account(keiri2_accounts, code=item.get('code'), name=item.get('name'))
            found_5436 = find_account(keiri2_accounts, code='5436')
            txt_credit = all_data.get('txt_credit_data', {})
            monthly_data = {m: (found.get('monthly_data', {}).get(m, 0) if found else 0) + (found_5436.get('monthly_data', {}).get(m, 0) if found_5436 else 0) + txt_credit.get(m, 0) for m in months}
            display_accounts.append({'code': '', 'name': item['label'], 'monthly_data': monthly_data, 'is_subtotal': False, 'is_keiri2': True})
        elif item['type'] == 'taishokukin':
            monthly_data = calculate_formula(accounts, item['formula'], months)
            keiri2_accounts = all_data.get('keiri2_accounts', [])
            found_5436 = find_account(keiri2_accounts, code='5436')
            txt_debit = all_data.get('txt_debit_data', {})
            for m in months:
                monthly_data[m] = monthly_data.get(m, 0) + item.get('fixed_add', 0) + (found_5436.get('monthly_data', {}).get(m, 0) if found_5436 else 0) + txt_debit.get(m, 0)
            display_accounts.append({'code': '', 'name': item['label'], 'monthly_data': monthly_data, 'is_subtotal': False, 'is_calculated': True})
        elif item['type'] == 'keihi_kei':
            found = find_account(accounts, name='経費計')
            txt_debit, txt_credit = all_data.get('txt_debit_data', {}), all_data.get('txt_credit_data', {})
            monthly_data = {m: (found.get('monthly_data', {}).get(m, 0) if found else 0) - txt_debit.get(m, 0) + txt_credit.get(m, 0) - YAKUIN_TAISHOKUKIN_MONTHLY for m in months}
            display_accounts.append({'code': '', 'name': item['label'], 'monthly_data': monthly_data, 'is_subtotal': False, 'is_calculated': True})
        elif item['type'] == 'igyou_hiyo':
            found = find_account(accounts, name='医業（事業）費用合計')
            found_5436 = find_account(accounts, code='5436')
            txt_debit, txt_credit = all_data.get('txt_debit_data', {}), all_data.get('txt_credit_data', {})
            monthly_data = {m: (found.get('monthly_data', {}).get(m, 0) if found else 0) - txt_debit.get(m, 0) + txt_credit.get(m, 0) - YAKUIN_TAISHOKUKIN_MONTHLY - (found_5436.get('monthly_data', {}).get(m, 0) if found_5436 else 0) for m in months}
            display_accounts.append({'code': '', 'name': item['label'], 'monthly_data': monthly_data, 'is_subtotal': False, 'is_calculated': True})
        elif item['type'] == 'igyou_rieki':
            found_revenue = find_account(accounts, name='医業収益合計')
            found_expense = find_account(accounts, name='医業（事業）費用合計')
            found_5436 = find_account(accounts, code='5436')
            txt_debit, txt_credit = all_data.get('txt_debit_data', {}), all_data.get('txt_credit_data', {})
            monthly_data = {}
            for m in months:
                revenue_val = found_revenue.get('monthly_data', {}).get(m, 0) if found_revenue else 0
                expense_val = found_expense.get('monthly_data', {}).get(m, 0) if found_expense else 0
                val_5436 = found_5436.get('monthly_data', {}).get(m, 0) if found_5436 else 0
                monthly_data[m] = revenue_val - (expense_val - txt_debit.get(m, 0) + txt_credit.get(m, 0) - YAKUIN_TAISHOKUKIN_MONTHLY - val_5436)
            display_accounts.append({'code': '', 'name': item['label'], 'monthly_data': monthly_data, 'is_subtotal': False, 'is_calculated': True})
        elif item['type'] == 'keijo_houjin':
            keiri1_keijo = all_data.get('keiri1_keijo_data', {})
            keiri2_accounts = all_data.get('keiri2_accounts', [])
            keiri2_keijo = find_account(keiri2_accounts, code='KEIJO', name='経常利益')
            taishoku_base = calculate_formula(accounts, '5436', months)
            found_5436_keiri2 = find_account(keiri2_accounts, code='5436')
            txt_debit = all_data.get('txt_debit_data', {})
            monthly_data = {}
            for m in months:
                taishoku_val = taishoku_base.get(m, 0) + YAKUIN_TAISHOKUKIN_MONTHLY + (found_5436_keiri2.get('monthly_data', {}).get(m, 0) if found_5436_keiri2 else 0) + txt_debit.get(m, 0)
                monthly_data[m] = keiri1_keijo.get(m, 0) + (keiri2_keijo.get('monthly_data', {}).get(m, 0) if keiri2_keijo else 0) + taishoku_val
            display_accounts.append({'code': '', 'name': item['label'], 'monthly_data': monthly_data, 'is_subtotal': False, 'is_calculated': True})
    return {'months': months, 'accounts': display_accounts, 'organization': all_data['organization'], 'keiri_kubun': all_data['keiri_kubun']}


@app.route('/')
def index():
    return render_template('index.html')


MANUAL_INPUT_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'manual_inputs.json')


@app.route('/api/autoload', methods=['GET'])
def autoload_data():
    """損益/data/ 内のPDF・TXTを自動読み込み + 手入力値をマージ"""
    data_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')
    if not os.path.isdir(data_dir):
        return jsonify({'error': 'data/ folder not found'}), 404
    pdf_results, chutaikyo_data = [], {}
    for fname in sorted(os.listdir(data_dir)):
        filepath = os.path.join(data_dir, fname)
        try:
            if fname.lower().endswith('.pdf'):
                result = parse_tkc_pdf(filepath)
                year_f, month_f = parse_month_from_filename(fname)
                if year_f and month_f:
                    result['period_year'] = year_f
                    result['period_month'] = month_f
                pdf_results.append(result)
            elif fname.lower().endswith('.txt'):
                chutaikyo_data = parse_chutaikyo_txt(filepath)
        except Exception as e:
            print(f"Error processing {fname}: {e}")
    if not pdf_results:
        return jsonify({'error': 'No PDF files found in data/'}), 404
    all_data = merge_all_monthly_data(pdf_results, chutaikyo_data)
    result = {'all_data': all_data, 'revenue_display': create_display_data(all_data, REVENUE_DISPLAY_ITEMS), 'expense_display': create_display_data(all_data, EXPENSE_DISPLAY_ITEMS), 'profit_display': create_display_data(all_data, PROFIT_DISPLAY_ITEMS), 'output_display': create_display_data(all_data, OUTPUT_DISPLAY_ITEMS), 'chutaikyo_data': chutaikyo_data}
    # 手入力値をマージ
    if os.path.isfile(MANUAL_INPUT_FILE):
        try:
            with open(MANUAL_INPUT_FILE, encoding='utf-8') as f:
                manual = json.load(f)
            for composite_key, monthly_data in manual.items():
                parts = composite_key.split('::', 1)
                if len(parts) != 2:
                    continue
                disp_key, acc_name = parts
                disp = result.get(disp_key)
                if not disp:
                    continue
                for acc in disp['accounts']:
                    if acc.get('name') == acc_name and acc.get('is_manual'):
                        acc['monthly_data'].update({m: v for m, v in monthly_data.items()})
                        break
        except Exception as e:
            print(f"Error loading manual inputs: {e}")
    return jsonify(result)


@app.route('/api/manual_inputs', methods=['POST'])
def save_manual_inputs():
    """手入力値をサーバー側JSONファイルに保存"""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data'}), 400
    os.makedirs(os.path.dirname(MANUAL_INPUT_FILE), exist_ok=True)
    with open(MANUAL_INPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    return jsonify({'ok': True})



SECTION_ITEMS = ['医業収益', '医業費用', '人件費', '委託費', '設備費', '経費', '材料費', '退職金']
AVG_ITEMS_PDF = ['平均入院患者数', '一日当たり収入']


def _fmt_num(n):
    if n == 0 or n is None:
        return '-', False
    return f"{int(n):,}", n < 0


def _fmt_pct(n, base):
    return f"{n/base*100:.1f}%" if base else ''


def _fmt_oku(n):
    if n == 0 or n is None:
        return '-'
    neg, n = n < 0, abs(n)
    if n >= 1e8:
        r = f"{int(n//1e8)}億{int((n%1e8)//1e4):,}万円" if (n % 1e8) // 1e4 else f"{int(n//1e8)}億円"
    elif n >= 1e4:
        r = f"{int(n//1e4):,}万円"
    else:
        r = f"{int(n):,}円"
    return f"-{r}" if neg else r


def _build_pdf_rows(accounts, months, month_years, revenue_data):
    rows = []
    for acc in accounts:
        name = acc['name']
        skip_pct = name in AVG_ITEMS_PDF
        is_avg_item = name in AVG_ITEMS_PDF
        row_class = 'profit' if '利益' in name else ('section' if name in SECTION_ITEMS else '')
        td_class = 'indent' if name.startswith('　') else ''
        total, weighted_sum, total_days = 0, 0, 0
        cells = []
        for m in months:
            val = acc.get('monthly_data', {}).get(m, 0)
            total += val
            if is_avg_item:
                month_num = int(m.replace('月', ''))
                year = month_years.get(m, datetime.now().year)
                days = calendar.monthrange(year, month_num)[1]
                weighted_sum += val * days
                total_days += days
            base = revenue_data.get('monthly_data', {}).get(m, 0) if revenue_data else 0
            fmtd, neg = _fmt_num(val)
            pct = '' if skip_pct else _fmt_pct(val, base)
            cells.append({'fmtd': fmtd, 'neg': neg, 'pct': pct})
        if is_avg_item and total_days > 0:
            total = round(weighted_sum / total_days)
        total_base = sum(revenue_data.get('monthly_data', {}).values()) if revenue_data else 0
        total_fmtd, total_neg = _fmt_num(total)
        total_pct = '' if skip_pct else _fmt_pct(total, total_base)
        rows.append({
            'name': name.strip(), 'row_class': row_class, 'td_class': td_class,
            'cells': cells, 'total_fmtd': total_fmtd, 'total_neg': total_neg, 'total_pct': total_pct,
        })
    return rows


@app.route('/api/export_pdf', methods=['POST'])
def export_pdf():
    data = request.json
    if not data:
        return jsonify({'error': 'No data'}), 400
    output_display = data.get('output_display', {})
    months = output_display.get('months', [])
    accounts = output_display.get('accounts', [])
    month_years = data.get('all_data', {}).get('month_years', {})
    org = output_display.get('organization', '') or '医療法人 梁風会'
    revenue_data = next((a for a in accounts if a['name'] == '医業収益'), None)
    expense_data = next((a for a in accounts if a['name'] == '医業費用'), None)
    igyou_data = next((a for a in accounts if a['name'] == '医業利益'), None)
    keijo_data = next((a for a in accounts if a['name'] == '経常利益（法人）'), None)
    total_rev = sum(revenue_data.get('monthly_data', {}).values()) if revenue_data else 0
    total_exp = sum(expense_data.get('monthly_data', {}).values()) if expense_data else 0
    total_igyou = sum(igyou_data.get('monthly_data', {}).values()) if igyou_data else 0
    latest_m = months[-1] if months else ''
    latest_keijo = keijo_data.get('monthly_data', {}).get(latest_m, 0) if keijo_data else 0
    rows = _build_pdf_rows(accounts, months, month_years, revenue_data)
    return render_template('pdf_summary.html',
        org=org, now=datetime.now().strftime('%Y/%m/%d'), months=months, rows=rows,
        fmt_oku=_fmt_oku, total_rev=total_rev, total_exp=total_exp, total_igyou=total_igyou,
        exp_ratio=(total_exp / total_rev * 100) if total_rev else 0,
        igyou_ratio=(total_igyou / total_rev * 100) if total_rev else 0,
        latest_m=latest_m, latest_keijo_houjin=latest_keijo,
    )


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5002)