const PDFDocument = require('pdfkit');
const fs = require('fs');

const doc = new PDFDocument({
  size: 'A4',
  margins: { top: 50, bottom: 50, left: 55, right: 55 },
  info: {
    Title: '令和8年度 診療報酬改定 当院関連ピックアップ',
    Author: '医事課',
    Subject: 'R8診療報酬改定',
  }
});

const output = fs.createWriteStream('C:/Users/Mining-Base/SakigakeAPP/診療報酬/R8改定_当院関連ピックアップ.pdf');
doc.pipe(output);

// Font setup - use Yu Mincho TTF (not TTC)
const FONT_R = 'C:/Windows/Fonts/yumin.ttf';
const FONT_B = 'C:/Windows/Fonts/yumindb.ttf';
const FONT_M = 'C:/Windows/Fonts/yumin.ttf';

// Colors
const C_NAVY = '#1a3353';
const C_BLUE = '#2e5d8a';
const C_RED = '#c0392b';
const C_ORANGE = '#e67e22';
const C_DARK = '#2c3e50';
const C_GRAY = '#7f8c8d';
const C_LIGHT = '#ecf0f1';
const C_WHITE = '#ffffff';
const C_HEADER_BG = '#1a3353';
const C_NEW = '#c0392b';

const PW = 595.28; // A4 width
const PH = 841.89; // A4 height
const ML = 55;
const MR = 55;
const CW = PW - ML - MR; // content width

let y = 50;

function checkPage(needed) {
  if (y + needed > PH - 60) {
    doc.addPage();
    y = 50;
    return true;
  }
  return false;
}

// ========== Utility functions ==========

function drawTitle(text, size, color) {
  checkPage(size + 20);
  doc.font(FONT_B).fontSize(size).fillColor(color).text(text, ML, y);
  y += size + 8;
}

function drawSubTitle(text) {
  checkPage(30);
  doc.font(FONT_B).fontSize(13).fillColor(C_NAVY).text(text, ML, y);
  y += 18;
}

function drawText(text, opts = {}) {
  const size = opts.size || 9;
  const font = opts.bold ? FONT_B : FONT_R;
  const color = opts.color || C_DARK;
  const indent = opts.indent || 0;
  checkPage(size + 6);
  doc.font(font).fontSize(size).fillColor(color);
  const w = opts.width || (CW - indent);
  const h = doc.heightOfString(text, { width: w });
  checkPage(h + 4);
  doc.text(text, ML + indent, y, { width: w });
  y += h + (opts.spacing || 3);
}

function drawBullet(text, opts = {}) {
  const indent = opts.indent || 12;
  checkPage(14);
  doc.font(FONT_R).fontSize(9).fillColor(C_DARK).text('・', ML + indent - 10, y);
  const w = CW - indent;
  const h = doc.heightOfString(text, { width: w });
  doc.text(text, ML + indent, y, { width: w });
  y += h + 2;
}

function drawArrow(text, opts = {}) {
  checkPage(16);
  doc.font(FONT_B).fontSize(9).fillColor(opts.color || C_RED);
  const prefix = '→ ';
  const w = CW - 12;
  const h = doc.heightOfString(prefix + text, { width: w });
  checkPage(h + 4);
  doc.text(prefix + text, ML + 12, y, { width: w });
  y += h + 4;
}

function drawLine(color, thickness) {
  doc.moveTo(ML, y).lineTo(PW - MR, y).strokeColor(color || C_BLUE).lineWidth(thickness || 0.5).stroke();
  y += 4;
}

function drawTag(text, bgColor) {
  checkPage(18);
  const tw = doc.font(FONT_B).fontSize(8).widthOfString(text) + 10;
  doc.roundedRect(ML, y, tw, 15, 3).fill(bgColor || C_NEW);
  doc.font(FONT_B).fontSize(8).fillColor(C_WHITE).text(text, ML + 5, y + 3);
  y += 18;
}

function drawSectionHeader(code, title, extra) {
  checkPage(35);
  // Blue bar
  doc.rect(ML, y, CW, 26).fill(C_NAVY);
  doc.font(FONT_B).fontSize(12).fillColor(C_WHITE).text(code + '  ' + title, ML + 10, y + 6);
  if (extra) {
    const ew = doc.widthOfString(extra);
    doc.font(FONT_R).fontSize(9).fillColor('#aec7e8').text(extra, PW - MR - ew - 10, y + 9);
  }
  y += 30;
}

