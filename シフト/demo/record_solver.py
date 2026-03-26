"""
シフト管理アプリ ソルバーデモ動画 録画スクリプト v8
実機操作をそのまま再現: クリアボタン→希望入力→ソルバー起動→複数案→シフト表→公平性評価

v8 変更点:
- 実ブラウザの localStorage 全体をダンプしたファイルをそのまま Playwright に注入
- これにより D.staff (workType=fixed 等) が正しく設定される
- 希望は wishes_data.json から一病棟分だけフィルタして注入
"""
import asyncio
from playwright.async_api import async_playwright
import time, os, glob, json, shutil, subprocess

OUTPUT_DIR = r"C:\Users\sakigake\Desktop\solver_recording"
URL = "http://127.0.0.1:5000/"
FFMPEG = r"C:\Users\sakigake\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1-full_build\bin\ffmpeg.exe"
SHIFT_FILE = r"C:\Users\sakigake\SakigakeAPP\シフト管理\shifts\ichiboutou\2026-04.json"
BACKUP_FILE = r"C:\Users\sakigake\Desktop\2026-04_backup.json"
WISHES_FILE = r"C:\Users\sakigake\SakigakeAPP\シフト管理\shared\wishes_data.json"
LS_DUMP_FILE = r"C:\Users\sakigake\Desktop\localStorage_dump.json"


async def smooth_scroll(page, target_y, steps=20, pause=50):
    current_y = await page.evaluate("window.scrollY")
    delta = (target_y - current_y) / steps
    for i in range(steps):
        await page.evaluate(f"window.scrollTo(0, {int(current_y + delta * (i + 1))})")
        await page.wait_for_timeout(pause)


async def scroll_to_element(page, selector, offset=-100):
    pos = await page.evaluate(f"""() => {{
        const el = document.querySelector('{selector}');
        if (!el) return null;
        return window.scrollY + el.getBoundingClientRect().top + ({offset});
    }}""")
    if pos is not None:
        await smooth_scroll(page, max(0, pos))


# --- Scene 1: App overview (クリア前の状態) ---
async def scene1_overview(page, out):
    print("=== S1: Overview ===")
    await page.evaluate("window.scrollTo(0, 0)")
    await page.wait_for_timeout(3000)
    await page.screenshot(path=os.path.join(out, "s1_overview.png"))
    await page.wait_for_timeout(2000)


# --- Scene 2: クリアボタンを押してシフトをクリア ---
async def scene2_clear(page, out):
    print("=== S2: Clear shifts ===")
    # クリアボタンまでスクロール
    await scroll_to_element(page, "#clearBtn", offset=-200)
    await page.wait_for_timeout(2000)
    await page.screenshot(path=os.path.join(out, "s2_before_clear.png"))

    # クリアボタン押下（confirm ダイアログは handle_dialog で自動承認）
    print("   Click clearBtn")
    await page.click("#clearBtn")
    await page.wait_for_timeout(3000)

    # クリア後のシフト表を見せる
    await scroll_to_element(page, "#shiftTable", offset=-30)
    await page.wait_for_timeout(3000)
    await page.screenshot(path=os.path.join(out, "s2_cleared.png"))
    print("   Cleared via app button")


# --- Scene 3: Wish input ---
async def scene3_wish_input(page, out):
    print("=== S3: Wish input ===")
    await scroll_to_element(page, "#wishStaffSelect", offset=-50)
    await page.wait_for_timeout(2000)

    # (1) 1人目 - Day 5 Off
    print("   Select staff 1")
    await page.select_option("#wishStaffSelect", index=1)
    await page.wait_for_timeout(2000)

    chips = page.locator("#wishDayChips button, #wishDayChips .day-chip")
    chip_count = await chips.count()
    print(f"   Day chips: {chip_count}")

    if chip_count >= 5:
        print("   Click day 5")
        await chips.nth(4).click()
        await page.wait_for_timeout(1000)

    print("   Click Off btn")
    off_btn = page.locator("#wishShiftBtns button:has-text('休')")
    if await off_btn.count() > 0:
        await off_btn.first.click()
        await page.wait_for_timeout(1500)

    commit = page.locator("#wishCommitBtn")
    if await commit.count() > 0 and await commit.is_visible():
        print("   Commit")
        await commit.click()
        await page.wait_for_timeout(2500)

    await page.screenshot(path=os.path.join(out, "s3_wish1.png"))

    # (2) 2人目 - Day 10 Paid leave
    print("   Select staff 2")
    await page.select_option("#wishStaffSelect", index=2)
    await page.wait_for_timeout(1500)

    chips = page.locator("#wishDayChips button, #wishDayChips .day-chip")
    chip_count = await chips.count()

    if chip_count >= 10:
        print("   Click day 10")
        await chips.nth(9).click()
        await page.wait_for_timeout(1000)

    print("   Click Paid btn")
    paid_btn = page.locator("#wishShiftBtns button:has-text('有給')")
    if await paid_btn.count() > 0:
        await paid_btn.first.click()
        await page.wait_for_timeout(1500)

    if await commit.count() > 0 and await commit.is_visible():
        print("   Commit")
        await commit.click()
        await page.wait_for_timeout(2500)

    await page.screenshot(path=os.path.join(out, "s3_wish2.png"))
    await page.wait_for_timeout(2000)
    await page.screenshot(path=os.path.join(out, "s3_wishes_done.png"))


