"""
ocr_batch.py — Skill: 批量 OCR
读取 inbox/ 中的所有图片，调用本地 Ollama 驱动的 glm-ocr 视觉识别模型，
将识别的内容文本追加到待分析队列 ocr_queue.csv，并把源文件图移动到 processed/ 或 failed/ 目录下归档保存。
"""
import base64
import os
import sys

import requests
from dotenv import load_dotenv

# 将上级目录加入 sys.path，以便导入 utils 模块
sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
import utils

load_dotenv()

# 从环境配置中读取 Ollama 服务的配置和调用参数
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_MODEL    = os.getenv("OLLAMA_OCR_MODEL", "glm-ocr")
OCR_TIMEOUT     = int(os.getenv("OCR_TIMEOUT", "120"))

log = utils.get_logger("ocr_batch")


def _encode_image(path) -> str:
    """将指定路径的图片文件读取并转换为 Base64 字符串以供接口调用。"""
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def _call_ocr(image_path) -> str:
    """
    调用本地运行的 Ollama 提供的大模型视觉能力解析内容。
    这里使用的是 glm-ocr，返回所有被模型识别得到的纯粹原样文字。
    """
    b64 = _encode_image(image_path)
    # 构造 Ollama Generate 接口请求体
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": "请识别图片中的所有文字，原样输出，不要添加任何说明。", # 严格原样返回，防止附带 AI 无意义的话语
        "images": [b64],
        "stream": False,
    }
    
    # 向 Ollama 发起 HTTP 接口请求
    resp = requests.post(
        f"{OLLAMA_BASE_URL}/api/generate",
        json=payload,
        timeout=OCR_TIMEOUT,
    )
    resp.raise_for_status() # 假如 HTTP 返回任何由服务器提供的错误，立即向上抛出抛出异常
    return resp.json().get("response", "").strip()


def run() -> str:
    """
    主入口，供用户手动命令行运作或者由 mcp_server 触发。
    搜集收件箱，循环 OCR 请求，并将信息汇总保存。
    返回操作的结果总结报告字符串。
    """
    # 获取所有的受支持后缀的图照作为处理素材
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

    # 依次识别每一张图像
    for img in images:
        log.info(f"OCR 处理: {img.name}")
        try:
            text = _call_ocr(img)                       # 接口调用得到文本数据
            dest = utils.move_image(img, utils.PROCESSED) # 如果成功执行读取动作，把图片放入已操作包中
            
            # 将新得到的提取资讯封装成需要挂进缓存列队的行结构
            new_rows.append({
                "image_path": str(dest),
                "ocr_text":   text,
                "ocr_at":     utils.now_str(),
            })
            success += 1
            log.info(f"成功: {img.name} → {dest}")
        except Exception as e:
            # 图像如果识别因为崩溃失败，为了保护原始数据进行留底隔离备查
            utils.move_image(img, utils.FAILED_DIR)
            failed += 1
            log.error(f"失败: {img.name} — {e}")

    # 将成功处理的内容增量拼接到队列 CSV 底部，等待接下来的 AI 阅读及建账步做操作
    if new_rows:
        utils.append_csv(utils.OCR_QUEUE, new_rows, utils.OCR_QUEUE_FIELDS)

    msg = f"OCR 完成：成功 {success} 张，失败 {failed} 张。已追加到 ocr_queue.csv。"
    log.info(msg)
    return msg


if __name__ == "__main__":
    print(run())
