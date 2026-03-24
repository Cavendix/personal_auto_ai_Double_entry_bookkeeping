"""
utils.py — 公共函数库：包含主要的 CSV 数据表读写流、图片文件搬运以及全应用共享的日志初始化操作。
所有的 skill 执行流程脚本基本都会共用此模块里提供的方法。
"""
import csv
import logging
import os
import shutil
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ── 路径配置和常量 ──────────────────────────────────────────────────────────
# 以本项目根目录定位基准
BASE_DIR    = Path(__file__).parent.parent
# 读取配置或者采用默认命名，设定归属文件夹
INBOX_DIR   = BASE_DIR / os.getenv("INBOX_DIR", "inbox")           # 收件箱、原生态截图暂存处
PROCESSED   = BASE_DIR / os.getenv("PROCESSED_DIR", "processed")   # 处理完毕后的存档点
FAILED_DIR  = BASE_DIR / os.getenv("FAILED_DIR", "failed")         # 遭遇失败、无法被处理数据的废旧点
LOGS_DIR    = BASE_DIR / "logs"

# 固化需要操作到的具体文件定址
OCR_QUEUE   = BASE_DIR / "ocr_queue.csv"    # 初加工提取文字完毕后等带后续智能识别入账的情报队列
LEDGER_PATH = BASE_DIR / "ledger.xlsx"      # 最核心的数据展示成果和最终存放主文件账本
PROMPTS     = BASE_DIR / "prompts.yaml"     # 提供给 Gemini 用做 AI 指引思路的重要 Prompt 提供源

# 批量拉取时候仅支持对包含以下扩展名的图片发动执行操作
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}

# ── 日志工具服务 ───────────────────────────────────────────────────────────────
def get_logger(name: str) -> logging.Logger:
    """初始化并拿到具有文件记录和控制台打印双重特能的高阶排障信息记录器。"""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger(name)
    # 防止多重载入处理器导致的重复循环打印
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
        # 并行输入一份到日志持久化备份实体文件中
        fh = logging.FileHandler(LOGS_DIR / "app.log", encoding="utf-8")
        fh.setFormatter(fmt)
        # 在触发调用命令时打印一份至本控制台屏幕前
        sh = logging.StreamHandler()
        sh.setFormatter(fmt)
        
        logger.addHandler(fh)
        logger.addHandler(sh)
    # 强制压制继承机制导致主程序的复合并发打印输出情况发生
    logger.propagate = False 
    return logger


# ── CSV 表操作相关工具 ─────────────────────────────────────────────────────────
# 提供列索引保证读存信息时的序列稳定可靠对齐
OCR_QUEUE_FIELDS = ["image_path", "ocr_text", "ocr_at"]


def _ensure_csv(path: Path, fieldnames: list[str]) -> None:
    """辅助防御判断：如果目标 CSV 文本对象不存在，则自行创建出框架并先行填写入合规标准表头。"""
    if not path.exists():
        with open(path, "w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=fieldnames).writeheader()


def read_csv(path: Path, fieldnames: list[str]) -> list[dict]:
    """完整拉入内存并将提供的行列内容数据转化成了等于是 Dictionary 对象组成的队列列表集合（List of dicts）。"""
    _ensure_csv(path, fieldnames)
    with open(path, "r", newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def append_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    """在保持已有行存量基础上在结尾递增拼接上追加新的列表。忽略任何不属于声明段额外的内容键。"""
    _ensure_csv(path, fieldnames)
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writerows(rows)


def rewrite_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    """完全抹灭过往数据，实施一种极端的全额覆写，经常用来于状态信息大换水的情境下（例如消费并释放已经作废的清单状态）。"""
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


# ── 文件系统整理操作 ──────────────────────────────────────────────────────────
def move_image(src: Path, dest_dir: Path) -> Path:
    """
    文件隔离流转机制：针对指定内容源执行入库隔离移动迁移操作。
    为预防操作意外及由于源文件名极不规范导致的意外互写覆盖事故危险——
    如果目标地已经有任何一个同名异源文件驻留占据了，则在其原先拓展名后缀前塞入微秒级时间戳信息从而形成全新的无撞图身份认证。
    """
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name
    
    # 冲突后自保并随机生成的更命重制流程环节
    if dest.exists():
        stem, suffix = src.stem, src.suffix
        ts = datetime.now().strftime("%H%M%S%f")
        dest = dest_dir / f"{stem}_{ts}{suffix}"
    
    shutil.move(str(src), str(dest))
    return dest


def now_str() -> str:
    """标准化一个全局唯一时间样式的当前系统时间描述信息获取器。"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