function drawSubSection(code, title, tags) {
  checkPage(25);
  doc.font(FONT_B).fontSize(11).fillColor(C_BLUE).text(code, ML, y);
  const codeW = doc.widthOfString(code + ' ');
  doc.text(title, ML + codeW + 4, y);
  if (tags) {
    let tx = ML + codeW + doc.widthOfString(title) + 14;
    for (const tag of tags) {
      const tw = doc.font(FONT_B).fontSize(7).widthOfString(tag) + 8;
      doc.roundedRect(tx, y + 2, tw, 13, 2).fill(C_NEW);
      doc.font(FONT_B).fontSize(7).fillColor(C_WHITE).text(tag, tx + 4, y + 4);
      tx += tw + 4;
    }
  }
  y += 18;
  doc.moveTo(ML, y).lineTo(PW - MR, y).strokeColor(C_BLUE).lineWidth(0.3).stroke();
  y += 5;
}

// ========== Table drawing ==========

function drawTable(headers, rows, opts = {}) {
  const colWidths = opts.colWidths || headers.map(() => CW / headers.length);
  const headerBg = opts.headerBg || C_HEADER_BG;
  const rowHeight = opts.rowHeight || 20;
  const fontSize = opts.fontSize || 8;

  // Calculate needed height
  const totalRows = rows.length + 1;
  const needed = totalRows * rowHeight + 10;

  // Header
  checkPage(rowHeight + 10);
  let x = ML;
  doc.rect(x, y, CW, rowHeight).fill(headerBg);
  for (let i = 0; i < headers.length; i++) {
    doc.font(FONT_B).fontSize(fontSize).fillColor(C_WHITE);
    doc.text(headers[i], x + 4, y + (rowHeight - fontSize) / 2, { width: colWidths[i] - 8 });
    x += colWidths[i];
  }
  y += rowHeight;

  // Rows
  for (let r = 0; r < rows.length; r++) {
    // Calculate row height based on content
    let maxH = rowHeight;
    for (let c = 0; c < rows[r].length; c++) {
      const cellText = String(rows[r][c] || '');
      const font = (rows[r][c] && String(rows[r][c]).includes('★')) ? FONT_B : FONT_R;
      const h = doc.font(font).fontSize(fontSize).heightOfString(cellText, { width: colWidths[c] - 8 }) + 8;
      if (h > maxH) maxH = h;
    }

    checkPage(maxH + 2);
    const bg = r % 2 === 0 ? '#f7f9fc' : C_WHITE;
    x = ML;
    doc.rect(x, y, CW, maxH).fill(bg);

    // Row border
    doc.moveTo(x, y + maxH).lineTo(x + CW, y + maxH).strokeColor('#d5dce6').lineWidth(0.3).stroke();

    for (let c = 0; c < rows[r].length; c++) {
      const cellText = String(rows[r][c] || '');
      const isHighlight = cellText.includes('★') || cellText.includes('+') || cellText.includes('新設');
      const font = isHighlight ? FONT_B : FONT_R;
      const color = cellText.includes('★') ? C_RED : (cellText.includes('新設') ? C_NEW : C_DARK);
      doc.font(font).fontSize(fontSize).fillColor(color);
      doc.text(cellText, x + 4, y + 4, { width: colWidths[c] - 8 });
      x += colWidths[c];
    }
    y += maxH;
  }
  y += 6;
}

// ============================================================
// PAGE 1: Title & Hospital Profile
// ============================================================

// Title background
doc.rect(0, 0, PW, 120).fill(C_NAVY);
doc.font(FONT_B).fontSize(22).fillColor(C_WHITE).text('令和8年度 診療報酬改定', ML, 25);
doc.font(FONT_B).fontSize(22).fillColor(C_WHITE).text('当院関連ピックアップ【増補版】', ML, 52);

// Orange accent
doc.rect(ML, 82, 60, 3).fill(C_ORANGE);

doc.font(FONT_R).fontSize(8).fillColor('#aec7e8');
doc.text('作成日: 2026年3月9日  |  資料: 001666622.pdf（令和8年度診療報酬改定 全体概要版）+ 診療報酬改定.docx（改正後点数表）', ML, 92, { width: CW });
doc.text('対象: 1月・2月の請求データから特定した当院算定項目との照合  |  初版(3/6)からの増補箇所を【増補】タグで明示', ML, 104, { width: CW });

y = 130;

// Hospital Profile
drawTitle('当院プロフィール', 14, C_NAVY);
drawTable(
  ['項目', '内容'],
  [
    ['病院種別', '精神科病院'],
    ['病棟構成', '2病棟（精神病棟15対1）＋ 3病棟（精神病棟15対1＋特殊疾患＋療養環境）'],
    ['特定入院料', '精神療養病棟入院料（1,108点 → 改定後 1,174点）'],
    ['外来拠点', '高梁（本院）＋ 新見（サテライト）'],
    ['主な診療', '精神科専門療法、認知症医療、てんかん、レカネマブ（レケンビ）投与'],
    ['月間規模', '1日平均在院約160名・延べ約4,500〜5,000日、外来約1,700〜1,800名（両拠点合計）'],
  ],
  { colWidths: [100, CW - 100], fontSize: 8.5 }
);

