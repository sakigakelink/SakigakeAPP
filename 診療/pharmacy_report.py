#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""薬剤月次レポート生成スクリプト

精神科病院の入院帳票PDF（薬剤.pdf）から薬剤データを自動抽出し、
薬効分類別に集計した月次HTMLレポートを生成する。

使用法:
    python pharmacy_report.py [月フォルダ]

出力:
    薬剤月次サマリー_X月.html
"""

import os
import re
import sys
import json
import logging
import datetime
import unicodedata
from collections import defaultdict

import pdfplumber
import glob as _glob

logger = logging.getLogger(__name__)

# ======================================================================
# パス定義
# ======================================================================
_CODE_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_CODE_DIR)
BASE_DIR = os.path.join(_PROJECT_ROOT, 'shared', '診療')

# ======================================================================
# 薬効分類マッピング辞書（JSONファイルから読み込み）
# ======================================================================
_drug_class_path = os.path.join(_CODE_DIR, 'drug_classification.json')
try:
    with open(_drug_class_path, encoding='utf-8') as _f:
        _drug_class_data = json.load(_f)
    DRUG_CLASSIFICATION = _drug_class_data['classification']
    CLASSIFICATION_ORDER = _drug_class_data['order']
except (FileNotFoundError, ValueError, KeyError):
    # フォールバック: JSONが見つからない場合は空で起動
    logger.warning("drug_classification.json not found, using empty classification")
    DRUG_CLASSIFICATION = {}
    CLASSIFICATION_ORDER = ['その他']


# 診区コード → 名称
SHINKU_MAP = {
    '21': '内服', '22': '屯服', '23': '外用',
    '31': '注射', '33': '点滴', '40': '処置薬',
}

# ======================================================================
# 1. PDF解析モジュール
# ======================================================================

def parse_number(text):
    """カンマ付き数値文字列をfloatに変換"""
    if text is None:
        return 0.0
    text = str(text).strip().replace(',', '').replace(' ', '')
    if text in ('', '-', '―'):
        return 0.0
    try:
        return float(text)
    except ValueError:
        return 0.0


def extract_drugs_from_pdf(pdf_path):
    """薬剤.pdfからデータを抽出しリストで返す。

    Returns:
        list[dict]: 各薬剤のデータ辞書。キー:
            shinku, code, name, unit_price,
            outpatient_qty, inpatient_qty, total_qty,
            outpatient_amt, inpatient_amt, total_amt, ratio
    """
    drugs = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            tables = page.extract_tables({
                'vertical_strategy': 'lines',
                'horizontal_strategy': 'lines',
                'snap_tolerance': 5,
            })
            if not tables:
                # lines ベースでテーブルが見つからない場合 text ベースにフォールバック
                tables = page.extract_tables({
                    'vertical_strategy': 'text',
                    'horizontal_strategy': 'text',
                    'snap_tolerance': 5,
                })
            for table in tables:
                for row in table:
                    if row is None or len(row) < 8:
                        continue

                    # ヘッダー行・小計行・合計行をスキップ
                    cell0 = str(row[0] or '').strip()
                    row_text = ' '.join(str(c or '') for c in row)
                    if '診区' in cell0 and 'コード' in row_text:
                        continue
                    if '小計' in row_text or '合計' in row_text:
                        continue
                    if '診療行為' in row_text or '集計表' in row_text:
                        continue
                    if '令和' in row_text and '月' in row_text and len(cell0) <= 2:
                        continue

                    # 診区コードが21,22,23,31,33,40のいずれかであること
                    if cell0 not in ('21', '22', '23', '31', '33', '40'):
                        continue

                    # コード列が数値的かチェック
                    code_str = str(row[1] or '').strip().replace(' ', '')
                    if not code_str or not any(c.isdigit() for c in code_str):
                        continue

                    # 薬名を取得
                    name = str(row[2] or '').strip()
                    if not name:
                        continue

                    # 列数に応じてパース
                    # 期待: [診区, コード, 薬名, 単価, 外来使用量, 入院使用量, 合計使用量,
                    #         外来金額, 入院金額, 合計金額, 全体比率]
                    # PDFのテーブル抽出では列数が変動する場合がある
                    if len(row) >= 11:
                        drug = {
                            'shinku': cell0,
                            'code': code_str,
                            'name': name,
                            'unit_price': parse_number(row[3]),
                            'outpatient_qty': parse_number(row[4]),
                            'inpatient_qty': parse_number(row[5]),
                            'total_qty': parse_number(row[6]),
                            'outpatient_amt': parse_number(row[7]),
                            'inpatient_amt': parse_number(row[8]),
                            'total_amt': parse_number(row[9]),
                            'ratio': parse_number(row[10]),
                        }
                    elif len(row) >= 10:
                        drug = {
                            'shinku': cell0,
                            'code': code_str,
                            'name': name,
                            'unit_price': parse_number(row[3]),
                            'outpatient_qty': parse_number(row[4]),
                            'inpatient_qty': parse_number(row[5]),
                            'total_qty': parse_number(row[6]),
                            'outpatient_amt': parse_number(row[7]),
                            'inpatient_amt': parse_number(row[8]),
                            'total_amt': parse_number(row[9]),
                            'ratio': 0.0,
                        }
                    else:
                        # 最低限の列だけ取れた場合
                        drug = {
                            'shinku': cell0,
                            'code': code_str,
                            'name': name,
                            'unit_price': parse_number(row[3]) if len(row) > 3 else 0,
                            'outpatient_qty': 0,
                            'inpatient_qty': parse_number(row[4]) if len(row) > 4 else 0,
                            'total_qty': parse_number(row[5]) if len(row) > 5 else 0,
                            'outpatient_amt': 0,
                            'inpatient_amt': parse_number(row[6]) if len(row) > 6 else 0,
                            'total_amt': parse_number(row[7]) if len(row) > 7 else 0,
                            'ratio': 0.0,
                        }

                    drugs.append(drug)

    # 重複除去（同一コード+診区の重複がページ跨ぎで発生する場合）
    seen = set()
    unique_drugs = []
    for d in drugs:
        key = (d['shinku'], d['code'])
        if key not in seen:
            seen.add(key)
            unique_drugs.append(d)

    return unique_drugs


# ======================================================================
# 2. 薬効分類モジュール
# ======================================================================

def normalize_text(text):
    """全角英数字を半角に正規化（Ｓ→S, ０→0等）"""
    return unicodedata.normalize('NFKC', text)


def strip_maker_name(name):
    """後発品の社名（「メーカー名」「メーカー名）を除去"""
    import re
    return re.sub(r'[「\uFF62][^」\uFF63]*[」\uFF63]?\s*$', '', name).rstrip()


def classify_drug(drug_name):
    """薬名から薬効分類を返す。マッチしなければ'その他'。"""
    normalized = normalize_text(drug_name)
    for category, keywords in DRUG_CLASSIFICATION.items():
        for kw in keywords:
            if kw in drug_name or kw in normalized:
                return category
    return 'その他'


def classify_all_drugs(drugs):
    """全薬剤に分類を付与してdictに'classification'キーを追加。"""
    for d in drugs:
        d['classification'] = classify_drug(d['name'])
    return drugs


# ======================================================================
# 3. 集計ロジック
# ======================================================================

def aggregate_by_classification(drugs):
    """薬効分類ごとに入院金額を集計。

    Returns:
        dict: {分類名: {'total_amt': 金額合計, 'drugs': [drug, ...], 'count': 件数}}
    """
    result = defaultdict(lambda: {'total_amt': 0, 'drugs': [], 'count': 0})
    for d in drugs:
        cat = d['classification']
        result[cat]['total_amt'] += d['inpatient_amt']
        result[cat]['drugs'].append(d)
        result[cat]['count'] += 1
    return dict(result)


def get_report_month_from_pdf(pdf_path):
    """PDFの表紙から対象月を取得。失敗時は現在月-1。"""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = pdf.pages[0].extract_text() or ''
            # 「令和X年Y月」パターンを探す
            m = re.search(r'令和(\d+)年(\d+)月', text)
            if m:
                reiwa_year = int(m.group(1))
                month = int(m.group(2))
                western_year = reiwa_year + 2018
                return western_year, month
    except Exception:
        pass
    # フォールバック: 先月
    today = datetime.date.today()
    first = today.replace(day=1)
    prev = first - datetime.timedelta(days=1)
    return prev.year, prev.month




# ======================================================================
# HTML サマリー生成
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
    """1650865 -> '165万円'"""
    return f'{round(yen / 10000):,}万円'


def _yen_row(label, amt, total, cls='', td_cls='', qty=None):
    """円ベースのテーブル行を生成"""
    import html as _html
    pct = f'{amt / total * 100:.1f}%' if total and amt else ''
    tr = f' class="{cls}"' if cls else ''
    td = f' class="{td_cls}"' if td_cls else ''
    qty_cell = f'{qty:,.1f}'.rstrip('0').rstrip('.') if qty else ''
    return f'  <tr{tr}><td{td}>{_html.escape(str(label))}</td><td>{qty_cell}</td><td>{amt:,.0f}<span class="pct">円</span></td><td>{pct}</td></tr>'


def generate_drug_html(agg, drugs, grand_total, year, month):
    """薬剤月次サマリーHTMLを生成"""
    import html as _html

    report_date = f'令和{year - 2018}年{datetime.date.today().month}月{datetime.date.today().day}日'

    # 精神科薬剤合計
    psych_categories = [
        '抗精神病薬（非定型）', '抗精神病薬（定型）', '抗うつ薬', '睡眠薬',
        '抗不安薬', '気分安定薬・抗てんかん薬', '抗パーキンソン薬', 'ADHD治療薬',
        '認知症治療薬',
    ]
    psych_total = sum(agg.get(c, {}).get('total_amt', 0) for c in psych_categories)
    psych_pct = psych_total / grand_total * 100 if grand_total else 0

    # 品目数
    unique_drugs = len(set(d['name'] for d in drugs))

    # 非精神科薬剤
    non_psych_total = grand_total - psych_total
    non_psych_pct = non_psych_total / grand_total * 100 if grand_total else 0

    # --- テーブル行 ---
    rows = []
    for cat in CLASSIFICATION_ORDER:
        cat_data = agg.get(cat, {})
        if not cat_data or cat_data['total_amt'] == 0:
            continue
        # セクション行
        rows.append(_yen_row(cat, cat_data['total_amt'], grand_total, cls='section'))
        # 全品目（薬剤名順）
        sorted_drugs = sorted(cat_data['drugs'],
                              key=lambda d: d['name'])
        for d in sorted_drugs:
            if d['inpatient_amt'] > 0:
                shinku_label = SHINKU_MAP.get(d['shinku'], d['shinku'])
                display_name = strip_maker_name(d['name'])
                label = f'[{shinku_label}] {display_name}'
                rows.append(_yen_row(label, d['inpatient_amt'], grand_total,
                                     td_cls='indent',
                                     qty=d.get('inpatient_qty', 0)))

    # 合計
    rows.append(f'  <tr class="grand"><td>合計</td><td></td><td>{grand_total:,.0f}'
                f'<span class="pct">円</span></td><td>100.0%</td></tr>')

    table_body = '\n'.join(rows)
    save_name = f'薬剤月次サマリー_{month}月.html'

    html_text = f"""\
