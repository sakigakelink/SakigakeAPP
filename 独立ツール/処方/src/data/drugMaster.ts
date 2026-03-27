import type { DrugMasterEntry, DrugStrength } from '../types/prescription';

/** コンパクト記述用ヘルパー: s(規格値, 薬価) */
const s = (value: number, price: number): DrugStrength => ({ value, price });

/**
 * 院内採用薬マスタ — 診療報酬PDFデータ(2月)より自動抽出・整形
 * strengths: 院内で採用されている規格のみ（薬価: 2024年4月改定ベース）
 * maxDailyDose: 添付文書ベースの1日最大量（目安）
 */
export const drugMaster: DrugMasterEntry[] = [
  // ========== 抗精神病薬（非定型） ==========
  { id: 'aripiprazole-od', name: 'アリピプラゾールOD錠', genericName: 'アリピプラゾール', category: '抗精神病薬（非定型）', strengths: [s(3, 10.1), s(6, 13.2), s(12, 17.8), s(24, 31.0)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 30 },
  { id: 'aripiprazole-liq', name: 'アリピプラゾール内用液', genericName: 'アリピプラゾール', category: '抗精神病薬（非定型）', strengths: [s(6, 39.9)], unit: 'mg/包', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 30 },
  { id: 'ebilify-tab', name: 'エビリファイ錠', genericName: 'アリピプラゾール', category: '抗精神病薬（非定型）', strengths: [s(1, 19.2), s(3, 35.4), s(6, 64.9)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 30 },
  { id: 'ebilify-liq', name: 'エビリファイ内用液', genericName: 'アリピプラゾール', category: '抗精神病薬（非定型）', strengths: [s(1, 35.0)], unit: 'mg/mL', inputUnit: 'mL', formType: 'liquid', formSymbol: 'mL', maxDailyDose: 30 },
  { id: 'olanzapine-od', name: 'オランザピンOD錠', genericName: 'オランザピン', category: '抗精神病薬（非定型）', strengths: [s(2.5, 10.1), s(5, 16.3), s(10, 27.6)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 20 },
  { id: 'zyprexa-tab', name: 'ジプレキサ錠', genericName: 'オランザピン', category: '抗精神病薬（非定型）', strengths: [s(10, 249.8)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 20 },
  { id: 'quetiapine-tab', name: 'クエチアピン錠', genericName: 'クエチアピン', category: '抗精神病薬（非定型）', strengths: [s(12.5, 5.9), s(25, 10.1), s(100, 16.7), s(200, 28.2)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 750 },
  { id: 'invega-tab', name: 'インヴェガ錠', genericName: 'パリペリドン', category: '抗精神病薬（非定型）', strengths: [s(6, 335.3)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 12, defaultUsageId: 'qd-am-after' },
  { id: 'rexulti-od', name: 'レキサルティOD錠', genericName: 'ブレクスピプラゾール', category: '抗精神病薬（非定型）', strengths: [s(1, 190.1), s(2, 285.5)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 2, defaultUsageId: 'qd-am-after' },
  { id: 'blonanserin-tab', name: 'ブロナンセリン錠', genericName: 'ブロナンセリン', category: '抗精神病薬（非定型）', strengths: [s(4, 20.9), s(8, 35.0)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 24 },
  { id: 'lodopin-tab', name: 'ロドピン錠', genericName: 'ゾテピン', category: '抗精神病薬（非定型）', strengths: [s(25, 8.0), s(50, 12.6)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 450 },
  { id: 'latuda-tab', name: 'ラツーダ錠', genericName: 'ルラシドン', category: '抗精神病薬（非定型）', strengths: [s(20, 148.7)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 80, defaultUsageId: 'qd-pm-after' },
  { id: 'clozaril-tab', name: 'クロザリル錠', genericName: 'クロザピン', category: '抗精神病薬（非定型）', strengths: [s(100, 391.9)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 600 },

  // ========== 抗精神病薬（定型） ==========
  { id: 'serenace-tab', name: 'セレネース錠', genericName: 'ハロペリドール', category: '抗精神病薬（定型）', strengths: [s(1.5, 5.9), s(3, 6.9)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 30 },
  { id: 'hirnamin-tab', name: 'ヒルナミン錠', genericName: 'レボメプロマジン', category: '抗精神病薬（定型）', strengths: [s(5, 5.9), s(25, 7.0), s(50, 9.4)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 200 },
  { id: 'bromperidol-tab', name: 'ブロムペリドール錠', genericName: 'ブロムペリドール', category: '抗精神病薬（定型）', strengths: [s(6, 9.8)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 18 },
  { id: 'pyrethia-tab', name: 'ピレチア錠', genericName: 'プロメタジン', category: '抗精神病薬（定型）', strengths: [s(25, 5.9)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 150 },

  // ========== 抗うつ薬 ==========
  { id: 'effexor-cap', name: 'イフェクサーSRカプセル', genericName: 'ベンラファキシン', category: '抗うつ薬', strengths: [s(75, 128.8)], unit: 'mg', inputUnit: 'mg', formType: 'capsule', formSymbol: 'C', maxDailyDose: 225 },
  { id: 'escitalopram-tab', name: 'エスシタロプラム錠', genericName: 'エスシタロプラム', category: '抗うつ薬', strengths: [s(10, 13.0)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 20 },
  { id: 'lexapro-tab', name: 'レクサプロ錠', genericName: 'エスシタロプラム', category: '抗うつ薬', strengths: [s(10, 126.7)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 20 },
  { id: 'sertraline-tab', name: 'セルトラリン錠', genericName: 'セルトラリン', category: '抗うつ薬', strengths: [s(25, 10.1)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 100 },
  { id: 'duloxetine-cap', name: 'デュロキセチンカプセル', genericName: 'デュロキセチン', category: '抗うつ薬', strengths: [s(30, 20.1)], unit: 'mg', inputUnit: 'mg', formType: 'capsule', formSymbol: 'C', maxDailyDose: 60 },
  { id: 'trazodone-tab', name: 'トラゾドン塩酸塩錠', genericName: 'トラゾドン', category: '抗うつ薬', strengths: [s(25, 5.9)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 200 },
  { id: 'trintellix-tab', name: 'トリンテリックス錠', genericName: 'ボルチオキセチン', category: '抗うつ薬', strengths: [s(10, 182.3)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 20 },
  { id: 'mirtazapine-tab', name: 'ミルタザピン錠', genericName: 'ミルタザピン', category: '抗うつ薬', strengths: [s(15, 12.4)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 45 },
  { id: 'luvox-tab', name: 'ルボックス錠', genericName: 'フルボキサミン', category: '抗うつ薬', strengths: [s(25, 14.4), s(50, 23.1)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 150 },

  // ========== 睡眠薬 ==========
  { id: 'eszopiclone-tab', name: 'エスゾピクロン錠', genericName: 'エスゾピクロン', category: '睡眠薬', strengths: [s(1, 13.3), s(2, 18.3)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 3, defaultUsageId: 'hs' },
  { id: 'lunesta-tab', name: 'ルネスタ錠', genericName: 'エスゾピクロン', category: '睡眠薬', strengths: [s(2, 52.6)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 3, defaultUsageId: 'hs' },
  { id: 'zolpidem-tab', name: 'ゾルピデム酒石酸塩錠', genericName: 'ゾルピデム', category: '睡眠薬', strengths: [s(5, 10.1), s(10, 10.3)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 10, defaultUsageId: 'hs' },
  { id: 'dayvigo-tab', name: 'デエビゴ錠', genericName: 'レンボレキサント', category: '睡眠薬', strengths: [s(2.5, 57.3), s(5, 85.8)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 10, defaultUsageId: 'hs' },
  { id: 'flunitrazepam-tab', name: 'フルニトラゼパム錠', genericName: 'フルニトラゼパム', category: '睡眠薬', strengths: [s(1, 5.9), s(2, 8.1)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 2, defaultUsageId: 'hs' },
  { id: 'brotizolam-tab', name: 'ブロチゾラム錠', genericName: 'ブロチゾラム', category: '睡眠薬', strengths: [s(0.25, 5.9)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 0.5, defaultUsageId: 'hs' },
  { id: 'belsomra-tab', name: 'ベルソムラ錠', genericName: 'スボレキサント', category: '睡眠薬', strengths: [s(15, 68.4), s(20, 85.8)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 20, defaultUsageId: 'hs' },
  { id: 'benzalin-tab', name: 'ベンザリン錠', genericName: 'ニトラゼパム', category: '睡眠薬', strengths: [s(5, 8.2), s(10, 10.5)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 10, defaultUsageId: 'hs' },
  { id: 'ramelteon-tab', name: 'ラメルテオン錠', genericName: 'ラメルテオン', category: '睡眠薬', strengths: [s(8, 30.8)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 8, defaultUsageId: 'hs' },

  // ========== 抗不安薬 ==========
  { id: 'atarax-p-cap', name: 'アタラックスPカプセル', genericName: 'ヒドロキシジン', category: '抗不安薬', strengths: [s(25, 5.9)], unit: 'mg', inputUnit: 'mg', formType: 'capsule', formSymbol: 'C', maxDailyDose: 150 },
  { id: 'alprazolam-tab', name: 'アルプラゾラム錠', genericName: 'アルプラゾラム', category: '抗不安薬', strengths: [s(0.4, 5.9)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 2.4 },
  { id: 'lexotan-tab', name: 'レキソタン錠', genericName: 'ブロマゼパム', category: '抗不安薬', strengths: [s(2, 5.9), s(5, 6.4)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 15 },
  { id: 'wypax-tab', name: 'ワイパックス錠', genericName: 'ロラゼパム', category: '抗不安薬', strengths: [s(0.5, 5.9)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 3 },
  { id: 'diazepam-tab', name: 'セルシン錠', genericName: 'ジアゼパム', category: '抗不安薬', strengths: [s(2, 5.9)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 20 },

  // ========== 気分安定薬・抗てんかん薬 ==========
  { id: 'depakene-r-tab', name: 'デパケンR錠', genericName: 'バルプロ酸ナトリウム', category: '気分安定薬・抗てんかん薬', strengths: [s(100, 11.6), s(200, 16.3)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 1200 },
  { id: 'depakene-pow', name: 'デパケン細粒', genericName: 'バルプロ酸ナトリウム', category: '気分安定薬・抗てんかん薬', strengths: [s(400, 10.4)], unit: 'mg/g', inputUnit: 'g', formType: 'powder', formSymbol: 'g', maxDailyDose: 1200 },
  { id: 'tegretol-tab', name: 'テグレトール錠', genericName: 'カルバマゼピン', category: '気分安定薬・抗てんかん薬', strengths: [s(200, 9.8)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 1200 },
  { id: 'lithium-tab', name: '炭酸リチウム錠', genericName: '炭酸リチウム', category: '気分安定薬・抗てんかん薬', strengths: [s(100, 5.9), s(200, 8.0)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 1200 },
  { id: 'lamotrigine-tab', name: 'ラモトリギン錠', genericName: 'ラモトリギン', category: '気分安定薬・抗てんかん薬', strengths: [s(100, 24.4)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 400 },
  { id: 'rivotril-tab', name: 'リボトリール錠', genericName: 'クロナゼパム', category: '気分安定薬・抗てんかん薬', strengths: [s(0.5, 8.6), s(1, 12.5)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 6 },
  { id: 'levetiracetam-tab', name: 'レベチラセタム錠', genericName: 'レベチラセタム', category: '気分安定薬・抗てんかん薬', strengths: [s(500, 28.5)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 3000 },
  { id: 'aleviatin-tab', name: 'アレビアチン錠', genericName: 'フェニトイン', category: '気分安定薬・抗てんかん薬', strengths: [s(25, 5.9), s(100, 9.8)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 300 },
  { id: 'aleviatin-pow', name: 'アレビアチン散', genericName: 'フェニトイン', category: '気分安定薬・抗てんかん薬', strengths: [s(100, 7.8)], unit: 'mg/g', inputUnit: 'g', formType: 'powder', formSymbol: 'g', maxDailyDose: 300 },
  { id: 'zonisamide-od', name: 'ゾニサミドOD錠', genericName: 'ゾニサミド', category: '気分安定薬・抗てんかん薬', strengths: [s(25, 10.1)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 600 },
  { id: 'phenobal-tab', name: 'フェノバール錠', genericName: 'フェノバルビタール', category: '気分安定薬・抗てんかん薬', strengths: [s(30, 5.9)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 300 },
  { id: 'phenobal-pow', name: 'フェノバール散', genericName: 'フェノバルビタール', category: '気分安定薬・抗てんかん薬', strengths: [s(100, 6.3)], unit: 'mg/g', inputUnit: 'g', formType: 'powder', formSymbol: 'g', maxDailyDose: 300 },

  // ========== 抗パーキンソン薬 ==========
  { id: 'akineton-tab', name: 'アキネトン錠', genericName: 'ビペリデン', category: '抗パーキンソン薬', strengths: [s(1, 5.9)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 10 },
  { id: 'artane-tab', name: 'アーテン錠', genericName: 'トリヘキシフェニジル', category: '抗パーキンソン薬', strengths: [s(2, 5.9)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 10 },
  { id: 'bi-sifrol-tab', name: 'ビ・シフロール錠', genericName: 'プラミペキソール', category: '抗パーキンソン薬', strengths: [s(0.125, 13.8), s(0.5, 34.8)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 4.5 },
  { id: 'menesit-tab', name: 'メネシット配合錠', genericName: 'レボドパ/カルビドパ', category: '抗パーキンソン薬', strengths: [s(100, 13.1)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 1500 },

  // ========== ADHD治療薬 ==========
  { id: 'atomoxetine-tab', name: 'アトモキセチン錠', genericName: 'アトモキセチン', category: 'ADHD治療薬', strengths: [s(40, 72.9)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 120 },
  { id: 'intuniv-tab', name: 'インチュニブ錠', genericName: 'グアンファシン', category: 'ADHD治療薬', strengths: [s(1, 185.5)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 6 },

  // ========== 認知症治療薬 ==========
  { id: 'donepezil-od', name: 'ドネペジル塩酸塩OD錠', genericName: 'ドネペジル', category: '認知症治療薬', strengths: [s(5, 18.8)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 10 },
  { id: 'memantine-tab', name: 'メマンチン塩酸塩錠', genericName: 'メマンチン', category: '認知症治療薬', strengths: [s(5, 17.3), s(10, 30.6), s(20, 52.0)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 20 },
  { id: 'reminyl-od', name: 'レミニールOD錠', genericName: 'ガランタミン', category: '認知症治療薬', strengths: [s(4, 72.6), s(8, 119.2)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 24 },

  // ========== 消化器系薬 ==========
  { id: 'takecab-tab', name: 'タケキャブ錠', genericName: 'ボノプラザン', category: '消化器系薬', strengths: [s(20, 127.5)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 40 },
  { id: 'omepral-tab', name: 'オメプラール錠', genericName: 'オメプラゾール', category: '消化器系薬', strengths: [s(10, 26.2), s(20, 46.7)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 40 },
  { id: 'nexium-cap', name: 'ネキシウムカプセル', genericName: 'エソメプラゾール', category: '消化器系薬', strengths: [s(20, 81.3)], unit: 'mg', inputUnit: 'mg', formType: 'capsule', formSymbol: 'C', maxDailyDose: 40 },
  { id: 'lansoprazole-od', name: 'ランソプラゾールOD錠', genericName: 'ランソプラゾール', category: '消化器系薬', strengths: [s(15, 11.8), s(30, 16.2)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 30 },
  { id: 'famotidine-d-tab', name: 'ファモチジンD錠', genericName: 'ファモチジン', category: '消化器系薬', strengths: [s(10, 5.9)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 40 },
  { id: 'rebamipide-tab', name: 'レバミピド錠', genericName: 'レバミピド', category: '消化器系薬', strengths: [s(100, 10.1)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 300 },
  { id: 'promac-d-tab', name: 'プロマックD錠', genericName: 'ポラプレジンク', category: '消化器系薬', strengths: [s(75, 13.7)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 150 },
  { id: 'gascon-tab', name: 'ガスコン錠', genericName: 'ジメチコン', category: '消化器系薬', strengths: [s(40, 5.9)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 240 },
  { id: 'mosapride-tab', name: 'モサプリドクエン酸塩錠', genericName: 'モサプリド', category: '消化器系薬', strengths: [s(5, 10.1)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 15 },
  { id: 'urso-tab', name: 'ウルソ錠', genericName: 'ウルソデオキシコール酸', category: '消化器系薬', strengths: [s(100, 7.3)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 900 },
  { id: 'amitiza-cap', name: 'アミティーザカプセル', genericName: 'ルビプロストン', category: '消化器系薬', strengths: [s(24, 97.3)], unit: 'μg', inputUnit: 'μg', formType: 'capsule', formSymbol: 'C', maxDailyDose: 48 },
  { id: 'goofice-tab', name: 'グーフィス錠', genericName: 'エロビキシバット', category: '消化器系薬', strengths: [s(5, 72.8)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 15 },
  { id: 'sennoside-tab', name: 'センノシド錠', genericName: 'センノシド', category: '消化器系薬', strengths: [s(12, 5.9)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 48 },
  { id: 'picosulfate-tab', name: 'ピコスルファートナトリウム錠', genericName: 'ピコスルファートナトリウム', category: '消化器系薬', strengths: [s(2.5, 5.9)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 10 },
  { id: 'picosulfate-liq', name: 'ピコスルファートナトリウム内用液', genericName: 'ピコスルファートナトリウム', category: '消化器系薬', strengths: [s(7.5, 4.2)], unit: 'mg/mL', inputUnit: 'mL', formType: 'liquid', formSymbol: 'mL', maxDailyDose: 10 },
  { id: 'magmitt-tab', name: 'マグミット錠', genericName: '酸化マグネシウム', category: '消化器系薬', strengths: [s(250, 5.7), s(500, 8.5)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 2000 },
  { id: 'mg-oxide-pow', name: '酸化マグネシウム細粒', genericName: '酸化マグネシウム', category: '消化器系薬', strengths: [s(830, 6.5)], unit: 'mg/g', inputUnit: 'g', formType: 'powder', formSymbol: 'g', maxDailyDose: 2000 },
  { id: 'lactulose-syr', name: 'ラクツロースシロップ', genericName: 'ラクツロース', category: '消化器系薬', strengths: [s(600, 4.8)], unit: 'mg/mL', inputUnit: 'mL', formType: 'liquid', formSymbol: 'mL', maxDailyDose: 60000 },
  { id: 'biosthree-od', name: 'ビオスリー配合OD錠', genericName: 'ビオスリー', category: '消化器系薬', strengths: [s(1, 5.9)], unit: '錠', inputUnit: '錠', formType: 'tablet', formSymbol: 'T' },
  { id: 'sm-pow', name: 'Ｓ・Ｍ配合散', genericName: 'S・M配合散', category: '消化器系薬', strengths: [s(1, 6.3)], unit: 'g', inputUnit: 'g', formType: 'powder', formSymbol: 'g' },
  { id: 'mucosolvan-tab', name: 'ムコソルバン錠', genericName: 'アンブロキソール', category: '消化器系薬', strengths: [s(15, 5.9)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 45 },
  { id: 'mucodyne-syr', name: 'ムコダインシロップ', genericName: 'カルボシステイン', category: '消化器系薬', strengths: [s(50, 3.9)], unit: 'mg/mL', inputUnit: 'mL', formType: 'liquid', formSymbol: 'mL', maxDailyDose: 1500 },
  { id: 'polystyrene-jelly', name: 'ポリスチレンスルホン酸Ca経口ゼリー', genericName: 'ポリスチレンスルホン酸カルシウム', category: '消化器系薬', strengths: [s(20, 57.8)], unit: 'g/包', inputUnit: 'g', formType: 'powder', formSymbol: 'g' },

  // ========== 循環器系薬 ==========
  { id: 'amlodipine-tab', name: 'アムロジピン錠', genericName: 'アムロジピン', category: '循環器系薬', strengths: [s(2.5, 10.1)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 10 },
  { id: 'azilva-tab', name: 'アジルバ錠', genericName: 'アジルサルタン', category: '循環器系薬', strengths: [s(20, 50.1)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 40 },
  { id: 'candesartan-tab', name: 'カンデサルタン錠', genericName: 'カンデサルタン', category: '循環器系薬', strengths: [s(4, 10.1)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 12 },
  { id: 'entresto-tab', name: 'エンレスト錠', genericName: 'サクビトリルバルサルタン', category: '循環器系薬', strengths: [s(50, 62.1)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 400 },
  { id: 'lasix-tab', name: 'ラシックス錠', genericName: 'フロセミド', category: '循環器系薬', strengths: [s(20, 9.8)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 80 },
  { id: 'furosemide-tab', name: 'フロセミド錠', genericName: 'フロセミド', category: '循環器系薬', strengths: [s(20, 5.9)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 80 },
  { id: 'furosemide-pow', name: 'フロセミド細粒', genericName: 'フロセミド', category: '循環器系薬', strengths: [s(40, 6.3)], unit: 'mg/g', inputUnit: 'g', formType: 'powder', formSymbol: 'g', maxDailyDose: 80 },
  { id: 'diart-tab', name: 'ダイアート錠', genericName: 'アゾセミド', category: '循環器系薬', strengths: [s(30, 18.2)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 60 },
  { id: 'spironolactone-tab', name: 'スピロノラクトン錠', genericName: 'スピロノラクトン', category: '循環器系薬', strengths: [s(25, 5.9)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 100 },
  { id: 'maintate-tab', name: 'メインテート錠', genericName: 'ビソプロロール', category: '循環器系薬', strengths: [s(0.625, 10.1), s(2.5, 15.3)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 5 },
  { id: 'nifedipine-cr-tab', name: 'ニフェジピンCR錠', genericName: 'ニフェジピン', category: '循環器系薬', strengths: [s(20, 10.1)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 60 },
  { id: 'sigmart-tab', name: 'シグマート錠', genericName: 'ニコランジル', category: '循環器系薬', strengths: [s(5, 14.5)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 15 },
  { id: 'nitrol-r-cap', name: 'ニトロールRカプセル', genericName: 'イソソルビド', category: '循環器系薬', strengths: [s(20, 10.9)], unit: 'mg', inputUnit: 'mg', formType: 'capsule', formSymbol: 'C', maxDailyDose: 40 },
  { id: 'ebrantil-cap', name: 'エブランチルカプセル', genericName: 'ウラピジル', category: '循環器系薬', strengths: [s(15, 19.7)], unit: 'mg', inputUnit: 'mg', formType: 'capsule', formSymbol: 'C', maxDailyDose: 120 },
  { id: 'bayaspirin-tab', name: 'バイアスピリン錠', genericName: 'アスピリン', category: '循環器系薬', strengths: [s(100, 5.9)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 300 },
  { id: 'plavix-tab', name: 'プラビックス錠', genericName: 'クロピドグレル', category: '循環器系薬', strengths: [s(75, 18.3)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 75 },
  { id: 'lixiana-tab', name: 'リクシアナ錠', genericName: 'エドキサバン', category: '循環器系薬', strengths: [s(15, 132.4)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 60 },
  { id: 'cilostazol-tab', name: 'シロスタゾール錠', genericName: 'シロスタゾール', category: '循環器系薬', strengths: [s(50, 10.1)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 200 },
  { id: 'samsca-od', name: 'サムスカOD錠', genericName: 'トルバプタン', category: '循環器系薬', strengths: [s(7.5, 1094.3)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 60 },
  { id: 'opalmon-tab', name: 'オパルモン錠', genericName: 'リマプロスト', category: '循環器系薬', strengths: [s(5, 10.6)], unit: 'μg', inputUnit: 'μg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 15 },
  { id: 'livalo-tab', name: 'リバロ錠', genericName: 'ピタバスタチン', category: '循環器系薬', strengths: [s(2, 17.2)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 4 },
  { id: 'zetia-tab', name: 'ゼチーア錠', genericName: 'エゼチミブ', category: '循環器系薬', strengths: [s(10, 38.7)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 10 },
  { id: 'tamsulosin-od', name: 'タムスロシン塩酸塩OD錠', genericName: 'タムスロシン', category: '循環器系薬', strengths: [s(0.2, 10.1)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 0.4 },

  // ========== 糖尿病薬 ==========
  { id: 'jardiance-tab', name: 'ジャディアンス錠', genericName: 'エンパグリフロジン', category: '糖尿病薬', strengths: [s(10, 175.9)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 25 },
  { id: 'januvia-tab', name: 'ジャヌビア錠', genericName: 'シタグリプチン', category: '糖尿病薬', strengths: [s(50, 46.2)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 100 },
  { id: 'forxiga-tab', name: 'フォシーガ錠', genericName: 'ダパグリフロジン', category: '糖尿病薬', strengths: [s(5, 129.7)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 10 },
  { id: 'glufast-tab', name: 'グルファスト錠', genericName: 'ミチグリニド', category: '糖尿病薬', strengths: [s(10, 16.2)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 30 },
  { id: 'trazenta-tab', name: 'トラゼンタ錠', genericName: 'リナグリプチン', category: '糖尿病薬', strengths: [s(5, 132.1)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 5 },
  { id: 'voglibose-tab', name: 'ボグリボース錠', genericName: 'ボグリボース', category: '糖尿病薬', strengths: [s(0.2, 10.1)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 0.9 },
  { id: 'metgluco-tab', name: 'メトグルコ錠', genericName: 'メトホルミン', category: '糖尿病薬', strengths: [s(250, 10.1)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 2250 },

  // ========== リスペリドン系（複数剤型） ==========
  { id: 'risperidone-tab', name: 'リスペリドン錠', genericName: 'リスペリドン', category: '抗精神病薬（非定型）', strengths: [s(0.5, 5.9), s(1, 10.1), s(2, 14.1)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 12 },
  { id: 'risperidone-liq', name: 'リスペリドン内用液', genericName: 'リスペリドン', category: '抗精神病薬（非定型）', strengths: [s(1, 19.2)], unit: 'mg/mL', inputUnit: 'mL', formType: 'liquid', formSymbol: 'mL', maxDailyDose: 12 },
  { id: 'risperidone-pow', name: 'リスペリドン細粒', genericName: 'リスペリドン', category: '抗精神病薬（非定型）', strengths: [s(10, 40.8)], unit: 'mg/g', inputUnit: 'g', formType: 'powder', formSymbol: 'g', maxDailyDose: 12 },

  // ========== 漢方薬 ==========
  { id: 'yokukansan-pow', name: 'ツムラ抑肝散エキス顆粒', genericName: '抑肝散', category: '漢方薬', strengths: [s(2.5, 14.7)], unit: 'g/包', inputUnit: 'g', formType: 'powder', formSymbol: 'g' },
  { id: 'daikenchuto-pow', name: 'ツムラ大建中湯エキス顆粒', genericName: '大建中湯', category: '漢方薬', strengths: [s(2.5, 22.2)], unit: 'g/包', inputUnit: 'g', formType: 'powder', formSymbol: 'g' },
  { id: 'daiokanzo-pow', name: 'ツムラ大黄甘草湯エキス顆粒', genericName: '大黄甘草湯', category: '漢方薬', strengths: [s(2.5, 5.4)], unit: 'g/包', inputUnit: 'g', formType: 'powder', formSymbol: 'g' },
  { id: 'shakuyaku-pow', name: 'ツムラ芍薬甘草湯エキス顆粒', genericName: '芍薬甘草湯', category: '漢方薬', strengths: [s(2.5, 6.0)], unit: 'g/包', inputUnit: 'g', formType: 'powder', formSymbol: 'g' },
  { id: 'kakkonto-pow', name: 'ツムラ葛根湯エキス顆粒', genericName: '葛根湯', category: '漢方薬', strengths: [s(2.5, 8.6)], unit: 'g/包', inputUnit: 'g', formType: 'powder', formSymbol: 'g' },

  // ========== 抗菌薬 ==========
  { id: 'augmentin-tab', name: 'オーグメンチン配合錠', genericName: 'アモキシシリン/クラブラン酸', category: '抗菌薬', strengths: [s(250, 29.3)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 1000 },
  { id: 'sawacillin-cap', name: 'サワシリンカプセル', genericName: 'アモキシシリン', category: '抗菌薬', strengths: [s(250, 10.1)], unit: 'mg', inputUnit: 'mg', formType: 'capsule', formSymbol: 'C', maxDailyDose: 1500 },
  { id: 'keflex-cap', name: 'ケフレックスカプセル', genericName: 'セファレキシン', category: '抗菌薬', strengths: [s(250, 10.1)], unit: 'mg', inputUnit: 'mg', formType: 'capsule', formSymbol: 'C', maxDailyDose: 2000 },
  { id: 'levofloxacin-tab', name: 'レボフロキサシン錠', genericName: 'レボフロキサシン', category: '抗菌薬', strengths: [s(250, 16.6)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 500 },
  { id: 'valtrex-tab', name: 'バルトレックス錠', genericName: 'バラシクロビル', category: '抗菌薬', strengths: [s(500, 49.3)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 3000 },

  // ========== 鎮痛薬・解熱薬 ==========
  { id: 'calonal-tab', name: 'カロナール錠', genericName: 'アセトアミノフェン', category: '鎮痛薬', strengths: [s(200, 7.0)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 4000 },
  { id: 'loxonin-tab', name: 'ロキソニン錠', genericName: 'ロキソプロフェン', category: '鎮痛薬', strengths: [s(60, 7.8)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 180 },
  { id: 'celecox-tab', name: 'セレコックス錠', genericName: 'セレコキシブ', category: '鎮痛薬', strengths: [s(100, 21.3)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 400 },
  { id: 'lyrica-cap', name: 'リリカカプセル', genericName: 'プレガバリン', category: '鎮痛薬', strengths: [s(25, 18.1)], unit: 'mg', inputUnit: 'mg', formType: 'capsule', formSymbol: 'C', maxDailyDose: 600 },

  // ========== その他内科系 ==========
  { id: 'aspara-k-tab', name: 'アスパラカリウム錠', genericName: 'L-アスパラギン酸カリウム', category: 'その他', strengths: [s(300, 5.9)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 2700 },
  { id: 'avolve-cap', name: 'アボルブカプセル', genericName: 'デュタステリド', category: 'その他', strengths: [s(0.5, 52.0)], unit: 'mg', inputUnit: 'mg', formType: 'capsule', formSymbol: 'C', maxDailyDose: 0.5 },
  { id: 'arimidex-tab', name: 'アリミデックス錠', genericName: 'アナストロゾール', category: 'その他', strengths: [s(1, 97.2)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 1 },
  { id: 'allelock-tab', name: 'アレロック錠', genericName: 'オロパタジン', category: 'その他', strengths: [s(5, 10.1)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 10 },
  { id: 'allopurinol-tab', name: 'アロプリノール錠', genericName: 'アロプリノール', category: 'その他', strengths: [s(100, 5.9)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 300 },
  { id: 'febuxostat-tab', name: 'フェブキソスタット錠', genericName: 'フェブキソスタット', category: 'その他', strengths: [s(20, 17.7)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 60 },
  { id: 'thyradin-s-tab', name: 'チラーヂンS錠', genericName: 'レボチロキシン', category: 'その他', strengths: [s(25, 9.8)], unit: 'μg', inputUnit: 'μg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 300 },
  { id: 'theodur-tab', name: 'テオドール錠', genericName: 'テオフィリン', category: 'その他', strengths: [s(100, 7.0)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 400 },
  { id: 'darbuloc-tab', name: 'ダーブロック錠', genericName: 'ダプロデュスタット', category: 'その他', strengths: [s(2, 232.4)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 24 },
  { id: 'feromia-tab', name: 'フェロミア錠', genericName: 'クエン酸第一鉄ナトリウム', category: 'その他', strengths: [s(50, 5.9)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 200 },
  { id: 'foliamin-tab', name: 'フォリアミン錠', genericName: '葉酸', category: 'その他', strengths: [s(5, 9.8)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 20 },
  { id: 'methycobal-tab', name: 'メチコバール錠', genericName: 'メコバラミン', category: 'その他', strengths: [s(500, 5.9)], unit: 'μg', inputUnit: 'μg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 1500 },
  { id: 'yubera-n-cap', name: 'ユベラNカプセル', genericName: 'トコフェロールニコチン酸エステル', category: 'その他', strengths: [s(100, 5.9)], unit: 'mg', inputUnit: 'mg', formType: 'capsule', formSymbol: 'C', maxDailyDose: 600 },
  { id: 'rocaltrole-cap', name: 'ロカルトロールカプセル', genericName: 'カルシトリオール', category: 'その他', strengths: [s(0.25, 11.5)], unit: 'μg', inputUnit: 'μg', formType: 'capsule', formSymbol: 'C', maxDailyDose: 1 },
  { id: 'tancarl-tab', name: '炭カル錠', genericName: '沈降炭酸カルシウム', category: 'その他', strengths: [s(500, 5.7)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 3000 },
  { id: 'risedronate-tab', name: 'リセドロン酸Na錠', genericName: 'リセドロン酸ナトリウム', category: 'その他', strengths: [s(17.5, 68.8)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 17.5 },
  { id: 'methotrexate-cap', name: 'メトトレキサートカプセル', genericName: 'メトトレキサート', category: 'その他', strengths: [s(2, 24.2)], unit: 'mg', inputUnit: 'mg', formType: 'capsule', formSymbol: 'C', maxDailyDose: 8 },
  { id: 'betanis-tab', name: 'ベタニス錠', genericName: 'ミラベグロン', category: 'その他', strengths: [s(50, 112.3)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 50 },
  { id: 'silodosin-tab', name: 'ユリーフ錠', genericName: 'シロドシン', category: 'その他', strengths: [s(4, 19.6)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 8 },
  { id: 'xyzal-tab', name: 'ザイザル錠', genericName: 'レボセチリジン', category: 'その他', strengths: [s(5, 21.9)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 10 },
  { id: 'nacl-pow', name: '塩化ナトリウム', genericName: '塩化ナトリウム', category: 'その他', strengths: [s(1, 1.5)], unit: 'g', inputUnit: 'g', formType: 'powder', formSymbol: 'g' },
  { id: 'lactose-pow', name: '乳糖水和物', genericName: '乳糖', category: 'その他', strengths: [s(1, 1.2)], unit: 'g', inputUnit: 'g', formType: 'powder', formSymbol: 'g' },
  { id: 'loicon-tab', name: 'ロイコン錠', genericName: 'ピリドスチグミン', category: 'その他', strengths: [s(10, 5.9)], unit: 'mg', inputUnit: 'mg', formType: 'tablet', formSymbol: 'T', maxDailyDose: 180 },
];