// Reform overview
drawTitle('改定全体像（R8年度）', 14, C_NAVY);
drawText('診療報酬本体 +3.09%（R8: +2.41%, R9: +3.77%の2年度平均）', { bold: true, size: 9.5 });
drawText('うち賃上げ分 +1.70% / 物価対応分 +0.76% / 食費・光熱水費 +0.09%', { size: 9 });
drawText('薬価 ▲0.86%  R8年6月施行', { size: 9 });
y += 5;

// ============================================================
// PAGE 2: A. 賃上げ・物価対応
// ============================================================
doc.addPage();
y = 50;

drawSectionHeader('A.', '賃上げ・物価対応', '影響度：大');
drawText('当院算定: 入院BU評価料18 / 外来・在宅BU評価料(I)1・2', { bold: true, color: C_BLUE, size: 9 });
y += 3;

drawSubSection('A-1.', 'ベースアップ評価料の大幅見直し');

drawTable(
  ['変更点', '内容'],
  [
    ['対象職員の拡大', '40歳未満の医師・歯科医師・事務職員も新たに対象（経営者・役員除く）'],
    ['賃上げ目標', 'R8: 3.2%（看護補助者・事務職員は5.7%）、R9: さらに3.2%'],
    ['入院BU評価料', '区分165 → 区分250に拡大（R9は500区分）'],
    ['外来BU(I)', '初診6点→17点、再診2点→4点（R9はさらに倍増）'],
    ['★継続賃上げ上乗せ', 'R8.3.31時点でBU届出済 → 初診23点、再診6点等の高い点数'],
    ['夜勤手当', 'BU評価料の収入を夜勤手当の増額に充当可能に'],
    ['届出簡素化', '賃金改善計画書の作成不要。届出書添付書類のみ。様式97に統合'],
  ],
  { colWidths: [120, CW - 120], fontSize: 8 }
);

// 【増補】BU具体的点数
drawTag('増補');
drawText('外来・在宅ベースアップ評価料(I) 改定後の具体的点数（診療報酬改定.docxより確認）:', { bold: true, size: 8.5, color: C_NAVY });
drawTable(
  ['区分', 'R8年', 'R9年6月～（200/100）'],
  [
    ['初診時', '17点（継続賃上げ: 23点）', '34点（継続: 46点）'],
    ['再診時', '4点（継続: 6点）', '8点（継続: 12点）'],
    ['訪問診療（同一建物外）', '79点（継続: 107点）', '158点（継続: 214点）'],
    ['訪問診療（その他）', '19点（継続: 26点）', '38点（継続: 52点）'],
  ],
  { colWidths: [160, 160, CW - 320], fontSize: 8 }
);

drawSubSection('A-2.', '入院基本料の減算規定【新設・要注意】');
drawText('以下のいずれにも該当しない場合、入院基本料が減算される：', { bold: true, color: C_RED, size: 9 });
drawBullet('R8.3.31時点でBU評価料を届出済');
drawBullet('R6.3月比で継続的に賃上げを実施');
drawBullet('R8.6.1以降の新規開設');
drawArrow('当院はBU評価料18を算定済のため減算回避可能と思われるが、要確認');

drawSubSection('A-3.', '物価対応料【新設】');
drawTag('増補');
drawText('医科点数表（001665292.pdf）にて確認した当院関連の物価対応料:', { bold: true, size: 8.5, color: C_NAVY });
drawTable(
  ['区分', 'R8年', 'R9年（200/100）'],
  [
    ['外来・在宅物価対応料（初診時）', '2点', '4点'],
    ['外来・在宅物価対応料（再診時）', '2点', '4点'],
    ['入院物価対応料（精神病棟10対1）', '13点/日', '26点/日'],
    ['★入院物価対応料（精神病棟15対1）', '8点/日', '16点/日'],
    ['★入院物価対応料（精神療養病棟）', '7点/日', '14点/日'],
    ['入院物価対応料（特殊疾患病棟1）', '15点/日', '30点/日'],
    ['入院物価対応料（特殊疾患病棟2）', '12点/日', '24点/日'],
  ],
  { colWidths: [220, 130, CW - 350], fontSize: 8 }
);
drawArrow('入院・外来ともに届出により自動的に増収。15対1: 8点×延べ約2,500日＝月約20万円、療養病棟: 7点×延べ約2,500日＝月約17.5万円');

// ============================================================
// B. 入院基本料の見直し
// ============================================================
doc.addPage();
y = 50;

drawSectionHeader('B.', '入院基本料・入院料の見直し', '影響度：大');

drawSubSection('B-1.', '精神病棟入院基本料の引上げ');
drawTag('増補');
drawText('診療報酬改定.docxにて確認した改定後の正式点数:', { bold: true, size: 8.5, color: C_NAVY });

