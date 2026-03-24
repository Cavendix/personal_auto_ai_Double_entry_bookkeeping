# 📒 Personal Auto AI Double-Entry Bookkeeping

> 基于本地 OCR + gemini-cli Agent 的全自动图片记账系统

---

## 📌 项目概述

本项目实现「图片 → OCR → AI 结构化分析 → 表格入账」的全自动记账流水线：

- 手动投入票据图片，系统自动处理
- 本地 Ollama `glm-ocr` 离线 OCR，保护隐私
- **gemini-cli 作为 Agent 驱动整个流程**，Python 脚本作为可调用工具（Skill）
- OCR 与 AI 分析**完全解耦**，独立异步运行
- 结果写入 `ledger.xlsx`，原始图片路径可追溯
- 增加 check_ledger.py，对 ledger.xlsx 里的余额进行账本计算核对

---

## 🏗️ 架构设计

### Agent 驱动模式（gemini-cli + MCP）

```
gemini-cli (Agent / 大脑)
    │  通过 MCP Tool Calling 协议
    ▼
skills/mcp_server.py  (MCP Server)
    │
    ├── tool: run_ocr               # 批量 OCR → 写入 ocr_queue.csv
    ├── tool: run_analyze_and_write # 读取队列 → AI 提取并直接写入 ledger.xlsx
    └── tool: run_check_ledger      # 对 ledger.xlsx 里的余额进行账本计算核对
```

`mcp_server.py` 用 `mcp` 库将三个 Python 函数注册为 MCP 工具，在 `~/.gemini/settings.json` 中声明后，gemini-cli 即可像调用函数一样原生调用它们，**无需 shell 中转**。`GEMINI.md` 提供项目上下文与决策规则。


两个阶段可以在**不同进程/不同时间**运行，互不阻塞。

---

## 🗂️ 目录结构

```
personal_auto_ai_Double_entry_bookkeeping/
│
├── inbox/                  # 📥 手动放入图片
├── processed/              # ✅ OCR 完成后图片移入此处
├── failed/                 # ❌ OCR 失败的图片
│
├── skills/                 # 🔧 MCP 工具层
│   ├── mcp_server.py       # MCP Server 入口，向 gemini-cli 注册工具
│   ├── ocr_batch.py        # Tool: 批量 OCR inbox/ 中的图片
│   ├── analyze_and_write.py# Tool: 批量 AI 分析 ocr_queue.csv 并直接入账
│   ├── check_ledger.py     # Tool: 对 ledger.xlsx 进行记账一致性和余额检查
│   └── utils.py            # 公共函数（文件移动、CSV 读写、日志）
│
├── logs/
│   └── app.log
│
├── ocr_queue.csv           # 📋 OCR 完成、等待 AI 分析的队列
├── ledger.xlsx             # 📊 账本主文件
├── prompts.yaml            # 提示词（记账 AI 的 system prompt）
├── GEMINI.md               # gemini-cli 上下文：项目说明与决策规则
├── requirements.txt
├── .env.example
└── README.md
```

---

## 📋 中间状态文件

### `ocr_queue.csv` — OCR 队列（待 AI 分析）

| 列名 | 说明 |
|------|------|
| `image_path` | 图片在 `processed/` 中的绝对路径 |
| `ocr_text` | OCR 识别出的原始文字 |
| `ocr_at` | OCR 完成时间戳 |

每次 `ocr_batch.py` 运行后**追加**新行；`analyze_batch.py` 消费后将该行移至 `ocr_done.csv`。



---

## 📊 账本字段（ledger.xlsx）

每张图片通常生成 **1 行**；含手续费或信用卡还款优惠时自动拆分为 **2 行**。

| 列名 | 类型 | 说明 |
|------|------|------|
| `time` | datetime | 交易时间，精确到秒 |
| `type` | string | 支出 / 收入 / 互转 |
| `amount` | number | 金额（见符号规则） |
| `source` | string | 流出账户 |
| `dest` | string | 流入账户，含平台及消费品类 |
| `balance` | number | 提取的账户余额，配合 check_ledger 使用 |
| `note` | string | 人工备注（AI 留空） |
| `image_path` | string | 原始图片绝对路径 |

