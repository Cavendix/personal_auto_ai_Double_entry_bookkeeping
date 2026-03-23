"""
utils.py — 公共函数：CSV 读写、文件移动、日志初始化
所有 skill 脚本共用此模块。
"""
import csv
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ── 路径常量 ────────────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).parent.parent
INBOX_DIR   = BASE_DIR / os.getenv("INBOX_DIR", "inbox")
PROCESSED   = BASE_DIR / os.getenv("PROCESSED_DIR", "processed")
FAILED_DIR  = BASE_DIR / os.getenv("FAILED_DIR", "failed")
LOGS_DIR    = BASE_DIR / "logs"

OCR_QUEUE   = BASE_DIR / "ocr_queue.csv"
OCR_DONE    = BASE_DIR / "ocr_done.csv"
LEDGER_PATH = BASE_DIR / "ledger.xlsx"
PROMPTS     = BASE_DIR / "prompts.yaml"

# 支持的图片扩展名
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}

# ── 日志 ─────────────────────────────────────────────────────────────────────
def get_logger(name: str) -> logging.Logger:
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        fh = logging.FileHandler(LOGS_DIR / "app.log", encoding="utf-8")
        fh.setFormatter(fmt)
        sh = logging.StreamHandler()
        sh.setFormatter(fmt)
        logger.addHandler(fh)
        logger.addHandler(sh)
    return logger


# ── CSV 工具 ─────────────────────────────────────────────────────────────────
OCR_QUEUE_FIELDS = ["image_path", "ocr_text", "ocr_at"]
OCR_DONE_FIELDS  = [
    "image_path", "ocr_text", "ocr_at",
    "ai_result", "status", "error_msg", "analyzed_at", "written_to_ledger",
]


def _ensure_csv(path: Path, fieldnames: list[str]) -> None:
    """如果 CSV 文件不存在则创建并写入表头。"""
    if not path.exists():
        with open(path, "w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=fieldnames).writeheader()


def read_csv(path: Path, fieldnames: list[str]) -> list[dict]:
    _ensure_csv(path, fieldnames)
    with open(path, "r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def append_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    _ensure_csv(path, fieldnames)
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writerows(rows)


def rewrite_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    """整体覆盖重写（用于更新 written_to_ledger 等字段）。"""
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


# ── 文件移动 ───────────────────────────────────────────────────────────────────
def move_image(src: Path, dest_dir: Path) -> Path:
    """将图片移动到目标目录，文件名冲突时自动加时间戳后缀。"""
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name
    if dest.exists():
        stem, suffix = src.stem, src.suffix
        ts = datetime.now().strftime("%H%M%S%f")
        dest = dest_dir / f"{stem}_{ts}{suffix}"
    shutil.move(str(src), str(dest))
    return dest


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
