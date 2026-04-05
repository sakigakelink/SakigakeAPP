(function() {
    // ==================== グローバル変数 ====================
    let employees = [];
    let codes = [];
    let scheduleData = null;
    let convertedData = null;
    let targetYear = 2026;
    let targetMonth = 2;
    let deleteTarget = { type: null, index: null };

    // TKC変換用
    let rakurakuData = null;
    let tkcConvertedCsv = null;

    const STORAGE_KEY_EMP = 'sakigake_employees_v6';
    const STORAGE_KEY_CODE = 'sakigake_codes_v6';
    const STORAGE_KEY_SCHEDULE = 'sakigake_schedule_v1';

    // TKCテンプレート（ヘッダー）
    const TKC_HEADER = ['社員番号(必須)', '社員氏名(ﾃﾝﾌﾟﾚｰﾄ項目)', '平日出勤', '休日出勤', '出勤時間', '遅刻', '早退', '有休日数', '代休', '公休', 'その他の休日', '生理休暇', '休職日数', '欠勤日数', '日額表用勤務日数', '控除日数', '控除時間', '時間外手当時間Ａ', '時間外手当時間Ｂ', '時間外手当時間Ｃ', '時間外手当時間Ｄ', '時間外手当時間Ｅ', '時間外手当時間Ｆ', '時間外手当時間Ｇ', '回数手当回数Ⅰ', '回数手当回数Ⅱ', '回数手当回数Ⅲ', '回数手当回数Ⅳ', '回数手当回数Ⅴ', '要出勤日数', '要出勤時間', '所定労働日数', '所定労働時間', '有休日数残繰越分', '有休日数残当年分', '支給項目1', '支給項目2', '支給項目3', '支給項目4', '支給項目5', '支給項目6', '支給項目7', '支給項目8', '支給項目9', '支給項目10', '支給項目11', '支給項目12', '支給項目13', '時間外手当', '回数手当', '課税通勤手当', '給与控除額', '給与控除加算分', '(非)通勤手当/通勤手当', '(非)支給項目20', '健康保険料(介護)', '健康保険料(一般)', '厚生年金保険料', '報酬月額', '標準報酬月額', '厚生年金基金掛金', '確定拠出年金掛金', '雇用保険料', '所得税', '住民税', '控除項目1', '控除項目2', '控除項目3', '控除項目4', '控除項目5', '控除項目6', '控除項目7', '控除項目8', '控除項目9', '控除項目10', '預り金前残', '支給項目1単価', '支給項目2単価', '支給項目3単価', '支給項目4単価', '支給項目5単価', '支給項目6単価', '支給項目7単価', '支給項目8単価', '支給項目9単価', '支給項目10単価', '支給項目11単価', '支給項目12単価', '支給項目13単価', '(非)支給20単価', '課税通勤単価', '(非)通勤/通勤単価', '控除項目1単価', '控除項目2単価', '控除項目3単価', '控除項目4単価', '控除項目5単価', '控除項目6単価', '控除項目7単価', '控除項目8単価', '控除項目9単価', '控除項目10単価', '有休時間', '時間外手当時間Ｈ', '有休１日の時間数', '有休時間残繰越分', '有休時間残当年分', '代替休暇', '当月60超残業時間', '換算率', '前月代替休暇時間残', '前々月代替休暇時間残', '当月消化代替休暇時間数', 'うち時間単位分'];

    // マッピング定義（楽々勤怠の列インデックス → TKCの列インデックス）
    const TKC_MAPPING = {
        3: 2,    // D列(出勤日数) → C列(平日出勤)
        4: 4,    // E列(実働時間) → E列(出勤時間)
        6: 17,   // G列(法定内時間外) → R列(時間外手当時間Ａ)
        7: 18,   // H列(法定外時間外) → S列(時間外手当時間Ｂ)
        17: 42,  // R列(準夜手当) → AQ列
        16: 43,  // Q列(深夜手当) → AR列
        26: 44,  // AA列(夜) → AS列
        27: 45,  // AB列(明) → AT列
        18: 46,  // S列(遅出手当) → AU列
        24: 24,  // Y列(日直勤務日数) → Y列(回数手当回数Ⅰ)
        25: 25,  // Z列(宿直勤務日数) → Z列(回数手当回数Ⅱ)
    };

    // ==================== ユーティリティ ====================
    function escapeHtml(text) {
        var d = document.createElement('div');
        d.textContent = text;
        return d.innerHTML;
    }

    // ==================== 初期化 ====================
    function init() {
        try {
            const savedEmp = localStorage.getItem(STORAGE_KEY_EMP);
            const savedCode = localStorage.getItem(STORAGE_KEY_CODE);

            if (savedEmp) {
                try {
                    employees = JSON.parse(savedEmp);
                    updateEmployeeStatus();
                    renderEmployeeTable();
                    log('社員マスタを復元しました', 'success');
                } catch (e) {
                    console.error('社員マスタ復元エラー:', e);
                }
            }

            if (savedCode) {
                try {
                    codes = JSON.parse(savedCode);
                    updateCodeStatus();
                    renderCodeTable();
                    log('勤務符号を復元しました', 'success');
                } catch (e) {
                    console.error('勤務符号復元エラー:', e);
                }
            }

            const savedSchedule = localStorage.getItem(STORAGE_KEY_SCHEDULE);
            if (savedSchedule) {
                try {
                    const compact = JSON.parse(savedSchedule);
                    scheduleData = { sheets: {}, dateCols: compact.dateCols, workbook: null };
                    for (const [name, sheet] of Object.entries(compact.sheets)) {
                        scheduleData.sheets[name] = { staff: sheet.staff, data: [] };
                    }
                    targetYear = compact.targetYear;
                    targetMonth = compact.targetMonth;
                    let totalStaff = 0;
                    for (const sheet of Object.values(scheduleData.sheets)) totalStaff += sheet.staff.length;
                    document.getElementById('scheduleFileName').textContent = `✅ 復元済み`;
                    document.getElementById('scheduleZone').classList.add('loaded');
                    log(`勤務表を復元: ${totalStaff}名`, 'success');
                } catch (e) {
                    console.error('勤務表復元エラー:', e);
                }
            }

            setupEventListeners();
            checkReady();
            console.log('初期化完了');
        } catch (e) {
            console.error('初期化エラー:', e);
            alert('初期化エラー: ' + e.message);
        }
    }

    // ==================== ステータス更新 ====================
    function updateEmployeeStatus() {
        const dot = document.getElementById('empStatusDot');
        const count = document.getElementById('employeeCount');

        if (employees.length > 0) {
            dot.className = 'status-dot ok';
            count.textContent = `${employees.length}名`;
            count.className = 'badge badge-success';
        } else {
            dot.className = 'status-dot ng';
            count.textContent = '0名';
            count.className = 'badge badge-error';
        }
    }

    function updateCodeStatus() {
        const dot = document.getElementById('codeStatusDot');
        const count = document.getElementById('codeCount');

        if (codes.length > 0) {
            dot.className = 'status-dot ok';
            count.textContent = `${codes.length}件`;
            count.className = 'badge badge-success';
        } else {
            dot.className = 'status-dot ng';
            count.textContent = '0件';
            count.className = 'badge badge-error';
        }
    }

    // ==================== ログ ====================
    function log(message, type = 'info') {
        const logArea = document.getElementById('logArea');
        const entry = document.createElement('div');
        entry.className = `log-entry log-${type}`;
        const time = new Date().toLocaleTimeString('ja-JP');
        entry.textContent = `[${time}] ${message}`;
        logArea.appendChild(entry);
        logArea.scrollTop = logArea.scrollHeight;
    }

    // ==================== ファイルアップロード ====================
    function setupUploadZone(zoneId, inputId, handler) {
        const zone = document.getElementById(zoneId);
        const input = document.getElementById(inputId);

        zone.addEventListener('click', () => input.click());
        zone.addEventListener('dragover', (e) => { e.preventDefault(); zone.classList.add('dragover'); });
        zone.addEventListener('dragleave', () => zone.classList.remove('dragover'));
        zone.addEventListener('drop', (e) => {
            e.preventDefault();
            zone.classList.remove('dragover');
            if (e.dataTransfer.files.length) {
                input.files = e.dataTransfer.files;
                handler(e.dataTransfer.files[0]);
            }
        });
        input.addEventListener('change', (e) => {
            if (e.target.files.length) handler(e.target.files[0]);
        });
    }

    // ==================== 社員マスタ ====================
    async function loadEmployeeFile(file) {
        try {
            const text = await file.text();
            employees = JSON.parse(text);
            localStorage.setItem(STORAGE_KEY_EMP, JSON.stringify(employees));

            document.getElementById('employeeFileName').textContent = `✅ ${file.name}`;
            document.getElementById('employeeZone').classList.add('loaded');

            updateEmployeeStatus();
            renderEmployeeTable();
            log(`社員マスタ読込完了: ${employees.length}名`, 'success');
            checkReady();
        } catch (e) {
            log(`社員マスタ読込エラー: ${e.message}`, 'error');
        }
    }

    function saveEmployees() {
        localStorage.setItem(STORAGE_KEY_EMP, JSON.stringify(employees));
        updateEmployeeStatus();
    }

    function renderEmployeeTable(filter = '') {
        const tbody = document.getElementById('employeeTableBody');
        if (employees.length === 0) {
            tbody.innerHTML = '<tr><td colspan="3" style="text-align:center; color: var(--text-secondary);">データなし</td></tr>';
            return;
        }

        let filtered = filter
            ? employees.filter(e => e.name.includes(filter) || String(e.id).includes(filter))
            : employees;

        filtered.sort((a, b) => a.id - b.id);

        tbody.innerHTML = filtered.map((emp) => {
            const idx = employees.findIndex(e => e.id === emp.id && e.name === emp.name);
            return `
            <tr data-idx="${idx}">
                <td><input type="number" value="${escapeHtml(String(emp.id))}" class="emp-id"></td>
                <td><input type="text" value="${escapeHtml(emp.name)}" class="emp-name"></td>
                <td><button class="btn btn-danger btn-icon delete-emp" title="削除">🗑️</button></td>
            </tr>
        `}).join('');

        tbody.querySelectorAll('.emp-id, .emp-name').forEach(input => {
            input.addEventListener('change', handleEmployeeEdit);
        });
        tbody.querySelectorAll('.delete-emp').forEach(btn => {
            btn.addEventListener('click', handleEmployeeDelete);
        });
    }

    function handleEmployeeEdit(e) {
        const tr = e.target.closest('tr');
        const idx = parseInt(tr.dataset.idx);
        employees[idx].id = parseInt(tr.querySelector('.emp-id').value);
        employees[idx].name = tr.querySelector('.emp-name').value.trim();
        saveEmployees();
    }

    function handleEmployeeDelete(e) {
        const tr = e.target.closest('tr');
        const idx = parseInt(tr.dataset.idx);
        deleteTarget = { type: 'employee', index: idx };
        document.getElementById('deleteModalText').textContent =
            `「${employees[idx].name}」（社員番号: ${employees[idx].id}）を削除しますか？`;
        document.getElementById('deleteModal').classList.remove('hidden');
    }

    function addEmployee() {
        const maxId = employees.length > 0 ? Math.max(...employees.map(e => e.id)) : 0;
        employees.push({ id: maxId + 1, name: '新規社員' });
        saveEmployees();
        document.getElementById('employeeSearch').value = '';
        renderEmployeeTable();
        log(`社員追加: ${maxId + 1}`, 'success');
    }

    function saveEmployeeJSON() {
        const json = JSON.stringify(employees, null, 2);
        downloadFile(json, '社員マスタ.json', 'application/json');
        log('社員マスタJSONを保存しました', 'success');
    }

    function clearEmployees() {
        if (confirm('社員マスタをクリアしますか？')) {
            employees = [];
            localStorage.removeItem(STORAGE_KEY_EMP);
            document.getElementById('employeeZone').classList.remove('loaded');
            document.getElementById('employeeFileName').textContent = '';
            updateEmployeeStatus();
            renderEmployeeTable();
            checkReady();
            log('社員マスタをクリアしました', 'warning');
        }
    }

    // ==================== 勤務符号 ====================
    async function loadCodeFile(file) {
        try {
            const text = await file.text();
            codes = JSON.parse(text);
            localStorage.setItem(STORAGE_KEY_CODE, JSON.stringify(codes));

            document.getElementById('codeFileName').textContent = `✅ ${file.name}`;
            document.getElementById('codeZone').classList.add('loaded');

            updateCodeStatus();
            renderCodeTable();
            log(`勤務符号読込完了: ${codes.length}件`, 'success');
            checkReady();
        } catch (e) {
            log(`勤務符号読込エラー: ${e.message}`, 'error');
        }
    }

    function saveCodes() {
        localStorage.setItem(STORAGE_KEY_CODE, JSON.stringify(codes));
        updateCodeStatus();
    }

    function renderCodeTable(filter = '') {
        const tbody = document.getElementById('codeTableBody');
        if (codes.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; color: var(--text-secondary);">データなし</td></tr>';
            return;
        }

        let filtered = filter
            ? codes.filter(c => c.name.includes(filter) || c.master.includes(filter))
            : codes;

        tbody.innerHTML = filtered.map((code) => {
            const idx = codes.findIndex(c => c.master === code.master && c.name === code.name);
            return `
            <tr data-idx="${idx}">
                <td><input type="text" value="${escapeHtml(code.name)}" class="code-name"></td>
                <td><input type="text" value="${escapeHtml(code.master)}" class="code-master" style="width:60px;"></td>
                <td><input type="text" value="${escapeHtml(code.rakuraku || '')}" class="code-rakuraku"></td>
                <td><input type="text" value="${escapeHtml(code.note || '')}" class="code-note"></td>
                <td><button class="btn btn-danger btn-icon delete-code" title="削除">🗑️</button></td>
            </tr>
        `}).join('');

        tbody.querySelectorAll('.code-name, .code-master, .code-rakuraku, .code-note').forEach(input => {
            input.addEventListener('change', handleCodeEdit);
        });
        tbody.querySelectorAll('.delete-code').forEach(btn => {
            btn.addEventListener('click', handleCodeDelete);
        });
    }

    function handleCodeEdit(e) {
        const tr = e.target.closest('tr');
        const idx = parseInt(tr.dataset.idx);
        codes[idx].name = tr.querySelector('.code-name').value.trim();
        codes[idx].master = tr.querySelector('.code-master').value.trim();
        const rakuraku = tr.querySelector('.code-rakuraku').value.trim();
        codes[idx].rakuraku = rakuraku || null;
        codes[idx].note = tr.querySelector('.code-note').value.trim();
        saveCodes();
    }

    function handleCodeDelete(e) {
        const tr = e.target.closest('tr');
        const idx = parseInt(tr.dataset.idx);
        deleteTarget = { type: 'code', index: idx };
        document.getElementById('deleteModalText').textContent =
            `「${codes[idx].name}」（${codes[idx].master}）を削除しますか？`;
        document.getElementById('deleteModal').classList.remove('hidden');
    }

    function addCode() {
        console.log('addCode called, current codes:', codes.length);
        codes.push({ name: '新規符号', master: '?', rakuraku: '', note: '' });
        saveCodes();
        document.getElementById('codeSearch').value = '';
        renderCodeTable();
        log('勤務符号を追加しました', 'success');
        console.log('addCode done, new codes:', codes.length);
    }

    function saveCodeJSON() {
        const json = JSON.stringify(codes, null, 2);
        downloadFile(json, '勤務符号.json', 'application/json');
        log('勤務符号JSONを保存しました', 'success');
    }

    function clearCodes() {
        if (confirm('勤務符号をクリアしますか？')) {
            codes = [];
            localStorage.removeItem(STORAGE_KEY_CODE);
            document.getElementById('codeZone').classList.remove('loaded');
            document.getElementById('codeFileName').textContent = '';
            updateCodeStatus();
            renderCodeTable();
            checkReady();
            log('勤務符号をクリアしました', 'warning');
        }
    }

    // ==================== 削除確認 ====================
    function confirmDelete() {
        if (deleteTarget.type === 'employee') {
            const emp = employees[deleteTarget.index];
            employees.splice(deleteTarget.index, 1);
            saveEmployees();
            renderEmployeeTable(document.getElementById('employeeSearch').value);
            log(`社員削除: ${emp.id} - ${emp.name}`, 'warning');
        } else if (deleteTarget.type === 'code') {
            const code = codes[deleteTarget.index];
            codes.splice(deleteTarget.index, 1);
            saveCodes();
            renderCodeTable(document.getElementById('codeSearch').value);
            log(`勤務符号削除: ${code.master}`, 'warning');
        }
        document.getElementById('deleteModal').classList.add('hidden');
        deleteTarget = { type: null, index: null };
    }

    // ==================== 勤務表読み込み ====================
    async function loadScheduleFile(file) {
        try {
            log(`看護部勤務表を読み込み中: ${file.name}`);
            const buffer = await file.arrayBuffer();
            const workbook = XLSX.read(buffer, { type: 'array' });

            scheduleData = { sheets: {}, workbook, dateCols: [] };

            for (const sheetName of workbook.SheetNames) {
                const sheet = workbook.Sheets[sheetName];
                const data = XLSX.utils.sheet_to_json(sheet, { header: 1 });

                // タイトル行から年月を取得（全セルをスキャン）
                if (data[0]) {
                    for (let c = 0; c < data[0].length; c++) {
                        if (data[0][c]) {
                            const title = String(data[0][c]);
                            const match = title.match(/(\d{4})年(\d{1,2})月/);
                            if (match) {
                                targetYear = parseInt(match[1]);
                                targetMonth = parseInt(match[2]);
                                break;
                            }
                        }
                    }
                }

                // 日付行（行5）から日付列を取得
                if (data[5] && scheduleData.dateCols.length === 0) {
                    for (let col = 0; col < data[5].length; col++) {
                        const val = data[5][col];
                        if (val !== undefined && val !== null && !isNaN(parseInt(val))) {
                            const day = parseInt(val);
                            if (day >= 1 && day <= 31) {
                                scheduleData.dateCols.push({ col, day });
                            }
                        }
                    }
                    log(`日付列を検出: ${scheduleData.dateCols.length}日分`, 'info');
                }

                // 氏名列を自動検出（「氏名」ヘッダーを探す）
                let nameCol = -1;
                let scheduleCol = -1;
                if (data[5]) {
                    for (let c = 0; c < data[5].length; c++) {
                        const v = data[5][c];
                        if (v && String(v).includes('氏名')) nameCol = c;
                        if (v && String(v) === '日付') scheduleCol = c;
                    }
                }
                if (nameCol === -1) nameCol = 1;

                const staff = [];
                for (let i = 0; i < data.length; i++) {
                    const row = data[i];
                    // 予定行を検出: scheduleCol に「予定」がある行
                    if (row && scheduleCol >= 0 && String(row[scheduleCol] || '').trim() === '予定') {
                        // 次の行（実施行）に実名がある
                        const nextRow = (i + 1 < data.length) ? data[i + 1] : null;
                        let name = null;
                        if (nextRow && nextRow[nameCol] && typeof nextRow[nameCol] === 'string') {
                            const candidate = nextRow[nameCol].trim();
                            if ((candidate.includes('\u3000') || candidate.includes(' ')) &&
                                !candidate.includes('勤務表') && !candidate.includes('曜日')) {
                                name = candidate;
                            }
                        }
                        // 実施行に名前がなければ予定行の氏名列を試す
                        if (!name && row[nameCol] && typeof row[nameCol] === 'string') {
                            const candidate = row[nameCol].trim();
                            if ((candidate.includes('\u3000') || candidate.includes(' ')) &&
                                !candidate.includes('勤務表') && !candidate.includes('曜日')) {
                                name = candidate;
                            }
                        }
                        if (name) {
                            const shifts = [];
                            for (const dateCol of scheduleData.dateCols) {
                                const val = row[dateCol.col];
                                shifts.push(val !== undefined && val !== null ? String(val).trim() : '');
                            }
                            staff.push({ name, shifts, row: i });
                        }
                    }
                }

                // 予定/実施パターンで見つからなかった場合、従来ロジックにフォールバック
                if (staff.length === 0) {
                    for (let i = 0; i < data.length; i++) {
                        const row = data[i];
                        for (let c = 0; c <= Math.min(nameCol, 2); c++) {
                            if (row && row[c] && typeof row[c] === 'string') {
                                const cellValue = row[c].trim();
                                if ((cellValue.includes('\u3000') || cellValue.includes(' ')) &&
                                    !cellValue.includes('勤務表') &&
                                    cellValue !== '氏名／曜日' &&
                                    !cellValue.includes('曜日')) {
                                    const shifts = [];
                                    for (const dateCol of scheduleData.dateCols) {
                                        const val = row[dateCol.col];
                                        shifts.push(val !== undefined && val !== null ? String(val).trim() : '');
                                    }
                                    staff.push({ name: cellValue, shifts, row: i });
                                    break;
                                }
                            }
                        }
                    }
                }
                scheduleData.sheets[sheetName] = { data, staff };
                log(`${sheetName}: ${staff.length}名検出`, 'info');
            }

            document.getElementById('scheduleFileName').textContent = `✅ ${file.name}`;
            document.getElementById('scheduleZone').classList.add('loaded');

            const monthSelector = document.getElementById('monthSelector');
            const targetMonthSelect = document.getElementById('targetMonth');
            monthSelector.classList.remove('hidden');
            targetMonthSelect.innerHTML = '';
            for (let m = 1; m <= 12; m++) {
                const opt = document.createElement('option');
                opt.value = m;
                opt.textContent = `${targetYear}年${m}月`;
                if (m === targetMonth) opt.selected = true;
                targetMonthSelect.appendChild(opt);
            }
            targetMonthSelect.addEventListener('change', (e) => { targetMonth = parseInt(e.target.value); });

            let totalStaff = 0;
            for (const sheet of Object.values(scheduleData.sheets)) totalStaff += sheet.staff.length;

            document.getElementById('scheduleStats').innerHTML =
                `<div class="stat-item">合計: <span class="stat-value">${totalStaff}</span>名</div>
                 <div class="stat-item">シート: <span class="stat-value">${workbook.SheetNames.length}</span></div>`;

            log(`看護部勤務表読込完了: ${totalStaff}名 (${workbook.SheetNames.join(', ')})`, 'success');
            // scheduleDataをlocalStorageに保存（workbookオブジェクトは除外）
            try {
                const saveData = {
                    sheets: scheduleData.sheets,
                    dateCols: scheduleData.dateCols,
                    targetYear, targetMonth
                };
                const compact = { dateCols: saveData.dateCols, targetYear, targetMonth, sheets: {} };
                for (const [name, sheet] of Object.entries(saveData.sheets)) {
                    compact.sheets[name] = { staff: sheet.staff };
                }
                localStorage.setItem(STORAGE_KEY_SCHEDULE, JSON.stringify(compact));
            } catch (e) {
                console.error('勤務表保存エラー:', e);
            }
            checkReady();
        } catch (e) {
            log(`看護部勤務表読込エラー: ${e.message}`, 'error');
        }
    }

    // ==================== シフト変換処理 ====================
    function checkReady() {
        const ready = employees.length > 0 && codes.length > 0 && scheduleData;
        document.getElementById('convertBtn').disabled = !ready;

        if (ready) {
            log('準備完了。変換実行可能です。', 'success');
        }
    }

    function getCodeMapping() {
        const map = {};
        for (const code of codes) {
            map[code.master] = code.rakuraku;
        }
        return map;
    }

    function normalizeName(name) {
        return name.replace(/[\s\u3000]+/g, '\u3000').trim();
    }

    function getEmployeeMap() {
        const map = {};
        for (const emp of employees) {
            map[normalizeName(emp.name)] = emp.id;
        }
        return map;
    }

    function isHoliday(masterShift) {
        if (!masterShift || masterShift === 'nan') return false;
        const codeMap = getCodeMapping();
        return codeMap.hasOwnProperty(masterShift) && codeMap[masterShift] === null;
    }

    function convertShiftsForStaff(shifts, dateColumns) {
        const codeMap = getCodeMapping();
        const result = [];

        const weekdays = [];
        for (const dateCol of dateColumns) {
            weekdays.push(new Date(dateCol.year, dateCol.month - 1, dateCol.day).getDay());
        }

        let weekHasLegalHoliday = false;

        for (let d = 0; d < shifts.length; d++) {
            const weekday = weekdays[d];
            const masterShift = shifts[d] || '';

            if (weekday === 0) {
                weekHasLegalHoliday = false;
            }

            if (!masterShift || masterShift === 'nan') {
                result.push('');
            } else if (isHoliday(masterShift)) {
                if (!weekHasLegalHoliday) {
                    result.push('法定休日');
                    weekHasLegalHoliday = true;
                } else {
                    result.push('所定休日');
                }
            } else if (codeMap.hasOwnProperty(masterShift)) {
                result.push(codeMap[masterShift]);
            } else {
                log(`未知の符号: "${masterShift}"`, 'warning');
                result.push(masterShift);
            }
        }

        return result;
    }

    function convert() {
        try {
            if (!scheduleData || !scheduleData.dateCols || scheduleData.dateCols.length === 0) {
                log('⚠️ 勤務表が読み込まれていません。看護部勤務表Excelを再度ドロップしてください。', 'error');
                return;
            }
            let totalStaffCheck = 0;
            for (const sheet of Object.values(scheduleData.sheets)) totalStaffCheck += (sheet.staff ? sheet.staff.length : 0);
            if (totalStaffCheck === 0) {
                log('⚠️ 勤務表のスタッフデータが空です。看護部勤務表Excelを再度ドロップしてください。', 'error');
                return;
            }
            log('変換処理を開始...', 'info');
            const employeeMap = getEmployeeMap();

            const dateColumns = [];
            let currentYear = targetYear;
            let currentMonth = targetMonth;
            let prevDay = 0;

            for (const dateCol of scheduleData.dateCols) {
                if (dateCol.day < prevDay) {
                    currentMonth++;
                    if (currentMonth > 12) {
                        currentMonth = 1;
                        currentYear++;
                    }
                }
                prevDay = dateCol.day;

                dateColumns.push({
                    str: String(currentYear) + '-' + String(currentMonth).padStart(2, '0') + '-' + String(dateCol.day).padStart(2, '0'),
                    year: currentYear,
                    month: currentMonth,
                    day: dateCol.day
                });
            }

            const daysInMonth = scheduleData.dateCols.length;

            convertedData = [];
            let matchedCount = 0;
            let unmatchedNames = [];

            for (const [sheetName, sheet] of Object.entries(scheduleData.sheets)) {
                for (const staff of sheet.staff) {
                    const empId = employeeMap[normalizeName(staff.name)];
                    if (empId) {
                        matchedCount++;

                        const convertedShifts = convertShiftsForStaff(staff.shifts, dateColumns);

                        const shortId = String(parseInt(empId.slice(-4), 10));
                        const shiftRow = { 社員番号: shortId, 区分: 'シフト' };
                        const calRow = { 社員番号: shortId, 区分: 'カレンダー' };
                        for (let d = 0; d < daysInMonth; d++) {
                            shiftRow[dateColumns[d].str] = convertedShifts[d] || '';
                            calRow[dateColumns[d].str] = '';
                        }
                        convertedData.push(shiftRow);
                        convertedData.push(calRow);
                    } else {
                        unmatchedNames.push(staff.name);
                    }
                }
            }

            log(`変換完了: ${matchedCount}名`, 'success');
            if (unmatchedNames.length > 0) {
                log(`マッチなし(${unmatchedNames.length}名): ${unmatchedNames.join(', ')}`, 'warning');
            }

            if (matchedCount === 0) {
                log('--- デバッグ情報 ---', 'info');
                for (const [sheetName, sheet] of Object.entries(scheduleData.sheets)) {
                    const sample = sheet.staff[0];
                    if (sample) {
                        const raw = sample.name;
                        const norm = normalizeName(raw);
                        const codes = [...raw].map(c => c.charCodeAt(0).toString(16)).join(' ');
                        log(`マイスター名[0] raw="${raw}" norm="${norm}" codes=[${codes}]`, 'info');
                    }
                }
                const empSample = employees[0];
                if (empSample) {
                    const raw = empSample.name;
                    const norm = normalizeName(raw);
                    const codes = [...raw].map(c => c.charCodeAt(0).toString(16)).join(' ');
                    log(`マスタ名[0] raw="${raw}" norm="${norm}" codes=[${codes}]`, 'info');
                }
                const mapKeys = Object.keys(getEmployeeMap()).slice(0, 3);
                log(`employeeMapキー例: ${mapKeys.map(k => `"${k}"`).join(', ')}`, 'info');
            }

            showPreview();
            document.getElementById('downloadBtn').classList.remove('hidden');
        } catch (e) {
            log(`変換エラー: ${e.message}`, 'error');
        }
    }

    function showPreview() {
        const previewSection = document.getElementById('previewSection');
        const previewTable = document.getElementById('previewTable');
        previewSection.classList.remove('hidden');

        if (!convertedData || convertedData.length === 0) return;

        const headers = Object.keys(convertedData[0]);
        let html = '<thead><tr>' + headers.slice(0, 12).map(h => `<th>${escapeHtml(h)}</th>`).join('') + '<th>...</th></tr></thead>';
        html += '<tbody>';
        for (let i = 0; i < Math.min(10, convertedData.length); i++) {
            const row = convertedData[i];
            html += '<tr>' + headers.slice(0, 12).map(h => `<td>${escapeHtml(String(row[h] || ''))}</td>`).join('') + '<td>...</td></tr>';
        }
        html += '</tbody>';
        previewTable.innerHTML = html;
    }

    function downloadCSV() {
        if (!convertedData || convertedData.length === 0) {
            log('変換データがありません。先に変換を実行してください。', 'error');
            return;
        }
        const headers = Object.keys(convertedData[0]);
        const quoteCell = (val) => {
            const str = String(val || '');
            return '"' + str.replace(/"/g, '""') + '"';
        };
        let csv = headers.map(quoteCell).join(',') + '\n';
        for (const row of convertedData) {
            csv += headers.map(h => quoteCell(row[h])).join(',') + '\n';
        }

        const bom = '\uFEFF';
        const blob = new Blob([bom + csv], { type: 'text/csv;charset=utf-8' });

        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        const now = new Date();
        const ts = now.getFullYear().toString() +
                   String(now.getMonth()+1).padStart(2,'0') +
                   String(now.getDate()).padStart(2,'0') +
                   String(now.getHours()).padStart(2,'0') +
                   String(now.getMinutes()).padStart(2,'0') +
                   String(now.getSeconds()).padStart(2,'0');
        a.download = `シフトスケジュール_(${targetMonth}月)_${ts}.csv`;
        a.click();
        URL.revokeObjectURL(url);
        log('CSVファイルをダウンロードしました（UTF-8 BOM）', 'success');
    }

    // ==================== TKC変換処理 ====================
    function parseCSV(text) {
        const lines = [];
        let current = '';
        let inQuotes = false;

        for (let i = 0; i < text.length; i++) {
            const char = text[i];
            if (char === '"') {
                inQuotes = !inQuotes;
                current += char;
            } else if ((char === '\n' || char === '\r') && !inQuotes) {
                if (current.trim()) {
                    lines.push(parseCSVLine(current));
                }
                current = '';
                if (char === '\r' && text[i + 1] === '\n') i++;
            } else {
                current += char;
            }
        }
        if (current.trim()) {
            lines.push(parseCSVLine(current));
        }
        return lines;
    }

    function parseCSVLine(line) {
        const result = [];
        let current = '';
        let inQuotes = false;

        for (let i = 0; i < line.length; i++) {
            const char = line[i];
            if (char === '"') {
                if (inQuotes && line[i + 1] === '"') {
                    current += '"';
                    i++;
                } else {
                    inQuotes = !inQuotes;
                }
            } else if (char === ',' && !inQuotes) {
                result.push(current);
                current = '';
            } else {
                current += char;
            }
        }
        result.push(current);
        return result;
    }

    function toCSV(data) {
        return data.map(row =>
            row.map(cell => {
                if (cell === null || cell === undefined) return '';
                const str = String(cell);
                if (str.includes(',') || str.includes('"') || str.includes('\n')) {
                    return '"' + str.replace(/"/g, '""') + '"';
                }
                return str;
            }).join(',')
        ).join('\r\n');
    }

    async function loadTkcFile(file) {
        try {
            const buffer = await file.arrayBuffer();
            const uint8 = new Uint8Array(buffer);
            const detectedEncoding = Encoding.detect(uint8);
            const unicodeArray = Encoding.convert(uint8, { to: 'UNICODE', from: detectedEncoding });
            const text = Encoding.codeToString(unicodeArray);
            rakurakuData = parseCSV(text);

            document.getElementById('tkcFileName').textContent = `✅ ${file.name}`;
            document.getElementById('tkcUploadZone').classList.add('loaded');

            setTimeout(() => convertTkc(), 300);
        } catch (e) {
            alert('ファイル読み込みエラー: ' + e.message);
        }
    }

    function convertTkc() {
        try {
            const rakurakuByEmp = {};
            for (let i = 1; i < rakurakuData.length; i++) {
                const row = rakurakuData[i];
                if (row && row[0]) {
                    const empNo = row[0].trim();
                    rakurakuByEmp[empNo] = row;
                }
            }

            const colCount = TKC_HEADER.length;
            const resultData = [TKC_HEADER];

            for (const empNo in rakurakuByEmp) {
                const srcRow = rakurakuByEmp[empNo];

                const newRow = new Array(colCount).fill('');
                newRow[0] = empNo;
                newRow[1] = srcRow[1];

                for (const [srcColStr, dstCol] of Object.entries(TKC_MAPPING)) {
                    const srcCol = Number(srcColStr);
                    if (srcCol < srcRow.length) {
                        newRow[dstCol] = srcRow[srcCol] || '';
                    }
                }

                // 時間列の秒を除去
                for (const col of [4, 17, 18]) {
                    const val = newRow[col];
                    if (val) {
                        const m = val.match(/^(\d+:\d{2}):\d{2}$/);
                        if (m) {
                            newRow[col] = m[1];
                        }
                    }
                }

                // 手当統合: 深夜手当と明が両方存在 → 明に合算
                const shinya = Number(newRow[43]) || 0;
                const ake = Number(newRow[45]) || 0;
                if (shinya > 0 && ake > 0) {
                    newRow[45] = String(shinya + ake);
                    newRow[43] = '0';
                }

                // 手当統合: 準夜手当と夜が両方存在 → 夜に合算
                const junnya = Number(newRow[42]) || 0;
                const yoru = Number(newRow[44]) || 0;
                if (junnya > 0 && yoru > 0) {
                    newRow[44] = String(junnya + yoru);
                    newRow[42] = '0';
                }

                resultData.push(newRow);
            }

            tkcConvertedCsv = toCSV(resultData);

            document.getElementById('tkcStatTotal').textContent = Object.keys(rakurakuByEmp).length;
            document.getElementById('tkcResultCard').classList.remove('hidden');
        } catch (e) {
            alert('変換エラー: ' + e.message);
        }
    }

    function downloadTkcCSV() {
        if (!tkcConvertedCsv) return;

        const unicodeArray = Encoding.stringToCode(tkcConvertedCsv);
        const sjisArray = Encoding.convert(unicodeArray, {
            to: 'SJIS',
            from: 'UNICODE'
        });
        const uint8Array = new Uint8Array(sjisArray);

        const blob = new Blob([uint8Array], { type: 'text/csv' });

        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        const today = new Date().toISOString().slice(0, 10).replace(/-/g, '');
        a.download = `TKC_勤怠データ_${today}.csv`;
        a.click();
        URL.revokeObjectURL(url);
    }

    // ==================== ユーティリティ ====================
    function downloadFile(content, filename, type) {
        const blob = new Blob([content], { type });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        a.click();
        URL.revokeObjectURL(url);
    }

    // ==================== イベント設定 ====================
    function setupEventListeners() {
        document.querySelectorAll('.tab').forEach(tab => {
            tab.addEventListener('click', () => {
                document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
                document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
                tab.classList.add('active');
                document.getElementById(`tab-${tab.dataset.tab}`).classList.add('active');
            });
        });

        setupUploadZone('employeeZone', 'employeeFile', loadEmployeeFile);
        setupUploadZone('codeZone', 'codeFile', loadCodeFile);
        setupUploadZone('scheduleZone', 'scheduleFile', loadScheduleFile);
        setupUploadZone('tkcUploadZone', 'tkcFile', loadTkcFile);

        document.getElementById('convertBtn').addEventListener('click', convert);
        document.getElementById('downloadBtn').addEventListener('click', downloadCSV);
        document.getElementById('tkcDownloadBtn').addEventListener('click', downloadTkcCSV);

        document.getElementById('employeeSearch').addEventListener('input', (e) => renderEmployeeTable(e.target.value));
        document.getElementById('addEmployeeBtn').addEventListener('click', addEmployee);
        document.getElementById('saveEmployeeBtn').addEventListener('click', saveEmployeeJSON);
        document.getElementById('clearEmployeeBtn').addEventListener('click', clearEmployees);

        document.getElementById('codeSearch').addEventListener('input', (e) => renderCodeTable(e.target.value));
        document.getElementById('addCodeBtn').addEventListener('click', addCode);
        document.getElementById('saveCodeBtn').addEventListener('click', saveCodeJSON);
        document.getElementById('clearCodeBtn').addEventListener('click', clearCodes);

        document.getElementById('cancelDeleteBtn').addEventListener('click', () => {
            document.getElementById('deleteModal').classList.add('hidden');
            deleteTarget = { type: null, index: null };
        });
        document.getElementById('confirmDeleteBtn').addEventListener('click', confirmDelete);
    }

    document.addEventListener('DOMContentLoaded', init);
})();
