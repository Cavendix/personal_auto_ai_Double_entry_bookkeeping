"""
Skill 1: 智能识图记账
直接读取图片，调用 Gemini API 提取记账 JSON，写入 ledger.csv。
"""
import os
import json
import csv
import shutil
import base64
import logging
from pathlib import Path

import yaml
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

# ===== 配置 =====
INBOX_DIR     = Path(os.getenv("INBOX_DIR", "./inbox"))
PROCESSED_DIR = Path(os.getenv("PROCESSED_DIR", "./processed"))
FAILED_DIR    = Path(os.getenv("FAILED_DIR", "./failed"))
LEDGER_PATH   = Path(os.getenv("LEDGER_PATH", "./ledger.csv"))
LOG_PATH      = Path(os.getenv("LOG_PATH", "./logs/app.log"))
PROMPTS_PATH  = Path(os.getenv("PROMPTS_PATH", "./prompts.yaml"))
GEMINI_MODEL  = os.getenv("GEMINI_MODEL", "gemini-2.5-pro-preview-03-25")

SUPPORTED_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}

LEDGER_HEADERS = ["time", "type", "amount", "source", "dest", "balance", "note", "image_path"]

# ===== 日志 =====
def _setup_logger() -> logging.Logger:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("process_receipt")
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        fh = logging.FileHandler(LOG_PATH, encoding="utf-8")
        fh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        sh = logging.StreamHandler()
        sh.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
        logger.addHandler(fh)
        logger.addHandler(sh)
    return logger

logger = _setup_logger()


def _load_system_prompt() -> str:
    with open(PROMPTS_PATH, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("system", "")


def _ensure_ledger():
    """初始化 ledger.csv（如不存在则创建并写入表头）"""
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not LEDGER_PATH.exists():
        with open(LEDGER_PATH, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=LEDGER_HEADERS)
            writer.writeheader()


def _append_rows(rows: list[dict]):
    with open(LEDGER_PATH, "a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=LEDGER_HEADERS, extrasaction="ignore")
        writer.writerows(rows)


def _call_gemini(image_path: Path, system_prompt: str) -> str:
    """上传图片并调用 Gemini API，返回原始文本响应。"""
    mime_map = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png", ".webp": "image/webp",
        ".gif": "image/gif", ".bmp": "image/bmp",
    }
    mime = mime_map.get(image_path.suffix.lower(), "image/jpeg")

    with open(image_path, "rb") as f:
        image_bytes = f.read()

    api_key = os.getenv("GEMINI_API_KEY", "")
    client = genai.Client(api_key=api_key)

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[
            types.Content(
                role="user",
                parts=[
                    types.Part.from_bytes(data=image_bytes, mime_type=mime),
                    types.Part.from_text(text="请分析图片，提取所有交易记账信息，按要求返回 JSON。"),
                ],
            )
        ],
        config=types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.1,  # 低温保证输出稳定
        ),
    )
    return response.text.strip()


def _parse_response(raw: str, image_path: Path) -> list[dict] | None:
    """
    解析 Gemini 返回的 JSON。
    支持单个 dict 或 list[dict]；检查 is_success 字段。
    返回 None 表示识别失败。
    """
    text = raw.strip()
    # 移除可能的 markdown 代码块包装
    if text.startswith("```"):
        lines = text.splitlines()
        # 去掉首行 ```json 和末行 ```
        inner = lines[1:] if len(lines) > 1 else lines
        if inner and inner[-1].strip() == "```":
            inner = inner[:-1]
        text = "\n".join(inner)

    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as e:
        logger.error(f"[{image_path.name}] JSON 解析失败: {e}\n原始返回:\n{raw}")
        return None

    # 统一为列表
    if isinstance(parsed, dict):
        if "error" in parsed:
            logger.error(f"[{image_path.name}] AI 报告错误: {parsed['error']}")
            return None
        records = [parsed]
    elif isinstance(parsed, list):
        records = parsed
    else:
        logger.error(f"[{image_path.name}] 意外的返回类型: {type(parsed)}\n{raw}")
        return None

    # 检查 is_success（任意一条 false 则整图视为失败）
    all_success = all(r.get("is_success", True) for r in records)
    if not all_success:
        logger.warning(f"[{image_path.name}] AI 标记 is_success=false\n原始返回:\n{raw}")
        return None

    # 组装 ledger 行
    rows = []
    for r in records:
        balance_val = r.get("balance")
        # null / None / 空字符串 → 存空
        if balance_val in (None, "null", "NULL", "", "None"):
            balance_val = ""

        row = {
            "time":       r.get("time", ""),
            "type":       r.get("type", ""),
            "amount":     r.get("amount", ""),
            "source":     r.get("source", ""),
            "dest":       r.get("dest", ""),
            "balance":    balance_val,
            "note":       r.get("note", ""),
            "image_path": str(image_path.resolve()),
        }
        rows.append(row)

    return rows


def process_inbox() -> str:
    """
    主入口：处理 inbox/ 中的全部图片。
    返回处理摘要字符串（供 MCP 工具返回给 Agent）。
    """
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key or api_key == "your_api_key_here":
        return "❌ 错误：未配置 GEMINI_API_KEY，请在 .env 中填写真实 API Key。"

    _ensure_ledger()
    system_prompt = _load_system_prompt()

    INBOX_DIR.mkdir(exist_ok=True)
    PROCESSED_DIR.mkdir(exist_ok=True)
    FAILED_DIR.mkdir(exist_ok=True)

    images = sorted(p for p in INBOX_DIR.iterdir() if p.suffix.lower() in SUPPORTED_EXTS)
    if not images:
        return "📭 inbox/ 中没有待处理的图片。"

    success_count = 0
    fail_count = 0
    row_count = 0

    for img in images:
        logger.info(f"▶ 处理: {img.name}")
        try:
            raw = _call_gemini(img, system_prompt)
            logger.info(f"[{img.name}] API 原始返回:\n{raw}")
            rows = _parse_response(raw, img)
        except Exception as e:
            logger.error(f"[{img.name}] API 调用异常: {e}")
            rows = None

        if rows:
            _append_rows(rows)
            shutil.move(str(img), str(PROCESSED_DIR / img.name))
            logger.info(f"✅ 成功: {img.name} → {len(rows)} 条记录，图片移至 processed/")
            success_count += 1
            row_count += len(rows)
        else:
            shutil.move(str(img), str(FAILED_DIR / img.name))
            logger.warning(f"❌ 失败: {img.name} → 图片移至 failed/")
            fail_count += 1

    summary = (
        f"✅ 处理完成：{success_count} 张成功（写入 {row_count} 条记录），"
        f"{fail_count} 张失败。\n"
        f"账本路径：{LEDGER_PATH.resolve()}\n"
        f"失败图片：{FAILED_DIR.resolve()}\n"
        f"详细日志：{LOG_PATH.resolve()}"
    )
    return summary


if __name__ == "__main__":
    print(process_inbox())
