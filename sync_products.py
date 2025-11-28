import os
import sqlite3
from typing import Any, Dict, List

import requests

DB_PATH = os.path.join(os.path.dirname(__file__), "products.db")
API_URL = "https://app.partnerboost.com/api/datafeed/get_fba_products"
TOKEN_ENV_NAME = "PARTNERBOOST_TOKEN"


def init_db() -> None:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS products (
            asin TEXT PRIMARY KEY,
            brand_id TEXT,
            brand_name TEXT,
            title TEXT,
            country_code TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def upsert_product(conn: sqlite3.Connection, product: Dict[str, Any]) -> None:
    """根据 get_fba_products 返回的一条记录写入/更新产品信息。

    注意：这里的字段名是根据常见命名做的假设：
    - asin
    - brand_id
    - brand_name 或 brand
    - title 或 name
    - country_code

    如果你的实际返回字段不同，请根据实际 JSON 调整这里的 key。
    """

    asin = product.get("asin")
    if not asin:
        return

    brand_id = product.get("brand_id")
    brand_name = product.get("brand_name") or product.get("brand")
    title = product.get("title") or product.get("name")
    country_code = product.get("country_code")

    conn.execute(
        """
        INSERT INTO products (asin, brand_id, brand_name, title, country_code)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(asin) DO UPDATE SET
            brand_id=excluded.brand_id,
            brand_name=excluded.brand_name,
            title=excluded.title,
            country_code=excluded.country_code
        """,
        (asin, brand_id, brand_name, title, country_code),
    )


def fetch_fba_products_page(page: int, page_size: int) -> Dict[str, Any]:
    token = os.getenv(TOKEN_ENV_NAME)
    if not token:
        raise RuntimeError(f"请先在环境变量 {TOKEN_ENV_NAME} 中配置 PartnerBoost token")

    payload = {
        "token": token,
        "page_size": page_size,
        "page": page,
        "default_filter": 1,
        "country_code": "",
        "brand_id": None,
        "sort": "",
        "asins": "",
        "relationship": 1,
        "is_original_currency": 0,
        "has_promo_code": 0,
        "has_acc": 0,
        "filter_sexual_wellness": 0,
    }

    resp = requests.post(API_URL, json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    status = data.get("status", {})
    code = status.get("code")
    if code not in (0, "0"):
        raise RuntimeError(f"API error: code={code}, msg={status.get('msg')}")

    return data


def sync_products(page_size: int = 50) -> None:
    init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.isolation_level = None  # 手动控制事务

    page = 1
    total_count = 0

    print(f"[sync_products] Start syncing products with page_size={page_size} ...")

    while True:
        print(f"[sync_products] Fetching page {page} ...")
        data = fetch_fba_products_page(page=page, page_size=page_size)

        # 根据实际返回结构调整这里的路径
        data_block = data.get("data", {})
        product_list: List[Dict[str, Any]] = data_block.get("list") or data_block.get("rows") or []

        if not product_list:
            print("[sync_products] No products returned, stopping.")
            break

        page_count = len(product_list)
        print(f"[sync_products] Page {page} returned {page_count} products.")

        conn.execute("BEGIN")
        for p in product_list:
            upsert_product(conn, p)
            total_count += 1
        conn.execute("COMMIT")

        print(f"[sync_products] Accumulated total products upserted: {total_count}.")

        # 翻页逻辑：优先使用 has_more，如果没有就根据本页数量判断
        has_more = data_block.get("has_more")
        if has_more is False or len(product_list) < page_size:
            print("[sync_products] Reached last page.")
            break

        page += 1

    # 打印数据库中的实际统计信息，便于对比（总产品数、去重品牌数）
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM products")
    db_total = cur.fetchone()[0]

    cur.execute("SELECT COUNT(DISTINCT brand_id) FROM products")
    distinct_brand_id = cur.fetchone()[0]

    cur.execute("SELECT COUNT(DISTINCT brand_name) FROM products")
    distinct_brand_name = cur.fetchone()[0]

    print(f"[sync_products] Product sync done. processed records: {total_count}.")
    print(f"[sync_products] DB stats -> total products: {db_total}, distinct brand_id: {distinct_brand_id}, distinct brand_name: {distinct_brand_name}.")

    conn.close()


if __name__ == "__main__":
    sync_products()