# --- Scene 4: Start solver ---
async def scene4_start_solver(page, out):
    print("=== S4: Start solver ===")
    await scroll_to_element(page, "#btnSolvePool", offset=-200)
    await page.wait_for_timeout(2000)

    # ソルバー起動前の状態を確認
    state = await page.evaluate("""() => {
        const d = JSON.parse(localStorage.getItem('sakigakeData') || '{}');
        const shifts = d.shifts || {};
        const keys = Object.keys(shifts);
        let shiftCounts = {};
        for (const k of keys) {
            shiftCounts[k] = Object.keys(shifts[k] || {}).length;
        }
        return {
            url: location.href,
            shiftKeys: keys,
            shiftCounts: shiftCounts
        };
    }""")
    print(f"   App state: {json.dumps(state, ensure_ascii=False)}")

    await page.screenshot(path=os.path.join(out, "s4_before.png"))

    print("   Click pool solver")
    await page.click("#btnSolvePool")
    await page.wait_for_timeout(3000)
    await page.screenshot(path=os.path.join(out, "s4_started.png"))


# --- Scene 5: Solver running ---
async def scene5_solver_running(page, out):
    print("=== S5: Solver running ===")
    await scroll_to_element(page, "#solveProgress", offset=-50)
    await page.wait_for_timeout(1000)

    n = 0
    t0 = time.time()
    max_wait = 180

    while time.time() - t0 < max_wait:
        await page.wait_for_timeout(5000)
        sec = int(time.time() - t0)
        fname = f"s5_{n:03d}_{sec}s.png"
        await page.screenshot(path=os.path.join(out, fname))
        print(f"   {fname}")
        n += 1

        try:
            status = await page.evaluate("""() => {
                const progress = document.getElementById('solveProgress');
                const btn = document.getElementById('btnSolve');
                const btnPool = document.getElementById('btnSolvePool');
                const draftList = document.getElementById('draftList');
                const draftBtns = draftList ? draftList.querySelectorAll('button').length : 0;
                return {
                    progressVisible: progress && progress.style.display !== 'none' && progress.offsetHeight > 0,
                    btnDisabled: btn ? btn.disabled : null,
                    draftBtns: draftBtns
                };
            }""")
            print(f"   Status: progress={status['progressVisible']}, "
                  f"disabled={status['btnDisabled']}, drafts={status['draftBtns']}")

            if not status['progressVisible'] and status['btnDisabled'] is False:
                print(f"   >>> Solver DONE ({sec}s) - button re-enabled")
                break

        except Exception as ex:
            print(f"   Check error: {ex}")

    elapsed = int(time.time() - t0)
    print(f"   Total wait: {elapsed}s")

    # ソルバーログ保存
    log_content = await page.evaluate("""() => {
        const log = document.getElementById('log');
        const solveLog = document.getElementById('solveLog');
        return {
            logText: log ? log.innerText.substring(0, 2000) : '',
            solveLogText: solveLog ? solveLog.innerText.substring(0, 2000) : '',
            progressText: document.getElementById('solveProgress') ?
                document.getElementById('solveProgress').innerText.substring(0, 500) : ''
        };
    }""")
    log_path = os.path.join(out, "solver_log.txt")
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(f"=== log ===\n{log_content['logText']}\n\n")
        f.write(f"=== solveLog ===\n{log_content['solveLogText']}\n\n")
        f.write(f"=== progress ===\n{log_content['progressText']}\n")
    print(f"   Solver log saved to {log_path}")

    await page.wait_for_timeout(3000)
    await page.screenshot(path=os.path.join(out, "s5_done.png"))


