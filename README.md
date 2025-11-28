# PartnerBoost Amazon Reports

Python + SQLite 项目，用于从 PartnerBoost API 拉取 Amazon 报表，并按 Brand Name 生成每日佣金汇总。

## 环境准备

1. 安装依赖：

```bash
pip install -r requirements.txt
```

2. 配置环境变量（建议放到 shell 配置或专门的 `.env` 管理）：

```bash
export PARTNERBOOST_TOKEN="你的 PartnerBoost token"
```

## 脚本说明

### 1. 同步产品信息到 SQLite

```bash
python sync_products.py
```

- 调用 `/api/datafeed/get_fba_products` 接口
- 将 ASIN 与品牌等信息写入 `products.db` 的 `products` 表

> 注意：如果接口返回的字段名与你实际看到的不同，请根据实际 JSON 调整 `sync_products.py` 中的字段映射。

### 2. 生成每日 Amazon 品牌佣金报表

```bash
python daily_amazon_report.py
```

- 调用 `/api/datafeed/get_amazon_report` 拉取指定日期数据（默认昨天）
- 从 `products.db` 查询 ASIN 对应的 Brand Name
- 按 Brand Name 汇总：订单数、销售金额、佣金金额

## 定时任务示例（crontab）

每天 00:30 同步产品，01:00 生成前一天日报：

```bash
30 0 * * * /usr/bin/python3 /absolute/path/to/partnerboost_reports/sync_products.py >> /absolute/path/to/logs/sync_products.log 2>&1
0 1 * * * /usr/bin/python3 /absolute/path/to/partnerboost_reports/daily_amazon_report.py >> /absolute/path/to/logs/daily_report.log 2>&1
```

根据你的 Python 路径和项目实际目录调整上述路径。