drawTable(
  ['入院料', '現行', '改定後', '増減'],
  [
    ['精神病棟10対1入院基本料', '1,306点', '1,471点', '★+165点'],
    ['精神病棟13対1入院基本料', '—', '1,114点', '（新区分）'],
    ['精神病棟15対1入院基本料', '844点', '918点', '★+74点'],
    ['精神病棟18対1（1年未満）', '—', '816点', '—'],
    ['精神病棟18対1（1年以上）', '—', '703点', '—'],
    ['精神病棟20対1（1年未満）', '—', '754点', '—'],
    ['精神病棟20対1（1年以上）', '—', '649点', '—'],
    ['特別入院基本料', '—', '618点', '—'],
  ],
  { colWidths: [180, 80, 90, CW - 350], fontSize: 8 }
);

drawArrow('当院2病棟（15対1）: +74点/日 × 延べ約2,500日 ≒ 月額約185万円の増収見込み', { color: C_RED });

drawTag('増補');
drawText('入院期間加算（精神病棟入院基本料 全区分共通）:', { bold: true, size: 8.5, color: C_NAVY });
drawTable(
  ['入院期間', '加算点数', '特別入院基本料等'],
  [
    ['14日以内', '+465点/日', '+300点/日'],
    ['15日以上30日以内', '+250点/日', '+155点/日'],
    ['31日以上90日以内', '+125点/日', '+100点/日'],
    ['91日以上180日以内', '+10点/日', '—'],
    ['181日以上1年以内', '+3点/日', '—'],
  ],
  { colWidths: [180, 150, CW - 330], fontSize: 8 }
);

drawSubSection('B-2.', '精神療養病棟入院料の引上げ');
drawTag('増補');
drawTable(
  ['入院料', '現行', '改定後', '増減'],
  [
    ['精神療養病棟入院料', '1,108点', '1,174点', '★+66点/日'],
  ],
  { colWidths: [180, 80, 90, CW - 350], fontSize: 8 }
);
drawText('加算:', { bold: true, size: 8.5 });
drawBullet('非定型抗精神病薬加算: +15点/日（抗精神病薬2種類以下の統合失調症患者）');
drawBullet('重症者加算1: +60点/日 / 重症者加算2: +30点/日');
drawBullet('精神保健福祉士配置加算: +30点/日');
drawArrow('3病棟（療養環境）で算定の場合、+66点 × 延べ約2,500日 ≒ 月額約165万円の増収見込み');

drawSubSection('B-3.', '初診料・再診料の引上げ');
drawTag('増補');
drawTable(
  ['項目', '現行', '改定後', '増減'],
  [
    ['初診料', '288点', '291点', '+3点'],
    ['再診料', '75点', '76点', '+1点'],
    ['外来診療料', '74点', '77点', '+3点'],
  ],
  { colWidths: [180, 80, 90, CW - 350], fontSize: 8 }
);

drawSubSection('B-4.', '食事療養費の引上げ');
drawTable(
  ['項目', '現行', '改定後'],
  [
    ['食事療養費（1食）', '690円', '730円（+40円）'],
    ['患者負担増', '—', '原則+40円/食（低所得者は+20〜30円）'],
    ['光熱水費（療養病床65歳以上）', '—', '+60円/日'],
    ['特別食加算', '—', 'てんかん食を明記、嚥下調整食を追加'],
  ],
  { colWidths: [180, 120, CW - 300], fontSize: 8 }
);
drawArrow('当院は延べ約35,000食/月のため、月額約140万円の増収見込み');

// ============================================================
// C. 精神医療関連の新設・見直し
// ============================================================
doc.addPage();
y = 50;

drawSectionHeader('C.', '精神医療関連の新設・見直し', '影響度：大');

drawSubSection('C-1.', '精神病棟看護・多職種協働加算【新設】 ★最重要', ['新設']);
drawTable(
  ['項目', '内容'],
  [
    ['点数（15対1入院基本料の場合）', '★196点/日'],
    ['点数（13対1入院基本料の場合）', '357点/日'],
    ['施設基準①', '看護職員＋OT＋PSW＋公認心理師の合計が常時入院患者13名に1名以上'],
    ['施設基準②', 'うちOT・PSW・公認心理師が1名以上'],
    ['施設基準③', '平均在院日数100日以内'],
    ['増収試算', '2病棟で取得の場合、月額約240万円の増収ポテンシャル'],
  ],
  { colWidths: [170, CW - 170], fontSize: 8 }
);

drawTag('増補');
drawText('算定時の入院ベースアップ評価料への影響:', { bold: true, size: 8.5, color: C_NAVY });
drawBullet('多職種協働加算を算定する15対1の場合、入院BU評価料は「106点/日」区分に該当');
drawBullet('算定しない15対1の場合は「39点/日」区分 → 差額67点/日');
y += 3;

