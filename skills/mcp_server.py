"""
MCP Server 入口
将 Skill 1 (process_receipt) 和 Skill 2 (check_ledger) 注册为 MCP 工具，
供 gemini-cli Agent 通过 Tool Calling 直接调用。
"""
import sys
import os
from pathlib import Path

# 确保项目根目录在 sys.path 中（无论从哪里启动）
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)  # 保证相对路径（.env、inbox/、ledger.csv 等）正确解析

from mcp.server.fastmcp import FastMCP
from skills.process_receipt import process_inbox
from skills.check_ledger import check_ledger

mcp = FastMCP("bookkeeping")


@mcp.tool()
def run_process_receipt() -> str:
    """
    【Skill 1】智能识图记账：
    读取 inbox/ 中的所有图片，调用 Gemini API 直接识别并提取记账 JSON，
    成功则写入 ledger.csv 并将图片移至 processed/，
    失败则将图片移至 failed/ 并记录日志。
    """
    return process_inbox()


@mcp.tool()
def run_check_ledger() -> str:
    """
    【Skill 2】复式账本对账：
    按复式记账规则（支出扣减source、收入增加dest、互转双向）
    逐行核对 ledger.csv 中的每笔流水，
    输出各账户资金总览，并精准报告出现余额偏差的日期与账户。
    不对账本做任何修改。
    """
    return check_ledger()


if __name__ == "__main__":
    mcp.run(transport="stdio")
