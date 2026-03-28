"""
Skill 2: 复式账本对账
按复式记账规则逐行还原各账户余额；统计资金总览；发现异常时报告，不修改账本。

规则：
- 支出 (Expense)：只扣减 source 账户（我的钱少了）
- 收入 (Income)：只增加 dest 账户（我的钱多了）
- 互转 (Transfer)：source 扣减，dest 增加
"""
import os
import csv
from pathlib import Path
from collections import defaultdict
from dotenv import load_dotenv

load_dotenv()

LEDGER_PATH = Path(os.getenv("LEDGER_PATH", "./ledger.csv"))

# 哪些账户名是「我的账户」（余额会随流水变动）
MY_ACCOUNTS = {
    "微信", "支付宝", "花呗",
    "工商银行4674", "工商银行8642",
    "中国银行9158", "中国银行9168", "中国银行数字人民币",
    "邮储银行8533", "交通银行2162",
    "天星银行储蓄账户", "中信银行2684",
}


def _is_my_account(name: str) -> bool:
    if not name:
        return False
    name = name.strip()
    # 精确匹配 或 包含关键词（处理"工商银行尾号4674"等写法）
    if name in MY_ACCOUNTS:
        return True
    for acc in MY_ACCOUNTS:
        if acc in name:
            return True
    return False


def check_ledger() -> str:
    """
    主入口：读取 ledger.csv，逐行模拟余额，与 balance 字段比对，输出报告。
    """
    if not LEDGER_PATH.exists():
        return f"❌ 账本文件不存在: {LEDGER_PATH.resolve()}"

    with open(LEDGER_PATH, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        return "📭 账本为空，无数据可核对。"

    # 累计余额：account -> float
    balances: dict[str, float] = defaultdict(float)
    anomalies: list[str] = []
    TOLERANCE = 0.01  # 浮点误差容忍

    for i, row in enumerate(rows, start=2):  # start=2 对应 CSV 数据行号（第1行是表头）
        txn_time   = row.get("time", "").strip() or f"行{i}"
        txn_type   = row.get("type", "").strip()
        source     = row.get("source", "").strip()
        dest       = row.get("dest", "").strip()
        image_path = row.get("image_path", "")

        try:
            amount = float(row.get("amount", 0) or 0)
        except ValueError:
            anomalies.append(f"⚠️  [{txn_time}] amount 字段非数字: {row.get('amount')}")
            continue

        balance_raw = row.get("balance", "").strip()
        has_balance = balance_raw not in ("", "None", "null", "NULL")
        try:
            snapshot_balance = float(balance_raw) if has_balance else None
        except ValueError:
            snapshot_balance = None

        # ===== 按类型更新余额 =====
        if txn_type == "支出":
            if _is_my_account(source):
                balances[source] -= amount
            # dest 是商家/消费品类，不参与余额计算

        elif txn_type == "收入":
            if _is_my_account(dest):
                balances[dest] += amount
            # source 是付款方，不参与余额计算

        elif txn_type == "互转":
            if _is_my_account(source):
                balances[source] -= amount
            if _is_my_account(dest):
                balances[dest] += amount

        else:
            anomalies.append(f"⚠️  [{txn_time}] 未知交易类型: '{txn_type}'（行{i}）")
            continue

        # ===== 余额比对（仅互转时 balance 有意义，其余类型可选比对 source） =====
        if snapshot_balance is not None:
            # 互转时，balance 是 source 账户扣减后的余额
            compare_account = source if txn_type in ("互转", "支出") else dest
            if _is_my_account(compare_account):
                calc = balances[compare_account]
                diff = abs(calc - snapshot_balance)
                if diff > TOLERANCE:
                    anomalies.append(
                        f"❌ [{txn_time}] {compare_account} 余额不符 "
                        f"| 计算值: {calc:.2f}  截图值: {snapshot_balance:.2f}  "
                        f"差额: {snapshot_balance - calc:+.2f}"
                        f"  | 图片: {image_path}"
                    )

    # ===== 汇总报告 =====
    lines = []
    lines.append("=" * 55)
    lines.append("📊 资金总览（基于流水累计计算）")
    lines.append("=" * 55)

    my_total = 0.0
    for acc in sorted(balances.keys()):
        bal = balances[acc]
        is_mine = _is_my_account(acc)
        tag = "💳" if is_mine else "🏪"
        lines.append(f"  {tag} {acc:<20} ¥ {bal:>12,.2f}")
        if is_mine:
            my_total += bal

    lines.append("-" * 55)
    lines.append(f"  💰 我的账户总资产（估算）      ¥ {my_total:>12,.2f}")
    lines.append("=" * 55)

    if anomalies:
        lines.append(f"\n⚠️  发现 {len(anomalies)} 处对账异常，请人工复查：\n")
        lines.extend(anomalies)
    else:
        lines.append("\n✅ 账本余额核对一致，未发现异常。")

    lines.append(f"\n📋 共核对 {len(rows)} 笔记录。")
    return "\n".join(lines)


if __name__ == "__main__":
    print(check_ledger())