<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="UTF-8">
<title>さきがけホスピタル 薬剤月次サマリー {month}月度</title>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Noto+Sans+JP:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
{_COMMON_CSS}</style>
</head>
<body>
<div class="container">

<div class="header">
  <h1>さきがけホスピタル 薬剤月次サマリー {month}月度</h1>
  <div class="btn-group no-print">
    <button class="btn btn-save" onclick="saveHTML()">💾 HTMLを保存</button>
    <button class="btn btn-print" onclick="window.print()">🖨️ 印刷 / PDF</button>
  </div>
  <div class="print-date">{report_date}作成</div>
</div>

<div class="summary-cards">
  <div class="card card-revenue">
    <div class="card-label"><span class="card-icon">💊</span>入院薬剤費合計</div>
    <div class="card-value">{_man_yen(grand_total)}</div>
    <div class="card-sub"><span class="card-period">{grand_total:,.0f}円</span></div>
  </div>
  <div class="card card-expense">
    <div class="card-label"><span class="card-icon">🧠</span>精神科薬剤</div>
    <div class="card-value">{_man_yen(psych_total)}</div>
    <div class="card-sub"><span class="card-period">{psych_total:,.0f}円 ／ 構成比 {psych_pct:.1f}%</span></div>
  </div>
  <div class="card card-profit">
    <div class="card-label"><span class="card-icon">💉</span>品目数</div>
    <div class="card-value">{unique_drugs}</div>
    <div class="card-sub"><span class="card-period">全{len(drugs)}レコード</span></div>
  </div>
  <div class="card card-margin">
    <div class="card-label"><span class="card-icon">📊</span>その他薬剤</div>
    <div class="card-value">{_man_yen(non_psych_total)}</div>
    <div class="card-sub"><span class="card-period">{non_psych_total:,.0f}円 ／ 構成比 {non_psych_pct:.1f}%</span></div>
  </div>
