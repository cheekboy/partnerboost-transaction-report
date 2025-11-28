import os
import datetime
import sqlite3
from collections import defaultdict
from typing import Any, Dict, List

import requests

API_URL = "https://app.partnerboost.com/api/datafeed/get_amazon_report"
TOKEN_ENV_NAME = "PARTNERBOOST_TOKEN"
DB_PATH = os.path.join(os.path.dirname(__file__), "products.db")


def get_db_conn() -> sqlite3.Connection:
    return sqlite3.connect(DB_PATH)


def get_brand_name_from_db(conn: sqlite3.Connection, asin: str) -> str:
    cur = conn.cursor()
    cur.execute("SELECT brand_name FROM products WHERE asin = ?", (asin,))
    row = cur.fetchone()
    if row and row[0]:
        return row[0]
    return "Unknown"


def fetch_amazon_report(start_date: str, end_date: str, page_size: int = 500) -> List[Dict[str, Any]]:
    token = os.getenv(TOKEN_ENV_NAME)
    if not token:
        raise RuntimeError(f"请先在环境变量 {TOKEN_ENV_NAME} 中配置 PartnerBoost token")

    page = 1
    all_rows: List[Dict[str, Any]] = []

    while True:
        payload = {
            "token": token,
            "page_size": page_size,
            "page": page,
            "start_date": start_date,
            "end_date": end_date,
            "marketplace": "",
            "asins": "",
            "adGroupIds": "",
        }

        resp = requests.post(API_URL, json=payload, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        status = data.get("status", {})
        if status.get("code") != 0:
            raise RuntimeError(f"API error: {status.get('code')} {status.get('msg')}")

        data_block = data.get("data", {})
        page_list: List[Dict[str, Any]] = data_block.get("list", [])
        all_rows.extend(page_list)

        has_more = data_block.get("has_more", False)
        if not has_more:
            break

        page += 1

    return all_rows


def aggregate_by_brand(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
    conn = get_db_conn()
    result: Dict[str, Dict[str, float]] = defaultdict(
        lambda: {"orders": 0, "sales": 0.0, "commission": 0.0}
    )

    for r in rows:
        asin = r.get("asin")
        if asin:
            brand = get_brand_name_from_db(conn, asin)
        else:
            brand = "Unknown"

        quantity = r.get("quantity", 0) or 0
        sales = r.get("sales", 0.0) or 0.0
        commission = r.get("estCommission", 0.0) or 0.0

        if quantity > 0:
            result[brand]["orders"] += 1

        result[brand]["sales"] += float(sales)
        result[brand]["commission"] += float(commission)

    conn.close()
    return result


def main_for_date(day: datetime.date) -> None:
    day_str = day.strftime("%Y%m%d")

    print(f"Fetching Amazon report for {day_str} ...")
    rows = fetch_amazon_report(day_str, day_str)
    print(f"Total rows: {len(rows)}")

    agg = aggregate_by_brand(rows)

    print("Brand Report for", day_str)
    print("Brand, Orders, Sales, Commission")
    for brand, stats in sorted(agg.items(), key=lambda x: x[0]):
        print(
            f"{brand}, "
            f"{int(stats['orders'])}, "
            f"{stats['sales']:.2f}, "
            f"{stats['commission']:.2f}"
        )


def main_for_yesterday() -> None:
    yesterday = datetime.date.today() - datetime.timedelta(days=1)
    main_for_date(yesterday)


if __name__ == "__main__":
    main_for_yesterday()
