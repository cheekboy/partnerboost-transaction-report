import json
import os

import requests

API_URL = "https://app.partnerboost.com/api.php"
TOKEN_ENV_NAME = "PARTNERBOOST_TOKEN"


def fetch_brands_page(page: int = 1, limit: int = 10) -> dict:
    token = os.getenv(TOKEN_ENV_NAME)
    if not token:
        raise RuntimeError(f"请先在环境变量 {TOKEN_ENV_NAME} 中配置 PartnerBoost token")

    params = {
        "mod": "medium",
        "op": "monetization_api",
    }
    # 品牌 API 支持多种 HTTP 方式，这里用 x-www-form-urlencoded 形式的 POST
    data = {
        "token": token,
        "type": "json",        # 返回 JSON
        "brand_type": "Amazon",  # 只看 Amazon 品牌，后续可调整
        "page": page,
        "limit": limit,
        # 其他可选过滤：relationship, categories, country 等
    }

    resp = requests.post(API_URL, params=params, data=data, timeout=30)
    resp.raise_for_status()
    return resp.json()


def main() -> None:
    data = fetch_brands_page(page=1, limit=10)
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
