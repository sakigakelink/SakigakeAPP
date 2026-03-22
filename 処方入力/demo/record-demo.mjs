import puppeteer from 'puppeteer';
import { mkdir, rm } from 'fs/promises';
import { join, dirname } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));
const FRAMES_DIR = join(__dirname, 'frames');
const URL = 'http://localhost:5173';

// 前回フレームをクリア
await rm(FRAMES_DIR, { recursive: true, force: true });
await mkdir(FRAMES_DIR, { recursive: true });

let frame = 0;
const HOLD = 12;       // 通常ショット: 12フレーム（4fps→3秒）
const HOLD_LONG = 20;  // 重要ショット: 20フレーム（5秒）
const HOLD_TITLE = 16; // タイトルカード: 16フレーム（4秒）

async function shot(page, label, holdOverride) {
  const h = holdOverride || HOLD;
  for (let i = 0; i < h; i++) {
    const name = String(frame++).padStart(4, '0');
    await page.screenshot({ path: join(FRAMES_DIR, `${name}.png`), type: 'png' });
  }
  console.log(`  📸 ${label} (frames ${frame - h}-${frame - 1}, ${h}f)`);
}

async function wait(ms) {
  return new Promise((r) => setTimeout(r, ms));
}

// ── キャプション表示/非表示 ──
async function showCaption(page, text, sub) {
  await page.evaluate((t, s) => {
    let el = document.getElementById('demo-caption');
    if (!el) {
      el = document.createElement('div');
      el.id = 'demo-caption';
      el.style.cssText = `
        position: fixed; bottom: 0; left: 0; right: 0; z-index: 99999;
        background: linear-gradient(transparent, rgba(15,23,42,0.92) 30%);
        padding: 32px 24px 18px; text-align: center;
        font-family: "Noto Sans JP", "Yu Gothic UI", sans-serif;
        pointer-events: none;
      `;
      document.body.appendChild(el);
    }
    el.innerHTML = `
      <div style="color:#fff; font-size:17px; font-weight:700; line-height:1.5;
                  text-shadow: 0 1px 4px rgba(0,0,0,0.6);">${t}</div>
      ${s ? `<div style="color:#94a3b8; font-size:13px; margin-top:4px;
                         text-shadow: 0 1px 3px rgba(0,0,0,0.5);">${s}</div>` : ''}
    `;
    el.style.display = 'block';
  }, text, sub || '');
}

async function hideCaption(page) {
  await page.evaluate(() => {
    const el = document.getElementById('demo-caption');
    if (el) el.style.display = 'none';
  });
}

// ── シーンタイトルカード（暗い背景+大文字） ──
async function sceneTitle(page, sceneNum, title, sub) {
  await page.evaluate((num, t, s) => {
    let el = document.getElementById('demo-scene-title');
    if (!el) {
      el = document.createElement('div');
      el.id = 'demo-scene-title';
      el.style.cssText = `
        position: fixed; inset: 0; z-index: 100000;
        background: rgba(15,23,42,0.95);
        display: flex; flex-direction: column;
        align-items: center; justify-content: center;
        font-family: "Noto Sans JP", "Yu Gothic UI", sans-serif;
        pointer-events: none;
      `;
      document.body.appendChild(el);
    }
    el.innerHTML = `
      <div style="color:#60a5fa; font-size:14px; font-weight:600;
                  letter-spacing:2px; margin-bottom:12px;">SCENE ${num}</div>
      <div style="color:#fff; font-size:22px; font-weight:700;
                  line-height:1.5; text-align:center; padding:0 40px;">${t}</div>
      ${s ? `<div style="color:#94a3b8; font-size:14px; margin-top:10px;
                         text-align:center; padding:0 40px;">${s}</div>` : ''}
    `;
    el.style.display = 'flex';
  }, sceneNum, title, sub || '');
  await wait(100);
  await shot(page, `タイトル: Scene ${sceneNum}`, HOLD_TITLE);
  // タイトルを消す
  await page.evaluate(() => {
    const el = document.getElementById('demo-scene-title');
    if (el) el.style.display = 'none';
  });
}

/** テキストを含むボタンをクリック */
async function clickBtnByText(page, selector, text) {
  await page.evaluate((sel, txt) => {
    const btns = document.querySelectorAll(sel);
    for (const btn of btns) {
      if (btn.textContent.trim() === txt) { btn.click(); return; }
    }
    throw new Error(`Button "${txt}" not found in "${sel}"`);
  }, selector, text);
}

/** 薬剤を検索して最初の候補を選択 */
async function searchAndSelect(page, query) {
  await page.evaluate(() => window.scrollTo(0, 0));
  await wait(200);
  await page.click('.drug-search__input');
  await page.type('.drug-search__input', query, { delay: 60 });
  await wait(400);
  await page.click('.drug-search__item:first-child');
  await wait(400);
}

/** 錠数の +/- ボタンクリック */
async function clickPlus(page, times = 1) {
  for (let i = 0; i < times; i++) {
    await page.click('.dose-input__count-btn:last-child');
    await wait(150);
  }
}
async function clickMinus(page, times = 1) {
  for (let i = 0; i < times; i++) {
    await page.click('.dose-input__count-btn:first-child');
    await wait(150);
  }
}

// =====================================================
const browser = await puppeteer.launch({
  headless: true,
  args: ['--no-sandbox', '--window-size=750,900'],
  defaultViewport: { width: 750, height: 900 },
});
const page = await browser.newPage();

console.log('🎬 デモ録画開始（10シーン・キャプション付き）\n');

// ============================================================
// シーン1: 初期画面
// ============================================================
await page.goto(URL, { waitUntil: 'networkidle0' });
await wait(500);

await sceneTitle(page, 1, '処方入力アプリ', '入院処方モード・初期画面');

await showCaption(page, '初期画面', '入院処方 ─ 開始日と投与タイミング（朝/昼/夕/寝る前）を指定');
await shot(page, '初期画面', HOLD_LONG);
await hideCaption(page);

// ============================================================
// シーン2: デフォルト用法自動設定 [§2.1 + §2.4]
// ============================================================
await sceneTitle(page, 2,
  'デフォルト用法の自動設定',
  '眠剤など添付文書で投与タイミングが決まっている薬は、選択時に用法を自動設定');

console.log('--- シーン2: デフォルト用法自動設定 ---');
await searchAndSelect(page, 'デエビゴ');
await page.evaluate(() => window.scrollTo(0, 250));
await wait(300);
await showCaption(page,
  '💊 デエビゴ錠（眠剤）→ 用法「寝る前」が自動選択',
  '添付文書ベースのデフォルト用法を自動適用 ─ 手動選択の手間を削減');
await shot(page, 'デエビゴ → 寝る前自動', HOLD_LONG);

// 5mg選択
await page.click('.dose-input__strength-btn:nth-child(2)');
await wait(200);
await showCaption(page,
  '規格ボタンに薬価を併記: 2.5mg（57.3円）/ 5mg（85.8円）',
  'リアルタイム薬価表示でコスト意識を支援');
await shot(page, '5mg選択＋薬価', HOLD_LONG);

// 追加
await hideCaption(page);
await page.click('.drug-entry-form__add-btn');
await wait(300);
await page.evaluate(() => window.scrollTo(0, 9999));
await wait(200);
await showCaption(page, 'デエビゴ錠 5mg × 1T 寝る前 ─ プールに追加');
await shot(page, 'プールに追加');
await hideCaption(page);

// ============================================================
// シーン3: 最大量超過の警告付き許容 [§2.5]
// ============================================================
await sceneTitle(page, 3,
  '最大量超過の警告（ブロックしない）',
  '1日最大量を超えた場合、警告を表示しつつ医師の判断で追加を許容');

console.log('\n--- シーン3: 最大量超過警告 ---');
await searchAndSelect(page, 'ゾルピデム');
await page.click('.dose-input__strength-btn:nth-child(2)');
await wait(200);
await clickPlus(page, 1);
await wait(300);
await page.evaluate(() => window.scrollTo(0, 300));
await wait(300);
await showCaption(page,
  '⚠️ ゾルピデム 10mg×2T = 20mg（最大量 10mg 超過）',
  '赤い警告バナー表示 → ブロックせず「⚠ 最大量超過で追加」ボタンで許容');
await shot(page, '最大量超過警告', HOLD_LONG);

// オーバーライド追加
await hideCaption(page);
await page.click('.drug-entry-form__add-btn');
await wait(300);
await page.evaluate(() => window.scrollTo(0, 9999));
await wait(200);
await showCaption(page, '医師の判断で最大量超過のまま追加 ─ 処方をブロックしない設計');
await shot(page, 'オーバーライド追加');
await hideCaption(page);

// ============================================================
// シーン4: 割り切れない錠数の警告 [§2.6]
// ============================================================
await sceneTitle(page, 4,
  '割り切れない錠数の警告',
  '錠数 ÷ 投与回数が割り切れない場合に即座に警告 → 修正で解消');

console.log('\n--- シーン4: 割り切れない警告 ---');
await searchAndSelect(page, 'ラモトリギン');
await page.click('.dose-input__strength-btn:first-child');
await wait(200);
await clickPlus(page, 2); // 3T
await wait(200);
await clickBtnByText(page, '.schedule-selector__usage-btn', '朝夕食後');
await wait(300);
await page.evaluate(() => window.scrollTo(0, 300));
await wait(300);
await showCaption(page,
  '⚠️ 3T ÷ 2回 = 1回1.50T（割り切れません）',
  '錠剤の均等分割ができない場合の即時警告');
await shot(page, '割り切れない警告', HOLD_LONG);

// 修正: 2Tへ
await clickMinus(page, 1);
await wait(300);
await showCaption(page,
  '✅ 2T に修正 → 警告が消失',
  '2T ÷ 2回 = 1回1T ─ 均等に分割可能');
await shot(page, '修正→警告消失', HOLD_LONG);
await hideCaption(page);

// 追加
await page.click('.drug-entry-form__add-btn');
await wait(300);

// ============================================================
// シーン5: 通常薬追加 [§2.4]
// ============================================================
await sceneTitle(page, 5,
  'リアルタイム薬価表示',
  '全規格の薬価を規格ボタンに併記 ─ コスト比較が一目で可能');

console.log('\n--- シーン5: 通常薬追加 ---');
await searchAndSelect(page, 'アリピプラゾール');
await page.click('.dose-input__strength-btn:nth-child(2)');
await wait(200);
await clickPlus(page, 1);
await wait(200);
await clickBtnByText(page, '.schedule-selector__usage-btn', '朝夕食後');
await wait(200);
await page.evaluate(() => window.scrollTo(0, 100));
await wait(200);
await showCaption(page,
  '💊 アリピプラゾールOD錠 ─ 4規格の薬価を一覧表示',
  '3mg(10.1円) / 6mg(13.2円) / 12mg(17.8円) / 24mg(31.0円)');
await shot(page, '4規格薬価表示', HOLD_LONG);
await hideCaption(page);

await page.click('.drug-entry-form__add-btn');
await wait(300);

// ============================================================
// シーン6: 頓用モード
// ============================================================
await sceneTitle(page, 6,
  '頓用（PRN）モード',
  'プリセット条件（不穏時・不眠時・疼痛時…）からワンクリック選択');

console.log('\n--- シーン6: 頓用モード ---');
await searchAndSelect(page, 'ワイパックス');
await page.click('.dose-input__strength-btn:first-child');
await wait(200);
await clickBtnByText(page, '.schedule-selector__mode-tab', '頓用');
await wait(300);
await page.evaluate(() => window.scrollTo(0, 300));
await wait(200);
await showCaption(page,
  '💊 ワイパックス錠 0.5mg ─ 頓用「不穏時」',
  '8種類のプリセット条件 + 自由入力に対応');
await shot(page, '頓用モード', HOLD_LONG);
await hideCaption(page);

await page.click('.drug-entry-form__add-btn');
await wait(300);

// ============================================================
// シーン7: 不均等モード [§2.3]
// ============================================================
await sceneTitle(page, 7,
  '不均等投与の専用UI',
  '朝1T/夕2Tなど、スロット別に異なる錠数を入力');

console.log('\n--- シーン7: 不均等モード ---');
await searchAndSelect(page, 'デパケンR');
await page.click('.dose-input__strength-btn:nth-child(2)');
await wait(200);
await clickBtnByText(page, '.schedule-selector__mode-tab', '不均等');
await wait(300);

// 朝食後 +1
await page.evaluate(() => {
  const rows = document.querySelectorAll('.schedule-selector__slot-row');
  const morning = Array.from(rows).find((r) =>
    r.querySelector('.schedule-selector__slot-label')?.textContent === '朝食後'
  );
  morning?.querySelectorAll('.schedule-selector__slot-btn')[1]?.click();
});
await wait(200);

// 夕食後 +2
for (let i = 0; i < 2; i++) {
  await page.evaluate(() => {
    const rows = document.querySelectorAll('.schedule-selector__slot-row');
    const evening = Array.from(rows).find((r) =>
      r.querySelector('.schedule-selector__slot-label')?.textContent === '夕食後'
    );
    evening?.querySelectorAll('.schedule-selector__slot-btn')[1]?.click();
  });
  await wait(150);
}
await wait(200);

await page.evaluate(() => window.scrollTo(0, 300));
await wait(200);
await showCaption(page,
  '💊 デパケンR錠 200mg ─ 朝1T / 夕2T（合計3T）',
  '4スロット（朝・昼・夕・寝る前）別に錠数を個別指定');
await shot(page, '不均等UI', HOLD_LONG);
await hideCaption(page);

// 追加
await page.evaluate(() => window.scrollTo(0, 600));
await wait(200);
await page.click('.drug-entry-form__add-btn');
await wait(300);
await page.evaluate(() => window.scrollTo(0, 9999));
await wait(200);
await showCaption(page, '不均等投与をプールに追加 ─ 合計6件の処方');
await shot(page, '不均等追加');
await hideCaption(page);

// ============================================================
// シーン8: 体重換算モード
// ============================================================
await sceneTitle(page, 8,
  '体重換算モード',
  'mg/kg/日の用量と体重から1日総量・1回量を自動計算');

console.log('\n--- シーン8: 体重換算モード ---');
await searchAndSelect(page, 'デパケン細');
await clickBtnByText(page, '.schedule-selector__mode-tab', '体重換算');
await wait(300);

// 体重25kg
const pedInputs = await page.$$('.schedule-selector__ped-input');
await pedInputs[0].click({ clickCount: 3 });
await pedInputs[0].type('25');
await wait(200);

// 用量20mg/kg/日
await pedInputs[1].click({ clickCount: 3 });
await pedInputs[1].type('20');
await wait(200);

// 分割3回
await clickBtnByText(page, '.schedule-selector__ped-times button, .schedule-selector__usage-btn', '3回');
await wait(300);

// 朝・昼・夕チェック
await page.evaluate(() => {
  const checks = document.querySelectorAll('.schedule-selector__ped-check input[type="checkbox"]');
  if (checks[0] && !checks[0].checked) checks[0].click();
  if (checks[1] && !checks[1].checked) checks[1].click();
  if (checks[2] && !checks[2].checked) checks[2].click();
});
await wait(300);

await page.evaluate(() => window.scrollTo(0, 350));
await wait(200);
await showCaption(page,
  '💊 デパケン細粒 ─ 体重25kg × 20mg/kg/日',
  '1日総量: 500.0mg / 1回量: 166.7mg × 3回（朝・昼・夕）');
await shot(page, '体重換算計算結果', HOLD_LONG);
await hideCaption(page);

// 追加
await page.evaluate(() => window.scrollTo(0, 600));
await wait(200);
await page.click('.drug-entry-form__add-btn');
await wait(300);
await page.evaluate(() => window.scrollTo(0, 9999));
await wait(200);
await showCaption(page, '体重換算処方をプールに追加 ─ 全7件');
await shot(page, '体重換算追加');
await hideCaption(page);

// ============================================================
// シーン9: 処方箋成形 [§2.2 + §2.4]
// ============================================================
await sceneTitle(page, 9,
  '処方箋成形 ─ 一包化サマリー＋合計薬価',
  'Rp番号自動付番、同一用法の薬剤を自動グループ化');

console.log('\n--- シーン9: 処方箋成形 ---');
await page.click('.app__standardize-btn');
await wait(500);

// 上部
await page.evaluate(() => {
  const output = document.querySelector('.std-output');
  if (output) output.scrollIntoView({ block: 'start' });
});
await wait(300);
await showCaption(page,
  '📋 成形結果 ─ Rp番号 + 用法ラベル + 薬価',
  '同じ用法の薬剤が自動でRpグループにまとまる');
await shot(page, '成形結果上部', HOLD_LONG);

// 下部
await page.evaluate(() => window.scrollTo(0, 9999));
await wait(300);
await showCaption(page,
  '📊 一包化サマリー: 朝4 昼1 夕5 寝3（計13錠/日）',
  '合計薬価（屯用除く）をリアルタイム算出');
await shot(page, '一包化+合計薬価', HOLD_LONG);
await hideCaption(page);

// ============================================================
// シーン10: エンドカード
// ============================================================
console.log('\n--- シーン10: エンドカード ---');
await page.evaluate(() => {
  const output = document.querySelector('.std-output');
  if (output) output.scrollIntoView({ block: 'start' });
});
await wait(300);

// エンドカードオーバーレイ
await page.evaluate(() => {
  let el = document.getElementById('demo-scene-title');
  if (!el) {
    el = document.createElement('div');
    el.id = 'demo-scene-title';
    document.body.appendChild(el);
  }
  el.style.cssText = `
    position: fixed; inset: 0; z-index: 100000;
    background: rgba(15,23,42,0.88);
    display: flex; flex-direction: column;
    align-items: center; justify-content: center;
    font-family: "Noto Sans JP", "Yu Gothic UI", sans-serif;
    pointer-events: none;
  `;
  el.innerHTML = `
    <div style="color:#fff; font-size:26px; font-weight:800;
                line-height:1.6; text-align:center; padding:0 30px;">
      処方入力アプリ
    </div>
    <div style="color:#60a5fa; font-size:15px; font-weight:600;
                margin-top:16px; letter-spacing:1px;">
      設計思想 ─ 6つの工夫
    </div>
    <div style="color:#94a3b8; font-size:13px; margin-top:18px;
                text-align:center; line-height:2; padding:0 40px;">
      ✅ デフォルト用法の自動設定<br>
      ✅ 一包化サマリー自動集計<br>
      ✅ 不均等投与の専用UI<br>
      ✅ リアルタイム薬価表示<br>
      ✅ 最大量超過の警告（非ブロック）<br>
      ✅ 割り切れない錠数の即時警告<br>
      ✅ 体重換算モード
    </div>
  `;
  el.style.display = 'flex';
});
await wait(100);
await shot(page, 'エンドカード', HOLD_LONG);

// =====================================================
console.log(`\n✅ 録画完了: ${frame} フレーム → ${FRAMES_DIR}`);
console.log(`📹 MP4生成: ffmpeg -framerate 4 -i demo/frames/%04d.png -c:v libx264 -pix_fmt yuv420p demo/demo.mp4`);
await browser.close();
