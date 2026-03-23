"""
ocr_batch.py — Skill: 批量 OCR
读取 inbox/ 中的所有图片，调用本地 Ollama glm-ocr，
将结果追加到 ocr_queue.csv，并把图片移动到 processed/ 或 failed/。
"""
import base64
import os
import sys

import requests
from dotenv import load_dotenv

# 允许从 skills/ 子目录直接运行
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
import utils

load_dotenv()

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL    = os.getenv("OLLAMA_OCR_MODEL", "glm-ocr")
OCR_TIMEOUT     = int(os.getenv("OCR_TIMEOUT", "120"))

log = utils.get_logger("ocr_batch")


def _encode_image(path) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _call_ocr(image_path) -> str:
    """调用 Ollama glm-ocr，返回识别的文字。"""
    b64 = _encode_image(image_path)
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": "请识别图片中的所有文字，原样输出，不要添加任何说明。",
        "images": [b64],
        "stream": False,
    }
    resp = requests.post(
        f"{OLLAMA_BASE_URL}/api/generate",
        json=payload,
        timeout=OCR_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json().get("response", "").strip()


def run() -> str:
    """
    主入口，供 mcp_server.py 和命令行调用。
    返回处理摘要字符串。
    """
    images = [
        p for p in utils.INBOX_DIR.iterdir()
        if p.is_file() and p.suffix.lower() in utils.IMAGE_EXTS
    ]

    if not images:
        msg = "inbox/ 中没有待处理的图片。"
        log.info(msg)
        return msg

    success, failed = 0, 0
    new_rows = []

    for img in images:
        log.info(f"OCR 处理: {img.name}")
        try:
            text = _call_ocr(img)
            dest = utils.move_image(img, utils.PROCESSED)
            new_rows.append({
                "image_path": str(dest),
                "ocr_text":   text,
                "ocr_at":     utils.now_str(),
            })
            success += 1
            log.info(f"成功: {img.name} → {dest}")
        except Exception as e:
            utils.move_image(img, utils.FAILED_DIR)
            failed += 1
            log.error(f"失败: {img.name} — {e}")

    if new_rows:
        utils.append_csv(utils.OCR_QUEUE, new_rows, utils.OCR_QUEUE_FIELDS)

    msg = f"OCR 完成：成功 {success} 张，失败 {failed} 张。已追加到 ocr_queue.csv。"
    log.info(msg)
    return msg


if __name__ == "__main__":
    print(run())
