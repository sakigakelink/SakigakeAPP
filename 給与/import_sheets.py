#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R7支払いタブ CSV → JSON 変換スクリプト（ワンショット）"""

import csv
import json
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, 'data', 'R7支払.csv')
JSON_PATH = os.path.join(BASE_DIR, 'data', 'r7_sheets.json')

MONTHS = ['4月', '5月', '6月', '7月', '8月', '9月', '10月', '11月', '12月', '1月', '2月', '3月']

# 医師名リスト
DOCTOR_NAMES = ['樋口', '兒玉', '白石', '赤穂', '原田', '難波', '中田']

# 内訳項目ラベル
BREAKDOWN_LABELS = ['本給', '職能手当', '他・固定', '控除', 'シフト', '時間外', '回数', '通勤', '賞与']


def parse_number(s):
    """文字列を数値に変換。空/None → 0"""
    if not s or not str(s).strip():
        return 0
    s = str(s).strip().replace(',', '').replace(' ', '').replace('\u3000', '')
    try:
        if '.' in s:
            return float(s)
        return int(s)
    except ValueError:
        return 0


def monthly(row, start=2, count=12):
    """行からC-N列（index 2-13）の12ヶ月分を取得"""
    vals = []
    for i in range(start, start + count):
        vals.append(parse_number(row[i]) if i < len(row) else 0)
    return vals


def cell_a(row):
    """A列の文字列を取得"""
    return str(row[0]).strip() if row and row[0] else ''


def is_data_row(row):
    """C-N列にデータがある行か"""
    if not row:
        return False
    for i in range(2, min(14, len(row))):
        if row[i] and str(row[i]).strip():
            return True
    return False


def parse_doctor_block(rows, start_row):
    """医師ブロック解析: start_row=名前行の1つ前（変動額行）or 名前行自体"""
    # 名前行を特定
    name = ''
    name_idx = start_row
    for i in range(max(0, start_row - 1), min(start_row + 2, len(rows))):
        a = cell_a(rows[i])
        if a in DOCTOR_NAMES:
            name = a
            name_idx = i
            break

    if not name:
        return None

    # ブロック範囲: 名前行の前後を含む連続データ行
    # 上方向: 名前行の直前にデータ行があればそれも含む
    block_start = name_idx
    if name_idx > 0 and is_data_row(rows[name_idx - 1]) and not cell_a(rows[name_idx - 1]):
        block_start = name_idx - 1

    # 下方向: 空行まで
    block_end = name_idx + 1
    while block_end < len(rows) and is_data_row(rows[block_end]):
        block_end += 1

    # 空行の先に合計行（数値A列ラベル）があれば含める
    # ただし500以上は全体合計行なのでスキップ
    for skip in range(block_end, min(block_end + 3, len(rows))):
        if is_data_row(rows[skip]):
            a = cell_a(rows[skip])
            try:
                num = int(a)
                if num < 500:
                    block_end = skip + 1
            except ValueError:
                pass
            break

    # ブロック内の全行を取得
    block_rows = []
    for i in range(block_start, block_end):
        a = cell_a(rows[i])
        vals = monthly(rows[i])
        block_rows.append({'label': a, 'values': vals, 'row': i + 1})

    # 最後の行を月別合計とする
    monthly_total = block_rows[-1]['values'] if block_rows else [0] * 12

    # 内訳（最初と最後を除く中間行）
    breakdown = {}
    for idx, br in enumerate(block_rows):
        if idx == len(block_rows) - 1:
            continue  # 最後=合計
        if br['label'] == name:
            # 名前行: 基本給行であることが多い
            breakdown['基本給'] = br['values']
        elif br['label'] == '' and idx == 0 and block_start < name_idx:
            # 名前行の前の行 = 変動額
            breakdown['変動額'] = br['values']
        elif br['label'] and br['label'] not in DOCTOR_NAMES:
            # A列に数値 = 通勤など
            try:
                int(br['label'])
                # 数値ラベル → 通勤行の可能性
                if idx < len(block_rows) - 1:
                    breakdown['通勤'] = br['values']
                else:
                    breakdown[f'項目{idx}'] = br['values']
            except ValueError:
                breakdown[br['label']] = br['values']
        else:
            breakdown[f'手当{idx}'] = br['values']

    return {
        'name': name,
        'monthly_total': monthly_total,
        'breakdown': breakdown,
        'block_range': f'{block_start + 1}-{block_end}',
    }


