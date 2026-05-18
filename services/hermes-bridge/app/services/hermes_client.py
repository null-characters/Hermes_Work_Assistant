"""
Hermes Client Service
======================

与 Hermes Agent 容器通信的客户端服务。

通过 Docker exec 将任务发送给 Hermes Agent 并获取响应。
支持同步执行和流式执行（SSE）。
"""

import subprocess
import logging
import asyncio
import os
import shlex
import threading
import queue
from typing import Optional, AsyncGenerator, Any
from dataclasses import dataclass

logger = logging.getLogger(__name__)


# B-01 安全修复：容器白名单
# 硬编码允许执行的容器列表，防止通过环境变量注入恶意容器名
ALLOWED_CONTAINERS = {"hermes-agent"}


class SecurityError(Exception):
    """安全校验失败"""
    pass


@dataclass
class HermesResponse:
    """Hermes Agent 响应结果"""
    success: bool
    message: str
    output: str
    error: Optional[str] = None
    hermes_session_id: Optional[str] = None  # Hermes 内部会话 ID，用于恢复对话


class HermesClient:
    """Hermes Agent Docker 客户端"""
    
    CONTAINER_NAME = os.getenv("HERMES_CONTAINER_NAME", "hermes-agent")
    TIMEOUT = int(os.getenv("HERMES_TIMEOUT", "600"))
    
    def __init__(self):
        # B-01 安全修复：校验容器名在白名单内
        if self.CONTAINER_NAME not in ALLOWED_CONTAINERS:
            raise SecurityError(
                f"安全错误: 容器 '{self.CONTAINER_NAME}' 不在允许列表中。"
                f"允许的容器: {ALLOWED_CONTAINERS}"
            )
        self._container_status = None
    
    def is_available(self) -> bool:
        """检查 Hermes Agent 是否可用"""
        # B-01 安全修复：运行时双重校验容器名
        if self.CONTAINER_NAME not in ALLOWED_CONTAINERS:
            logger.error(f"安全错误: 容器 '{self.CONTAINER_NAME}' 不在白名单内")
            return False
        try:
            result = subprocess.run(
                ["docker", "inspect", "-f", "{{.State.Status}}", self.CONTAINER_NAME],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                status = result.stdout.strip()
                self._container_status = status
                return status == "running"
            return False
        except Exception as e:
            logger.warning(f"检查 Hermes Agent 状态失败: {e}")
            return False
    
    async def execute_task(
        self,
        prompt: str,
        timeout: Optional[int] = None
    ) -> HermesResponse:
        """执行任务（同步模式）"""
        timeout = timeout or self.TIMEOUT
        
        if not self.is_available():
            return HermesResponse(
                success=False,
                message="Hermes Agent 容器不可用",
                output="",
                error="container_not_found"
            )
        
        try:
            logger.info(f"发送任务到 Hermes Agent: {prompt[:100]}...")
            
            result = await asyncio.to_thread(
                self._exec_in_container,
                prompt,
                timeout
            )
            
            return result
            
        except asyncio.TimeoutError:
            logger.error(f"任务执行超时 ({timeout}s)")
            return HermesResponse(
                success=False,
                message=f"任务执行超时",
                output="",
                error="timeout"
            )
        except Exception as e:
            logger.error(f"任务执行异常: {e}")
            return HermesResponse(
                success=False,
                message=f"执行异常: {str(e)}",
                output="",
                error=str(e)
            )
    
    def _exec_in_container(
        self,
        prompt: str,
        timeout: int
    ) -> HermesResponse:
        """在容器中执行命令"""
        
        safe_prompt = shlex.quote(prompt)
        HERMES_PATH = "/opt/hermes/.venv/bin/hermes"
        
        cmd = [
            "docker", "exec", self.CONTAINER_NAME,
            HERMES_PATH, "chat", "-q", safe_prompt
        ]
        
        try:
            logger.info(f"执行命令: docker exec {self.CONTAINER_NAME} hermes chat -q ...")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            
            logger.debug(f"Exit code: {result.returncode}")
            logger.debug(f"Stdout length: {len(result.stdout)}")
            
            if result.returncode == 0:
                return HermesResponse(
                    success=True,
                    message="任务执行成功",
                    output=result.stdout.strip(),
                    error=None
                )
            else:
                return HermesResponse(
                    success=False,
                    message="任务执行失败",
                    output=result.stdout.strip(),
                    error=result.stderr.strip() if result.stderr else f"exit_code={result.returncode}"
                )
                
        except subprocess.TimeoutExpired:
            logger.error(f"任务执行超时 ({timeout}s)")
            return HermesResponse(
                success=False,
                message=f"任务执行超时",
                output="",
                error="timeout"
            )
        except Exception as e:
            logger.error(f"容器执行异常: {e}")
            return HermesResponse(
                success=False,
                message=f"执行异常: {str(e)}",
                output="",
                error=str(e)
            )
    
    async def execute_task_stream(
        self,
        prompt: str,
        timeout: Optional[int] = None,
        hermes_session_id: Optional[str] = None
    ) -> AsyncGenerator[dict[str, Any], None]:
        """执行任务（流式模式）- 实时显示 Agent 思考过程
        
        Args:
            prompt: 发送给 Agent 的提示
            timeout: 超时时间（秒）
            hermes_session_id: Hermes 内部会话 ID，用于恢复对话（可选）
        """
        timeout = timeout or self.TIMEOUT
        
        if not self.is_available():
            yield {"type": "error", "content": "Hermes Agent 容器不可用"}
            return
        
        yield {"type": "progress", "content": "🔄 正在启动 Agent..."}
        
        safe_prompt = shlex.quote(prompt)
        HERMES_PATH = "/opt/hermes/.venv/bin/hermes"
        
        # 构建命令，支持会话恢复
        cmd = [
            "docker", "exec", self.CONTAINER_NAME,
            HERMES_PATH, "chat", "-q", safe_prompt, "-v"
        ]
        
        # 如果有 Hermes 会话 ID，使用 --resume 恢复对话
        if hermes_session_id:
            cmd.extend(["--resume", hermes_session_id])
            logger.info(f"恢复 Hermes 会话: {hermes_session_id}")
        
        logger.info(f"流式执行: docker exec {self.CONTAINER_NAME} hermes chat -q -v ...")
        
        # 使用线程池执行 Popen
        process, output_queue = await asyncio.to_thread(
            self._start_stream_process,
            cmd
        )
        
        yield {"type": "progress", "content": "📖 Agent 正在初始化..."}
        
        # 实时处理输出，解析不同类型的信息
        last_heartbeat = 0
        heartbeat_interval = 5
        output_lines = []
        hermes_sid = None  # 捕获 Hermes 会话 ID
        
        while True:
            try:
                # 非阻塞读取队列
                item = await asyncio.to_thread(output_queue.get, timeout=0.5)
                
                if item is None:
                    # 队列结束信号
                    break
                    
                item_type, content = item
                
                if item_type == 'output' and content is not None:
                    output_lines.append(content)
                    
                    # 解析 Hermes 会话 ID（格式: "Session: sess_xxx" 或类似）
                    sid_match = self._extract_session_id(content)
                    if sid_match:
                        hermes_sid = sid_match
                    
                    # 解析结构化输出
                    parsed = self._parse_hermes_output(content)
                    if parsed:
                        parsed_content = parsed.get('content', '')
                        content_preview = parsed_content[:50] if parsed_content else ''
                        logger.info(f"解析成功: {parsed.get('type')} - {content_preview}")
                        yield parsed
                    else:
                        # 未解析的输出，作为普通日志
                        if content.strip():
                            yield {"type": "log", "content": content}
                            
                elif item_type == 'stderr' and content is not None:
                    # stderr 包含 INFO/DEBUG 日志，需要解析
                    # 也可能包含会话 ID
                    sid_match = self._extract_session_id(content)
                    if sid_match:
                        hermes_sid = sid_match
                    
                    parsed = self._parse_hermes_output(content)
                    if parsed:
                        yield parsed
                    elif 'ERROR' in content or 'CRITICAL' in content:
                        yield {"type": "error", "content": f"⚠️ {content}"}
                    elif 'DEBUG' in content:
                        # DEBUG 日志不显示，减少噪音
                        pass
                    elif self._is_important_info(content):
                        # 只显示重要的 INFO 日志
                        yield {"type": "log", "content": content}
                elif item_type == 'done':
                    break
                    
            except queue.Empty:
                # 队列空时检查进程状态
                if process.poll() is not None:
                    # 进程已结束，等待队列清空
                    await asyncio.sleep(0.3)
                    try:
                        while True:
                            item = output_queue.get_nowait()
                            if item is None:
                                break
                            item_type, content = item
                            if item_type == 'output' and content is not None:
                                parsed = self._parse_hermes_output(content)
                                if parsed:
                                    yield parsed
                            elif item_type == 'stderr' and content is not None:
                                parsed = self._parse_hermes_output(content)
                                if parsed:
                                    yield parsed
                                elif 'ERROR' in content or 'CRITICAL' in content:
                                    yield {"type": "error", "content": f"⚠️ {content}"}
                    except queue.Empty:
                        break
                    break
                
                # 发送心跳进度
                import time
                current_time = time.time()
                if current_time - last_heartbeat >= heartbeat_interval:
                    elapsed = int(current_time % 60)
                    yield {"type": "progress", "content": f"⏳ 处理中... ({elapsed}s)"}
                    last_heartbeat = current_time
        
        # 等待进程结束
        return_code = process.poll()
        
        if return_code == 0:
            # 返回 Hermes 会话 ID（如果有）
            if hermes_sid:
                yield {"type": "done", "content": "✅ 任务执行完成", "hermes_session_id": hermes_sid}
            else:
                yield {"type": "done", "content": "✅ 任务执行完成"}
        elif return_code is not None:
            yield {"type": "error", "content": f"❌ 执行失败: Exit code {return_code}"}
    
    def _extract_session_id(self, line: str) -> Optional[str]:
        """从 Hermes 输出中提取会话 ID
        
        Hermes 会话 ID 格式通常为：
        - "Session: sess_xxxx"
        - "Resume with: --resume sess_xxxx"
        - 或类似格式
        """
        import re
        
        # 匹配 "Session: sess_xxxx" 或 "Resume with: --resume sess_xxxx"
        patterns = [
            r'Session:\s*(sess_[a-zA-Z0-9]+)',
            r'--resume\s+(sess_[a-zA-Z0-9]+)',
            r'Resume with:\s*--resume\s+(sess_[a-zA-Z0-9]+)',
            r'session_id:\s*(sess_[a-zA-Z0-9]+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, line)
            if match:
                return match.group(1)
        
        return None
    
    def _parse_hermes_output(self, line: str) -> Optional[dict[str, Any]]:
        """
        解析 Hermes Agent 输出，提取结构化信息
        
        返回事件类型：
        - thinking: Agent 思考过程
        - tool: 工具调用
        - tool_result: 工具执行结果
        - api_call: API 调用信息
        - init: 初始化信息
        - progress: 进度信息
        - response: Agent 响应内容
        """
        import re
        
        # 去除 ANSI 转义码
        ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
        line = ansi_escape.sub('', line)
        # 去除回车符
        line = line.replace('\r', '')
        # 检查前导空格（Hermes 响应内容以 4 个空格缩进）
        is_indented = line.startswith('    ')
        line = line.strip()
        if not line:
            return None
        
        # 记录原始行用于调试
        logger.debug(f"解析行: {repr(line[:100])}")
        
        # 思考过程 [thinking] ...
        if '[thinking]' in line:
            thinking_content = line.split('[thinking]', 1)[-1].strip()
            if thinking_content:
                return {"type": "thinking", "content": f"💭 {thinking_content}"}
        
        # 工具准备 - "┊ 🔎 preparing search_files…" 或 "┊ 💻 preparing terminal…"
        elif 'preparing' in line and '┊' in line:
            match = re.search(r'preparing\s+(\w+)', line)
            if match:
                tool_name = match.group(1)
                return {"type": "tool", "content": f"🔧 准备工具: {tool_name}"}
            return None  # 不明确的准备行，跳过
        
        # 工具完成 - "✅ Tool 1 completed in 0.87s"
        elif 'Tool' in line and 'completed' in line:
            match = re.search(r'Tool\s+(\d+)\s+completed\s+in\s+([\d.]+)s', line)
            if match:
                tool_num = match.group(1)
                time_str = match.group(2)
                return {"type": "tool_result", "content": f"✅ 工具 {tool_num} 完成 ({time_str}s)"}
        
        # 命令执行 - "┊ 💻 $ ls -la 0.5s"
        elif '$' in line and re.search(r'\d+\.?\d*s$', line):
            cmd_match = re.search(r'\$\s+(.+?)\s+(\d+\.?\d*)s', line)
            if cmd_match:
                cmd = cmd_match.group(1).strip()[:60]
                time_str = cmd_match.group(2)
                return {"type": "tool", "content": f"🔧 执行: {cmd} ({time_str}s)"}
        
        # Hermes 响应框边框 - 跳过
        elif '⚕ Hermes' in line or line.startswith('╭') or line.startswith('╰'):
            return None
        
        # 纯边框字符行 - 跳过
        elif set(line) <= {'─', ' ', '╭', '╰', '╮', '╯', '│', '┆', '┊', ' '}:
            return None
        
        # Agent 响应内容（缩进的内容，非日志行）
        # Hermes 响应格式: "    OK" 或 "    这是中文回复"
        elif is_indented:
            content = line.strip()
            # 排除包含特殊符号的行、日志行、边框行
            if (content and
                '┊' not in content and '│' not in content and
                '$' not in content and 'DEBUG' not in content and
                'INFO' not in content and 'WARNING' not in content and
                'Hermes' not in content and
                not content.startswith('Resume') and
                not content.startswith('Session:') and
                not content.startswith('Duration:') and
                not content.startswith('Messages:') and
                not re.match(r'^\d{2}:\d{2}:\d{2}', content)):  # 排除时间戳开头的日志
                
                # 区分"最终结论"和"工具调用结果"
                # 工具调用结果特征：包含 JSON 格式、大量数据、表格格式等
                is_tool_result = (
                    # JSON 格式数据
                    content.startswith('{') or content.startswith('[') or
                    '"FNumber"' in content or '"FName"' in content or  # 金蝶 ERP 数据
                    # 表格/列表格式
                    content.startswith('|') or content.startswith('-') or
                    # 包含大量数据的特征
                    '":' in content or '", "' in content or
                    # MCP 工具返回的数据格式
                    'Result:' in content or 'total:' in content.lower()
                )
                
                if is_tool_result:
                    # 工具调用结果，不作为最终响应
                    return {"type": "tool_result", "content": f"📋 {content[:100]}..."}
                else:
                    # 最终结论
                    return {"type": "response", "content": f"🤖 {content}"}
        
        # API 调用 - "API call #N: model=..."
        elif 'API call' in line and 'model=' in line:
            # 提取关键信息
            match = re.search(r'API call\s+#(\d+):\s*model=(\S+)', line)
            if match:
                call_num = match.group(1)
                model = match.group(2)
                return {"type": "api_call", "content": f"🌐 API 调用 #{call_num}: {model}"}
            return {"type": "api_call", "content": f"🌐 {line.strip()}"}
        
        # 初始化信息 🤖 AI Agent initialized
        elif 'AI Agent initialized' in line:
            model_match = line.split('model:')[-1].strip() if 'model:' in line else ''
            return {"type": "init", "content": f"🤖 Agent 已初始化 (模型: {model_match})"}
        
        # 工具集启用 ✅ Enabled toolset（汇总行）
        elif 'Enabled toolset' in line and 'Enabled toolsets:' in line:
            # 汇总行 "✅ Enabled toolsets: browser, clarify, ..."
            toolsets = line.split('Enabled toolsets:')[-1].strip()
            return {"type": "init", "content": f"📦 已加载工具集: {toolsets}"}
        elif 'Enabled toolset' in line:
            # 单个工具集行，跳过以减少噪音
            return None
        
        # 会话完成 🎉 Conversation completed
        elif 'Conversation completed' in line:
            match = re.search(r'(\d+)\s+API call', line)
            calls = match.group(1) if match else '?'
            return {"type": "progress", "content": f"🎉 会话完成 (共 {calls} 次 API 调用)"}
        
        # Token 使用信息
        elif 'Token usage:' in line:
            return {"type": "api_call", "content": f"📊 {line.strip()}"}
        
        # Query 显示
        elif line.startswith('Query:'):
            return {"type": "init", "content": f"📝 {line}"}
        
        # 初始化进度
        elif 'Initializing agent' in line:
            return {"type": "progress", "content": "🔄 正在初始化 Agent..."}
        
        # WARNING 日志 - "07:26:11 - run_agent - WARNING ..."
        elif ' - WARNING ' in line:
            return {"type": "log", "content": f"⚠️ {line}"}
        
        # Result 行 - 工具执行结果（包含 "error": null 等字段，不应标记为错误）
        elif line.strip().startswith('Result:') or line.strip().startswith('"Result:'):
            return {"type": "tool_result", "content": f"📋 {line.strip()[:100]}"}
        
        # 错误信息（排除 DEBUG 日志和 Result 行中的 error 字段）
        elif ('Error' in line or 'error' in line.lower()) and 'DEBUG' not in line and '"error"' not in line and 'Result:' not in line:
            return {"type": "error", "content": f"⚠️ {line}"}
        
        return None
    
    def _is_important_info(self, content: str) -> bool:
        """判断 INFO 日志是否重要，用于过滤噪音"""
        # 跳过不重要的 INFO 日志
        skip_patterns = [
            'Vision auto-detect',
            'Auxiliary auto-detect',
            'Auxiliary client:',
            'Could not detect context length',
            'conversation turn:',
            'Turn ended:',
            'OpenAI client created',
            'OpenAI client closed',
            'Manually cleaned up',
            'Active sessions:',
            'Auxiliary title_generation',
        ]
        for pattern in skip_patterns:
            if pattern in content:
                return False
        return True
    
    def _start_stream_process(self, cmd: list[str]) -> tuple[subprocess.Popen[str], queue.Queue[tuple[str, Optional[str]]]]:
        """启动流式进程"""
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1
        )
        
        output_queue = queue.Queue()
        
        def read_stdout():
            try:
                while True:
                    line = process.stdout.readline()
                    if not line:
                        break
                    line = line.rstrip()
                    if line:
                        output_queue.put(('output', line))
                process.stdout.close()
                output_queue.put(('done', None))
            except Exception as e:
                output_queue.put(('error', str(e)))
        
        def read_stderr():
            try:
                while True:
                    line = process.stderr.readline()
                    if not line:
                        break
                    line = line.rstrip()
                    if line:
                        output_queue.put(('stderr', line))
                process.stderr.close()
            except Exception as e:
                output_queue.put(('error', str(e)))
        
        stdout_thread = threading.Thread(target=read_stdout, daemon=True)
        stderr_thread = threading.Thread(target=read_stderr, daemon=True)
        stdout_thread.start()
        stderr_thread.start()
        
        return process, output_queue
    
    async def send_message(
        self,
        message: str,
        file_id: Optional[str] = None,
        user_id: Optional[str] = None
    ) -> HermesResponse:
        """发送消息到 Hermes Agent"""
        prompt = message
        
        if file_id:
            prompt = f"处理文件 {file_id}: {message}"
        
        if user_id:
            prompt = f"[用户 {user_id}] {prompt}"
        
        return await self.execute_task(prompt)
    
    async def process_file(
        self,
        file_path: Optional[str],
        task: str,
        session_id: str,
        output_dir: Optional[str] = None
    ) -> HermesResponse:
        """处理文件或纯文本任务（同步模式）

    file_path 可选：
    - 有值：生成包含文件路径和输出目录的结构化 prompt
    - 无值：直接将 task 作为指令发送给 Agent（直接对话模式）
    """
        if output_dir is None:
            output_dir = f"/app/data/sessions/{session_id}/outputs"

        # 根据是否有文件生成不同的 prompt
        if file_path:
            prompt = (
                f"请处理以下任务：\n"
                f"- 输入文件: {file_path}\n"
                f"- 任务要求: {task}\n"
                f"- 输出目录: {output_dir}/\n"
                f"\n"
                f"说明：\n"
                f"1. 根据任务要求选择合适的输出格式（xlsx/txt/csv/json等）\n"
                f"2. 输出文件保存在 {output_dir}/ 目录下\n"
                f"3. 文件名根据任务内容命名，如：result.xlsx、分析报告.txt、汇总表.csv 等\n"
                f"4. 如果任务不需要生成文件（如查询、分析），直接回答即可"
            )
        else:
            prompt = task

        return await self.execute_task(prompt)
    
    # 别名，保持向后兼容
    async def process_excel(self, file_path: Optional[str], task: str, session_id: str, output_dir: Optional[str] = None) -> HermesResponse:
        """处理 Excel 文件（同步模式）- 别名，推荐使用 process_file"""
        return await self.process_file(file_path, task, session_id, output_dir)
    
    async def process_file_stream(
        self,
        file_path: Optional[str],
        task: str,
        session_id: str,
        output_dir: Optional[str] = None,
        hermes_session_id: Optional[str] = None
    ) -> AsyncGenerator[dict[str, Any], None]:
        """处理文件或纯文本任务（流式模式）

        file_path 可选：
        - 有值：生成包含文件路径和输出目录的结构化 prompt
        - 无值：直接将 task 作为指令发送给 Agent（直接对话模式）
        
        hermes_session_id 可选：
        - 有值：恢复之前的 Hermes 会话，实现连续对话
        - 无值：开始新会话
        """
        if output_dir is None:
            output_dir = f"/app/data/sessions/{session_id}/outputs"

        # 根据是否有文件生成不同的 prompt
        if file_path:
            prompt = (
                f"请处理以下任务：\n"
                f"- 输入文件: {file_path}\n"
                f"- 任务要求: {task}\n"
                f"- 输出目录: {output_dir}/\n"
                f"\n"
                f"说明：\n"
                f"1. 根据任务要求选择合适的输出格式（xlsx/txt/csv/json等）\n"
                f"2. 输出文件保存在 {output_dir}/ 目录下\n"
                f"3. 文件名根据任务内容命名，如：result.xlsx、分析报告.txt、汇总表.csv 等\n"
                f"4. 如果任务不需要生成文件（如查询、分析），直接回答即可"
            )
        else:
            prompt = task

        async for event in self.execute_task_stream(prompt, hermes_session_id=hermes_session_id):
            yield event
    
    # 别名，保持向后兼容
    async def process_excel_stream(self, file_path: Optional[str], task: str, session_id: str, output_dir: Optional[str] = None) -> AsyncGenerator[dict[str, Any], None]:
        """处理 Excel 文件（流式模式）- 别名，推荐使用 process_file_stream"""
        async for event in self.process_file_stream(file_path, task, session_id, output_dir):
            yield event