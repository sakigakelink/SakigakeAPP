#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
給与分析アプリ（スタンドアロン実行用）
ビジネスロジックは salary_logic.py に分離
"""

from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import salary_logic

app = Flask(__name__)
CORS(app)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024
app.json.sort_keys = False


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/parse', methods=['POST'])
def parse_pdfs():
    result = salary_logic.parse_uploaded_files(request.files)
    if result is None:
        return jsonify({'error': 'ファイルが選択されていません'}), 400
    return jsonify(result)


@app.route('/api/parse_folder', methods=['POST'])
def parse_folder():
    folder = request.json.get('folder', '')
    result = salary_logic.parse_folder_data(folder)
    if result is None:
        return jsonify({'error': f'フォルダが見つかりません: {folder}'}), 404
    return jsonify(result)


@app.route('/api/folders', methods=['GET'])
def list_folders():
    return jsonify(salary_logic.list_folders_data())


@app.route('/api/parse_all_folders', methods=['POST'])
def parse_all_folders():
    result = salary_logic.parse_all_folders_data()
    if result is None:
        return jsonify({'error': '月フォルダが見つかりません'}), 404
    return jsonify(result)


@app.route('/api/sheets_data')
def get_sheets_data():
    data = salary_logic.get_sheets_json()
    if data is None:
        return jsonify({'error': 'R7支払いデータなし'}), 404
    return jsonify(data)


if __name__ == '__main__':
    import webbrowser
    import threading
    port = 5001
    threading.Timer(1.5, lambda: webbrowser.open(f'http://localhost:{port}')).start()
    app.run(debug=False, host='127.0.0.1', port=port)
