# 📒 Personal Auto AI Double-Entry Bookkeeping

> 基于 Gemini 3.1 Pro API 的全自动图片提取与复式记账对账系统

---

## 📌 项目概述

本项目实现「图片 → Gemini API (多模态识图提取) → 结构化 JSON → 表格入账 → 复式对账检查」的全自动记账流水线：

- 手动投入票据图片，系统自动识别处理
- **统一使用 Gemini 3.1 Pro API**，合二为一完成图片 OCR 与数据结构化提取，大幅简化架构
- **解耦为两个核心 Skill**：
  1. **智能识图记账**：读取图片、调用大模型提取 JSON、记录成功/失败状态。
  2. **复式健康度检查**：针对账本数据进行严谨的复式记账规则核对、统计并输出异常报告。

---

## 🏗️ 架构设计与核心技能 (Skills)

当前系统精简为两个核心 Skill：

### Skill 1: 智能识图记账
- **流程**：读取 `inbox/` 中的图片 -> 调用 Gemini 3.1 Pro API -> 按提示词输出包含记账信息的 JSON。
- **AI 自检**：JSON 返回结果中需额外包含一个 AI 自我判断字段`is_success`，由大模型自行判断本次识别是否完整、成功。
- **成功分支**：识别与解析成功后，将结构化数据写入 `ledger.csv` 表格（账单），并将原图片移动至 `processed/` 目录。
- **失败分支**：若识别失败或异常，将图片移动至 `failed/` 目录，并将 API 返回的具体内容与错误原因写入日志，方便排查。

### Skill 2: 复式账本对账
- **功能**：基于复式记账原理，检查每个账户的金额变动是否正确，并**统计资金总览**。
- **核心逻辑**：
  - **支出 (Expense)**：只扣减 `源账户 (Source)`（我的钱少了），不增加 `目的账户`（那是商家或消费类别，不属于我的资金）。
  - **收入 (Income)**：只增加 `目的账户 (Dest)`（我的钱多了），不扣减 `源账户`（那是发工资的公司或付款人，不属于我的资金）。
  - **互转 (Transfer)**：`源账户 (Source)` 扣减，`目的账户 (Dest)` 增加（左口袋进右口袋，总资产不变）。互转的`余额（Balance）`列填写`源账户 (Source)`扣减后的数值。
- **执行动作**：**不做任何自动矫正或系统修改**。发现哪天的账目出问题时，精准报告具体的日期和异常账户情况，留给人工介入检查和修正。

---

## 🗂️ 目录结构

```text
personal_auto_ai_Double_entry_bookkeeping/
│
├── inbox/                  # 📥 手动放入待处理图片
├── processed/              # ✅ 处理成功的图片移入此处
├── failed/                 # ❌ 处理失败的图片存放处 (或失败记录表)
│
├── skills/                 # 🔧 核心业务逻辑代码
│   ├── mcp_server.py       # MCP Server 入口，向 Agent 暴露应用路由
│   ├── process_receipt.py  # Skill 1: 调用 Gemini API 识别图片写入表格
│   └── check_ledger.py     # Skill 2: 对账本进行复式校验与总览统计
│
├── logs/                   # 日志文件 (存放失败堆栈、API返回原文)
├── ledger.csv              # 📊 账本主文件 (或 ledger.xlsx)
├── prompts.yaml            # 提示词设定
├── .env                    # 环境变量
└── README.md
```

---

## 📊 账本字段（ledger 表结构不变）

| 列名 | 类型 | 说明 |
|------|------|------|
| `time` | datetime | 交易时间 |
| `type` | string | 支出 / 收入 / 互转 |
| `amount` | number | 流水金额 |
| `source` | string | 流出账户 |
| `dest` | string | 流入账户 |
| `balance` | number | 提取的账户余额，配合 check_ledger 使用 |
| `note` | string | 备注 |
| `image_path` | string | 原始图片路径 |

---

## 🤖 MCP 路由配置与 Agent 执行 (gemini-cli)

本项目由大模型 Agent（如 `gemini-cli`）作为大脑进行任务分发，将本地的两个核心 Skill 封装为 MCP (Model Context Protocol) 工具供其直接调用。

### 1. 配置路由

在 `~/.gemini/settings.json` 中配置本项目的 MCP Server 路径，暴露本地能力：

```json
{
  "mcpServers": {
    "bookkeeping": {
      "command": "C:/Users/p/Documents/code/personal_auto_ai_Double_entry_bookkeeping/.venv/Scripts/python.exe",
      "args": ["skills/mcp_server.py"],
      "cwd": "C:/Users/p/Documents/code/personal_auto_ai_Double_entry_bookkeeping"
    }
  }
}
```

### 2. 通过 Agent 执行

配置完成后启动 `gemini-cli`，Agent 将自动挂载上述 `bookkeeping` 路由。你只需与之进行自然语言对话即可
