"""
Solver subprocess wrapper.

OR-Tools の CP-SAT ソルバーが内部で abort() する可能性があるため、
メインの Flask プロセスとは別プロセスで実行する。

Usage:
    python solver_subprocess.py <result_path>
    - stdin: JSON (solver input data)
    - stdout: JSONL (progress messages)
    - result_path: 結果 JSON の書き出し先
"""
import sys
import json
import queue
import threading


def _stdout_writer(log_queue):
    """log_queue からメッセージを取り出し、stdout に JSONL で書き出す。"""
    while True:
        try:
            msg = log_queue.get(timeout=1)
        except queue.Empty:
            continue
        if msg is None:
            break
        try:
            line = json.dumps(msg, ensure_ascii=False)
            sys.stdout.write(line + "\n")
            sys.stdout.flush()
        except Exception:
            pass


def main():
    result_path = sys.argv[1]

    # stdin から入力データを読み取り
    raw = sys.stdin.buffer.read()
    data = json.loads(raw.decode("utf-8"))

    # ログキュー（進捗を stdout に流す）
    log_queue = queue.Queue()
    writer_thread = threading.Thread(
        target=_stdout_writer, args=(log_queue,), daemon=True
    )
    writer_thread.start()

    # ソルバー実行
    from solver import ShiftSolver
    solver = ShiftSolver(data)

    solve_mode = data.get("config", {}).get("solveMode", "standard")

    if solve_mode == "pool":
        result = solver.solve_pool(log_queue=log_queue)
    elif solve_mode == "relaxed":
        result = solver.solve_relaxed(log_queue=log_queue)
    else:
        result = solver.solve(log_queue=log_queue)

    # ログキュー終了
    log_queue.put(None)
    writer_thread.join(timeout=3)

    # 結果をファイルに書き出し
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False)


if __name__ == "__main__":
    main()
