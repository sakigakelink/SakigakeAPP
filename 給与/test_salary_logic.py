#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""給与分析ロジックのユニットテスト"""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(__file__))
import salary_logic


class TestParseNumber:
    """数値パーステスト"""

    def test_basic(self):
        assert salary_logic.parse_number('1234') == 1234

    def test_comma(self):
        assert salary_logic.parse_number('1,234,567') == 1234567

    def test_triangle_minus(self):
        assert salary_logic.parse_number('△500') == -500

    def test_filled_triangle(self):
        assert salary_logic.parse_number('▲1,000') == -1000

    def test_empty(self):
        assert salary_logic.parse_number('') == 0

    def test_none(self):
        assert salary_logic.parse_number(None) == 0

    def test_non_string(self):
        assert salary_logic.parse_number(123) == 0

    def test_whitespace(self):
        assert salary_logic.parse_number('  500  ') == 500


class TestSafeCell:
    """テーブルセル安全アクセステスト"""

    def test_normal(self):
        table = [['a', 'b'], ['c', 'd']]
        assert salary_logic.safe_cell(table, 0, 0) == 'a'

    def test_out_of_range(self):
        table = [['a']]
        assert salary_logic.safe_cell(table, 5, 5) == ''

    def test_none_cell(self):
        table = [[None, 'b']]
        assert salary_logic.safe_cell(table, 0, 0) == ''

    def test_strip(self):
        table = [['  hello  ']]
        assert salary_logic.safe_cell(table, 0, 0) == 'hello'


class TestIsSummaryPage:
    """合計ページ判定テスト"""

    def test_summary(self):
        table = [['', '全社合計', '', '', ''], ['', '', '', '', '']]
        assert salary_logic.is_summary_page(table) is True

    def test_not_summary(self):
        table = [['', '個人データ', '', '', ''], ['', '', '', '', '']]
        assert salary_logic.is_summary_page(table) is False


class TestDetectEmployeeColumns:
    """従業員列検出テスト"""

    def test_with_codes(self):
        table = [
            [''] * 30,  # NAME_ROW=1 なのでrow 0はヘッダ
            [''] * 30,  # NAME_ROW
            [''] * 30,  # CODE_ROW
        ]
        # CODE_ROW (index 2) の col_off=4 に数値コードを設定
        table[2][4] = '10101001'
        cols = salary_logic.detect_employee_columns(table)
        assert 4 in cols

    def test_empty_table(self):
        table = [[''] * 5]
        cols = salary_logic.detect_employee_columns(table)
        assert cols == []


class TestBuildCombinedSummary:
    """カテゴリ集計テスト"""

    def test_basic(self):
        results = {
            '一般': {
                'summary': {'headcount': 10, 'total_pay': 3000000, 'avg_age': 40.0, 'avg_tenure': 10.0},
                'employees': [
                    {'salary': {'支給合計': 300000, '基本給': 200000, '役職手当': 10000,
                                '調整手当': 0, 'その他固定': 0, 'その他変動': 0,
                                '通勤費': 5000, '時間外計': 15000}}
                ] * 10,
            }
        }
        combined = salary_logic.build_combined_summary(results)
        assert combined['totals']['headcount'] == 10
        assert combined['totals']['支給合計'] == 3000000

    def test_error_category_skipped(self):
        results = {
            '一般': {'error': 'some error', 'category': '一般'},
        }
        combined = salary_logic.build_combined_summary(results)
        assert combined['totals']['headcount'] == 0


class TestMonthSortKey:
    """月ソートキーテスト"""

    def test_sort(self):
        folders = ['12月', '1月', '3月', '10月']
        sorted_folders = sorted(folders, key=salary_logic._month_sort_key)
        assert sorted_folders == ['1月', '3月', '10月', '12月']


class TestListFolders:
    """フォルダ一覧テスト"""

    def test_list(self, tmp_path):
        original = salary_logic._DATA_ROOT
        salary_logic._DATA_ROOT = str(tmp_path)
        try:
            (tmp_path / '1月').mkdir()
            (tmp_path / '2月').mkdir()
            (tmp_path / '1月' / '一般.pdf').touch()
            (tmp_path / 'notmonth').mkdir()

            result = salary_logic.list_folders_data()
            names = [f['name'] for f in result]
            assert '1月' in names
            assert '2月' in names
            assert 'notmonth' not in names
            # 1月にはPDFが1つ
            f1 = next(f for f in result if f['name'] == '1月')
            assert f1['pdf_count'] == 1
        finally:
            salary_logic._DATA_ROOT = original
