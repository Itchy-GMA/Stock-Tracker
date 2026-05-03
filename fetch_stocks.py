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
 
RESULTS_FILE = "results.json"
STOOQ_APIKEY = os.environ.get("STOOQ_APIKEY", "")
STOOQ_URL = "https://stooq.com/q/d/l/?s={symbol}&i=d&apikey={apikey}"
 
# 証券コード → 企業名マッピング（stooqが社名を返さない場合のフォールバック）
COMPANY_NAMES = {
    "2404": "鉄人化計画",
    "2694": "焼肉坂井HD",
    "2762": "三光マーケ",
    "3053": "ペッパーFS",
    "3372": "関門海",
    "3904": "カヤック",
    "4584": "キッズウェル・バイオ",
    "4661": "オリエンタルランド",
    "6752": "パナソニックHD",
    "7918": "ヴィア・HD",
    "8002": "丸紅",
    "8088": "岩谷産業",
    "8214": "AOKIホールディングス",
    "8306": "三菱UFJ FG",
    "9023": "東京メトロ",
    "9202": "ANA HD",
    "9704": "アゴーラ・ホスピタリティ",
    "9973": "小僧寿し",
    "9861": "吉野家HD",
    "3407": "旭化成",
    "6326": "クボタ",
    "7004": "日立造船",
    "7013": "IHI",
    "8729": "ソニーフィナンシャル",
    "8801": "三井不動産",
    "9432": "NTT",
    "7201": "日産自動車",
    "7203": "トヨタ自動車",
    "6594": "日本電産（ニデック）",
    "261A": "ソラスト",
    "4245": "ダイキアクシス",
    "5602": "栗本鐵工所",
    "256A": "ツルハHD",
    "1961": "三機工業",
    "1833": "奥村組",
    "9551": "メタウォーター",
    "7925": "前澤化成工業",
    "1820": "西松建設",
    "6946": "日本アビオニクス",
    "4275": "カーリットHD",
    "4403": "日油",
    "7721": "東京計器",
    "5019": "出光興産",
    "5631": "日本製鋼所",
    "5020": "ENEOSホールディングス",
    "7011": "三菱重工業",
    "218A": "ツクルバ",
    "7545": "西松屋チェーン",
    "5411": "JFEホールディングス",
    "5021": "コスモエネルギーHD",
    "9513": "電源開発（J-POWER）",
    "1605": "INPEX",
}
 
 
def load_results() -> dict:
    if os.path.exists(RESULTS_FILE):
        with open(RESULTS_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"stocks": [], "history": {}, "lastUpdated": None}
 
 
def save_results(data: dict):
    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
 
 
def fetch_latest_close(code: str) -> float | None:
    if not STOOQ_APIKEY:
        raise EnvironmentError("STOOQ_APIKEY が設定されていません。")
 
    symbol = f"{code}.jp"
    url = STOOQ_URL.format(symbol=symbol, apikey=STOOQ_APIKEY)
 
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  [ERROR] {code}: HTTPエラー → {e}")
        return None
 
    text = resp.text.strip()
 
    if "apikey" in text.lower() and len(text) < 300:
        print(f"  [WARN]  {code}: apikey が無効または失効しています。")
        print(f"          再取得URL: https://stooq.com/q/d/?s={symbol}&get_apikey")
        return None
 
    reader = csv.DictReader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        print(f"  [WARN]  {code}: データが空でした。")
        return None
 
    latest = rows[0]
    close_key = next((k for k in latest if k.strip().lower() == "close"), None)
    if close_key is None:
        print(f"  [WARN]  {code}: Close 列が見つかりません。")
        return None
 
    try:
        return round(float(latest[close_key]), 2)
    except (ValueError, TypeError):
        return None
 
 
def main():
    today = date.today().isoformat()
    data = load_results()
 
    if not data.get("stocks"):
        print("銘柄リストが空です。")
        save_results(data)
        return
 
    # 企業名をマッピングから補完
    for stock in data["stocks"]:
        code = stock["code"]
        if stock.get("name") == code and code in COMPANY_NAMES:
            stock["name"] = COMPANY_NAMES[code]
 
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
 
        stock["latestPrice"] = price
        stock["latestDate"] = today
 
        history = data["history"].setdefault(code, [])
        entry = next((h for h in history if h["date"] == today), None)
        if entry:
            entry["price"] = price
        else:
            history.append({"date": today, "price": price})
 
        data["history"][code] = sorted(history, key=lambda h: h["date"])[-52:]
 
    data["lastUpdated"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    save_results(data)
    print(f"=== 完了: {RESULTS_FILE} を更新しました ===")
 
 
if __name__ == "__main__":
    main()
