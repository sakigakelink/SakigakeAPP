#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
損益計算表 重点項目ビューア（スタンドアロン実行用）
ビジネスロジックは pnl_logic.py に分離
"""

from flask import Flask, render_template, request, jsonify
import pnl_logic

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/autoload', methods=['GET'])
def autoload_data():
    result = pnl_logic.load_all_data()
    if 'error' in result:
        return jsonify(result), 404
    return jsonify(result)


@app.route('/api/manual_inputs', methods=['POST'])
def save_manual_inputs():
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data'}), 400
    pnl_logic.save_manual_inputs(data)
    return jsonify({'ok': True})


@app.route('/api/export_pdf', methods=['POST'])
def export_pdf():
    data = request.json
    if not data:
        return jsonify({'error': 'No data'}), 400
    ctx = pnl_logic.build_pdf_context(data)
    return render_template('pdf_summary.html', **ctx)


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5002)
