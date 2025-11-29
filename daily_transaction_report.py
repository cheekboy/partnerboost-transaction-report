import os
import sys
from datetime import date, datetime, timedelta
from collections import defaultdict
from typing import Any, Dict, List

import requests
from dotenv import load_dotenv

API_URL = "https://app.partnerboost.com/api.php"
TOKEN_ENV_NAME = "PARTNERBOOST_TOKEN"

# 从 .env 文件加载环境变量（如果存在）
load_dotenv()


def fetch_transactions(begin_date: str, end_date: str, limit: int = 1000) -> List[Dict[str, Any]]:
    """拉取一段时间内的所有交易（按交易时间 begin_date/end_date）。

    begin_date, end_date: 'YYYY-MM-DD'
    """
    token = os.getenv(TOKEN_ENV_NAME)
    if not token:
        raise RuntimeError(f"请先在环境变量 {TOKEN_ENV_NAME} 中配置 PartnerBoost token")

    all_items: List[Dict[str, Any]] = []
    page = 1

    while True:
        params = {
            "mod": "medium",
            "op": "transaction",
        }
        # 使用 x-www-form-urlencoded 形式
        data = {
            "token": token,
            "type": "json",
            "begin_date": begin_date,
            "end_date": end_date,
            "page": page,
            "limit": limit,
            # 如需过滤可加: status, brand_id, mcid, uid 等
        }

        print(f"[transaction] Fetching {begin_date} -> {end_date}, page={page} ...")
        resp = requests.post(API_URL, params=params, data=data, timeout=30)
        resp.raise_for_status()
        result = resp.json()

        status = result.get("status", {})
        if status.get("code") != 0:
            raise RuntimeError(f"API error {status.get('code')}: {status.get('msg')}")

        data_block = result.get("data", {})
        items: List[Dict[str, Any]] = data_block.get("list", [])
        if not items:
            print("[transaction] Empty list, stop.")
            break

        all_items.extend(items)
        print(f"[transaction] Page {page} items: {len(items)}, accumulated: {len(all_items)}")

        total_page = int(data_block.get("total_page", 1))
        if page >= total_page:
            print("[transaction] Reached last page.")
            break

        page += 1

    return all_items


def aggregate_by_brand(transactions: List[Dict[str, Any]]) -> Dict[str, Dict[str, float]]:
    """按品牌名称汇总：订单数、销售额、佣金额。"""
    result: Dict[str, Dict[str, float]] = defaultdict(
        lambda: {"orders": 0, "sales": 0.0, "commission": 0.0}
    )

    for t in transactions:
        brand_name = t.get("merchant_name") or "Unknown"

        # sale_amount / sale_comm 以文档为准，可能是字符串
        try:
            sale_amount = float(t.get("sale_amount", 0) or 0)
        except (TypeError, ValueError):
            sale_amount = 0.0

        try:
            sale_comm = float(t.get("sale_comm", 0) or 0)
        except (TypeError, ValueError):
            sale_comm = 0.0

        # 订单数：每条交易视为一单
        result[brand_name]["orders"] += 1
        result[brand_name]["sales"] += sale_amount
        result[brand_name]["commission"] += sale_comm

    return result


