import json

from sync_products import fetch_fba_products_page


def main() -> None:
    data = fetch_fba_products_page(page=1, page_size=10)
    print(json.dumps(data, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
