"""
fetch_stocks.py
毎週土曜日にGitHub Actionsから実行される株価取得スクリプト。
stooq.com の apikey 経由 CSV エンドポイントを使用。
結果は results.json に追記・保存される。
"""

import os
import json
import csv
import io
import requests
from datetime import date, datetime

# ── 設定 ────────────────────────────────────────────────
RESULTS_FILE = "results.json"
STOOQ_APIKEY = os.environ.get("STOOQ_APIKEY", "")
STOOQ_URL = "https://stooq.com/q/d/l/?s={symbol}&i=d&apikey={apikey}"
# ────────────────────────────────────────────────────────


def load_results() -> dict:
    """既存の results.json を読み込む（なければ空dictを返す）"""
    if os.path.exists(RESULTS_FILE):
        with open(RESULTS_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"stocks": [], "history": {}, "lastUpdated": None}


def save_results(data: dict):
    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def fetch_latest_close(code: str) -> float | None:
    """
    stooq から最新終値を取得する。
    シンボル形式: 7203.jp（小文字の .jp を付ける）
    """
    if not STOOQ_APIKEY:
        raise EnvironmentError(
            "STOOQ_APIKEY が設定されていません。"
            "GitHub Secrets に STOOQ_APIKEY を追加してください。"
        )

    symbol = f"{code}.jp"
    url = STOOQ_URL.format(symbol=symbol, apikey=STOOQ_APIKEY)

    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  [ERROR] {code}: HTTPエラー → {e}")
        return None

    text = resp.text.strip()

    # apikey が無効・失効している場合は案内テキストが返る
    if "apikey" in text.lower() and len(text) < 300:
        print(f"  [WARN]  {code}: apikey が無効または失効しています。再取得してください。")
        print(f"          再取得URL: https://stooq.com/q/d/?s={symbol}&get_apikey")
        return None

    # CSV パース（最新行 = 先頭行）
    reader = csv.DictReader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        print(f"  [WARN]  {code}: データが空でした。")
        return None

    # ヘッダー名の揺らぎ対応（Close / close / CLOSE）
    latest = rows[0]
    close_key = next((k for k in latest if k.strip().lower() == "close"), None)
    if close_key is None:
        print(f"  [WARN]  {code}: Close 列が見つかりません。列: {list(latest.keys())}")
        return None

    try:
        return round(float(latest[close_key]), 2)
    except (ValueError, TypeError):
        print(f"  [WARN]  {code}: Close 値のパースに失敗しました → {latest[close_key]!r}")
        return None


def main():
    today = date.today().isoformat()
    data = load_results()

    if not data.get("stocks"):
        print("銘柄リストが空です。index.html のアプリから銘柄を追加してください。")
        save_results(data)
        return

    print(f"=== 株価取得開始: {today} ===")

    for stock in data["stocks"]:
        code = stock["code"]
        name = stock.get("name", code)
        print(f"  取得中: {code} ({name}) ...", end=" ")

        price = fetch_latest_close(code)
        if price is None:
            print("スキップ")
            continue

        print(f"¥{price:,.0f}")

        # latestPrice を更新
        stock["latestPrice"] = price
        stock["latestDate"] = today

        # 履歴に追記（同日は上書き、52週分を保持）
        history = data["history"].setdefault(code, [])
        entry = next((h for h in history if h["date"] == today), None)
        if entry:
            entry["price"] = price
        else:
            history.append({"date": today, "price": price})

        # 52週（1年分）を超えたら古いものを削除
        data["history"][code] = sorted(history, key=lambda h: h["date"])[-52:]

    data["lastUpdated"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    save_results(data)
    print(f"=== 完了: {RESULTS_FILE} を更新しました ===")


if __name__ == "__main__":
    main()
