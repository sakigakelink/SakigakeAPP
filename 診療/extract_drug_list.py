#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""院内採用薬リストをPDFから抽出してJSONで出力"""
import sys
import os
import json

sys.stdout.reconfigure(encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pharmacy_report import extract_drugs_from_pdf, SHINKU_MAP
import glob

base = os.path.dirname(os.path.abspath(__file__))
folder = os.path.join(base, '2月', '元データ')

all_drugs = []
for pdf_file in sorted(glob.glob(os.path.join(folder, '薬剤*.pdf'))):
    drugs = extract_drugs_from_pdf(pdf_file)
    all_drugs.extend(drugs)

# 内服(21)・屯服(22)のみ抽出
oral_drugs = [d for d in all_drugs if d['shinku'] in ('21', '22')]

# 薬名の重複除去
seen = set()
unique = []
for d in oral_drugs:
    if d['name'] not in seen:
        seen.add(d['name'])
        unique.append({
            'name': d['name'],
            'shinku': SHINKU_MAP.get(d['shinku'], d['shinku']),
            'code': d['code'],
        })

unique.sort(key=lambda x: x['name'])
print(json.dumps(unique, ensure_ascii=False, indent=2))
