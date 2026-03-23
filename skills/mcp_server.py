"""
mcp_server.py — MCP Server 入口
向 gemini-cli 注册三个记账工具：run_ocr / run_analyze / run_write_ledger。

注册方式（~/.gemini/settings.json）：
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

# 确保 skills/ 目录在路径中，使 import utils 可以找到
sys.path.insert(0, str(Path(__file__).parent))

from mcp.server.fastmcp import FastMCP
import ocr_batch
import analyze_batch
import write_ledger

mcp = FastMCP("bookkeeping", version="1.0.0")


@mcp.tool()
def run_ocr() -> str:
    """
    对 inbox/ 中所有新图片执行 OCR（本地 Ollama glm-ocr），
    识别结果追加到 ocr_queue.csv，图片移入 processed/ 或 failed/。
    返回处理摘要。
    """
    return ocr_batch.run()


@mcp.tool()
def run_analyze() -> str:
    """
    读取 ocr_queue.csv 中所有待分析条目，调用 gemini-cli 提取结构化记账 JSON，
    结果写入 ocr_done.csv，成功/失败均记录。
    返回处理摘要。
    """
    return analyze_batch.run()


@mcp.tool()
def run_write_ledger() -> str:
    """
    将 ocr_done.csv 中 status=success 且未入账的行解析并追加写入 ledger.xlsx。
    支持单笔和多笔拆分（手续费、信用卡返现等）。
    返回入账摘要。
    """
    return write_ledger.run()


if __name__ == "__main__":
    mcp.run()
