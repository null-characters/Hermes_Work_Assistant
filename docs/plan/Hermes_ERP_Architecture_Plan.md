# Hermes-ERP 智能办公助手：产品构思与架构规划文档

## 1. 产品愿景与定位

- **目标人群**：非技术背景的文职人员、销售业务员。
- **核心痛点**：多系统切换繁琐（IM软件、ERP系统、本地文件）、标准化数据搬运耗时、ERP 操作路径深。
- **产品形态**：一个无需安装独立 App、隐身于**企业微信/微信**中的"个人数字助理"。用户通过自然语言下发指令，系统自动完成查询、数据清洗、建单及文件发送。
- **核心价值**：零代码、无感操作、跨系统闭环，"帮打工人省下时间去偷懒"。

## 2. 整体系统架构设计（Brain - Limbs 架构）

整个系统将采取**高度解耦**的分布式架构，分为"大脑"、"感官"和"手脚"三部分：

### 2.1 交互层（感官 - Messaging Gateway）

- **组件**：Hermes 自带的 Gateway 或社区开源微信桥接项目（如 HermesClaw）。
- **职责**：接收用户的自然语言、图片、语音，将其转发给核心引擎，并将最终生成的文本或 Excel/PDF 文件发回给用户。

### 2.2 决策层（大脑 - Hermes Agent）

- **组件**：部署在中心化服务器（如 Docker 容器）上的 Hermes Agent。
- **职责**：维持会话上下文、意图识别、逻辑推理。当识别到 ERP 需求时，生成遵循 MCP 协议的 Tool Calling 请求。

### 2.3 执行层（手脚 - Kingdee MCP Server）

- **组件**：基于已有的 `kingdee_webapi_sdk` 封装的独立 MCP 服务进程。
- **职责**：向 Hermes 暴露"工具箱"。接收大脑的参数，调用金蝶 WebAPI 执行实际的增删改查。

> **架构优势**：采用 **MCP (Model Context Protocol)** 进行解耦挂载，金蝶 SDK 成为一套独立微服务，不仅 Hermes Agent 可以用，未来接入其他支持 MCP 的平台（如 Claude Desktop）也能无缝切换，完全保证核心业务资产不受开源框架版本更迭的影响。

## 3. 核心模块拆解与落地指南

### 模块一：Kingdee MCP Server 开发（优先级：最高）

这是目前需要编写的核心代码。使用 Python 的 MCP SDK（如 `mcp-python-sdk`）将金蝶 SDK 的方法暴露出去。

#### 工具1：查询工具 (`execute_bill_query`)

- **MCP Tool Name**: `query_erp_data`
- **参数定义**: `form_id` (表单), `filter_string` (条件), `field_keys` (字段)。
- **关键点**: 必须约束大模型在执行任何"写入"操作前，先调用此工具查询准确的 ID（Grounding 机制，防止幻觉）。

#### 工具2：建单工具 (`save_and_submit_bill`)

- **MCP Tool Name**: `create_erp_bill`
- **参数定义**: `form_id`, `json_data`。
- **关键点**: 将 SDK 里的 `save` 和 `submit` 包装在一个原子操作里，确保事务一致性。

#### 工具3：文件附件工具 (`upload_attachment`)

- **MCP Tool Name**: `upload_erp_file`
- **参数定义**: 文件流或路径、`form_id`、`bill_no`。

### 模块二：Hermes Agent 核心配置调整

- **连接 MCP**：在 Hermes 的配置文件中，将写好的 Kingdee MCP Server 注册为 External Server。
- **System Prompt / Persona 定制**：为 Agent 编写特定的系统指令。例如：
  > "你是一个精通金蝶云星空 ERP 的财务/销售助理。在创建订单前，你必须先使用 `query_erp_data` 确认客户的 `FNumber`。如果用户提供了 Excel，请先使用 Pandas 读取内容，再逐条转换为建单参数。"

### 模块三：IM 交互与文件流闭环

- 利用 Hermes 的 Messaging 功能。
- **数据导出场景**：Agent 调用 MCP 拿到 ERP JSON 数据 → 本地 Python 子进程（Subagent）将其转为 Excel → 发送至微信。
- **数据导入场景**：用户微信发送 Markdown/Excel → Agent 读取并解析 → 循环调用 MCP `create_erp_bill` 批量建单。

## 4. 典型业务工作流演练 (User Story)

**场景：销售员小李需要根据客户要求发货。**

1. **输入**：小李在微信里对机器人说："帮我查一下 M001 物料现在的库存，如果够的话，按这个 Excel（拖拽文件）里的清单给张总建一个销售订单。"
2. **推理与查询**：Agent 分析意图。调用 MCP `query_erp_data` (表单 `BD_STOCK`，条件 `FNumber='M001'`)。
3. **二次查询**：Agent 调用 MCP `query_erp_data` 查询"张总"在 `BD_CUSTOMER` 里的唯一编号。
4. **数据处理**：Agent 自动读取小李发的 Excel，提取发货数量。
5. **执行操作**：Agent 调用 MCP `create_erp_bill` (表单 `SAL_ORDER`)。
6. **结果反馈**：Agent 通过微信回复："✅ 查到 M001 库存充足（现有 500 件）。已成功为张总创建销售订单（单号：SO20260514-01），已提交系统审核。"

## 5. 分阶段实施路径 (Roadmap)

### Phase 1: MCP Server MVP（1-2周）

- **目标**：用 Python 把金蝶 SDK 包装成 MCP Server。
- **验证**：使用 MCP 官方提供的 Inspector 测试工具，确保工具能被正确发现和调用。

### Phase 2: 命令行/Web联调（1周）

- **目标**：在 Hermes 的 CLI 或原有 Web UI 环境下挂载 MCP。
- **验证**：在终端输入自然语言，观察 Agent 是否能正确调度金蝶工具。调优 Prompt 解决"幻觉"参数问题。

### Phase 3: 微信/企微网关接入（1-2周）

- **目标**：启动 Hermes Gateway，接入微信体系。
- **验证**：实现跨平台对话连续性，解决微信上传大文件的路径挂载问题。

### Phase 4: 工作流固化与 Skills 沉淀（中长期）

- **目标**：利用 Hermes 的 Skills 学习机制，当 Agent 成功完成一次复杂的"报表合并+ERP查询"后，将其固化为标准化技能，后续以极低成本秒级调用。

## 6. 核心风险防范

### 6.1 数据灾难防范（写操作隔离）

- **措施**：给 MCP Server 设置**运行模式参数**（如 `--dry-run` 模式）。或者在调用 `save` 和 `submit` 前，强制要求 Agent 发送一条确认信息给用户："即将创建 10 条订单，请确认(Y/N)"。

### 6.2 权限越界限制

- **措施**：金蝶的 API 凭证（`app_id`, `app_secret`）绝对不能交给大模型本身，必须封死在 MCP Server 的 `.env` 中。大模型只能决定"传什么参数"，绝不能接触认证逻辑。

### 6.3 Token 消耗与死循环

- **措施**：如果 ERP 查询返回了 10 万条数据，直接喂给 LLM 会撑爆上下文。MCP Server 在返回 `execute_bill_query` 结果时，必须做分页截断（`limit`），或者让 Agent 在本地写临时文件再进行统计，而不是将大数据放进 Context 中。
