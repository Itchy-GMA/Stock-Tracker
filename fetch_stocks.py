"""
fetch_stocks.py
毎週土曜日にGitHub Actionsから実行される株価取得スクリプト。
J-Quants API を使用（無料プラン対応）。
結果は results.json に追記・保存される。
"""

import os
import json
import requests
from datetime import date, datetime, timedelta

RESULTS_FILE = "results.json"
JQUANTS_EMAIL = os.environ.get("JQUANTS_EMAIL", "")
JQUANTS_PASSWORD = os.environ.get("JQUANTS_PASSWORD", "")

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
    "7004": "カナデビア",
    "7013": "IHI",
    "8729": "ソニーフィナンシャルグループ",
    "8801": "三井不動産",
    "9432": "NTT",
    "7201": "日産自動車",
    "7203": "トヨタ自動車",
    "6594": "ニデック",
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


def get_refresh_token():
    """メール・パスワードでリフレッシュトークンを取得"""
    url = "https://api.jquants.com/v1/token/auth_user"
    resp = requests.post(url, json={"mailaddress": JQUANTS_EMAIL, "password": JQUANTS_PASSWORD}, timeout=15)
    resp.raise_for_status()
    return resp.json()["refreshToken"]


def get_id_token(refresh_token):
    """リフレッシュトークンでIDトークンを取得"""
    url = f"https://api.jquants.com/v1/token/auth_refresh?refreshtoken={refresh_token}"
    resp = requests.post(url, timeout=15)
    resp.raise_for_status()
    return resp.json()["idToken"]


def fetch_latest_close(code, id_token):
    """J-Quants APIから最新終値を取得"""
    # 直近10営業日分を取得して最新を使う
    date_from = (date.today() - timedelta(days=14)).strftime("%Y%m%d")
    # J-Quantsのコードは4桁+1桁（例: 72030）
    jq_code = code + "0" if len(code) == 4 and code.isdigit() else code
    url = f"https://api.jquants.com/v1/prices/daily_quotes?code={jq_code}&from={date_from}"
    headers = {"Authorization": f"Bearer {id_token}"}
    try:
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()
        quotes = resp.json().get("daily_quotes", [])
        if not quotes:
            print(f"  [WARN] {code}: データなし（新規上場・上場廃止の可能性）")
            return None
        # 最新日付のデータを使用
        latest = sorted(quotes, key=lambda q: q["Date"])[-1]
        close = latest.get("Close") or latest.get("AdjustmentClose")
        if close is None:
            return None
        return round(float(close), 2)
    except Exception as e:
        print(f"  [ERROR] {code}: {e}")
        return None


def load_results():
    if os.path.exists(RESULTS_FILE):
        with open(RESULTS_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"stocks": [], "history": {}, "lastUpdated": None}


def save_results(data):
    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    today = date.today().isoformat()
    data = load_results()

    if not data.get("stocks"):
        print("銘柄リストが空です。")
        save_results(data)
        return

    # 企業名を補完
    for stock in data["stocks"]:
        code = stock["code"]
        if stock.get("name") == code and code in COMPANY_NAMES:
            stock["name"] = COMPANY_NAMES[code]

    print("J-Quants APIトークンを取得中...")
    try:
        refresh_token = get_refresh_token()
        id_token = get_id_token(refresh_token)
        print("トークン取得成功")
    except Exception as e:
        print(f"[ERROR] トークン取得失敗: {e}")
        return

    print(f"=== 株価取得開始: {today} ===")

    for stock in data["stocks"]:
        code = stock["code"]
        name = stock.get("name", code)
        print(f"  取得中: {code} ({name}) ...", end=" ", flush=True)

        price = fetch_latest_close(code, id_token)
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
