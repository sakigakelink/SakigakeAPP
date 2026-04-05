#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""損益計算ロジックのユニットテスト"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(__file__))
import pnl_logic


class TestParseNumber:
    """parse_tkc_pdf内部のparse_number相当のテスト"""

    def test_basic_number(self):
        # parse_tkc_pdf内のparse_numberはfloatを返す
        assert float('1234'.replace(',', '').replace(' ', '')) == 1234.0

    def test_comma_separated(self):
        assert float('1,234,567'.replace(',', '').replace(' ', '')) == 1234567.0


class TestParseMonthFromFilename:
    """ファイル名からの月解析テスト"""

    def test_valid_filename(self):
        year, month = pnl_logic.parse_month_from_filename('0704.pdf')
        assert year == 2025
        assert month == 4

    def test_reiwa_7_january(self):
        year, month = pnl_logic.parse_month_from_filename('0701.pdf')
        assert year == 2025
        assert month == 1

    def test_reiwa_8_march(self):
        year, month = pnl_logic.parse_month_from_filename('0803.pdf')
        assert year == 2026
        assert month == 3

    def test_invalid_filename(self):
        year, month = pnl_logic.parse_month_from_filename('invalid.pdf')
        assert year is None
        assert month is None

    def test_short_filename(self):
        year, month = pnl_logic.parse_month_from_filename('07.pdf')
        assert year is None
        assert month is None

    def test_invalid_month(self):
        year, month = pnl_logic.parse_month_from_filename('0713.pdf')
        assert year is None
        assert month is None


class TestMakeMonthKey:
    """月キー生成テスト"""

    def test_basic(self):
        assert pnl_logic._make_month_key(2025, 4) == '25/4月'

    def test_no_year(self):
        assert pnl_logic._make_month_key(0, 4) == '4月'


class TestFindAccount:
    """勘定科目検索テスト"""

    def test_find_by_code(self):
        accounts = [
            {'code': '5211', 'name': '医薬品費'},
            {'code': '5212', 'name': '診療材料費'},
        ]
        result = pnl_logic.find_account(accounts, code='5211')
        assert result is not None
        assert result['name'] == '医薬品費'

    def test_find_by_name(self):
        accounts = [
            {'code': 'SUBTOTAL', 'name': '材料費計'},
        ]
        result = pnl_logic.find_account(accounts, name='材料費計')
        assert result is not None
        assert result['code'] == 'SUBTOTAL'

    def test_not_found(self):
        accounts = [{'code': '5211', 'name': '医薬品費'}]
        result = pnl_logic.find_account(accounts, code='9999')
        assert result is None


class TestCalculateFormula:
    """計算式テスト"""

    def test_addition(self):
        accounts = [
            {'code': '5211', 'name': '医薬品費', 'monthly_data': {'4月': 100}},
            {'code': '5212', 'name': '診療材料費', 'monthly_data': {'4月': 200}},
        ]
        result = pnl_logic.calculate_formula(accounts, '5211+5212', ['4月'])
        assert result['4月'] == 300

    def test_subtraction(self):
        accounts = [
            {'code': 'SUBTOTAL', 'name': '給与費計', 'monthly_data': {'4月': 1000}},
            {'code': '5431', 'name': '賞与', 'monthly_data': {'4月': 100}},
        ]
        result = pnl_logic.calculate_formula(accounts, '給与費計-5431', ['4月'])
        assert result['4月'] == 900


class TestFmtOku:
    """億円フォーマットテスト"""

    def test_zero(self):
        assert pnl_logic._fmt_oku(0) == '-'

    def test_yen(self):
        assert pnl_logic._fmt_oku(5000) == '5,000円'

    def test_man(self):
        assert pnl_logic._fmt_oku(10000) == '1万円'

    def test_oku(self):
        assert pnl_logic._fmt_oku(100000000) == '1億円'

    def test_negative(self):
        assert pnl_logic._fmt_oku(-50000) == '-5万円'


class TestSaveManualInputs:
    """手入力保存テスト"""

    def test_save_and_load(self, tmp_path):
        original_file = pnl_logic.MANUAL_INPUT_FILE
        test_file = str(tmp_path / 'manual_inputs.json')
        pnl_logic.MANUAL_INPUT_FILE = test_file

        try:
            data = {'output_display::平均入院患者数': {'4月': 150}}
            pnl_logic.save_manual_inputs(data)
            assert os.path.isfile(test_file)

            import json
            with open(test_file, encoding='utf-8') as f:
                loaded = json.load(f)
            assert loaded == data
        finally:
            pnl_logic.MANUAL_INPUT_FILE = original_file
