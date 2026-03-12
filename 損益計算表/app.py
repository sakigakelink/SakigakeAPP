#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TKC月次合算試算表 解析アプリ
TXTファイルから中退共を抽出して退職金を計算
"""

import os
import re
import json
import calendar
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file
import pdfplumber
import pandas as pd
from io import BytesIO

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024
app.config['UPLOAD_FOLDER'] = '/tmp/tkc_uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

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
    {'type': 'taishokukin', 'formula': '5436', 'fixed_add': 248700, 'label': '退職金'},
]

OUTPUT_DISPLAY_ITEMS = [
    {'type': 'single', 'code': None, 'name': '医業収益合計', 'label': '医業収益'},
    {'type': 'daily_revenue', 'label': '一日当たり収入'},
    {'type': 'manual_input', 'label': '平均入院患者数'},
    {'type': 'calc_fixed', 'formula': '医業（事業）費用合計-CHUTAIKYO-5436', 'fixed_add': -248700, 'label': '医業費用'},
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
    {'type': 'taishokukin', 'formula': '5436', 'fixed_add': 248700, 'label': '退職金'},
]


def parse_chutaikyo_txt(txt_path):
    debit_data, credit_data, debug_lines = {}, {}, []
    content = None
    for enc in ['shift_jis', 'cp932', 'utf-8']:
        try:
            with open(txt_path, 'r', encoding=enc) as f:
                content = f.read()
            break
        except:
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
                    except:
                        pass
    return {'debit': debit_data, 'credit': credit_data, 'debug': debug_lines}


def parse_tkc_pdf(pdf_path):
    result = {'filename': os.path.basename(pdf_path), 'organization': '', 'period': '', 'period_month': 0, 'period_year': 0, 'keiri_kubun': '', 'accounts': [], 'keiri2_accounts': [], 'keiri1_keijo': None}
    def parse_number(s):
        try:
            return float(s.replace(',', '').replace(' ', ''))
        except:
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


def merge_all_monthly_data(pdf_results, chutaikyo_data=None):
    sorted_results = sorted(pdf_results, key=lambda x: (x.get('period_year', 0), x.get('period_month', 0)))
    months, all_accounts, keiri2_accounts = [], {}, {}
    month_years = {}
    for result in sorted_results:
        month_key = f"{result.get('period_month', 0)}月"
        if month_key not in months and result.get('period_month'):
            months.append(month_key)
        if result.get('period_month') and result.get('period_year'):
            month_years[month_key] = result['period_year']
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
        month_key = f"{result.get('period_month', 0)}月"
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
        if name and name in acc.get('name', ''):
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
            monthly_data = {m: (found.get('monthly_data', {}).get(m, 0) if found else 0) - txt_debit.get(m, 0) + txt_credit.get(m, 0) - 248700 for m in months}
            display_accounts.append({'code': '', 'name': item['label'], 'monthly_data': monthly_data, 'is_subtotal': False, 'is_calculated': True})
        elif item['type'] == 'igyou_hiyo':
            found = find_account(accounts, name='医業（事業）費用合計')
            found_5436 = find_account(accounts, code='5436')
            txt_debit, txt_credit = all_data.get('txt_debit_data', {}), all_data.get('txt_credit_data', {})
            monthly_data = {m: (found.get('monthly_data', {}).get(m, 0) if found else 0) - txt_debit.get(m, 0) + txt_credit.get(m, 0) - 248700 - (found_5436.get('monthly_data', {}).get(m, 0) if found_5436 else 0) for m in months}
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
                monthly_data[m] = revenue_val - (expense_val - txt_debit.get(m, 0) + txt_credit.get(m, 0) - 248700 - val_5436)
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
                taishoku_val = taishoku_base.get(m, 0) + 248700 + (found_5436_keiri2.get('monthly_data', {}).get(m, 0) if found_5436_keiri2 else 0) + txt_debit.get(m, 0)
                monthly_data[m] = keiri1_keijo.get(m, 0) + (keiri2_keijo.get('monthly_data', {}).get(m, 0) if keiri2_keijo else 0) + taishoku_val
            display_accounts.append({'code': '', 'name': item['label'], 'monthly_data': monthly_data, 'is_subtotal': False, 'is_calculated': True})
    return {'months': months, 'accounts': display_accounts, 'organization': all_data['organization'], 'keiri_kubun': all_data['keiri_kubun']}


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/upload', methods=['POST'])
def upload_files():
    if 'files' not in request.files:
        return jsonify({'error': 'No files selected'}), 400
    files = request.files.getlist('files')
    pdf_results, chutaikyo_data = [], {}
    for file in files:
        if file.filename:
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
            file.save(filepath)
            try:
                if file.filename.lower().endswith('.pdf'):
                    pdf_results.append(parse_tkc_pdf(filepath))
                elif file.filename.lower().endswith('.txt'):
                    chutaikyo_data = parse_chutaikyo_txt(filepath)
            except Exception as e:
                print(f"Error processing {file.filename}: {e}")
            finally:
                if os.path.exists(filepath):
                    os.remove(filepath)
    all_data = merge_all_monthly_data(pdf_results, chutaikyo_data)
    return jsonify({'individual': pdf_results, 'all_data': all_data, 'revenue_display': create_display_data(all_data, REVENUE_DISPLAY_ITEMS), 'expense_display': create_display_data(all_data, EXPENSE_DISPLAY_ITEMS), 'profit_display': create_display_data(all_data, PROFIT_DISPLAY_ITEMS), 'output_display': create_display_data(all_data, OUTPUT_DISPLAY_ITEMS), 'chutaikyo_data': chutaikyo_data})


@app.route('/api/export', methods=['POST'])
def export_excel():
    data = request.json
    if not data:
        return jsonify({'error': 'No data'}), 400
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        months = data.get('all_data', {}).get('months', [])
        for sheet_name, display_key, label_col in [('収益', 'revenue_display', '勘定科目名'), ('費用', 'expense_display', '勘定科目名'), ('利益', 'profit_display', '勘定科目名'), ('出力', 'output_display', '項目')]:
            display = data.get(display_key, {})
            if display.get('accounts'):
                rows = [{label_col: acc['name'], **{m: acc.get('monthly_data', {}).get(m, 0) for m in months}, '合計': sum(acc.get('monthly_data', {}).get(m, 0) for m in months)} for acc in display['accounts']]
                pd.DataFrame(rows).to_excel(writer, sheet_name=sheet_name, index=False)
    output.seek(0)
    return send_file(output, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', as_attachment=True, download_name=f'tkc_monthly_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx')


@app.route('/api/save_json', methods=['POST'])
def save_json():
    data = request.json
    if not data:
        return jsonify({'error': 'No data'}), 400
    output = BytesIO()
    output.write(json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8'))
    output.seek(0)
    return send_file(output, mimetype='application/json', as_attachment=True, download_name=f'tkc_data_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json')


@app.route('/api/load_json', methods=['POST'])
def load_json():
    if 'file' not in request.files:
        return jsonify({'error': 'No file'}), 400
    file = request.files['file']
    if not file.filename.endswith('.json'):
        return jsonify({'error': 'JSON file required'}), 400
    try:
        return jsonify(json.load(file))
    except Exception as e:
        return jsonify({'error': str(e)}), 400


@app.route('/api/export_pdf', methods=['POST'])
def export_pdf():
    data = request.json
    if not data:
        return jsonify({'error': 'No data'}), 400
    output_display = data.get('output_display', {})
    months = output_display.get('months', [])
    accounts = output_display.get('accounts', [])
    org = output_display.get('organization', '') or '医療法人 梁風会'
    revenue_data = next((acc for acc in accounts if acc['name'] == '医業収益'), None)
    expense_data = next((acc for acc in accounts if acc['name'] == '医業費用'), None)
    igyou_rieki_data = next((acc for acc in accounts if acc['name'] == '医業利益'), None)
    keijo_houjin_data = next((acc for acc in accounts if acc['name'] == '経常利益（法人）'), None)
    def fmt_num(n):
        if n == 0 or n is None:
            return '-', False
        return f"{int(n):,}", n < 0
    def fmt_pct(n, base):
        return f"{n/base*100:.1f}%" if base else ''
    def fmt_oku(n):
        if n == 0 or n is None:
            return '-'
        neg, n = n < 0, abs(n)
        if n >= 1e8:
            r = f"{int(n//1e8)}億{int((n%1e8)//1e4):,}万円" if (n%1e8)//1e4 else f"{int(n//1e8)}億円"
        elif n >= 1e4:
            r = f"{int(n//1e4):,}万円"
        else:
            r = f"{int(n):,}円"
        return f"-{r}" if neg else r
    now = datetime.now().strftime('%Y/%m/%d')
    total_rev = sum(revenue_data.get('monthly_data', {}).values()) if revenue_data else 0
    total_exp = sum(expense_data.get('monthly_data', {}).values()) if expense_data else 0
    total_igyou = sum(igyou_rieki_data.get('monthly_data', {}).values()) if igyou_rieki_data else 0
    exp_ratio = (total_exp / total_rev * 100) if total_rev else 0
    igyou_ratio = (total_igyou / total_rev * 100) if total_rev else 0
    latest_m = months[-1] if months else ''
    latest_keijo_houjin = keijo_houjin_data.get('monthly_data', {}).get(latest_m, 0) if keijo_houjin_data else 0
    html = f'''<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<title>{org} 月次サマリー</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Noto+Sans+JP:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
@media print{{@page{{size:A4 landscape;margin:6mm}}*{{-webkit-print-color-adjust:exact!important;print-color-adjust:exact!important}}body{{padding:0!important;font-size:7px!important}}.no-print{{display:none!important}}.summary-cards{{gap:8px!important;margin-bottom:10px!important}}.card{{padding:10px!important}}.card-value{{font-size:18px!important}}table{{font-size:7.5px!important}}th,td{{padding:4px 5px!important}}}}
*{{margin:0;padding:0;box-sizing:border-box}}body{{font-family:'Inter','Noto Sans JP',sans-serif;font-size:11px;color:#1e293b;background:linear-gradient(135deg,#f8fafc 0%,#e2e8f0 100%);min-height:100vh;padding:20px}}.container{{max-width:1400px;margin:0 auto;background:#fff;border-radius:16px;box-shadow:0 4px 24px rgba(0,0,0,0.08);padding:24px}}.header{{display:flex;justify-content:space-between;align-items:center;margin-bottom:20px;padding-bottom:16px;border-bottom:1px solid #e2e8f0}}h1{{font-size:22px;font-weight:700;color:#0f172a;display:flex;align-items:center;gap:12px}}h1::before{{content:'';width:5px;height:28px;background:linear-gradient(180deg,#3b82f6,#1d4ed8);border-radius:3px}}.print-date{{font-size:11px;color:#64748b}}.btn-group{{display:flex;gap:10px}}.btn{{padding:10px 20px;color:#fff;border:none;border-radius:8px;cursor:pointer;font-size:13px;font-weight:600;transition:all 0.2s;display:flex;align-items:center;gap:6px}}.btn-print{{background:linear-gradient(135deg,#6366f1,#4f46e5)}}.btn-print:hover{{transform:translateY(-2px);box-shadow:0 4px 12px rgba(99,102,241,0.4)}}.btn-save{{background:linear-gradient(135deg,#10b981,#059669)}}.btn-save:hover{{transform:translateY(-2px);box-shadow:0 4px 12px rgba(16,185,129,0.4)}}.summary-cards{{display:grid;grid-template-columns:repeat(4,1fr);gap:16px;margin-bottom:24px}}.card{{background:#fff;border-radius:12px;padding:18px;position:relative;overflow:hidden;border:1px solid #e2e8f0;transition:transform 0.2s,box-shadow 0.2s}}.card:hover{{transform:translateY(-2px);box-shadow:0 8px 24px rgba(0,0,0,0.1)}}.card::before{{content:'';position:absolute;top:0;left:0;right:0;height:4px}}.card-revenue::before{{background:linear-gradient(90deg,#3b82f6,#60a5fa)}}.card-expense::before{{background:linear-gradient(90deg,#f59e0b,#fbbf24)}}.card-profit::before{{background:linear-gradient(90deg,#10b981,#34d399)}}.card-margin::before{{background:linear-gradient(90deg,#8b5cf6,#a78bfa)}}.card-label{{font-size:11px;color:#64748b;font-weight:500;margin-bottom:8px;display:flex;align-items:center;gap:6px}}.card-icon{{width:20px;height:20px;border-radius:6px;display:flex;align-items:center;justify-content:center;font-size:11px}}.card-revenue .card-icon{{background:#dbeafe;color:#2563eb}}.card-expense .card-icon{{background:#fef3c7;color:#d97706}}.card-profit .card-icon{{background:#d1fae5;color:#059669}}.card-margin .card-icon{{background:#ede9fe;color:#7c3aed}}.card-value{{font-size:26px;font-weight:700;color:#0f172a;font-variant-numeric:tabular-nums;letter-spacing:-0.5px}}.card-value.positive{{color:#059669}}.card-value.negative{{color:#dc2626}}.card-sub{{display:flex;align-items:center;gap:8px;margin-top:8px;font-size:11px}}.trend{{display:inline-flex;align-items:center;gap:3px;padding:3px 8px;border-radius:20px;font-weight:600;font-size:10px}}.trend-up{{background:#dcfce7;color:#16a34a}}.trend-down{{background:#fee2e2;color:#dc2626}}.card-period{{color:#94a3b8;font-size:10px}}table{{width:100%;border-collapse:collapse;font-size:9px;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.06)}}thead th{{background:linear-gradient(135deg,#1e3a8a 0%,#1e40af 100%);color:#fff;padding:10px 8px;text-align:center;font-weight:600;letter-spacing:0.3px;position:relative}}thead th::after{{content:'';position:absolute;bottom:0;left:0;right:0;height:1px;background:rgba(255,255,255,0.1)}}th:first-child{{text-align:left;padding-left:14px;min-width:120px;border-radius:8px 0 0 0}}th:last-child{{background:linear-gradient(135deg,#172554 0%,#1e3a8a 100%);border-radius:0 8px 0 0}}td{{padding:8px 10px;border-bottom:1px solid #f1f5f9;text-align:right;font-family:'Inter',monospace;font-variant-numeric:tabular-nums;color:#334155}}td:first-child{{text-align:left;padding-left:14px;font-family:'Noto Sans JP',sans-serif;font-weight:500;color:#1e293b}}td:last-child{{background:#f8fafc;font-weight:700;color:#0f172a}}tbody tr{{background:#fff;transition:background 0.15s}}tbody tr:nth-child(even){{background:#fafbfc}}tbody tr:hover{{background:#f1f5f9}}.indent{{padding-left:28px!important;color:#64748b;font-weight:400!important}}.section{{background:linear-gradient(90deg,#eff6ff,#f8fafc)!important}}.section td{{font-weight:600}}.section td:first-child{{color:#1d4ed8}}.section td:last-child{{background:#dbeafe!important}}.profit{{background:linear-gradient(90deg,#ecfdf5,#f0fdf4)!important}}.profit td{{font-weight:600;color:#047857}}.profit td:last-child{{background:#d1fae5!important;color:#047857}}.negative{{color:#dc2626!important}}.pct{{color:#94a3b8;font-size:7px;display:block;margin-top:2px}}tbody tr:last-child td:first-child{{border-radius:0 0 0 8px}}tbody tr:last-child td:last-child{{border-radius:0 0 8px 0}}
</style>
</head>
<body>
<div class="container">
<div class="header"><h1>{org} 月次サマリー</h1><div class="btn-group no-print"><button class="btn btn-save" onclick="saveHTML()">💾 HTMLを保存</button><button class="btn btn-print" onclick="window.print()">🖨️ 印刷 / PDF</button></div><div class="print-date">出力日時：{now}</div></div>
<div class="summary-cards">
<div class="card card-revenue"><div class="card-label"><span class="card-icon">💰</span>医業収益（累計）</div><div class="card-value">{fmt_oku(total_rev)}</div><div class="card-sub"><span class="card-period">4月〜{latest_m}</span></div></div>
<div class="card card-expense"><div class="card-label"><span class="card-icon">📊</span>医業費用（累計）</div><div class="card-value">{fmt_oku(total_exp)}</div><div class="card-sub"><span class="card-period">対収益比 {exp_ratio:.1f}%</span></div></div>
<div class="card card-profit"><div class="card-label"><span class="card-icon">📈</span>医業利益（累計）</div><div class="card-value {"positive" if total_igyou>=0 else "negative"}">{fmt_oku(total_igyou)}</div><div class="card-sub"><span class="card-period">利益率 {igyou_ratio:.1f}%</span></div></div>
<div class="card card-margin"><div class="card-label"><span class="card-icon">📉</span>当月経常利益</div><div class="card-value {"positive" if latest_keijo_houjin>=0 else "negative"}">{fmt_oku(latest_keijo_houjin)}</div><div class="card-sub"><span class="card-period">{latest_m}</span></div></div>
</div>
<table><thead><tr><th>項目</th>'''
    for m in months:
        html += f'<th>{m}</th>'
    html += '<th>合計</th></tr></thead><tbody>'
    for acc in accounts:
        name = acc['name']
        skip_pct = name in ['平均入院患者数', '一日当たり収入']
        row_class = 'profit' if '利益' in name else ('section' if name in ['医業収益','医業費用','人件費','委託費','設備費','経費','材料費','退職金'] else '')
        td_class = 'indent' if name.startswith('　') else ''
        html += f'<tr class="{row_class}"><td class="{td_class}">{name.strip()}</td>'
        total = 0
        for m in months:
            val = acc.get('monthly_data', {}).get(m, 0)
            total += val
            base = revenue_data.get('monthly_data', {}).get(m, 0) if revenue_data else 0
            pct = '' if skip_pct else fmt_pct(val, base)
            fmtd, neg = fmt_num(val)
            html += f'<td{" class=\"negative\"" if neg else ""}>{fmtd}{"<span class=\"pct\">"+pct+"</span>" if pct else ""}</td>'
        total_base = sum(revenue_data.get('monthly_data', {}).values()) if revenue_data else 0
        pct_total = '' if skip_pct else fmt_pct(total, total_base)
        fmtd_total, neg_total = fmt_num(total)
        html += f'<td{" class=\"negative\"" if neg_total else ""}>{fmtd_total}{"<span class=\"pct\">"+pct_total+"</span>" if pct_total else ""}</td></tr>'
    html += '</tbody></table></div><script>function saveHTML(){const h=document.documentElement.outerHTML;const b=new Blob([h],{type:"text/html;charset=utf-8"});const u=URL.createObjectURL(b);const a=document.createElement("a");a.href=u;a.download="monthly_summary.html";a.click();URL.revokeObjectURL(u);}</script></body></html>'
    return html, 200, {'Content-Type': 'text/html; charset=utf-8'}


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5002)