---

## 🧠 提示词（prompts.yaml）

详见 [prompts.yaml](prompts.yaml)。

---

## 🤖 MCP 注册（~/.gemini/settings.json）

在 `~/.gemini/settings.json` 中注册本项目的 MCP Server：

```json
{
  "mcpServers": {
    "bookkeeping": {
      "command": "python",
      "args": ["skills/mcp_server.py"],
      "cwd": "C:/Users/p/Documents/code/personal_auto_ai_Double_entry_bookkeeping"
    }
  }
}
```

gemini-cli 启动后自动连接该 Server，直接在对话中调用三个工具。

### `skills/mcp_server.py` — MCP Server 框架

详见 [skills/mcp_server.py](skills/mcp_server.py)。

### `GEMINI.md` — Agent 上下文

详见 [GEMINI.md](GEMINI.md)。

---

## 🔧 配置（.env）

```env
# 目录
INBOX_DIR=./inbox
PROCESSED_DIR=./processed
FAILED_DIR=./failed

# 本地 Ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_OCR_MODEL=glm-ocr

# AI 分析方式（二选一）
# 方式 A：gemini-cli（免费，需登录 Google 账号）
ANALYZE_MODE=cli
GEMINI_CLI_CMD=gemini

# 方式 B：Google Gemini API（备用，需 API Key）
# ANALYZE_MODE=api
# GEMINI_API_KEY=AIza-xxxx
# GEMINI_API_MODEL=gemini-2.0-flash

WATCH_INTERVAL=5
```

---

## 🚀 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

```
# requirements.txt
mcp[cli]       # MCP Server（gemini-cli Tool Calling）
watchdog       # 目录监控
requests       # HTTP 调用 Ollama
openpyxl       # Excel 读写
python-dotenv  # 环境变量
pyyaml         # 读取 prompts.yaml
Pillow         # 图片处理
```

### 2. 安装 gemini-cli

```bash
npm install -g @google/gemini-cli
gemini auth     # 登录 Google 账号，无需 API Key
```

### 3. 配置并启动 Ollama

```bash
ollama pull glm-ocr
ollama serve
```

### 4. 注册 MCP Server

编辑 `~/.gemini/settings.json`，填入项目路径（参见 MCP 注册章节）。

### 5. 运行

**方式 A：手动分步（推荐调试）**

```bash
python skills/ocr_batch.py        # 阶段1：OCR
python skills/analyze_and_write.py# 阶段2：AI 分析并写入账本
python skills/check_ledger.py     # 附加：账本余额核对检查
```

**方式 B：gemini-cli Agent 驱动（MCP Tool Calling）**

```bash
gemini   # 进入对话，直接说"处理今天的票据"，Agent 自动按序调用三个工具
```

---

## 📁 Skill 模块说明

| 文件 | 输入 | 输出 | 说明 |
|------|------|------|------|
| `ocr_batch.py` | `inbox/` 图片 | `ocr_queue.csv` 新行 | 批量 OCR，图片移入 `processed/` 或 `failed/` |
| `analyze_and_write.py` | `ocr_queue.csv` 未分析行 | `ledger.xlsx` 新增 | 调用 AI 分析，解析提取结果并直接入账，清空队列 |
| `check_ledger.py` | `ledger.xlsx` | 错误列表/报告 | 核对所有行的金额变动与OCR提取余额是否自洽一致 |
| `utils.py` | — | — | 公共函数：CSV 读写、文件移动、日志 |

---

## 🛡️ 错误处理

| 场景 | 处理方式 |
|------|----------|
| OCR 失败 | 图片移入 `failed/`，跳过该图片 |
| AI 返回非 JSON | 重试一次，仍失败写入 `ocr_done.csv` status=error |
| gemini-cli 超时 | 单条超时 30s，失败后继续下一条 |
| 账本写入冲突 | 文件锁顺序写入 |
| `ocr_queue.csv` 为空 | `analyze_batch.py` 静默退出（exit 0） |

---

## 📄 License

MIT — 个人项目，欢迎 Fork。