drawSubSection('C-2.', '精神科急性期医師配置加算の対象拡大');
drawText('精神病棟15対1にも対象を拡大（従来は10対1以上のみ）', { size: 9 });
drawTag('増補');
drawTable(
  ['加算区分', '点数/日', '備考'],
  [
    ['加算1', '600点', '—'],
    ['加算2（精神病棟入院基本料）', '500点', '★当院15対1で新規算定の可能性'],
    ['加算2（急性期治療病棟）', '450点', '—'],
    ['加算3', '400点', '—'],
  ],
  { colWidths: [180, 80, CW - 260], fontSize: 8 }
);
drawArrow('施設基準の充足状況を要確認。取得時の増収効果は極めて大きい');

drawSubSection('C-3.', '精神科地域密着多機能体制加算【新設】 ★最重要', ['新設']);
drawTable(
  ['加算', '点数/日', '主な病床要件'],
  [
    ['加算1', '★800点', '精神病床≦100床'],
    ['加算2', '★250点', '101〜150床（又は151〜250床で削減実績あり）'],
    ['加算3', '50点', '精神病床≦250床で削減実績あり'],
  ],
  { colWidths: [80, 80, CW - 160], fontSize: 8 }
);

drawText('主な共通施設基準:', { bold: true, size: 8.5 });
drawBullet('許可病床数350床以下、精神病床割合65%以上');
drawBullet('常勤精神保健指定医2名以上');
drawBullet('精神科救急医療体制への協力実績');
drawBullet('退院支援部門の設置');
drawBullet('平均在院日数≦150日（加算1・2）又は≦250日（加算3）');
drawBullet('新規入院患者の6割以上が6か月以内に退院・自宅等移行（加算1・2）');
drawBullet('精神科在宅医療の提供実績');
drawBullet('障害福祉サービス事業所等の開設');
drawBullet('精神療養病棟の病床割合≦30%');
drawBullet('PSW≧2名、OT≧1名、公認心理師≧1名（常勤）');
drawArrow('加算2（250点/日）取得の場合、月額約125万円の増収（延べ5,000日×250点÷10）');

// ============================================================
// C-4〜 精神科関連その他
// ============================================================
doc.addPage();
y = 50;

drawSectionHeader('C.', '精神医療関連の新設・見直し（続き）', '');

drawSubSection('C-4.', '精神科慢性身体合併症管理加算【新設】', ['新設']);
drawTag('増補');
drawTable(
  ['項目', '内容'],
  [
    ['点数', '★700点/月1回'],
    ['対象', '精神科を標榜する病院で、別に定める慢性疾患を有する精神障害者に必要な治療を行った場合'],
    ['算定可能病棟', '精神病棟入院基本料（18対1・20対1を除く）、精神療養病棟入院料、精神科急性期治療病棟入院料'],
    ['併算定不可', '精神科身体合併症管理加算（A230-3: 7日以内450点/日）とは同時算定不可'],
  ],
  { colWidths: [120, CW - 120], fontSize: 8 }
);
drawArrow('慢性疾患（糖尿病、高血圧等）を有する入院患者への評価。対象患者の洗い出しが必要');

drawSubSection('C-5.', '身体的拘束最小化推進体制加算【新設】', ['新設']);
drawTag('増補');
drawTable(
  ['項目', '内容'],
  [
    ['点数', '40点/日'],
    ['対象病棟', '施設基準に適合する病棟（特殊疾患病棟も対象 → 3病棟で算定可能性）'],
    ['★重要：通則変更', '身体的拘束最小化について別に定める基準を満たす場合に限り入院基本料・特定入院料を算定可能'],
  ],
  { colWidths: [120, CW - 120], fontSize: 8 }
);

drawText('関連する減算ルール（要注意）:', { bold: true, size: 8.5, color: C_RED });
drawBullet('認知症ケア加算: 身体的拘束を実施した日は所定点数の20/100で算定（80%減算）');
drawBullet('看護補助体制充実加算: 拘束実施日は加算1(20点)→加算2(5点)に格下げ');
drawArrow('拘束最小化は単なる加算ではなく、入院基本料算定の前提条件化。体制整備が急務');

drawSubSection('C-6.', '精神科入退院支援加算の詳細', ['増補']);
drawTable(
  ['項目', '内容'],
  [
    ['基本点数', '1,000点（退院時1回）'],
    ['精神科措置入院退院支援加算', '+300点（退院時1回）'],
    ['対象', '退院困難な要因を有する入院患者で在宅療養を希望するもの'],
    ['併算定不可', '精神保健福祉士配置加算、精神科地域移行実施加算、精神科退院指導料'],
  ],
  { colWidths: [170, CW - 170], fontSize: 8 }
);

drawSubSection('C-7.', 'その他の精神科関連改定');
drawTable(
  ['項目', '現行', '改定後'],
  [
    ['心理支援加算', '250点', '★280点/月2回（初回から2年限度）'],
    ['重度認知症加算', '—', '300点/日（入院1月以内）'],
    ['精神科身体合併症管理加算', '7日以内450点等', '透析に係る評価の出来高化等の見直し'],
    ['看護補助加算の名称', '—', '「看護補助・患者ケア体制充実加算」に変更'],
  ],
  { colWidths: [170, 100, CW - 270], fontSize: 8 }
);