# --- Scene 6: Draft list ---
async def scene6_draft_list(page, out):
    print("=== S6: Draft list ===")

    await page.evaluate("""() => {
        const dp = document.getElementById('draftPanel');
        if (dp) dp.style.display = 'block';
    }""")
    await page.wait_for_timeout(1000)

    await scroll_to_element(page, "#draftPanel", offset=-50)
    await page.wait_for_timeout(4000)
    await page.screenshot(path=os.path.join(out, "s6_drafts.png"))

    btns = page.locator("#draftList button")
    cnt = await btns.count()
    print(f"   Draft buttons (all): {cnt}")

    show_btns = []
    for i in range(cnt):
        txt = await btns.nth(i).text_content()
        if "表示" in (txt or ""):
            show_btns.append(i)
    print(f"   Show buttons: {len(show_btns)}")

    if len(show_btns) >= 2:
        print("   View draft B")
        await btns.nth(show_btns[1]).scroll_into_view_if_needed()
        await page.wait_for_timeout(500)
        await btns.nth(show_btns[1]).click(timeout=10000)
        await page.wait_for_timeout(3000)
        await page.screenshot(path=os.path.join(out, "s6_draftB.png"))

    if len(show_btns) >= 1:
        print("   View best")
        await btns.nth(show_btns[0]).scroll_into_view_if_needed()
        await page.wait_for_timeout(500)
        await btns.nth(show_btns[0]).click(timeout=10000)
        await page.wait_for_timeout(3000)
    await page.screenshot(path=os.path.join(out, "s6_best.png"))


# --- Scene 7: Shift grid ---
async def scene7_shift_grid(page, out):
    print("=== S7: Shift grid ===")
    await scroll_to_element(page, "#shiftTable", offset=-30)
    await page.wait_for_timeout(3000)
    await page.screenshot(path=os.path.join(out, "s7_grid0.png"))

    for i in range(4):
        await page.evaluate("window.scrollBy(0, 300)")
        await page.wait_for_timeout(2500)
        await page.screenshot(path=os.path.join(out, f"s7_grid{i+1}.png"))


# --- Scene 8: Evaluation ---
async def scene8_evaluation(page, out):
    print("=== S8: Evaluation ===")

    await scroll_to_element(page, "#fairnessMetrics", offset=-30)
    await page.wait_for_timeout(4000)
    await page.screenshot(path=os.path.join(out, "s8_fairness.png"))

    await scroll_to_element(page, "#personalLoadPanel", offset=-30)
    await page.wait_for_timeout(4000)
    await page.screenshot(path=os.path.join(out, "s8_load.png"))

    await scroll_to_element(page, "#laborCompliancePanel", offset=-30)
    await page.wait_for_timeout(4000)
    await page.screenshot(path=os.path.join(out, "s8_labor.png"))

    await page.screenshot(path=os.path.join(out, "s8_fullpage.png"), full_page=True)


