# main.py
import os
import requests
import datetime

NOTION_TOKEN = os.environ["NOTION_TOKEN"]
DATABASE_ID = os.environ["NOTION_DB_ID"]

NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"


def is_last_day_of_month(date: datetime.date) -> bool:
    """渡された日付が月末かどうか"""
    next_day = date + datetime.timedelta(days=1)
    return next_day.month != date.month


def get_usd_jpy_rate() -> float:
    """
    為替レート取得
    例として exchangerate.host（無料・APIキー不要）を使用
    """
    resp = requests.get(
        "https://api.exchangerate.host/latest",
        params={"base": "USD", "symbols": "JPY"},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["rates"]["JPY"]


def query_pages_with_dollar_without_yen():
    """
    「ドルが入っていて、円が空」のページをNotionから取得
    ※ ページ数が多い場合は has_more / next_cursor でループが必要
    """
    url = f"{NOTION_API_BASE}/databases/{DATABASE_ID}/query"
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }
    payload = {
        "filter": {
            "and": [
                {"property": "ドル", "number": {"is_not_empty": True}},
                {"property": "円", "number": {"is_empty": True}},
            ]
        }
    }

    resp = requests.post(url, headers=headers, json=payload, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    return data["results"]


def update_page_yen_and_meta(page_id: str, yen_value: float, rate: float, today: datetime.date):
    """
    該当ページの「円」「レート」「換算日」を更新
    ※ プロパティ名はNotionのDBに合わせて変える
    """
    url = f"{NOTION_API_BASE}/pages/{page_id}"
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }

    payload = {
        "properties": {
            "円": {"number": yen_value},
            "レート": {"number": rate},             # 任意（あれば便利）
            "換算日": {"date": {"start": today.isoformat()}},  # 任意
        }
    }

    resp = requests.patch(url, headers=headers, json=payload, timeout=10)
    resp.raise_for_status()


def main():
    today = datetime.date.today()

    # 月末チェック（毎日回しても、月末以外は何もしない）
    if not is_last_day_of_month(today):
        print("Today is not the last day of the month. Exit.")
        return

    print("Last day of month. Start FX conversion.")

    # 1. 為替レート取得
    rate = get_usd_jpy_rate()
    print(f"USD/JPY rate: {rate}")

    # 2. Notionで「ドルあり・円なし」レコード取得
    pages = query_pages_with_dollar_without_yen()
    print(f"Target pages: {len(pages)}")

    # 3. 各ページ更新
    for page in pages:
        page_id = page["id"]
        dollar_value = page["properties"]["ドル"]["number"]
        yen_value = round(dollar_value * rate)  # 四捨五入など好みで

        print(f"Update page {page_id}: {dollar_value} USD -> {yen_value} JPY")

        update_page_yen_and_meta(page_id, yen_value, rate, today)


if __name__ == "__main__":
    main()