drawTag('増補');
drawText('看護補助加算の改定後点数:', { bold: true, size: 8.5, color: C_NAVY });
drawTable(
  ['区分', '点数/日', '備考'],
  [
    ['看護補助加算1', '141点', '—'],
    ['看護補助加算2', '116点', '—'],
    ['看護補助加算3', '88点', '—'],
    ['夜間75対1看護補助加算', '+55点', '入院20日限度'],
    ['夜間看護体制加算', '+176点', '入院初日'],
    ['看護補助体制充実加算1', '+20点/日', '拘束実施日は加算2で算定'],
    ['看護補助体制充実加算2', '+5点/日', '—'],
  ],
  { colWidths: [180, 80, CW - 260], fontSize: 8 }
);

drawSubSection('C-8.', '歯科・口腔管理連携【新設】', ['新設', '増補']);
drawTable(
  ['項目', '点数', '内容'],
  [
    ['★口腔管理連携加算（A233-3）', '600点（入院中1回）', '歯科標榜のない病院の入院患者で口腔状態に課題があり、連携歯科医療機関に紹介→歯科診療が行われた場合。診療情報提供料(I)は包含'],
    ['歯科医療機関連携強化加算', '60点（年1回）', '生活習慣病管理料(I)(II)の加算。糖尿病患者の歯周病予防等のため歯科連携を行った場合'],
    ['（参考）医科連携訪問加算', '500点（歯科側算定）', '連携先の歯科が入院患者へ歯科訪問診療を実施した場合に歯科側で算定。連携の促進に寄与'],
  ],
  { colWidths: [150, 120, CW - 270], fontSize: 8 }
);
drawArrow('口腔管理連携加算（600点）は精神病棟・精神療養病棟ともに算定可能（A103注6・A312にて確認）。歯科との連携体制構築が必要');

// ============================================================
// D. 外来・指導管理・処方関連
// ============================================================
doc.addPage();
y = 50;

drawSectionHeader('D.', '外来・指導管理・処方関連', '影響度：中');

drawSubSection('D-1.', '通院・在宅精神療法の改定', ['増補']);
drawText('改定後の具体的点数（診療報酬改定.docxより確認）:', { bold: true, size: 8.5, color: C_NAVY });
drawTable(
  ['区分', '指定医', '非指定医'],
  [
    ['★初診日 60分以上', '650点', '550点'],
    ['初診日 指定医30分以上60分未満', '550点', '—'],
    ['30分以上', '410点', '390点'],
    ['30分未満', '315点', '290点'],
    ['在宅 60分以上', '590点', '540点'],
    ['在宅 30分以上60分未満', '410点', '390点'],
    ['在宅 30分未満', '315点', '290点'],
    ['措置入院退院後', '660点', '660点'],
  ],
  { colWidths: [200, 140, CW - 340], fontSize: 8 }
);

drawText('主な加算:', { bold: true, size: 8.5 });
drawBullet('20歳未満加算: +320点（初受診1年以内）');
drawBullet('特定薬剤副作用評価加算: +25点/月');
drawBullet('措置入院後継続支援加算: +275点/3月1回');

drawTag('増補');
drawSubSection('D-2.', '療養生活継続支援加算【新設】', ['新設']);
drawTable(
  ['区分', '点数', '条件'],
  [
    ['退院時共同指導料算定患者', '500点/月', '月1回、1年限度'],
    ['それ以外', '350点/月', '月1回、1年限度'],
  ],
  { colWidths: [190, 100, CW - 290], fontSize: 8 }
);
drawArrow('退院後の通院患者への療養生活継続支援を新たに評価。対象患者の把握が重要');

drawTag('増補');
drawSubSection('D-3.', '早期診療体制充実加算【新設】', ['新設']);
drawTable(
  ['加算区分', '初受診3年以内', 'その他'],
  [
    ['加算1', '+50点', '+15点'],
    ['加算2', '+20点', '+15点'],
    ['加算3', '+15点', '+10点'],
  ],
  { colWidths: [160, 160, CW - 320], fontSize: 8 }
);

drawSubSection('D-4.', '精神科継続外来支援・指導料');
drawTag('増補');
drawTable(
  ['項目', '点数'],
  [
    ['基本点数', '55点/日'],
    ['療養生活環境整備指導加算', '+40点（支援を行った場合）'],
  ],
  { colWidths: [200, CW - 200], fontSize: 8 }
);

drawSubSection('D-5.', '精神科訪問看護指示料', ['増補']);
drawTable(
  ['項目', '点数'],
  [
    ['基本点数', '300点/月1回'],
    ['精神科特別訪問看護指示加算', '+100点/月1回（急性増悪時）'],
    ['手順書加算', '+150点/6月1回'],
    ['衛生材料等提供加算', '+80点/月1回'],
  ],
  { colWidths: [200, CW - 200], fontSize: 8 }
);