</div>

<table>
<thead>
  <tr>
    <th>薬効分類</th>
    <th>使用量</th>
    <th>金額（円）</th>
    <th>構成比</th>
  </tr>
</thead>
<tbody>
{table_body}
</tbody>
</table>

</div>

<script>
function saveHTML(){{
  const h=document.documentElement.outerHTML;
  const b=new Blob([h],{{type:'text/html;charset=utf-8'}});
  const u=URL.createObjectURL(b);
  const a=document.createElement('a');
  a.href=u;
  a.download='{save_name}';
  a.click();
  URL.revokeObjectURL(u);
}}
</script>
</body>
</html>
"""

    month_dir = os.path.join(BASE_DIR, f'{month}月')
    if not os.path.isdir(month_dir):
        month_dir = BASE_DIR
    html_path = os.path.join(month_dir, save_name)
    tmp_path = html_path + '.tmp'
    with open(tmp_path, 'w', encoding='utf-8') as f:
        f.write(html_text)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_path, html_path)
    return html_path


# ======================================================================
# PDFフォルダ自動検出
# ======================================================================

def find_drug_pdfs(base_dir, month_arg=None):
    """薬剤PDFのパスを自動検出する。

    Args:
        base_dir: プロジェクトルート
        month_arg: CLI引数（例: '2月', '2月/2月'）。Noneなら自動検出。

    Returns:
        tuple: (pdf_paths, month_dir) or (None, None) if not found
    """
    if month_arg:
        # 明示指定
        folder = os.path.join(base_dir, month_arg)
        pdf_paths = _find_pdfs_in_folder(folder)
        if pdf_paths:
            return pdf_paths, _get_month_dir(base_dir, month_arg)
        month_dir = _get_month_dir(base_dir, month_arg)
        # 「薬剤（全体）」を含むフォルダを優先的に探索（包括病棟データ含む）
        pdf_paths = _find_zentai_pdfs(folder)
        if pdf_paths:
            return pdf_paths, month_dir
        # その他サブフォルダも探索
        for sub in os.listdir(folder) if os.path.isdir(folder) else []:
            sub_path = os.path.join(folder, sub)
            if os.path.isdir(sub_path) and '薬剤（全体）' not in sub:
                pdf_paths = _find_pdfs_in_folder(sub_path)
                if pdf_paths:
                    return pdf_paths, month_dir
        return None, None

    # 自動検出: 月名フォルダを新しい順に探索
    month_dirs = []
    for name in os.listdir(base_dir):
        full = os.path.join(base_dir, name)
        if os.path.isdir(full) and re.match(r'^\d{1,2}月$', name):
            m = int(re.match(r'^(\d{1,2})月$', name).group(1))
            month_dirs.append((m, name, full))

    for _, name, full in sorted(month_dirs, key=lambda x: x[0], reverse=True):
        # 直下を探索
        pdf_paths = _find_pdfs_in_folder(full)
        if pdf_paths:
            return pdf_paths, full
        # 「薬剤（全体）」を含むフォルダを優先的に探索（包括病棟データ含む）
        pdf_paths = _find_zentai_pdfs(full)
        if pdf_paths:
            return pdf_paths, full
        # その他サブフォルダ（例: 2月/2月/, 1月/元データ/）
        for sub in sorted(os.listdir(full)):
            sub_path = os.path.join(full, sub)
            if os.path.isdir(sub_path) and '薬剤（全体）' not in sub:
                pdf_paths = _find_pdfs_in_folder(sub_path)
                if pdf_paths:
                    return pdf_paths, full
    return None, None


def _find_zentai_pdfs(folder, depth=0):
    """「薬剤（全体）」を含むサブフォルダを再帰的に探索してPDFを返す"""
    if depth > 3 or not os.path.isdir(folder):
        return []
    for sub in os.listdir(folder):
        sub_path = os.path.join(folder, sub)
        if os.path.isdir(sub_path) and '薬剤（全体）' in sub:
            pdf_paths = _find_pdfs_in_folder(sub_path)
            if pdf_paths:
                return pdf_paths
            # さらにネストされている場合（例: R8.1薬剤（全体）/R8.1薬剤（全体）/）
            result = _find_zentai_pdfs(sub_path, depth + 1)
            if result:
                return result
    return []


def _find_pdfs_in_folder(folder):
    """フォルダ内の薬剤PDFを検出"""
    if not os.path.isdir(folder):
        return []
    single = os.path.join(folder, '薬剤.pdf')
    if os.path.exists(single):
        return [single]
    found = sorted(_glob.glob(os.path.join(folder, '薬剤*.pdf')))
    if found:
        return found
    # 「全体薬剤①.pdf」等のパターンにも対応
    found = sorted(_glob.glob(os.path.join(folder, '*薬剤*.pdf')))
    return found if found else []


def _get_month_dir(base_dir, month_arg):
    """月ディレクトリのパスを返す（X月 レベル）"""
    parts = month_arg.replace('\\', '/').split('/')
    return os.path.join(base_dir, parts[0])


def get_month_from_folder(month_dir):
    """フォルダ名から対象月を取得。例: '1月' → 1, '2月' → 2"""
    folder_name = os.path.basename(month_dir)
    m = re.match(r'^(\d{1,2})月$', folder_name)
    if m:
        return int(m.group(1))
    return None


# ======================================================================
# メイン処理
# ======================================================================

def main():
    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
    logger.info('=' * 60)
    logger.info('薬剤月次レポート生成')
    logger.info('=' * 60)

    # 1. PDF検出
    month_arg = sys.argv[1] if len(sys.argv) > 1 else None
    pdf_paths, month_dir = find_drug_pdfs(BASE_DIR, month_arg)

    if not pdf_paths:
        target = month_arg or '(自動検出)'
        logger.error('薬剤PDFが見つかりません: %s', target)
        return

    logger.info('対象フォルダ: %s', month_dir)

    # 2. PDF解析
    drugs = []
    for pp in pdf_paths:
        logger.info('PDF読み込み: %s', os.path.basename(pp))
        d = extract_drugs_from_pdf(pp)
        logger.info('  → %d件', len(d))
        drugs.extend(d)

    # 複数ファイルからの重複除去（ページ境界の重複を排除）
    seen = set()
    unique_drugs = []
    for d in drugs:
        key = (d['shinku'], d['code'])
        if key not in seen:
            seen.add(key)
            unique_drugs.append(d)
    drugs = unique_drugs
    logger.info('  抽出薬剤数（重複除去後）: %d件', len(drugs))

    if not drugs:
        logger.error('薬剤データを抽出できませんでした。')
        return

    # 3. 薬効分類
    classify_all_drugs(drugs)

    # 4. 集計
    agg = aggregate_by_classification(drugs)
    grand_total = sum(d['inpatient_amt'] for d in drugs)

    logger.info('  入院金額合計: %s円', f'{grand_total:,.0f}')
    logger.info('  分類数: %d', len(agg))
    for cat in CLASSIFICATION_ORDER:
        data = agg.get(cat, {})
        if data:
            logger.info('    %s: %s円 (%d品目)', cat, f'{data["total_amt"]:>12,.0f}', data["count"])

    # 対象月（フォルダ名優先、フォールバックはPDF内テキスト）
    folder_month = get_month_from_folder(month_dir)
    pdf_year, pdf_month = get_report_month_from_pdf(pdf_paths[0])
    if folder_month:
        month = folder_month
        year = pdf_year  # 年はPDFから取得（フォルダ名に年情報がないため）
        # PDFの月がフォルダ月+1の場合は請求月のため、年を調整
        if pdf_month == folder_month + 1 or (folder_month == 12 and pdf_month == 1):
            year = pdf_year if pdf_month != 1 else pdf_year - 1
    else:
        year, month = pdf_year, pdf_month
    current_ym = f'{year}-{month:02d}'
    logger.info('  対象月: %d年%d月', year, month)

    # 5. HTML生成
    logger.info('薬剤HTML生成中...')
    html_path = generate_drug_html(agg, drugs, grand_total, year, month)
    logger.info('OK: %s', html_path)

    # 6. JSONデータ保存（キャッシュ + sources記録）
    source_map = {}
    for pp in pdf_paths:
        rel = os.path.relpath(pp, month_dir)
        source_map[rel] = round(os.path.getmtime(pp), 2)
    json_data = {
        'sources': source_map,
        'year': year,
        'month': month,
        'grand_total': grand_total,
        'record_count': len(drugs),
        'unique_drugs': len(drugs),
        'categories': {cat: agg[cat]['total_amt'] for cat in CLASSIFICATION_ORDER if cat in agg},
    }
    json_path = os.path.join(month_dir, f'薬剤月次データ_{month}月.json')
    tmp_json = json_path + '.tmp'
    with open(tmp_json, 'w', encoding='utf-8') as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_json, json_path)
    logger.info('JSON: %s', json_path)

    # 検証
    total_classified = sum(
        len(agg.get(c, {}).get('drugs', [])) for c in CLASSIFICATION_ORDER
    )
    logger.info('--- 検証 ---')
    logger.info('  全薬剤数: %d', len(drugs))
    logger.info('  分類済み: %d', total_classified)
    logger.info('  入院金額合計: %s円', f'{grand_total:,.0f}')
    logger.info('  PDFファイル数: %d', len(pdf_paths))


if __name__ == '__main__':
    main()