def write_html_report(range_key: str, begin_date: str, end_date: str, agg: Dict[str, Dict[str, float]]) -> str:
    """把按品牌汇总的结果写入一个静态 HTML 文件，返回文件路径。

    range_key: today / yesterday / last7 / last14 / single
    begin_date, end_date: 'YYYY-MM-DD'

    HTML 文件输出到 docs/ 目录，方便后续用 GitHub Pages 直接托管。
    """
    docs_dir = os.path.join(os.path.dirname(__file__), "docs")
    os.makedirs(docs_dir, exist_ok=True)

    # 文件名：单日仍然以日期命名；范围则包含起止日期和范围 key
    if begin_date == end_date:
        filename = f"transaction_report_{end_date}.html"
    else:
        filename = f"transaction_report_{begin_date}_to_{end_date}_{range_key}.html"
    filepath = os.path.join(docs_dir, filename)

    # 总体汇总
    total_orders = 0
    total_sales = 0.0
    total_commission = 0.0
    for stats in agg.values():
        total_orders += int(stats["orders"])
        total_sales += float(stats["sales"])
        total_commission += float(stats["commission"])

    # 生成表格行
    rows_html = []
    for brand, stats in sorted(agg.items(), key=lambda x: x[0].lower()):
        rows_html.append(
            f"<tr>"
            f"<td class='brand'>{brand}</td>"
            f"<td class='num'>{int(stats['orders'])}</td>"
            f"<td class='num'>{stats['sales']:.2f}</td>"
            f"<td class='num'>{stats['commission']:.2f}</td>"
            f"</tr>"
        )

    # 标题显示的人类可读范围
    if begin_date == end_date:
        if range_key == "today":
            range_label = f"{end_date} · Today"
        elif range_key == "yesterday":
            range_label = f"{end_date} · Yesterday"
        else:
            range_label = end_date
    else:
        human = {"last7": "Last 7 days", "last14": "Last 14 days"}.get(range_key, "")
        range_label = f"{begin_date} → {end_date}"
        if human:
            range_label = f"{range_label} · {human}"

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Transaction Report {range_label}</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    :root {{
      --bg: #f5f5f7;
      --card-bg: #ffffff;
      --border: #e5e5ea;
      --text: #1d1d1f;
      --muted: #6e6e73;
      --accent: #0071e3;
      --accent-soft: rgba(0,113,227,0.08);
    }}
    * {{
      box-sizing: border-box;
    }}
    body {{
      margin: 0;
      padding: 32px 16px;
      font-family: -apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif;
      background: var(--bg);
      color: var(--text);
      -webkit-font-smoothing: antialiased;
    }}
    .container {{
      max-width: 980px;
      margin: 0 auto;
    }}
    .card {{
      background: var(--card-bg);
      border-radius: 28px;
      border: 1px solid var(--border);
      box-shadow: 0 20px 40px rgba(0,0,0,0.06);
      padding: 24px 28px 28px;
    }}
    .header {{
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      gap: 12px;
      margin-bottom: 18px;
    }}
    .title {{
      font-size: 22px;
      font-weight: 600;
      letter-spacing: -0.01em;
    }}
    .date-pill {{
      font-size: 13px;
      color: var(--accent);
      background: var(--accent-soft);
      border-radius: 999px;
      padding: 4px 12px;
    }}
    .summary {{
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      margin-bottom: 18px;
    }}
    .summary-item {{
      flex: 1 1 160px;
      min-width: 160px;
      padding: 10px 14px;
      border-radius: 16px;
      background: #f9fafb;
      border: 1px solid #ededf0;
    }}
    .summary-label {{
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: var(--muted);
      margin-bottom: 4px;
    }}
    .summary-value {{
      font-size: 20px;
      font-weight: 600;
      letter-spacing: -0.02em;
    }}
    .summary-sub {{
      font-size: 11px;
      color: var(--muted);
      margin-top: 2px;
    }}
    .table-wrapper {{
      margin-top: 8px;
      border-radius: 18px;
      border: 1px solid var(--border);
      overflow: hidden;
    }}
    table {{
      border-collapse: collapse;
      width: 100%;
      font-size: 13px;
    }}
    thead {{
      background: #f5f5f7;
    }}
    th, td {{
      padding: 9px 12px;
      border-bottom: 1px solid #f2f2f7;
      white-space: nowrap;
    }}
    th {{
      text-align: left;
      font-weight: 500;
      color: var(--muted);
      font-size: 12px;
    }}
    tbody tr:hover {{
      background: #f9fafb;
    }}
    td.brand {{
      max-width: 260px;
      overflow: hidden;
      text-overflow: ellipsis;
    }}
    td.num {{
      text-align: right;
      font-variant-numeric: tabular-nums;
    }}
    .footer-note {{
      margin-top: 12px;
      font-size: 11px;
      color: var(--muted);
      text-align: right;
    }}
    @media (max-width: 640px) {{
      body {{ padding: 16px 10px; }}
      .card {{ padding: 18px 16px 20px; border-radius: 22px; }}
      .title {{ font-size: 18px; }}
    }}
  </style>
