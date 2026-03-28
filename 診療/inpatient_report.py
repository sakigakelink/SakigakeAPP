#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""月次入院収益レポート自動生成スクリプト

指定月フォルダ内の診療行為別集計表PDF群から入院データを自動抽出し、
月次入院収益HTMLサマリーを生成する。

使用法:
    python inpatient_report.py

出力:
    入院収益月次サマリー.html
"""

import os
import re
import sys
import glob
import datetime
from collections import defaultdict, Counter

import pdfplumber

# ======================================================================
# パス定義
# ======================================================================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MONTH_FOLDER = os.path.join(BASE_DIR, '2月', '2月')


# ======================================================================
# 1. PDF解析モジュール
# ======================================================================

def _yen2pt(yen):
    """円→点 変換（四捨五入）"""
    return (yen + 5) // 10


def _parse_num(s):
    """カンマ付き数値文字列をintに変換"""
    if s is None:
        return 0
    s = str(s).strip().replace(',', '').replace(' ', '')
    if not s or s in ('-', '―'):
        return 0
    try:
        return int(float(s))
    except ValueError:
        return 0


def extract_grand_total(pdf_path):
    """PDFの総合計行から入院金額（円）を抽出
    テーブル構造: [診区, コード, 名称, 点/単価, 外来数量, 入院数量, 合計数量,
                   外来金額, 入院金額(idx8), 合計金額, 全体比率, グループ比率, ?, ?]
    """
    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[-1]
        # テーブル抽出を試みる
        tables = page.extract_tables({
            'vertical_strategy': 'lines',
            'horizontal_strategy': 'lines',
            'snap_tolerance': 5,
        })
        if not tables:
            tables = page.extract_tables({
                'vertical_strategy': 'text',
                'horizontal_strategy': 'text',
            })
        for table in tables:
            for row in table:
                if row is None or len(row) < 9:
                    continue
                cell2 = str(row[2] or '').strip()
                # 総合計行を検出（改行なしの独立行）
                if '総' in cell2 and '計' in cell2 and '\n' not in cell2:
                    return _parse_num(row[8])
                # 診区別小計が改行で結合されている場合、最終行を確認
                if '\n' in cell2:
                    lines = cell2.split('\n')
                    if any('総' in l and '計' in l for l in lines):
                        idx = next(i for i, l in enumerate(lines) if '総' in l and '計' in l)
                        vals = str(row[8] or '').split('\n')
                        val = _parse_num(vals[idx]) if idx < len(vals) else 0
                        if val > 0:
                            return val
                        # 総合計行のcol8が空の場合はテキストフォールバックへ
                        break

        # テーブルから取れない場合（薬剤・器材等）: テキストベースで抽出
        # 全ページを走査（総合計が最終ページに無い場合もある）
        for page2 in pdf.pages:
            text = page2.extract_text() or ''
            last_subtotal = 0
            for line in text.split('\n'):
                if '総' in line and '計' in line:
                    nums = [_parse_num(p) for p in re.findall(r'[\d,.]+', line)]
                    # テキスト行の数値配列:
                    # [外来数量(0), 入院数量, 合計数量, 外来金額(0), 入院金額, 合計金額, 比率...]
                    # 入院金額は常にindex 4
                    if len(nums) > 4:
                        return nums[4]
                # 総合計が空の場合のフォールバック: 診区別小計の合計を使う
                if '小計' in line:
                    nums = [_parse_num(p) for p in re.findall(r'[\d,.]+', line)]
                    if len(nums) > 4 and nums[4] > 0:
                        last_subtotal += nums[4]
        if last_subtotal > 0:
            return last_subtotal
    return 0


def extract_drug_subtotals(pdf_path):
    """薬剤PDFから診区別小計（円）を抽出
    テーブル構造: [診区, コード, 名称, 単価, 外来数量, 入院数量, 合計数量,
                   外来金額, 入院金額(idx8), 合計金額, 全体比率, ?, ?]
    """
    subtotals = {}
    shinku_codes = {'21', '22', '23', '31', '33', '40'}

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables({
                'vertical_strategy': 'lines',
                'horizontal_strategy': 'lines',
                'snap_tolerance': 5,
            })
            if not tables:
                tables = page.extract_tables({
                    'vertical_strategy': 'text',
                    'horizontal_strategy': 'text',
                })
            current_shinku = None
            for table in tables:
                for row in table:
                    if row is None or len(row) < 9:
                        continue
                    cell0 = str(row[0] or '').strip()
                    cell2 = str(row[2] or '').strip()
                    # 診区番号を追跡
                    if cell0 in shinku_codes:
                        current_shinku = cell0
                    # 改行結合セルの場合
                    if '\n' in cell0:
                        for l in cell0.split('\n'):
                            if l.strip() in shinku_codes:
                                current_shinku = l.strip()
                    # 診区別小計行
                    if '小計' in cell2 and '\n' not in cell2 and current_shinku:
                        subtotals[current_shinku] = _parse_num(row[8])
    return subtotals


def extract_psych_items(pdf_path):
    """精神科専門PDFから主要項目別の入院金額（円）を抽出"""
    items = {}
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ''
            for line in text.split('\n'):
                if '入院精神療法（１）' in line or '入院精神療法(I)' in line or '180018110' in line:
                    nums = [_parse_num(p) for p in re.findall(r'[\d,]+', line) if _parse_num(p) > 100]
                    if nums:
                        items['入院精神療法(I)'] = _find_amount(nums)
                elif '入院精神療法（２）' in line and '６月以内' in line or '180012010' in line:
                    nums = [_parse_num(p) for p in re.findall(r'[\d,]+', line) if _parse_num(p) > 100]
                    if nums:
                        items['入院精神療法(II)(6月以内)'] = _find_amount(nums)
                elif '入院精神療法（２）' in line and '６月超' in line or '180012110' in line:
                    nums = [_parse_num(p) for p in re.findall(r'[\d,]+', line) if _parse_num(p) > 100]
                    if nums:
                        items['入院精神療法(II)(6月超)'] = _find_amount(nums)
    return items


def _find_amount(nums):
    """数値リストから入院金額を推定（2回出現する最大値 or 最大値）
    PDFの行は [数量, 数量, 金額, 金額] のように同値ペアが2組出現する。
    金額ペアは通常、数量ペアより大きいため、最大ペアを返す。
    """
    if not nums:
        return 0
    c = Counter(nums)
    pairs = [val for val, cnt in c.items() if cnt >= 2]
    if pairs:
        return max(pairs)
    return max(nums)


def extract_admission_subtotals(pdf_path):
    """入院料PDFから診区別小計（円）を抽出（単一ファイル版）"""
    return _extract_admission_subtotals_from_paths([pdf_path])


def _extract_admission_subtotals_from_paths(pdf_paths):
    """入院料PDF群から診区別小計（円）を抽出
    テキストベースで解析し、診区番号を追跡して小計行の最大値（＝入院金額）を取得。
    分割PDFの場合、全ファイルを順番に連結して解析する。
    Returns: {'90': int, '92': int, '97': int}
    """
    subtotals = {}
    current_shinku = None

    for pdf_path in pdf_paths:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ''
                for line in text.split('\n'):
                    stripped = line.strip()
                    if stripped.startswith('90 '):
                        current_shinku = '90'
                    elif stripped.startswith('92 '):
                        current_shinku = '92'
                    elif stripped.startswith('97 '):
                        current_shinku = '97'

                    if '小計' in line and current_shinku:
                        nums = [_parse_num(p) for p in re.findall(r'[\d,]+', line)]
                        large = [n for n in nums if n > 1000]
                        if large:
                            subtotals[current_shinku] = max(large)
    return subtotals


def extract_admission_items(pdf_path):
    """入院料PDFからベースアップ評価料の入院金額（円）を抽出"""
    baseup_total = 0
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ''
            for line in text.split('\n'):
                if 'ベースアップ評価料' in line:
                    nums = [_parse_num(p) for p in re.findall(r'[\d,]+', line)]
                    large = [n for n in nums if n > 100]
                    if large:
                        baseup_total += _find_amount(large)
    return baseup_total


def extract_ward_items(pdf_path):
    """病棟別PDFから加算項目別の入院金額（円）を抽出"""
    items = {}
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables({
                'vertical_strategy': 'lines',
                'horizontal_strategy': 'lines',
                'snap_tolerance': 5,
            })
            if not tables:
                tables = page.extract_tables({
                    'vertical_strategy': 'text',
                    'horizontal_strategy': 'text',
                })
            for table in tables:
                for row in table:
                    if row is None or len(row) < 8:
                        continue
                    cell0 = str(row[0] or '').strip()
                    row_text = ' '.join(str(c or '') for c in row)
                    if '診区' in row_text and 'コード' in row_text:
                        continue
                    if '小計' in row_text or '合計' in row_text:
                        continue
                    if '集計表' in row_text or '令和' in row_text:
                        continue
                    if cell0 not in ('90', '92'):
                        continue
                    name = str(row[2] or '').strip()
                    if not name:
                        continue
                    # 入院金額を取得 (index 8)
                    amt = _parse_num(row[8] if len(row) > 8 else row[-3])
                    if amt > 0:
                        items[name] = amt
    return items


def extract_exam_detail(pdf_path):
    """診察PDFから診区別サブカテゴリ（円）を抽出
    診区11=初診, 診区13=指導
    """
    detail = {'初診': 0, '指導': 0}
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ''
            current = None
            for line in text.split('\n'):
                stripped = line.strip()
                if stripped.startswith('11 '):
                    current = '初診'
                elif stripped.startswith('13 '):
                    current = '指導'
                if '小計' in line and current:
                    nums = [_parse_num(p) for p in re.findall(r'[\d,.]+', line)]
                    if len(nums) > 4:
                        detail[current] = nums[4]
    return detail


def extract_test_detail(pdf_path):
    """検査PDFからサブカテゴリ別入院金額（円）を抽出
    心電図・呼吸心拍等: ECG, EEG, 呼吸心拍監視, 脈波
    心理検査: 認知機能検査, 心理検査
    一般: それ以外
    テキスト行の数値配列(ASCII正規表現): idx0=診区, idx1=コード, idx2=点数, ..., idx7=入院金額
    """
    ecg_total = 0
    psych_test_total = 0
    general_total = 0

    ecg_keywords = ['ＥＣＧ', 'ECG', 'ＥＥＧ', 'EEG', '心電図', '呼吸心拍', '脈波', '賦活検査', '脳波']
    psych_keywords = ['認知機能検査', '心理検査', '知能検査', '発達検査']

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ''
            for line in text.split('\n'):
                stripped = line.strip()
                if not stripped.startswith('60 '):
                    continue
                if '小計' in line or '合計' in line or '810000001' in line:
                    continue
                # ASCII数字のみマッチ（全角数字を名前内で拾わないように）
                nums = [_parse_num(p) for p in re.findall(r'[0-9,.]+', line)]
                if len(nums) < 8:
                    continue
                amt = nums[7]  # 入院金額 = idx7
                if amt == 0:
                    continue

                if any(kw in line for kw in ecg_keywords):
                    ecg_total += amt
                elif any(kw in line for kw in psych_keywords):
                    psych_test_total += amt
                else:
                    general_total += amt

    return {'一般': general_total, '心電図': ecg_total, '心理': psych_test_total}


def extract_image_detail(pdf_path):
    """画像PDFからサブカテゴリ別入院金額（円）を抽出
    CT: CT撮影, コンピューター断層
    X-P: それ以外（単純撮影等）
    テキスト行の数値配列(ASCII正規表現): idx7=入院金額
    """
    ct_total = 0
    xp_total = 0
    ct_keywords = ['ＣＴ', 'CT', 'コンピューター断層', 'コンピュータ断層']

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ''
            for line in text.split('\n'):
                stripped = line.strip()
                if not stripped.startswith('70 '):
                    continue
                if '小計' in line or '合計' in line:
                    continue
                nums = [_parse_num(p) for p in re.findall(r'[0-9,.]+', line)]
                if len(nums) < 8:
                    continue
                amt = nums[7]  # 入院金額 = idx7
                if amt == 0:
                    continue

                if any(kw in line for kw in ct_keywords):
                    ct_total += amt
                else:
                    xp_total += amt

    return {'X-P': xp_total, 'CT': ct_total}


def extract_w1_detail(pdf_path):
    """入院料（全体）PDFから1病棟明細（円）を抽出
    診区92: 精神療養病棟入院料, 地域移行実施加算
    診区90: 重症者加算1, 重症者加算2(療養環境), 非定型抗精神病薬
    テキスト行の数値配列(ASCII正規表現): idx7=入院金額
    """
    items = {}

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ''
            current_shinku = None
            for line in text.split('\n'):
                stripped = line.strip()
                # 診区の追跡
                if stripped.startswith('90 '):
                    current_shinku = '90'
                elif stripped.startswith('92 '):
                    current_shinku = '92'
                elif stripped.startswith('97 '):
                    current_shinku = '97'
                elif '小計' in line or '合計' in line:
                    continue

                nums = [_parse_num(p) for p in re.findall(r'[0-9,.]+', line)]
                if len(nums) < 8:
                    continue
                amt = nums[7]  # 入院金額 = idx7
                if amt == 0:
                    continue

                if current_shinku == '92':
                    if '190055010' in line or '精神療養病棟入院料' in line:
                        items['精神療養病棟入院料'] = amt
                    elif '190127810' in line or '地域移行' in line:
                        items['地域移行実施加算'] = amt
                elif current_shinku == '90':
                    # 診区90のアイテムはコードベースで特定
                    # ※190105570は療養環境加算(3病棟)であり重症者加算2ではない
                    if '190151470' in line:
                        items['重症者加算1'] = amt
                    elif '190151270' in line:
                        items['非定型抗精神病薬'] = amt

    return items


def extract_ward_detail(pdf_path):
    """2/3病棟PDFから加算明細（円）を抽出しグループ化して返す。
    入院基本料+期間加算を合算、ベースアップ除外。
    テキスト行の数値配列(ASCII正規表現): idx7=入院金額
    """
    # コード→カテゴリのマッピング
    base_codes = {'190083810'}  # 入院基本料15:1
    period_codes = {'190085210', '190085410', '190085610', '190085710', '190085810'}  # 期間加算
    code_map = {
        '190103970': '看護補助加算',
        '190102070': '看護配置加算',
        '190832970': '看護補助体制充実',
        '190833070': '看護補助体制充実',
        '190118570': '重度認知症加算',
        '190107070': '隔離室管理加算',
        '190127910': '身体合併症管理',
        '190173110': '身体合併症管理',
        '190127810': '地域移行実施加算',
        '190101970': '特殊疾患入院施設管理',
        '190105570': '療養環境加算',
    }
    baseup_code = '180729410'

    result = {}
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ''
            for line in text.split('\n'):
                stripped = line.strip()
                if not stripped.startswith('90 '):
                    continue
                if '小計' in line or '合計' in line:
                    continue
                nums = [_parse_num(p) for p in re.findall(r'[0-9,.]+', line)]
                if len(nums) < 8:
                    continue
                amt = nums[7]
                if amt == 0:
                    continue
                # コードを取得 (nums[1]相当だがテキストから直接取得)
                code = re.findall(r'[0-9]{9}', line)
                if not code:
                    continue
                c = code[0]

                if baseup_code in line:
                    continue  # ベースアップ除外
                elif c in base_codes or c in period_codes:
                    result['入院基本料15:1(期間加算含)'] = result.get('入院基本料15:1(期間加算含)', 0) + amt
                elif c in code_map:
                    key = code_map[c]
                    result[key] = result.get(key, 0) + amt

    return result


def get_report_period(folder_path):
    """フォルダ内のPDFから対象期間を取得"""
    for fname in os.listdir(folder_path):
        if fname.endswith('.pdf'):
            fpath = os.path.join(folder_path, fname)
            try:
                with pdfplumber.open(fpath) as pdf:
                    text = pdf.pages[0].extract_text() or ''
                    m = re.search(r'令和\s*(\d+)\s*年\s*(\d+)\s*月', text)
                    if m:
                        reiwa = int(m.group(1))
                        month = int(m.group(2))
                        year = reiwa + 2018
                        return year, month
            except Exception:
                continue
    return datetime.date.today().year, datetime.date.today().month


# ======================================================================
# 2. データ組み立て
# ======================================================================

def find_pdf(folder, *candidates):
    """フォルダ内からファイル名候補でPDFを探す"""
    for name in candidates:
        path = os.path.join(folder, name)
        if os.path.exists(path):
            return path
    # グロブで探す
    for name in candidates:
        base = name.replace('.pdf', '')
        matches = glob.glob(os.path.join(folder, f'*{base}*'))
        if matches:
            return matches[0]
    return None


def find_pdfs(folder, *candidates):
    """フォルダ内からファイル名候補でPDF群を探す（分割ファイル対応）
    完全一致が1つ見つかればそれだけ返す。なければグロブで全一致を返す。
    """
    for name in candidates:
        path = os.path.join(folder, name)
        if os.path.exists(path):
            return [path]
    for name in candidates:
        base = name.replace('.pdf', '')
        matches = sorted(glob.glob(os.path.join(folder, f'{base}*.pdf')))
        if matches:
            return matches
    return []


def build_data(folder):
    """PDFフォルダから全データを組み立て"""
    data = {}

    # --- 各PDF総合計（円）--- 分割ファイル対応
    pdf_totals = {}
    pdf_map = {
        '診察': ['診察.pdf'],
        '薬剤': ['薬剤.pdf'],
        '調剤処方': ['調剤処方.pdf', '調剤.pdf'],
        '注射手技': ['注射手技.pdf', '注射.pdf'],
        '処置': ['処置.pdf'],
        '検査': ['検査.pdf'],
        '画像': ['画像.pdf'],
        '精神科専門': ['精神科専門.pdf'],
        '器材': ['器材.pdf'],
    }
    for key, fnames in pdf_map.items():
        paths = find_pdfs(folder, *fnames)
        if paths:
            total = sum(extract_grand_total(p) for p in paths)
            pdf_totals[key] = total
            if len(paths) > 1:
                print(f'  {key}: {total:>12,}円 ({len(paths)}ファイル合算)')
            else:
                print(f'  {key}: {total:>12,}円')
        else:
            pdf_totals[key] = 0
            print(f'  {key}: PDF未検出')

    # --- 薬剤 診区別小計（分割ファイル対応） ---
    drug_paths = find_pdfs(folder, '薬剤.pdf')
    drug_subtotals = {}
    for dp in drug_paths:
        subs = extract_drug_subtotals(dp)
        for k, v in subs.items():
            drug_subtotals[k] = drug_subtotals.get(k, 0) + v
    print(f'  薬剤診区別: {drug_subtotals} ({len(drug_paths)}ファイル)')

    # --- 入院料 ---
    # 単体ファイル（従来パターン: 完全一致のみ）
    adm_path = None
    for cand in ['入院料（全体）・食事.pdf', '入院料(全体)・食事.pdf',
                 '入院料（全体）・食事①.pdf', '入院料(全体)・食事①.pdf',
                 '入院料（全体）.pdf']:
        p = os.path.join(folder, cand)
        if os.path.exists(p):
            adm_path = p
            break
    adm_subtotals = {}
    adm_baseup = 0

    if adm_path:
        adm_subtotals = extract_admission_subtotals(adm_path)
        adm_baseup = extract_admission_items(adm_path)
    else:
        # 分割パターン: 入院料①.pdf + 入院料②・食事.pdf 等
        adm_split_paths = sorted(glob.glob(os.path.join(folder, '入院料*.pdf')))
        # 病棟別ファイルを除外
        adm_split_paths = [p for p in adm_split_paths
                           if '病棟' not in os.path.basename(p)]
        if adm_split_paths:
            print(f'  入院料（分割ファイル検出）: {len(adm_split_paths)}件')
            for sp in adm_split_paths:
                print(f'    → {os.path.basename(sp)}')
            # 全ファイルを連結して解析（診区が跨る場合に対応）
            adm_subtotals = _extract_admission_subtotals_from_paths(adm_split_paths)
            for sp in adm_split_paths:
                adm_baseup += extract_admission_items(sp)
            # w1_detail抽出用に最初のファイルをadm_pathに設定
            adm_path = adm_split_paths[0]

    print(f'  入院料診区別: {adm_subtotals}')
    print(f'  入院料ベースアップ: {adm_baseup:,}円')

    # 精神科専門のベースアップ（位置ベース抽出: idx7=入院金額）
    psych_path = find_pdf(folder, '精神科専門.pdf')
    psych_baseup = 0
    if psych_path:
        with pdfplumber.open(psych_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ''
                for line in text.split('\n'):
                    stripped = line.strip()
                    if 'ベースアップ' in line and stripped.startswith('80 '):
                        nums = [_parse_num(p) for p in re.findall(r'[0-9,.]+', line)]
                        if len(nums) >= 8:
                            psych_baseup += nums[7]  # 入院金額 = idx7
    print(f'  精神科ベースアップ: {psych_baseup:,}円（精神科専門から除外のみ、入院料側で計上済）')
    total_baseup = adm_baseup  # 入院料PDFのみを使用（精神科専門PDFへの計上は月により不安定）

    # --- 食事②.pdf がある場合の追加取得 ---
    food2_path = find_pdf(folder, '食事②.pdf', '食事2.pdf')
    if food2_path:
        food2_subs = extract_admission_subtotals(food2_path)
        food2_97 = food2_subs.get('97', 0)
        if food2_97 > 0:
            adm_subtotals['97'] = adm_subtotals.get('97', 0) + food2_97
            print(f'  食事②追加: {food2_97:,}円 → 食事合計: {adm_subtotals.get("97", 0):,}円')

    # --- 区分別データ（点） ---
    # 投薬 = 薬剤(内服+屯服+外用) + 調剤処方
    drug_touyaku = (drug_subtotals.get('21', 0) +
                    drug_subtotals.get('22', 0) +
                    drug_subtotals.get('23', 0))
    touyaku = _yen2pt(drug_touyaku + pdf_totals.get('調剤処方', 0))

    # 注射 = 注射手技 + 薬剤(注射+点滴)
    drug_chusha = drug_subtotals.get('31', 0) + drug_subtotals.get('33', 0)
    chusha = _yen2pt(pdf_totals.get('注射手技', 0) + drug_chusha)

    # 処置 = 処置 + 薬剤(処置薬)
    shochi = _yen2pt(pdf_totals.get('処置', 0) + drug_subtotals.get('40', 0))

    # 精神科専門（ベースアップ除く）
    seishin = _yen2pt(pdf_totals.get('精神科専門', 0) - psych_baseup)

    compare_data = {
        '診察': _yen2pt(pdf_totals.get('診察', 0)),
        '投薬（薬剤+調剤処方）': touyaku,
        '注射（手技+薬剤）': chusha,
        '処置': shochi,
        '検査': _yen2pt(pdf_totals.get('検査', 0)),
        '画像': _yen2pt(pdf_totals.get('画像', 0)),
        '精神科専門': seishin,
        'ベースアップ評価料': _yen2pt(total_baseup),
        'その他・器材': _yen2pt(pdf_totals.get('器材', 0)),
    }
    data['compare'] = compare_data

    # --- 病棟データ（点） ---
    adm90 = adm_subtotals.get('90', 0)
    adm92 = adm_subtotals.get('92', 0)
    food = adm_subtotals.get('97', 0)

    # 1病棟 = 診区92 + 診区90中の1病棟分加算
    # （重症者加算、非定型抗精神病薬加算は1病棟に帰属）
    # 概算: 全入院料(90+92) - ベースアップ - 食事 = 病棟合計
    ward_total_yen = adm90 + adm92 - adm_baseup

    # 各病棟の個別PDFから取得を試みる
    w2_path = find_pdf(folder, '入院料(2病棟）.pdf', '入院料（2病棟）.pdf',
                        '入院料(2病棟).pdf')
    w3_path = find_pdf(folder, '入院料（3病棟）.pdf', '入院料(3病棟).pdf')

    w2_total = 0
    w3_total = 0
    w2_items = {}
    w3_items = {}

    if w2_path:
        # 診区90小計のみ取得（食事97を除外）
        w2_subs = extract_admission_subtotals(w2_path)
        w2_total = w2_subs.get('90', 0)
        # ベースアップを除外
        w2_total -= extract_admission_items(w2_path)
        print(f'  2病棟: {w2_total:>12,}円')

    if w3_path:
        # 診区90小計のみ取得（食事97を除外）
        w3_subs = extract_admission_subtotals(w3_path)
        w3_total = w3_subs.get('90', 0)
        # ベースアップを除外
        w3_total -= extract_admission_items(w3_path)
        print(f'  3病棟: {w3_total:>12,}円')

    # 1病棟 = 全体 - 2病棟 - 3病棟
    w1_total = ward_total_yen - w2_total - w3_total
    print(f'  1病棟: {w1_total:>12,}円（逆算）')

    data['ward'] = {
        '1病棟（精神療養）': _yen2pt(w1_total),
        '2病棟（精神15:1）': _yen2pt(w2_total),
        '3病棟（精神15:1）': _yen2pt(w3_total),
    }
    data['food'] = _yen2pt(food)

    # --- 精神科専門 詳細（点） ---
    psych_detail = {}
    if psych_path:
        with pdfplumber.open(psych_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ''
                for line in text.split('\n'):
                    stripped = line.strip()
                    if not stripped.startswith('80 '):
                        continue
                    if '小計' in line or '合計' in line:
                        continue
                    nums = [_parse_num(p) for p in re.findall(r'[0-9,.]+', line)]
                    if len(nums) < 8:
                        continue
                    amt = nums[7]  # 入院金額 = idx7
                    if amt == 0:
                        continue
                    if '入院精神療法' in line and ('（１）' in line or '(I)' in line or '180018110' in line):
                        psych_detail['入院精神療法'] = psych_detail.get('入院精神療法', 0) + amt
                    elif '入院精神療法' in line and ('（２）' in line or '(II)' in line or '180012010' in line or '180012110' in line):
                        psych_detail['入院精神療法'] = psych_detail.get('入院精神療法', 0) + amt
                    elif '精神科作業療法' in line or '180007410' in line:
                        psych_detail['精神科作業療法'] = amt
                    elif '医療保護入院等' in line or '180026410' in line:
                        psych_detail['医療保護入院等'] = amt
                    elif '退院指導' in line and '退院前' not in line:
                        psych_detail['退院指導料'] = amt
                    elif '治療抵抗性' in line:
                        psych_detail['治療抵抗性統合失調症'] = amt
                    elif '退院前訪問' in line:
                        psych_detail['退院前訪問指導料'] = amt
                    elif 'ベースアップ' not in line:
                        if '810000001' not in line and '診区別' not in line:
                            psych_detail.setdefault('その他', 0)
                            psych_detail['その他'] += amt

    # 円→点（四捨五入）
    data['psych_detail'] = {k: _yen2pt(v) for k, v in psych_detail.items()}

    # --- サブカテゴリ詳細データ ---
    # 診察サブカテゴリ
    exam_path = find_pdf(folder, '診察.pdf')
    if exam_path:
        exam_detail_yen = extract_exam_detail(exam_path)
        data['exam_detail'] = {k: _yen2pt(v) for k, v in exam_detail_yen.items()}
    else:
        data['exam_detail'] = {'初診': 0, '指導': 0}

    # 検査サブカテゴリ（分割ファイル対応）
    test_paths = find_pdfs(folder, '検査.pdf')
    if test_paths:
        combined_test = {'一般': 0, '心電図': 0, '心理': 0}
        for tp in test_paths:
            td = extract_test_detail(tp)
            for k, v in td.items():
                combined_test[k] = combined_test.get(k, 0) + v
        data['test_detail'] = {k: _yen2pt(v) for k, v in combined_test.items()}
    else:
        data['test_detail'] = {'一般': 0, '心電図': 0, '心理': 0}

    # 画像サブカテゴリ
    image_path = find_pdf(folder, '画像.pdf')
    if image_path:
        image_detail_yen = extract_image_detail(image_path)
        data['image_detail'] = {k: _yen2pt(v) for k, v in image_detail_yen.items()}
    else:
        data['image_detail'] = {'X-P': 0, 'CT': 0}

    # 薬剤全診区横断（全subtotalの合計）
    data['drug_total'] = _yen2pt(sum(drug_subtotals.values()))

    # 調剤処方（単独）
    data['dispensing'] = _yen2pt(pdf_totals.get('調剤処方', 0))

    # 注射手技のみ
    data['injection_tech'] = _yen2pt(pdf_totals.get('注射手技', 0))

    # 器材
    data['equipment'] = _yen2pt(pdf_totals.get('器材', 0))

    # 処置（処置PDF + 薬剤処置薬）
    data['procedure'] = _yen2pt(pdf_totals.get('処置', 0) + drug_subtotals.get('40', 0))

    # 1病棟明細
    if adm_path:
        w1_detail_yen = extract_w1_detail(adm_path)
        data['w1_detail'] = {k: _yen2pt(v) for k, v in w1_detail_yen.items()}
    else:
        data['w1_detail'] = {}

    # 入院精神療法 内訳（点）
    data['psych_therapy_detail'] = []
    if psych_path:
        with pdfplumber.open(psych_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text() or ''
                for line in text.split('\n'):
                    stripped = line.strip()
                    if not stripped.startswith('80 '):
                        continue
                    nums = [_parse_num(p) for p in re.findall(r'[0-9,.]+', line)]
                    if len(nums) < 8:
                        continue
                    amt = nums[7]  # 入院金額
                    cases = nums[5]  # 入院数量
                    if amt == 0:
                        continue
                    if '180018110' in line:
                        data['psych_therapy_detail'].append(
                            ('入院精神療法(I)', cases, _yen2pt(amt)))
                    elif '180012010' in line:
                        data['psych_therapy_detail'].append(
                            ('入院精神療法(II)(6月以内)', cases, _yen2pt(amt)))
                    elif '180012110' in line:
                        data['psych_therapy_detail'].append(
                            ('入院精神療法(II)(6月超)', cases, _yen2pt(amt)))

    # 2病棟・3病棟 加算明細（点）- PDFから抽出
    if w2_path:
        w2_detail_yen = extract_ward_detail(w2_path)
        data['w2_detail'] = {k: _yen2pt(v) for k, v in w2_detail_yen.items()}
    else:
        data['w2_detail'] = {}
    if w3_path:
        w3_detail_yen = extract_ward_detail(w3_path)
        data['w3_detail'] = {k: _yen2pt(v) for k, v in w3_detail_yen.items()}
    else:
        data['w3_detail'] = {}

    # 合計
    jan_total = (sum(compare_data.values()) +
                 sum(data['ward'].values()) +
                 data['food'])
    data['total'] = jan_total

    return data


# ======================================================================
# 3. HTML サマリー生成
# ======================================================================

_COMMON_CSS = """\
@media print{@page{size:A4 portrait;margin:6mm}*{-webkit-print-color-adjust:exact!important;print-color-adjust:exact!important}body{padding:0!important;font-size:7px!important}.no-print{display:none!important}.summary-cards{gap:8px!important;margin-bottom:10px!important}.card{padding:10px!important}.card-value{font-size:18px!important}table{font-size:7.5px!important}th,td{padding:4px 5px!important}}
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:'Segoe UI','Meiryo','Noto Sans JP',sans-serif;font-size:11px;color:#1e293b;background:#f8f9fb;min-height:100vh;padding:16px}
.container{max-width:100%;margin:0 auto;background:#fff;border-radius:10px;box-shadow:0 2px 12px rgba(0,0,0,0.06);padding:20px}
.header{display:flex;flex-wrap:wrap;justify-content:space-between;align-items:center;margin-bottom:16px;padding-bottom:12px;border-bottom:1px solid #e2e8f0;gap:8px}
h1{font-size:18px;font-weight:700;color:#0f172a;display:flex;align-items:center;gap:10px}
h1::before{content:'';width:4px;height:22px;background:linear-gradient(180deg,#1e40af,#1d4ed8);border-radius:2px}
.print-date{font-size:10px;color:#64748b}
.btn-group{display:flex;gap:8px}
.btn{padding:8px 16px;color:#fff;border:none;border-radius:6px;cursor:pointer;font-size:12px;font-weight:600;transition:all 0.2s;display:flex;align-items:center;gap:5px}
.btn-print{background:linear-gradient(135deg,#1e40af,#1d4ed8)}
.btn-print:hover{transform:translateY(-1px);box-shadow:0 3px 10px rgba(30,64,175,0.3)}
.btn-save{background:linear-gradient(135deg,#047857,#059669)}
.btn-save:hover{transform:translateY(-1px);box-shadow:0 3px 10px rgba(4,120,87,0.3)}
.summary-cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin-bottom:20px}
.card{background:#fff;border-radius:8px;padding:14px;position:relative;overflow:hidden;border:1px solid #e2e8f0}
.card::before{content:'';position:absolute;top:0;left:0;right:0;height:3px}
.card-revenue::before{background:linear-gradient(90deg,#1e40af,#2563eb)}
.card-expense::before{background:linear-gradient(90deg,#c2410c,#d97706)}
.card-profit::before{background:linear-gradient(90deg,#047857,#059669)}
.card-margin::before{background:linear-gradient(90deg,#6d28d9,#7c3aed)}
.card-label{font-size:10px;color:#64748b;font-weight:500;margin-bottom:6px;display:flex;align-items:center;gap:5px}
.card-icon{width:18px;height:18px;border-radius:5px;display:flex;align-items:center;justify-content:center;font-size:10px}
.card-revenue .card-icon{background:#dbeafe;color:#1e40af}
.card-expense .card-icon{background:#ffedd5;color:#c2410c}
.card-profit .card-icon{background:#d1fae5;color:#047857}
.card-margin .card-icon{background:#ede9fe;color:#6d28d9}
.card-value{font-size:22px;font-weight:700;color:#0f172a;font-variant-numeric:tabular-nums;letter-spacing:-0.5px}
.card-sub{display:flex;align-items:center;gap:6px;margin-top:6px;font-size:10px}
.card-period{color:#94a3b8;font-size:9px}
table{width:auto;border-collapse:collapse;font-size:10px;border-radius:8px;overflow:hidden;box-shadow:0 1px 4px rgba(0,0,0,0.04)}
thead th{background:linear-gradient(135deg,#1e3a8a,#1e40af);color:#fff;padding:8px 12px;text-align:right;font-weight:600;font-size:10px;letter-spacing:0.3px}
th:first-child{text-align:left;padding-left:12px;border-radius:6px 0 0 0}
th:last-child{border-radius:0 6px 0 0}
td{padding:6px 8px;border-bottom:1px solid #f1f5f9;text-align:right;font-family:'Segoe UI',monospace;font-variant-numeric:tabular-nums;color:#334155}
td:first-child{text-align:left;padding-left:12px;font-family:'Meiryo','Noto Sans JP',sans-serif;font-weight:500;color:#1e293b}
tbody tr{background:#fff;transition:background 0.15s}
tbody tr:nth-child(even){background:#fafbfc}
tbody tr:hover{background:#f1f5f9}
.indent{padding-left:26px!important;color:#64748b;font-weight:400!important}
.indent2{padding-left:40px!important;color:#94a3b8;font-weight:400!important;font-size:9px}
.section{background:linear-gradient(90deg,#eff6ff,#f8fafc)!important}
.section td{font-weight:600}
.section td:first-child{color:#1e40af}
.subtotal{background:#f8fafc!important}
.subtotal td{font-weight:600;color:#1e3a8a}
.grand{background:linear-gradient(90deg,#ecfdf5,#f0fdf4)!important}
.grand td{font-weight:700;color:#047857}
.final{background:linear-gradient(90deg,#eff6ff,#dbeafe)!important}
.final td{font-weight:700;color:#0f172a;font-size:11px}
.negative{color:#dc2626!important}
.pct{color:#94a3b8;font-size:7.5px;display:block;margin-top:1px}
tbody tr:last-child td:first-child{border-radius:0 0 0 6px}
tbody tr:last-child td:last-child{border-radius:0 0 6px 0}
"""


def _man_yen(yen):
    """83595442 -> '8,360万円'"""
    return f'{round(yen / 10000):,}万円'


def _pt_row(label, points, total, cls='', td_cls=''):
    """点数ベースのテーブル行を生成"""
    pct = f'{points / total * 100:.1f}%' if total and points else ''
    yen_span = f'<span class="pct">{points * 10:,}円</span>' if points >= 100 else ''
    tr = f' class="{cls}"' if cls else ''
    td = f' class="{td_cls}"' if td_cls else ''
    return f'  <tr{tr}><td{td}>{label}</td><td>{points:,}{yen_span}</td><td>{pct}</td></tr>'


def _build_row_items(data):
    """1ヶ月分のdataから表示行リスト [(label, value, cls, td_cls), ...] を返す"""
    total = data['total']
    items = []
    simple_cats = [
        ('診察', '診察'), ('投薬', '投薬（薬剤+調剤処方）'),
        ('注射', '注射（手技+薬剤）'), ('処置', '処置'),
        ('検査', '検査'), ('画像', '画像'),
    ]
    for disp, key in simple_cats:
        items.append((disp, data['compare'].get(key, 0), '', ''))
    items.append(('精神科専門', data['compare'].get('精神科専門', 0), 'section', ''))
    for name, val in data.get('psych_detail', {}).items():
        items.append((name, val, '', 'indent'))
        if name == '入院精神療法':
            for tname, cases, amt in data.get('psych_therapy_detail', []):
                short = tname.replace('入院精神療法', '')
                items.append((short, amt, '', 'indent2'))
    items.append(('ベースアップ評価料', data['compare'].get('ベースアップ評価料', 0), '', ''))
    items.append(('その他・器材', data['compare'].get('その他・器材', 0), '', ''))
    ward_names = [
        ('1病棟（精神療養）', '入院料（1病棟：精神療養）', 'w1_detail'),
        ('2病棟（精神15:1）', '入院料（2病棟：15対1）', 'w2_detail'),
        ('3病棟（精神15:1）', '入院料（3病棟：15対1）', 'w3_detail'),
    ]
    for wkey, wlabel, detail_key in ward_names:
        items.append((wlabel, data['ward'].get(wkey, 0), 'section', ''))
        for iname, ival in data.get(detail_key, {}).items():
            items.append((iname, ival, '', 'indent'))
    items.append(('入院料 小計', sum(data['ward'].values()), 'subtotal', ''))
    items.append(('食事 小計', data['food'], 'subtotal', ''))
    items.append(('合計', total, 'grand', ''))
    return items


def generate_html_summary(all_months_data, report_date, output_dir):
    """全月分のデータから入院収益月次サマリーHTMLを生成"""
    import html as _html

    months = sorted(all_months_data.keys())
    latest = months[-1]
    latest_data = all_months_data[latest]
    latest_total = latest_data['total']

    # 行定義（全月の和集合、順序は最新月ベース＋不足分を追加）
    row_items = _build_row_items(latest_data)
    seen_labels = set(label for label, _, _, _ in row_items)
    for m in months:
        for label, val, cls, td_cls in _build_row_items(all_months_data[m]):
            if label not in seen_labels:
                # 合計行の手前に挿入
                for i, (rl, _, _, _) in enumerate(row_items):
                    if rl == '入院料 小計':
                        row_items.insert(i, (label, 0, cls, td_cls))
                        break
                else:
                    row_items.append((label, 0, cls, td_cls))
                seen_labels.add(label)

    # テーブルヘッダー
    month_headers = ''.join(f'<th>{m}月</th>' for m in months)

    # テーブル行
    rows = []
    for label, _, cls, td_cls in row_items:
        tr_cls = f' class="{cls}"' if cls else ''
        td_c = f' class="{td_cls}"' if td_cls else ''
        cells = []
        for m in months:
            m_data = all_months_data[m]
            m_items = _build_row_items(m_data)
            val = 0
            for rl, rv, _, _ in m_items:
                if rl == label:
                    val = rv
                    break
            cells.append(f'<td>{val:,}</td>' if val else '<td>-</td>')
        rows.append(f'  <tr{tr_cls}><td{td_c}>{_html.escape(label)}</td>{"".join(cells)}</tr>')

    table_body = '\n'.join(rows)
    period_label = f'{months[0]}〜{latest}月' if len(months) > 1 else f'{latest}月'
    save_name = '入院収益月次サマリー.html'

    html_text = f"""\
<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<title>さきがけホスピタル 入院収益月次サマリー {period_label}</title>
<style>
{_COMMON_CSS}</style>
</head>
<body>
<div class="container">

<div class="header">
  <h1>さきがけホスピタル 入院収益月次サマリー</h1>
  <div class="btn-group no-print">
    <button class="btn btn-print" onclick="window.print()">印刷 / PDF</button>
  </div>
  <div class="print-date">{report_date}作成</div>
</div>

<table>
<thead>
  <tr>
    <th>項目（点）</th>
    {month_headers}
  </tr>
</thead>
<tbody>
{table_body}
</tbody>
</table>

</div>
</body>
</html>
"""

    html_path = os.path.join(output_dir, save_name)
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html_text)
    return html_path


# ======================================================================
# 4. メイン処理
# ======================================================================

def main():
    print('=' * 60)
    print('入院収益月次レポート自動生成')
    print('=' * 60)

    # 全月フォルダを走査
    all_months_data = {}
    month_dirs = []
    for entry in os.listdir(BASE_DIR):
        m = re.match(r'^(\d{1,2})月$', entry)
        if m and os.path.isdir(os.path.join(BASE_DIR, entry)):
            source = os.path.join(BASE_DIR, entry, '元データ')
            if os.path.isdir(source) and any(f.endswith('.pdf') for f in os.listdir(source)):
                month_dirs.append((int(m.group(1)), entry, source))

    # CLI引数で単月指定の場合
    if len(sys.argv) > 1:
        folder = os.path.join(BASE_DIR, sys.argv[1])
        if not os.path.isdir(folder):
            print(f'ERROR: フォルダが見つかりません: {folder}')
            return
        year, month = get_report_period(folder)
        print(f'対象: {year}年{month}月 ({folder})')
        data = build_data(folder)
        all_months_data[month] = data
    else:
        for month_num, entry, source in sorted(month_dirs):
            print(f'\n--- {entry} ---')
            year, month = get_report_period(source)
            data = build_data(source)
            all_months_data[month_num] = data
            print(f'  合計: {data["total"]:>10,}点')

    if not all_months_data:
        print('ERROR: データが見つかりません')
        return

    latest_month = max(all_months_data.keys())
    report_date = f'令和{datetime.date.today().year - 2018}年{datetime.date.today().month}月{datetime.date.today().day}日'

    # HTML生成（診療/ルートに出力）
    print('\nHTML生成中...')
    html_path = generate_html_summary(all_months_data, report_date, BASE_DIR)
    # 旧月別ファイルを削除
    for m in all_months_data.keys():
        old = os.path.join(BASE_DIR, f'{m}月', f'入院収益月次サマリー_{m}月.html')
        if os.path.isfile(old):
            os.remove(old)
            print(f'  旧ファイル削除: {old}')
    print(f'OK: {html_path}')

    print(f'\n--- 集計 ---')
    for m in sorted(all_months_data.keys()):
        d = all_months_data[m]
        print(f'  {m}月: {d["total"]:>10,}点 ({d["total"] * 10:>12,}円)')


if __name__ == '__main__':
    main()