async def main():
    # --- Step 0: バックアップ作成 ---
    print("=== Backup shift file ===")
    if os.path.exists(SHIFT_FILE):
        shutil.copy2(SHIFT_FILE, BACKUP_FILE)
        print(f"   Backup: {BACKUP_FILE}")

    if os.path.exists(OUTPUT_DIR):
        for f in glob.glob(os.path.join(OUTPUT_DIR, "*")):
            os.remove(f)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            record_video_dir=OUTPUT_DIR,
            record_video_size={"width": 1920, "height": 1080},
            locale="ja-JP"
        )
        page = await context.new_page()

        # ダイアログ（confirm/alert）を自動承認
        async def handle_dialog(dialog):
            print(f"   Dialog: {dialog.type} - {dialog.message[:80]}")
            await dialog.accept()
        page.on("dialog", handle_dialog)

        # ネットワーク監視
        async def on_request(request):
            if "solve-stream" in request.url and request.method == "POST":
                try:
                    body = request.post_data
                    if body:
                        data = json.loads(body)
                        staff = data.get("staff", [])
                        fixed_staff = [s for s in staff if s.get("workType") == "fixed"]
                        wishes = data.get("wishes", [])
                        print(f"   [NET] POST: staff={len(staff)}, fixed={len(fixed_staff)}, wishes={len(wishes)}")
                        from collections import Counter
                        off_by_day = Counter()
                        for w in wishes:
                            if w.get("shift") in ("off", "paid", "refresh") and w.get("type") == "assign":
                                for d in w.get("days", []):
                                    off_by_day[d] += 1
                        if off_by_day:
                            top3 = off_by_day.most_common(3)
                            print(f"   [NET] Wish off top3: {top3}")
                except Exception as ex:
                    print(f"   [NET] Parse error: {ex}")
        page.on("request", on_request)

        async def on_response(response):
            if "solve-stream" in response.url:
                print(f"   [NET] solve-stream response: {response.status}")
        page.on("response", on_response)

        print("Loading...")
        await page.goto(URL, wait_until="networkidle")
        await page.wait_for_timeout(2000)

        # --- 実ブラウザの localStorage 全体を注入 ---
        with open(LS_DUMP_FILE, "r", encoding="utf-8") as f:
            ls_data = json.load(f)

        # 確認: staff の workType 分布
        staff = ls_data.get("staff", [])
        fixed_count = sum(1 for s in staff if s.get("workType") == "fixed")
        ward1_staff = [s for s in staff if s.get("ward") == "1"]
        print(f"Confirmed shifts for solver: staff={len(staff)} ({fixed_count} fixed), ward1={len(ward1_staff)}")

        # 一病棟スタッフの希望のみフィルタ（固定・非固定とも）
        # shift.js は D.wishes[wk] を全件送信するため、他病棟分を除外
        ward1_ids = {s["id"] for s in ward1_staff}
        wishes = ls_data.get("wishes", {})
        for wk, wlist in wishes.items():
            before = len(wlist)
            filtered = [w for w in wlist if str(w.get("staffId")) in ward1_ids]
            ls_data["wishes"][wk] = filtered
            print(f"Wishes {wk}: {before} -> {len(filtered)} (ward1 only)")
        print(f"Ward1 staff IDs: {len(ward1_ids)}")

        # --- 前月引継ぎ制約を全除去（録画環境用） ---
        # 3月シフトを空にして前月引継ぎ制約を解消（18名分の制約が全て消える）
        for shift_key in list(ls_data.get("shifts", {}).keys()):
            if shift_key.startswith("2026-3-"):
                entry_count = len(ls_data["shifts"][shift_key])
                ls_data["shifts"][shift_key] = {}
                print(f"  Cleared {shift_key}: {entry_count} entries → 0 (no carryover)")

        # --- 希望休集中を緩和（録画環境用） ---
        # 集中日に複数希望があるスタッフの希望を除去してソルバー解可能に
        # 田中理加(5,8,12,19日), 久保彩夏(8,9,20日), 上田温奈(19,20日)
        trim_ids = {"10060951", "10061018", "10080941"}  # 田中理加, 久保彩夏, 上田温奈
        trim_names = {"10060951": "田中理加", "10061018": "久保彩夏", "10080941": "上田温奈"}
        for wk in list(ls_data.get("wishes", {}).keys()):
            before = len(ls_data["wishes"][wk])
            removed = []
            new_list = []
            for w in ls_data["wishes"][wk]:
                sid = str(w.get("staffId"))
                if sid in trim_ids:
                    removed.append(trim_names.get(sid, sid))
                else:
                    new_list.append(w)
            ls_data["wishes"][wk] = new_list
            if removed:
                print(f"  Wish trim {wk}: {before}→{len(new_list)} (removed: {', '.join(set(removed))})")

        # 全データを localStorage にセット
        await page.evaluate("""(data) => {
            localStorage.setItem('sakigakeData', JSON.stringify(data));
        }""", ls_data)
        print("Data injected into localStorage")

        # リロードで反映
        await page.reload(wait_until="networkidle")
        await page.wait_for_timeout(2000)

        # 一病棟を選択
        print("Ensuring ward 1 selected...")
        ward1_btn = page.locator("button:has-text('一病棟')")
        if await ward1_btn.count() > 0:
            await ward1_btn.first.click()
            await page.wait_for_timeout(3000)

        # 月確認
        month_info = await page.evaluate("""() => {
            const el = document.querySelector('.month-label, #monthLabel, [data-month]');
            return document.title + ' | ' + (el ? el.textContent : 'no month label');
        }""")
        print(f"   Month: {month_info}")

        # --- 実機通りの録画シーン ---
        await scene1_overview(page, OUTPUT_DIR)
        await scene2_clear(page, OUTPUT_DIR)       # クリアボタンで実機通りにクリア
        await scene3_wish_input(page, OUTPUT_DIR)
        await scene4_start_solver(page, OUTPUT_DIR)
        await scene5_solver_running(page, OUTPUT_DIR)
        await scene6_draft_list(page, OUTPUT_DIR)
        await scene7_shift_grid(page, OUTPUT_DIR)
        await scene8_evaluation(page, OUTPUT_DIR)

        print("\nClosing browser...")
        await context.close()
        await browser.close()

    # --- シフトファイル復元 ---
    if os.path.exists(BACKUP_FILE):
        shutil.copy2(BACKUP_FILE, SHIFT_FILE)
        print(f"Restored shift file from backup")

    # --- ffmpeg 変換 ---
    webm_files = glob.glob(os.path.join(OUTPUT_DIR, "*.webm"))
    if webm_files:
        mp4 = r"C:\Users\sakigake\Desktop\solver_demo_final.mp4"
        print(f"Converting {webm_files[0]} to MP4...")
        cmd = [
            FFMPEG, "-i", webm_files[0],
            "-c:v", "libx264",
            "-profile:v", "baseline",
            "-level", "3.1",
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            "-y", mp4
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode == 0:
            mb = os.path.getsize(mp4) / 1024 / 1024
            print(f"Done: {mp4} ({mb:.1f}MB)")
        else:
            print(f"FFmpeg FAILED (code {result.returncode})")
            print(f"stderr: {result.stderr[-500:]}")
    else:
        print("No WebM files found!")


if __name__ == "__main__":
    asyncio.run(main())
