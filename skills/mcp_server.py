"""
mcp_server.py — MCP Server 入口
向 gemini-cli 注册三个记账相关的核心工具。

注册方式（针对 ~/.gemini/settings.json）：
{
  "mcpServers": {
    "bookkeeping": {
      "command": "python",
      "args": ["skills/mcp_server.py"],
      "cwd": "C:/Users/p/Documents/code/personal_auto_ai_Double_entry_bookkeeping"
    }
  }
}
"""
import sys
from pathlib import Path

# 确保 skills/ 目录在 sys.path 查收路径中，使 import utils 及其它模块能够成功寻找路径
sys.path.insert(0, str(Path(__file__).parent))

from mcp.server.fastmcp import FastMCP
import ocr_batch
import analyze_and_write
import check_ledger

# 实例化 FastMCP 对象并命名
mcp = FastMCP("bookkeeping")


@mcp.tool()
def run_ocr() -> str:
    """
    对 inbox/ 中所有新图片执行 OCR（利用本地 Ollama 的 glm-ocr 预训练模型），
    识别结果追加到 ocr_queue.csv，并将图片移入 processed/ 或 failed/ 进行归档。
    返回处理摘要供用户查阅。
    """
    return ocr_batch.run()


@mcp.tool()
def run_analyze_and_write() -> str:
    """
    读取 ocr_queue.csv 中所有待分析条目，调用 gemini 工具自动提取结构化记账 JSON 数据，
    直接抽取附带的余额并进行结算，自动将信息落表至 ledger.xlsx 文件里，操作一旦完成将空置队列。
    返回最终写表现状摘要供用户评估。
    """
    return analyze_and_write.run()


@mcp.tool()
def run_check_ledger() -> str:
    """
    对 ledger.xlsx 进行复式记账健康度严谨检查，
    算法会根据明确的支出、收入/转账发生额计算每个账户的预计余额走势，
    并与提取出的真实发生时点账户余额（表格内的 balance 列）进行差错比对。
    如果发现任何不一致之处就会返回详细的行号和日期予以报告。
    """
    return check_ledger.run()


if __name__ == "__main__":
    mcp.run()
