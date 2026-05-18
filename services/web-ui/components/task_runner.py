"""
Task Runner Component
=====================

任务执行组件，调用 Hermes Bridge API 提交任务。
支持同步执行和 SSE 流式执行。
"""

import httpx
import os
import json
import logging
from typing import Optional, Generator
from pathlib import Path

logger = logging.getLogger(__name__)

BRIDGE_API_URL = os.getenv("BRIDGE_API_URL", "http://hermes-bridge:8000")

# T03-06: 文件大小限制
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "50"))
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024


class TaskRunner:
    """任务执行器"""
    
    def __init__(self, bridge_url: Optional[str] = None):
        self.bridge_url = bridge_url or BRIDGE_API_URL
        self.timeout = 600
    
    def save_upload_file(
        self,
        session_id: str,
        uploaded_file,
        data_path: Path
    ) -> str:
        """保存上传文件到会话目录
        
        Raises:
            ValueError: 文件大小超过限制
        """
        # T03-07: 文件大小校验
        file_size = len(uploaded_file.getbuffer())
        if file_size > MAX_FILE_SIZE_BYTES:
            raise ValueError(
                f"文件大小 {file_size / 1024 / 1024:.1f}MB 超过限制 {MAX_FILE_SIZE_MB}MB"
            )
        
        uploads_path = data_path / session_id / "uploads"
        uploads_path.mkdir(parents=True, exist_ok=True)
        
        file_path = uploads_path / uploaded_file.name
        with open(file_path, "wb") as f:
            f.write(uploaded_file.getbuffer())
        
        logger.info(f"文件已保存: {file_path}")
        return str(file_path)
    
    def run_task(
        self,
        session_id: str,
        uploaded_file,
        instruction: str,
        data_path: Path
    ) -> dict:
        """执行任务（同步模式）"""
        try:
            file_path = self.save_upload_file(session_id, uploaded_file, data_path)
            
            container_file_path = file_path.replace(
                str(data_path), "/app/data/sessions"
            )
            
            payload = {
                "file_path": container_file_path,
                "task": instruction,
                "session_id": session_id
            }
            
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    f"{self.bridge_url}/api/excel",
                    json=payload
                )
                
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "success": data.get("success", False),
                        "output": data.get("output", ""),
                        "error": data.get("error"),
                        "message": data.get("message", "")
                    }
                else:
                    return {
                        "success": False,
                        "error": f"API 错误: {response.status_code}",
                        "output": ""
                    }
                    
        except httpx.TimeoutException:
            return {"success": False, "error": "请求超时", "output": ""}
        except httpx.ConnectError:
            return {"success": False, "error": "无法连接到 Bridge API", "output": ""}
        except Exception as e:
            logger.error(f"任务执行失败: {e}")
            return {"success": False, "error": str(e), "output": ""}
    
    def run_task_stream(
        self,
        session_id: str,
        uploaded_file,
        instruction: str,
        data_path: Path,
        hermes_session_id: Optional[str] = None
    ) -> Generator[dict, None, None]:
        """
        执行任务（SSE 流式模式）

        uploaded_file 可选：
        - 有值：保存文件并传递 file_path 给后端
        - 无值：直接对话模式，不传 file_path
        
        hermes_session_id 可选：
        - 有值：恢复之前的 Hermes 会话，实现连续对话
        - 无值：开始新会话

        实时返回 Agent 处理进度，用于前端实时显示。

        Yields:
            dict: 事件消息
                - type: "progress" | "tool" | "output" | "error" | "done"
                - content: 具体内容
                - hermes_session_id: Hermes 内部会话 ID（仅在 done 事件中返回）
        """
        try:
            # 处理文件（如果有）
            container_file_path = None
            if uploaded_file:
                file_path = self.save_upload_file(session_id, uploaded_file, data_path)
                container_file_path = file_path.replace(
                    str(data_path), "/app/data/sessions"
                )
            
            payload = {
                "file_path": container_file_path,
                "task": instruction,
                "session_id": session_id
            }
            
            # 如果有 Hermes 会话 ID，添加到请求中
            if hermes_session_id:
                payload["hermes_session_id"] = hermes_session_id
            
            # 使用 SSE 流式请求
            with httpx.Client(timeout=self.timeout) as client:
                with client.stream(
                    "POST",
                    f"{self.bridge_url}/api/excel/stream",
                    json=payload,
                    headers={"Accept": "text/event-stream"}
                ) as response:
                    if response.status_code != 200:
                        yield {
                            "type": "error",
                            "content": f"API 错误: {response.status_code}"
                        }
                        return
                    
                    buffer = ""
                    for chunk in response.iter_text():
                        buffer += chunk
                        
                        # 解析 SSE 数据
                        while "\n\n" in buffer:
                            event_str, buffer = buffer.split("\n\n", 1)
                            for line in event_str.split("\n"):
                                if line.startswith("data: "):
                                    try:
                                        data = json.loads(line[6:])
                                        yield data
                                    except json.JSONDecodeError:
                                        continue
                    
                    # 处理缓冲区剩余数据
                    if buffer.strip():
                        for line in buffer.split("\n"):
                            if line.startswith("data: "):
                                try:
                                    data = json.loads(line[6:])
                                    yield data
                                except json.JSONDecodeError:
                                    continue
                                    
        except httpx.TimeoutException:
            yield {"type": "error", "content": "请求超时"}
        except httpx.ConnectError:
            yield {"type": "error", "content": "无法连接到 Bridge API"}
        except Exception as e:
            logger.error(f"流式任务执行失败: {e}")
            yield {"type": "error", "content": str(e)}


_task_runner: Optional[TaskRunner] = None


def get_task_runner() -> TaskRunner:
    """获取全局 TaskRunner 实例"""
    global _task_runner
    if _task_runner is None:
        _task_runner = TaskRunner()
    return _task_runner
