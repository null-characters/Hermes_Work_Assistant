"""
Hermes Work Assistant - Web UI
==============================

Streamlit 应用主入口。
支持 SSE 流式输出，实时显示 Agent 处理进度。
"""

import streamlit as st
import os
import uuid
import time
from pathlib import Path

from components.task_runner import TaskRunner, get_task_runner
from components.downloader import show_downloads, show_uploads

# 数据目录
DATA_PATH = Path(os.getenv("SESSION_BASE_PATH", "/app/data/sessions"))

# 页面配置
st.set_page_config(
    page_title="Hermes Work Assistant",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义样式
st.markdown("""
<style>
    .session-info {
        background-color: #f0f2f6;
        padding: 10px;
        border-radius: 5px;
        margin-bottom: 10px;
    }
    .progress-log {
        background-color: #1e1e1e;
        color: #d4d4d4;
        padding: 16px;
        border-radius: 8px;
        font-family: 'Menlo', 'Monaco', 'Courier New', monospace;
        font-size: 13px;
        line-height: 1.8;
        max-height: 500px;
        overflow-y: auto;
        white-space: pre-wrap;
        word-break: break-word;
    }
    .progress-log > div {
        padding: 2px 0;
        border-bottom: 1px solid rgba(255,255,255,0.05);
    }
    .progress-log .progress-line { color: #569cd6; }
    .progress-log .tool-line { color: #dcdcaa; }
    .progress-log .output-line { color: #ce9178; }
    .progress-log .error-line { color: #f44747; }
    .progress-log .done-line { color: #6a9955; font-weight: bold; }
    .progress-log .thinking-line { color: #c586c0; font-style: italic; }
    .progress-log .tool-result-line { color: #4ec9b0; }
    .progress-log .api-call-line { color: #9cdcfe; font-size: 11px; }
    .progress-log .init-line { color: #6a9955; font-size: 11px; }
    .progress-log .log-line { color: #808080; font-size: 11px; }
    .progress-log .response-line { color: #dcdcaa; font-weight: bold; }
    .step-indicator {
        display: inline-block;
        width: 24px;
        height: 24px;
        border-radius: 50%;
        text-align: center;
        line-height: 24px;
        margin-right: 8px;
        font-size: 12px;
    }
    .step-active { background-color: #ffa500; color: white; }
    .step-done { background-color: #4caf50; color: white; }
    .step-pending { background-color: #e0e0e0; color: #999; }
</style>
""", unsafe_allow_html=True)


def create_session() -> str:
    """创建新会话"""
    session_id = f"sess_{uuid.uuid4().hex[:12]}"
    session_path = DATA_PATH / session_id
    (session_path / "uploads").mkdir(parents=True, exist_ok=True)
    (session_path / "outputs").mkdir(parents=True, exist_ok=True)
    return session_id


def init_session_state():
    """初始化会话状态"""
    if "session_id" not in st.session_state:
        st.session_state["session_id"] = create_session()
        st.session_state["task_history"] = []
        st.session_state["hermes_session_id"] = None  # Hermes 内部会话 ID，用于恢复对话
        st.session_state["conversation_history"] = []  # 对话历史记录
        st.session_state["config"] = {
            "api_key": os.getenv("OPENAI_API_KEY", ""),
            "base_url": os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1"),
            "model": os.getenv("HERMES_MODEL", "gpt-4")
        }
        # T03-16: 模板持久化
        st.session_state["selected_template_id"] = None
        st.session_state["custom_templates"] = []


# T03-13: 预设处理模板
PROCESSING_TEMPLATES = [
    {"id": "sort_data", "name": "📊 数据排序", "instruction": "将数据按第一列升序排序，保留原有格式"},
    {"id": "remove_empty", "name": "🧹 清理空行", "instruction": "删除所有空行和空白单元格"},
    {"id": "add_summary", "name": "📈 添加汇总", "instruction": "在最后一行添加汇总行，计算数值列的总计"},
    {"id": "merge_sheets", "name": "🔗 合并工作表", "instruction": "合并所有工作表到一个工作表，保留所有数据"},
    {"id": "format_table", "name": "🎨 格式化表格", "instruction": "美化表格：添加边框、对齐列宽、设置标题样式"},
    {"id": "extract_data", "name": "🔍 提取数据", "instruction": "提取包含关键词的数据行"},
    {"id": "convert_format", "name": "🔄 格式转换", "instruction": "将文件转换为指定格式"},
    {"id": "translate", "name": "🌐 翻译内容", "instruction": "将表格内容翻译为目标语言"},
]


def show_sidebar():
    """显示侧边栏"""
    with st.sidebar:
        st.header("⚙️ 配置说明")
        st.info("请在项目根目录的 `.env` 文件中配置 LLM API Key 和模型参数")
        
        st.divider()
        
        # T03-13~T03-14: 处理模板选择
        st.header("📝 处理模板")
        template_names = [t["name"] for t in PROCESSING_TEMPLATES]
        selected_template = st.selectbox(
            "选择预设模板",
            options=["自定义"] + template_names,
            key="template_selector"
        )
        
        if selected_template != "自定义":
            # 找到选中的模板
            template = next((t for t in PROCESSING_TEMPLATES if t["name"] == selected_template), None)
            if template:
                st.session_state.selected_template_id = template["id"]
                st.caption(f"模板: {template['instruction']}")
        
        st.divider()
        
        st.header("📋 会话信息")
        st.caption(f"会话 ID: `{st.session_state.session_id}`")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 新建会话"):
                st.session_state.session_id = create_session()
                st.session_state.task_history = []
                st.session_state.hermes_session_id = None  # 清空 Hermes 会话 ID
                st.session_state.conversation_history = []  # 清空对话历史
                st.rerun()
        
        with col2:
            if st.button("🗑️ 清空对话"):
                st.session_state.task_history = []
                st.session_state.hermes_session_id = None  # 清空 Hermes 会话 ID
                st.session_state.conversation_history = []  # 清空对话历史
                st.rerun()
        
        st.divider()
        
        st.header("❓ 使用帮助")
        with st.expander("查看帮助"):
            st.markdown("""
            **使用步骤：**
            1. 上传文件（支持 Excel/Word/PPT/PDF/CSV/JSON/TXT/图片等）
            2. 输入处理指令或选择预设模板
            3. 点击"执行"按钮
            4. 实时查看处理进度
            5. 下载结果文件
            
            **模板功能：**
            - 选择预设模板快速处理常见任务
            - 可根据需要修改模板指令
            """)


def escape_html(text: str) -> str:
    """转义 HTML 特殊字符，防止 XSS 和渲染错误"""
    if not text:
        return ""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def show_main_content():
    """显示主内容区"""
    st.title("📊 智能文件助手")
    st.markdown("使用自然语言处理各种文件，无需编程知识")
    
    st.caption(f"当前会话: `{st.session_state.session_id}`")
    
    # 显示对话历史
    if st.session_state.get("conversation_history"):
        st.divider()
        st.header("💬 对话历史")
        for msg in st.session_state.conversation_history[-10:]:  # 显示最近10条对话
            if msg["role"] == "user":
                st.markdown(f"**👤 你:** {escape_html(msg['content'])}")
            else:
                st.markdown(f"**🤖 Agent:** {escape_html(msg['content'][:500])}...")
        st.caption(f"共 {len(st.session_state.conversation_history)} 条对话记录")
    
    st.divider()
    
    # 文件上传区 - T03-08: 支持多文件上传
    st.header("📁 文件上传（可选）")
    uploaded_files = st.file_uploader(
        "上传文件（可选，支持多文件）",
        type=["xlsx", "xls", "docx", "doc", "pptx", "ppt", "pdf", "csv", "json", "xml", "txt", "png", "jpg", "jpeg", "gif", "webp"],
        help="支持 Excel/Word/PPT/PDF/CSV/JSON/TXT/图片等格式，可同时上传多个文件",
        accept_multiple_files=True
    )
    
    # 兼容单文件和多文件模式
    if uploaded_files:
        if len(uploaded_files) == 1:
            st.success(f"✅ 已选择文件: {uploaded_files[0].name}")
        else:
            st.success(f"✅ 已选择 {len(uploaded_files)} 个文件")
            for f in uploaded_files[:5]:
                st.caption(f"  • {f.name}")
            if len(uploaded_files) > 5:
                st.caption(f"  ... 还有 {len(uploaded_files) - 5} 个文件")
    
    show_uploads(st.session_state.session_id, DATA_PATH)
    
    st.divider()
    
    # 指令输入区
    st.header("💬 处理指令")
    
    # T03-14~T03-15: 模板应用与参数填充
    default_instruction = ""
    if st.session_state.get("selected_template_id"):
        template = next((t for t in PROCESSING_TEMPLATES if t["id"] == st.session_state.selected_template_id), None)
        if template:
            default_instruction = template["instruction"]
    
    instruction = st.text_area(
        "输入处理指令",
        value=default_instruction,
        placeholder="例如：将第一列数据按升序排序，并添加汇总行",
        height=100,
        key="instruction_input"
    )
    
    # T03-15: 参数填充提示
    if instruction and "{" in instruction and "}" in instruction:
        st.info("💡 指令中包含参数占位符，请将 {参数} 替换为实际值")
    
    with st.expander("📝 查看示例指令"):
        for example in [
            "将第一列数据按升序排序",
            "删除所有空行",
            "在最后一行添加汇总行",
            "合并工作表 Sheet1 和 Sheet2"
        ]:
            st.code(example, language="text")
    
    st.divider()
    
    # 执行按钮 - T03-08: 支持批量执行
    is_batch = uploaded_files and len(uploaded_files) > 1
    col1, col2 = st.columns([2, 1])
    with col1:
        execute_button = st.button(
            "🚀 执行" if not is_batch else "🚀 批量执行",
            type="primary",
            use_container_width=True,
            disabled=not instruction
        )
    
    with col2:
        clear_button = st.button("🗑️ 清空", use_container_width=True)
    
    # 执行任务（流式模式）
    if execute_button and instruction:
        task_runner = get_task_runner()
        
        # T03-08: 多文件 → 批量处理；单文件/无文件 → 单任务处理
        files_to_process = uploaded_files if uploaded_files else [None]
        
        # 批量进度追踪 (T03-10)
        batch_results = []
        total_files = len(files_to_process)
        batch_start_time = time.time()
        
        for file_idx, uploaded_file in enumerate(files_to_process):
            # 批量模式显示进度
            if total_files > 1:
                st.markdown(f"### 📋 处理进度 ({file_idx + 1}/{total_files})")
                if uploaded_file:
                    st.info(f"📄 正在处理: {uploaded_file.name}")
            else:
                st.markdown("### 📋 处理进度")
            
            # 进度步骤指示器
            step_cols = st.columns(4)
            steps = [
                {"label": "上传", "icon": "1", "status": "active"},
                {"label": "分析", "icon": "2", "status": "pending"},
                {"label": "处理", "icon": "3", "status": "pending"},
                {"label": "完成", "icon": "4", "status": "pending"},
            ]
            
            step_placeholders = []
            for i, step in enumerate(steps):
                with step_cols[i]:
                    ph = st.empty()
                    step_placeholders.append(ph)
            
            # 更新步骤状态
            def update_steps(current_step: int):
                labels = ["📤 上传", "🧠 分析", "⚙️ 处理", "✅ 完成"]
                for i, ph in enumerate(step_placeholders):
                    if i < current_step:
                        ph.markdown(f"**{labels[i]}** ✅")
                    elif i == current_step:
                        ph.markdown(f"**{labels[i]}** 🔄")
                    else:
                        ph.markdown(f"~~{labels[i]}~~ ⏳")
            
            update_steps(0)
            
            # 实时日志区域
            log_placeholder = st.empty()
            log_lines = []
            start_time = time.time()
            
            def add_log(line: str, line_type: str = ""):
                """添加日志行"""
                # 转义 HTML 特殊字符
                line = escape_html(line)
                elapsed = time.time() - start_time
                timestamp = f"[{elapsed:.1f}s]"
                if line_type == "progress":
                    log_lines.append(f'<div class="progress-line">{timestamp} {line}</div>')
                elif line_type == "tool":
                    log_lines.append(f'<div class="tool-line">{timestamp} {line}</div>')
                elif line_type == "tool_result":
                    log_lines.append(f'<div class="tool-result-line">{timestamp} {line}</div>')
                elif line_type == "thinking":
                    log_lines.append(f'<div class="thinking-line">{timestamp} {line}</div>')
                elif line_type == "api_call":
                    log_lines.append(f'<div class="api-call-line">{timestamp} {line}</div>')
                elif line_type == "init":
                    log_lines.append(f'<div class="init-line">{timestamp} {line}</div>')
                elif line_type == "response":
                    log_lines.append(f'<div class="response-line">{timestamp} {line}</div>')
                elif line_type == "output":
                    log_lines.append(f'<div class="output-line">{timestamp} {line}</div>')
                elif line_type == "error":
                    log_lines.append(f'<div class="error-line">{timestamp} {line}</div>')
                elif line_type == "done":
                    log_lines.append(f'<div class="done-line">{timestamp} {line}</div>')
                elif line_type == "log":
                    log_lines.append(f'<div class="log-line">{timestamp} {line}</div>')
                else:
                    log_lines.append(f'<div>{timestamp} {line}</div>')
                
                log_placeholder.markdown(
                    f'<div class="progress-log">{"".join(log_lines)}</div>',
                    unsafe_allow_html=True
                )
            
            add_log("🚀 任务启动...", "progress")
            
            # 流式执行
            final_output = ""
            final_error = ""
            task_success = False
            last_error = ""
            hermes_sid = st.session_state.get("hermes_session_id")  # 获取之前保存的 Hermes 会话 ID
            
            for event in task_runner.run_task_stream(
                session_id=st.session_state.session_id,
                uploaded_file=uploaded_file,
                instruction=instruction,
                data_path=DATA_PATH,
                hermes_session_id=hermes_sid  # 传递 Hermes 会话 ID 以恢复对话
            ):
                event_type = event.get("type", "")
                content = event.get("content", "")

                if event_type == "progress":
                    add_log(content, "progress")
                    if "分析" in content or "初始化" in content:
                        update_steps(1)
                    elif "处理" in content or "工具" in content or "执行" in content:
                        update_steps(2)
                    elif "完成" in content:
                        update_steps(3)
                
                elif event_type == "init":
                    add_log(content, "init")
                    update_steps(1)
                
                elif event_type == "thinking":
                    add_log(content, "thinking")
                    update_steps(2)
                
                elif event_type == "tool":
                    add_log(content, "tool")
                    update_steps(2)
                
                elif event_type == "tool_result":
                    add_log(content, "tool_result")
                
                elif event_type == "response":
                    add_log(content, "response")
                    update_steps(2)
                    actual_content = content.replace("🤖 ", "").strip()
                    if actual_content:
                        if final_output:
                            final_output += "\n" + actual_content
                        else:
                            final_output = actual_content
                
                elif event_type == "api_call":
                    add_log(content, "api_call")
                
                elif event_type == "output":
                    if len(content) > 500:
                        add_log(f"📝 输出内容（{len(content)} 字符）...", "output")
                    else:
                        add_log(f"📝 {content}", "output")
                    final_output = content
                
                elif event_type == "log":
                    add_log(content, "log")
                
                elif event_type == "error":
                    add_log(content, "error")
                    last_error = content
                
                elif event_type == "done":
                    add_log(content, "done")
                    task_success = True
                    update_steps(3)
                    # 保存 Hermes 会话 ID，用于后续恢复对话
                    new_hermes_sid = event.get("hermes_session_id")
                    if new_hermes_sid:
                        st.session_state["hermes_session_id"] = new_hermes_sid
            
            # 记录任务结果
            if not task_success:
                final_error = last_error
            
            result = {
                "success": task_success,
                "output": final_output,
                "error": final_error if final_error else None,
                "message": "任务执行完成" if task_success else "任务执行失败"
            }
            
            batch_results.append({
                "file_name": uploaded_file.name if uploaded_file else None,
                "result": result
            })
            
            # 保存对话历史
            st.session_state.task_history.append({
                "instruction": instruction,
                "result": result,
                "file_name": uploaded_file.name if uploaded_file else None
            })
            
            # 保存对话到 conversation_history
            st.session_state.conversation_history.append({
                "role": "user",
                "content": instruction
            })
            if final_output:
                st.session_state.conversation_history.append({
                    "role": "assistant",
                    "content": final_output
                })
            
            # 显示当前任务结果
            st.divider()
            if result["success"]:
                st.success("✅ 处理完成!")
                elapsed = time.time() - start_time
                st.caption(f"⏱️ 总耗时: {elapsed:.1f}s")
                if result.get("output"):
                    st.markdown("#### 🤖 Agent 响应")
                    st.markdown(escape_html(result["output"]))
            else:
                st.error(f"❌ 处理失败: {result.get('error', '未知错误')}")
            
            # 批量模式分隔
            if total_files > 1 and file_idx < total_files - 1:
                st.divider()
        
        # T03-10: 批量结果汇总
        if total_files > 1 and len(batch_results) == total_files:
            st.divider()
            st.header("📊 批量处理结果汇总")
            success_count = sum(1 for r in batch_results if r["result"]["success"])
            fail_count = total_files - success_count
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("总计", total_files)
            with col2:
                st.metric("成功", success_count)
            with col3:
                st.metric("失败", fail_count)
            
            # T03-11: 打包下载
            if success_count > 0:
                import zipfile
                import io
                zip_buffer = io.BytesIO()
                outputs_path = DATA_PATH / st.session_state.session_id / "outputs"
                has_files = False
                if outputs_path.exists():
                    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                        for file_path in outputs_path.iterdir():
                            if file_path.is_file():
                                zf.write(file_path, file_path.name)
                                has_files = True
                if has_files:
                    total_elapsed = time.time() - batch_start_time
                    st.caption(f"⏱️ 批量总耗时: {total_elapsed:.1f}s")
                    st.download_button(
                        label="📦 打包下载全部结果",
                        data=zip_buffer.getvalue(),
                        file_name=f"batch_results_{st.session_state.session_id}.zip",
                        mime="application/zip",
                        use_container_width=True
                    )
    
    if clear_button:
        st.rerun()
    
    st.divider()
    
    # 结果下载区
    st.header("📥 结果下载")
    show_downloads(st.session_state.session_id, DATA_PATH)
    
    st.divider()
    
    # 任务历史
    if st.session_state.task_history:
        st.header("📜 任务历史")
        for i, task in enumerate(reversed(st.session_state.task_history[-5:])):
            with st.expander(f"任务 {len(st.session_state.task_history) - i}: {task['instruction'][:50]}..."):
                st.markdown(f"**文件:** {task['file_name']}")
                st.markdown(f"**状态:** {'✅ 成功' if task['result']['success'] else '❌ 失败'}")
                if task['result'].get('output'):
                    st.code(escape_html(task['result']['output'][:1000]), language="text")


def main():
    """主函数"""
    init_session_state()
    show_sidebar()
    show_main_content()


if __name__ == "__main__":
    main()
