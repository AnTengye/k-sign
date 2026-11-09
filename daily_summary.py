# -*- coding:utf-8 -*-
"""
cron: 30 20 * * *
new Env('每日签到汇总通知');
"""
import datetime
import json
from base import summary_directory
from notify import send


def build_daily_summary(today: str = None) -> str:
    today = today or datetime.date.today().isoformat()
    ledger_path = summary_directory() / f"{today}.json"

    if not ledger_path.exists():
        return "【今日成功0条，失败0条，失败任务：无】"

    try:
        records = json.loads(ledger_path.read_text(encoding="utf-8"))
    except Exception:
        records = {}
    if not isinstance(records, dict):
        records = {}

    succeeded = [name for name, info in records.items() if isinstance(info, dict) and info.get("success")]
    failed = [name for name, info in records.items() if not (isinstance(info, dict) and info.get("success"))]

    failed_text = "、".join(failed) if failed else "无"
    return f"【今日成功{len(succeeded)}条，失败{len(failed)}条，失败任务：{failed_text}】"


def main() -> str:
    summary_text = build_daily_summary()
    send(title="每日签到汇总", content=summary_text)
    return summary_text


if __name__ == "__main__":
    main()