def parse_labeled_section(rows, start_row, end_row):
    """ラベル付きセクション（一般職員/たいようの丘）を解析"""
    breakdown = {}
    total = [0] * 12
    social_insurance = [0] * 12
    # 全データ行を収集して後で合計・社保を判定
    data_rows = []

    for i in range(start_row, min(end_row, len(rows))):
        if not is_data_row(rows[i]):
            continue
        a = cell_a(rows[i])
        vals = monthly(rows[i])
        data_rows.append((i, a, vals))

    for idx, (i, a, vals) in enumerate(data_rows):
        if a in BREAKDOWN_LABELS:
            breakdown[a] = vals
        elif '社会保険' in a:
            social_insurance = vals
        else:
            # A列が数値（3850等）= 合計行
            is_num = False
            try:
                num = int(a)
                if num > 100:
                    total = vals
                    is_num = True
            except ValueError:
                pass
            if not is_num and a == '':
                # ラベルなしの行: 社会保険の直前 = 合計行
                if idx + 1 < len(data_rows) and '社会保険' in data_rows[idx + 1][1]:
                    total = vals
                elif a and a not in BREAKDOWN_LABELS:
                    breakdown[a] = vals

    return breakdown, total, social_insurance


def main():
    if not os.path.exists(CSV_PATH):
        print(f'エラー: CSVファイルが見つかりません: {CSV_PATH}')
        print(f'Google SheetsからR7支払いタブをCSVエクスポートして配置してください。')
        sys.exit(1)

    # CSV読込
    rows = []
    for enc in ('utf-8-sig', 'utf-8', 'cp932', 'shift_jis'):
        try:
            with open(CSV_PATH, encoding=enc, newline='') as f:
                reader = csv.reader(f)
                rows = list(reader)
            break
        except (UnicodeDecodeError, UnicodeError):
            continue

    if not rows:
        print('エラー: CSVを読み込めません')
        sys.exit(1)

    print(f'CSV読込完了: {len(rows)}行')

    # === 医師個人ブロック解析 (rows 1-52) ===
    doctors = []
    processed_rows = set()
    for name in DOCTOR_NAMES:
        # 名前行を検索（row 1-52）
        for i in range(min(len(rows), 55)):
            if cell_a(rows[i]) == name and i not in processed_rows:
                doc = parse_doctor_block(rows, i)
                if doc:
                    doctors.append(doc)
                    print(f'  医師: {doc["name"]} (行{doc["block_range"]})')
                    # マーク済み
                    start, end = doc['block_range'].split('-')
                    for r in range(int(start), int(end) + 1):
                        processed_rows.add(r - 1)
                break

    # === 医師内訳の後処理 ===
    for doc in doctors:
        bd = doc['breakdown']
        # 変動額は不要
        bd.pop('変動額', None)
        # 全ゼロの内訳行を除去
        bd = {k: v for k, v in bd.items() if any(x != 0 for x in v)}
        # 兒玉: 基本給不要
        if doc['name'] == '兒玉':
            bd.pop('基本給', None)
        # 赤穂: 手当3 → 通勤費
        if doc['name'] == '赤穂' and '手当3' in bd:
            bd['通勤費'] = bd.pop('手当3')

        # 項目名を振り直し（医師ごとに個別定義）
        special = {'通勤', '通勤費'}
        items = [(k, v) for k, v in bd.items() if k not in special]
        new_bd = {}

        if doc['name'] == '樋口':
            # 手当, 通勤費
            if len(items) >= 1:
                new_bd['手当'] = items[0][1]
            if len(items) >= 2:
                new_bd['通勤費'] = items[1][1]

        elif doc['name'] == '白石':
            # 基本給, 手当1, 手当2, ..., 通勤
            if '基本給' in bd:
                new_bd['基本給'] = bd['基本給']
            n = 1
            for key, vals in items:
                if key == '基本給':
                    continue
                new_bd[f'手当{n}'] = vals
                n += 1
            if '通勤' in bd:
                new_bd['通勤'] = bd['通勤']

        elif doc['name'] == '赤穂':
            # 手当1, 手当2(=旧通勤), 手当3(=旧手当2), 通勤費
            if len(items) >= 1:
                new_bd['手当1'] = items[0][1]
            if '通勤' in bd:
                new_bd['手当2'] = bd['通勤']
            if len(items) >= 2:
                new_bd['手当3'] = items[1][1]
            if '通勤費' in bd:
                new_bd['通勤費'] = bd['通勤費']

        elif doc['name'] in ('原田', '難波'):
            # 手当1, 手当2, 手当3(=旧通勤), 通勤費(=旧手当の最後)
            # 旧: items=[基本給,手当2,手当4], 通勤=大額 → 手当4が実は通勤費
            for i, (k, v) in enumerate(items[:-1]):
                new_bd[f'手当{i + 1}'] = v
            if '通勤' in bd:
                new_bd[f'手当{len(items)}'] = bd['通勤']
            if items:
                new_bd['通勤費'] = items[-1][1]

        else:
            # 兒玉等: 手当1, 手当2, ..., 通勤
            n = 1
            for key, vals in items:
                new_bd[f'手当{n}'] = vals
                n += 1
            if '通勤' in bd:
                new_bd['通勤'] = bd['通勤']

        doc['breakdown'] = new_bd

    # 医師合計 (row 50: A=750)
    doctors_subtotal = [0] * 12
    for i in range(45, 55):
        if i < len(rows):
            a = cell_a(rows[i])
            try:
                if int(a) >= 500:
                    doctors_subtotal = monthly(rows[i])
                    print(f'  医師合計: 行{i + 1} (A={a})')
                    break
            except ValueError:
                pass

    # 医師社会保険 (row 51)
    doctors_social = [0] * 12
    for i in range(48, 55):
        if i < len(rows) and '社会保険' in cell_a(rows[i]):
            doctors_social = monthly(rows[i])
            print(f'  医師社会保険: 行{i + 1}')
            break

    # 医師非常勤 (row 52)
    doctors_parttime = [0] * 12
    for i in range(48, 55):
        if i < len(rows) and '医師非常勤' in cell_a(rows[i]):
            doctors_parttime = monthly(rows[i])
            print(f'  医師非常勤: 行{i + 1}')
            break

    # === 一般職員セクション (rows 56-66) ===
    staff_start = -1
    for i in range(53, 62):
        if i < len(rows) and cell_a(rows[i]) == '本給':
            staff_start = i
            break
    if staff_start < 0:
        print('警告: 一般職員セクション（本給）が見つかりません')
        staff_start = 55

    staff_breakdown, staff_total, staff_social = parse_labeled_section(rows, staff_start, staff_start + 12)
    print(f'  一般職員: 行{staff_start + 1}〜 ({len(staff_breakdown)}項目)')

    # === 非常勤セクション (rows 68-69) ===
    parttime = [0] * 12
    parttime_social = [0] * 12
    for i in range(65, 72):
        if i < len(rows):
            a = cell_a(rows[i])
            if a == '非常勤':
                parttime = monthly(rows[i])
                print(f'  非常勤: 行{i + 1}')
                if i + 1 < len(rows) and '社会保険' in cell_a(rows[i + 1]):
                    parttime_social = monthly(rows[i + 1])
                break

    # === 全体合計 (rows 71-72) ===
    grand_payroll = [0] * 12
    grand_social = [0] * 12
    for i in range(68, 75):
        if i < len(rows):
            a = cell_a(rows[i])
            if a == '給与費':
                grand_payroll = monthly(rows[i])
                print(f'  給与費合計: 行{i + 1}')
            elif a == '社会保険料':
                grand_social = monthly(rows[i])
                print(f'  社会保険料合計: 行{i + 1}')

    # === たいようの丘セクション (rows 74-84) ===
    taiyou_start = -1
    for i in range(72, 80):
        if i < len(rows) and cell_a(rows[i]) == '本給':
            taiyou_start = i
            break
    if taiyou_start < 0:
        print('警告: たいようの丘セクション（本給）が見つかりません')
        taiyou_start = 73

    taiyou_breakdown, taiyou_total, taiyou_social = parse_labeled_section(rows, taiyou_start, taiyou_start + 12)
    print(f'  たいようの丘: 行{taiyou_start + 1}〜 ({len(taiyou_breakdown)}項目)')

    # === 一般職員・たいようの丘の項目順序統一 ===
    STAFF_ORDER = ['本給', '職能手当', '他・固定', '控除', 'シフト', '時間外', '回数', '通勤', '賞与引当']

    def reorder_staff(bd):
        # 賞与 → 賞与引当
        if '賞与' in bd:
            bd['賞与引当'] = bd.pop('賞与')
        ordered = {}
        for key in STAFF_ORDER:
            if key in bd:
                ordered[key] = bd[key]
        # 残りがあれば末尾に
        for key in bd:
            if key not in ordered:
                ordered[key] = bd[key]
        return ordered

    staff_breakdown = reorder_staff(staff_breakdown)
    taiyou_breakdown = reorder_staff(taiyou_breakdown)

    # === JSON出力 ===
    output = {
        'months': MONTHS,
        'doctors': [
            {'name': d['name'], 'monthly_total': d['monthly_total'], 'breakdown': d['breakdown']}
            for d in doctors
        ],
        'doctors_subtotal': doctors_subtotal,
        'doctors_social_insurance': doctors_social,
        'doctors_parttime': doctors_parttime,
        'staff': staff_breakdown,
        'staff_total': staff_total,
        'staff_social_insurance': staff_social,
        'parttime': parttime,
        'parttime_social_insurance': parttime_social,
        'grand_total_payroll': grand_payroll,
        'grand_total_social': grand_social,
        'taiyou': taiyou_breakdown,
        'taiyou_total': taiyou_total,
        'taiyou_social_insurance': taiyou_social,
    }

    os.makedirs(os.path.dirname(JSON_PATH), exist_ok=True)
    with open(JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f'\n出力完了: {JSON_PATH}')

    # サマリー
    fmt = lambda v: f'{sum(v):>15,.0f}'
    print(f'  医師合計:       {fmt(doctors_subtotal)}')
    print(f'  一般職員合計:   {fmt(staff_total)}')
    print(f'  非常勤合計:     {fmt(parttime)}')
    print(f'  たいようの丘:   {fmt(taiyou_total)}')
    print(f'  給与費総合計:   {fmt(grand_payroll)}')
    print(f'  社会保険料総計: {fmt(grand_social)}')


if __name__ == '__main__':
    main()
