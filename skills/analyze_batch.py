"""
analyze_batch.py — Skill: 批量 AI 分析
读取 ocr_queue.csv 中尚未分析的行，调用 AI 进行结构化提取，
将结果写入 ocr_done.csv，并清空队列。

支持两种 AI 调用方式（通过 .env 的 ANALYZE_MODE 切换）：
  cli — 调用本地 gemini-cli（免费，需登录 Google 账号）
  api — 调用 Google Gemini API（备用，需 GEMINI_API_KEY）
"""
import json
import os
import subprocess
import sys
import tempfile

import yaml
from dotenv import load_dotenv

sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
import utils

load_dotenv()

ANALYZE_MODE     = os.getenv("ANALYZE_MODE", "cli").lower()
GEMINI_CMD       = os.getenv("GEMINI_CLI_CMD", "gemini")
GEMINI_API_KEY   = os.getenv("GEMINI_API_KEY", "")
GEMINI_API_MODEL = os.getenv("GEMINI_API_MODEL", "gemini-2.0-flash")
ANALYZE_TIMEOUT  = int(os.getenv("ANALYZE_TIMEOUT", "60"))

log = utils.get_logger("analyze_batch")


# ── 提示词加载 ────────────────────────────────────────────────────────────────

def _load_prompt() -> tuple[str, str]:
    """读取 prompts.yaml，返回 (system, user_template)。"""
    with open(utils.PROMPTS, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data["system"], data["user_template"]


# ── AI 调用层 ─────────────────────────────────────────────────────────────────

def _call_gemini_cli(system: str, user_msg: str) -> str:
    """
    方式 A：调用 gemini-cli（免费）。
    system + user 拼合后写入临时文件，避免命令行长度限制。
    """
    prompt = f"{system}\n\n---\n\n{user_msg}"
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(prompt)
        tmp_path = tmp.name
    try:
        result = subprocess.run(
            [GEMINI_CMD, "-p", f"@{tmp_path}"],
            capture_output=True,
            text=True,
            timeout=ANALYZE_TIMEOUT,
            encoding="utf-8",
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "gemini-cli 返回非零退出码")
        return result.stdout.strip()
    finally:
        os.unlink(tmp_path)


def _call_gemini_api(system: str, user_msg: str) -> str:
    """
    方式 B：调用 Google Gemini API（备用）。
    需要 pip install google-generativeai 并在 .env 填写 GEMINI_API_KEY。
    """
    try:
        import google.generativeai as genai
    except ImportError:
        raise ImportError("请先安装：pip install google-generativeai")
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY 未配置，请在 .env 中设置")
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel(
        model_name=GEMINI_API_MODEL,
        system_instruction=system,
    )
    response = model.generate_content(user_msg)
    return response.text.strip()


def _call_ai(system: str, user_msg: str) -> str:
    """根据 ANALYZE_MODE 选择调用方式。"""
    if ANALYZE_MODE == "api":
        log.debug("使用 Gemini API 模式")
        return _call_gemini_api(system, user_msg)
    log.debug("使用 gemini-cli 模式")
    return _call_gemini_cli(system, user_msg)


def _extract_json(raw: str) -> str:
    """
    从模型输出中清理出纯 JSON 字符串。
    模型有时仍会包裹 ```json ... ``` 代码块。
    """
    raw = raw.strip()
    if raw.startswith("```"):
        lines = [l for l in raw.splitlines() if not l.startswith("```")]
        raw = "\n".join(lines).strip()
    return raw


# ── 主入口 ────────────────────────────────────────────────────────────────────

def run() -> str:
    system, user_tpl = _load_prompt()

    queue = utils.read_csv(utils.OCR_QUEUE, utils.OCR_QUEUE_FIELDS)
    if not queue:
        msg = "ocr_queue.csv 中没有待分析的条目。"
        log.info(msg)
        return msg

    success, failed = 0, 0
    done_rows = []

    for row in queue:
        image_path = row["image_path"]
        ocr_text   = row["ocr_text"]
        log.info(f"AI 分析: {image_path}")

        user_msg = user_tpl.replace("{ocr_text}", ocr_text)

        try:
            raw     = _call_ai(system, user_msg)
            cleaned = _extract_json(raw)
            json.loads(cleaned)          # 验证合法 JSON

            done_rows.append({
                **row,
                "ai_result":         cleaned,
                "status":            "success",
                "error_msg":         "",
                "analyzed_at":       utils.now_str(),
                "written_to_ledger": "false",
            })
            success += 1
            log.info(f"成功: {image_path}")

        except Exception as e:
            done_rows.append({
                **row,
                "ai_result":         "",
                "status":            "error",
                "error_msg":         str(e),
                "analyzed_at":       utils.now_str(),
                "written_to_ledger": "false",
            })
            failed += 1
            log.error(f"失败: {image_path} — {e}")

    utils.append_csv(utils.OCR_DONE, done_rows, utils.OCR_DONE_FIELDS)
    utils.rewrite_csv(utils.OCR_QUEUE, [], utils.OCR_QUEUE_FIELDS)

    msg = f"AI 分析完成：成功 {success} 条，失败 {failed} 条。详见 ocr_done.csv。"
    log.info(msg)
    return msg


if __name__ == "__main__":
    print(run())