drawSubSection('D-6.', '処方箋料・一般名処方加算', ['増補']);
drawTable(
  ['区分', '点数', '備考'],
  [
    ['処方箋料（通常）', '60点', '7種類未満、向精神薬適正'],
    ['7種類以上又はベンゾジアゼピン1年超', '32点', '—'],
    ['3種類以上の向精神薬多剤', '20点', '処方の適正化'],
    ['一般名処方加算1', '8点/回', '—'],
    ['一般名処方加算2', '6点/回', '—'],
    ['向精神薬調整連携加算', '+12点/月', '—'],
  ],
  { colWidths: [220, 80, CW - 300], fontSize: 8 }
);

drawSubSection('D-7.', 'その他の外来関連');
drawTable(
  ['当院算定項目', '改定内容'],
  [
    ['医療DX推進体制整備加算5', '電子的診療情報連携体制整備加算に改組（加算1:15点、加算2:9点、加算3:4点 /月）'],
    ['医療情報取得加算（初診/再診）', '医療DX関連の評価体系再編'],
    ['てんかん指導料', '250点/月1回（変更なし）、特別食加算の対象にてんかん食を明記'],
    ['精神科作業療法', '220点/日（多職種協働推進の文脈で見直し）'],
    ['持続性抗精神病注射薬剤治療指導管理料', '入院中: 250点（投与開始月・翌月各1回）、外来: 250点/月1回'],
  ],
  { colWidths: [190, CW - 190], fontSize: 8 }
);

// ============================================================
// E. 認知症医療関連【増補セクション】
// ============================================================
doc.addPage();
y = 50;

drawSectionHeader('E.', '認知症医療関連の改定【増補セクション】', '影響度：中');

drawTag('増補');
drawText('当院は認知症医療を主要な診療領域としており、以下の改定項目が該当する。', { size: 9 });
y += 3;

drawSubSection('E-1.', '認知症ケア加算');
drawTable(
  ['加算区分', '14日以内', '15日以上'],
  [
    ['加算1', '186点/日', '39点/日'],
    ['加算2', '115点/日', '31点/日'],
    ['加算3', '47点/日', '13点/日'],
  ],
  { colWidths: [160, 160, CW - 320], fontSize: 8 }
);
drawText('★重要: 身体的拘束を実施した日は所定点数の20/100で算定（80%減算）', { bold: true, color: C_RED, size: 8.5 });
y += 3;

drawSubSection('E-2.', '認知症専門診断管理料');
drawTable(
  ['区分', '基幹型/地域型', '連携型'],
  [
    ['管理料1（1人1回）', '700点', '500点'],
    ['管理料2（3月1回）', '300点', '280点'],
  ],
  { colWidths: [160, 160, CW - 320], fontSize: 8 }
);

drawSubSection('E-3.', '認知症療養指導料');
drawTable(
  ['区分', '点数', '期間'],
  [
    ['指導料1', '350点/月', '6月限度'],
    ['指導料2', '300点/月', '6月限度'],
    ['指導料3', '300点/月', '6月限度'],
  ],
  { colWidths: [160, 120, CW - 280], fontSize: 8 }
);

drawSubSection('E-4.', '認知症サポート指導料');
drawText('450点（6月に1回）', { bold: true, size: 9 });
y += 3;

drawSubSection('E-5.', '重度認知症患者デイ・ケア料');
drawTable(
  ['項目', '点数'],
  [
    ['基本点数（6時間以上）', '1,040点/日'],
    ['早期加算（1年以内）', '+50点'],
    ['夜間ケア加算（1年以内）', '+100点'],
  ],
  { colWidths: [200, CW - 200], fontSize: 8 }
);

// ============================================================
// F. デイケア等の精神科関連【増補セクション】
// ============================================================

drawSectionHeader('F.', '精神科デイケア等【増補セクション】', '影響度：中');
drawTag('増補');

drawTable(
  ['項目', '点数/日', '備考'],
  [
    ['精神科デイ・ケア（小規模）', '590点', '—'],
    ['精神科デイ・ケア（大規模）', '700点', '—'],
    ['精神科ショート・ケア（小規模）', '275点', '—'],
    ['精神科ショート・ケア（大規模）', '330点', '—'],
    ['★疾患別専門プログラム加算', '+200点', '40歳未満、週1回、5月限度【新設】'],
    ['精神科ナイト・ケア', '540点', '—'],
    ['精神科デイ・ナイト・ケア', '1,000点', '—'],
    ['早期加算（1年以内）', '+50点（デイ）/+20点（ショート）', '—'],
  ],
  { colWidths: [200, 120, CW - 320], fontSize: 8 }
);