</head>
<body>
  <div class="container">
    <div class="card">
      <div class="header">
        <div class="title">PartnerBoost Transaction Report</div>
        <div class="date-pill">{range_label}</div>
      </div>
      <div class="summary">
        <div class="summary-item">
          <div class="summary-label">Total Orders</div>
          <div class="summary-value">{total_orders}</div>
          <div class="summary-sub">Across all brands</div>
        </div>
        <div class="summary-item">
          <div class="summary-label">Total Sales</div>
          <div class="summary-value">{total_sales:.2f}</div>
          <div class="summary-sub">Sum of sale_amount</div>
        </div>
        <div class="summary-item">
          <div class="summary-label">Total Commission</div>
          <div class="summary-value">{total_commission:.2f}</div>
          <div class="summary-sub">Sum of sale_comm</div>
        </div>
      </div>
      <div class="table-wrapper">
        <table>
          <thead>
            <tr>
              <th>Brand</th>
              <th>Orders</th>
              <th>Sales</th>
              <th>Commission</th>
            </tr>
          </thead>
          <tbody>
            {''.join(rows_html)}
          </tbody>
        </table>
      </div>
      <div class="footer-note">
        Generated by daily_transaction_report.py using PartnerBoost Transaction API.
      </div>
    </div>
  </div>
</body>
</html>
"""
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"[transaction] HTML report written to: {filepath}")
    return filepath


def parse_range_arg(argv: List[str]) -> (str, str, str):
    """解析命令行参数，支持：

    - 无参数: 昨天 (range_key='yesterday')
    - today
    - yesterday
    - last7  (最近7天，包含今天)
    - last14 (最近14天，包含今天)
    - YYYY-MM-DD (单一天，range_key='single')

    返回: (begin_date_str, end_date_str, range_key)
    """

    today = date.today()

    if len(argv) < 2:
        # 默认昨天
        y = today - timedelta(days=1)
        d_str = y.strftime("%Y-%m-%d")
        return d_str, d_str, "yesterday"

    arg = argv[1].strip().lower()

    if arg == "today":
        d_str = today.strftime("%Y-%m-%d")
        return d_str, d_str, "today"

    if arg == "yesterday":
        y = today - timedelta(days=1)
        d_str = y.strftime("%Y-%m-%d")
        return d_str, d_str, "yesterday"

    if arg == "last7":
        end_d = today
        begin_d = today - timedelta(days=6)
        return begin_d.strftime("%Y-%m-%d"), end_d.strftime("%Y-%m-%d"), "last7"

    if arg == "last14":
        end_d = today
        begin_d = today - timedelta(days=13)
        return begin_d.strftime("%Y-%m-%d"), end_d.strftime("%Y-%m-%d"), "last14"

    # 其余情况按具体日期解析
    d = datetime.strptime(arg, "%Y-%m-%d").date()
    d_str = d.strftime("%Y-%m-%d")
    return d_str, d_str, "single"


def main() -> None:
    begin_str, end_str, range_key = parse_range_arg(sys.argv)

    print(
        f"[transaction] Generating transaction report for {begin_str} -> {end_str} (mode={range_key}) ..."
    )
    txs = fetch_transactions(begin_str, end_str)
    print(f"[transaction] Total transactions: {len(txs)}")

    agg = aggregate_by_brand(txs)

    print("Brand Transaction Report for", f"{begin_str} -> {end_str}")
    print("Brand, Orders, Sales, Commission")
    for brand, stats in sorted(agg.items(), key=lambda x: x[0]):
        print(
            f"{brand}, "
            f"{int(stats['orders'])}, "
            f"{stats['sales']:.2f}, "
            f"{stats['commission']:.2f}"
        )

    # 生成静态 HTML 报表
    write_html_report(range_key, begin_str, end_str, agg)


if __name__ == "__main__":
    main()