// ============================================================
// 影響度まとめ（更新版）
// ============================================================
doc.addPage();
y = 50;

drawSectionHeader('', '当院への影響度まとめ（優先度順）【増補版】', '');
y += 3;

drawTable(
  ['優先度', '項目', '影響', 'アクション'],
  [
    ['★★★', 'ベースアップ評価料見直し・減算規定', '増収＋減算リスク', '届出内容の確認・更新'],
    ['★★★', '物価対応料（新設 15対1: 8点/日、療養: 7点/日）', '月約37.5万円増', '届出準備'],
    ['★★★', '精神病棟看護・多職種協働加算（新設196点/日）', '大幅増収の可能性', 'OT/PSW/心理師の配置検討'],
    ['★★★', '精神科地域密着多機能体制加算（新設 最大800点/日）', '極めて大きい', '施設基準充足の精査'],
    ['★★★', '身体的拘束最小化（通則変更）', '★基本料算定の前提条件化', '体制整備が急務'],
    ['★★☆', '精神病棟15対1引上げ（844→918点 +74点）', '月約185万円増', '自動適用'],
    ['★★☆', '精神療養病棟引上げ（1,108→1,174点 +66点）', '月約165万円増', '自動適用'],
    ['★★☆', '食事療養費引上げ（+40円/食）', '月約140万円増', '自動適用'],
    ['★★☆', '精神科急性期医師配置加算の15対1拡大', '新規算定可能性', '要件確認'],
    ['★★☆', '精神科慢性身体合併症管理加算（新設700点/月）', '新規算定', '対象患者の洗い出し'],
    ['★★☆', '心理支援加算（250→280点＋対象拡大）', '増収', '対象患者の洗い出し'],
    ['★★☆', '療養生活継続支援加算（新設350〜500点/月）', '新規算定', '退院後患者の把握'],
    ['★☆☆', '初診料引上げ（288→291点）', '微増', '自動適用'],
    ['★☆☆', '再診料引上げ（75→76点）', '外来全体で微増', '自動適用'],
    ['★☆☆', '早期診療体制充実加算（新設 +15〜50点）', '新規算定', '施設基準確認'],
    ['★☆☆', '精神科入退院支援加算（1,000点）', '退院時増収', '退院支援体制の確認'],
    ['★☆☆', '認知症ケア加算（拘束時80%減算ルール）', '要注意', '拘束最小化と連動'],
    ['★★☆', '口腔管理連携加算（新設600点/入院中1回）', '新規算定', '歯科連携体制の構築'],
    ['★☆☆', '医療DX関連の評価改組', '届出変更の可能性', '新加算への移行確認'],
  ],
  { colWidths: [50, 230, 105, CW - 385], fontSize: 7.5, rowHeight: 18 }
);

y += 5;

// 増収試算まとめ
drawTitle('増収試算サマリー【増補】', 13, C_NAVY);
drawTable(
  ['項目', '月額試算', '年額試算', '備考'],
  [
    ['15対1入院基本料引上げ（+74点）', '約185万円', '約2,220万円', '2病棟 延べ約2,500日'],
    ['精神療養病棟引上げ（+66点）', '約165万円', '約1,980万円', '3病棟 延べ約2,500日'],
    ['物価対応料・15対1（8点/日）', '約20万円', '約240万円', '延べ約2,500日'],
    ['物価対応料・療養病棟（7点/日）', '約17.5万円', '約210万円', '延べ約2,500日'],
    ['食事療養費引上げ（+40円/食）', '約140万円', '約1,680万円', '延べ約35,000食'],
    ['多職種協働加算（196点/日）', '約240万円', '約2,880万円', '2病棟取得の場合'],
    ['地域密着多機能体制加算2（250点/日）', '約125万円', '約1,500万円', '延べ5,000日'],
    ['合計（上記すべて取得の場合）', '約892万円', '約10,710万円', '要施設基準充足'],
  ],
  { colWidths: [210, 80, 80, CW - 370], fontSize: 8 }
);

y += 8;
drawLine(C_NAVY, 1);
drawText('※本資料は改定概要版（001666622.pdf）及び改正後点数表（診療報酬改定.docx）に基づく整理です。', { size: 7.5, color: C_GRAY });
drawText('※具体的な施設基準の詳細は正式な告示・通知にて確認が必要です。', { size: 7.5, color: C_GRAY });
drawText('※増収試算は概算であり、実際の算定状況により変動します。【増補】マークは初版(3/6)からの追加・修正箇所を示します。', { size: 7.5, color: C_GRAY });

// Finish
doc.end();

output.on('finish', () => {
  console.log('PDF generated successfully!');
  const stats = fs.statSync('C:/Users/Mining-Base/SakigakeAPP/診療報酬/R8改定_当院関連ピックアップ.pdf');
  console.log('File size: ' + (stats.size / 1024).toFixed(1) + ' KB');
});
