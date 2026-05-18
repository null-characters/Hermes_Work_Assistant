"""
Task Router
===========

任务提交 API 路由。
支持同步执行和 SSE 流式执行。
"""

from fastapi import APIRouter, HTTPException, Request, Body
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional
import logging
import json

from app.services.hermes_client import HermesClient

logger = logging.getLogger(__name__)
router = APIRouter()


class TaskRequest(BaseModel):
    """任务请求"""
    message: str = Field(..., description="任务消息/指令")
    file_id: Optional[str] = Field(None, description="关联的文件 ID")
    user_id: Optional[str] = Field(None, description="用户 ID")
    timeout: Optional[int] = Field(None, description="超时时间（秒）")


class TaskResponse(BaseModel):
    """任务响应"""
    success: bool
    message: str
    output: str
    error: Optional[str] = None
    task_id: Optional[str] = None


class ExcelTaskRequest(BaseModel):
    """Excel/文件处理任务请求

    file_path 可选：
    - 有值：处理指定文件，生成结构化 prompt
    - 无值：直接对话模式，task 作为原始指令发送给 Agent
    
    hermes_session_id 可选：
    - 有值：恢复之前的 Hermes 会话，实现连续对话
    - 无值：开始新会话
    """
    file_path: Optional[str] = Field(None, description="文件在容器内的绝对路径（可选，不传则直接对话）")
    task: str = Field(..., description="处理任务描述或对话内容")
    session_id: str = Field(..., description="会话 ID")
    output_dir: Optional[str] = Field(None, description="输出目录路径")
    timeout: Optional[int] = Field(None, description="超时时间（秒）")
    hermes_session_id: Optional[str] = Field(None, description="Hermes 内部会话 ID，用于恢复对话（可选）")


def get_hermes_client(req: Request) -> HermesClient:
    """获取 Hermes 客户端"""
    return req.app.state.hermes_client


@router.post("/submit", response_model=TaskResponse)
async def submit_task(
    req: Request,
    task_request: TaskRequest = Body(...),
):
    """
    提交任务到 Hermes Agent（同步模式）
    """
    hermes_client: HermesClient = req.app.state.hermes_client
    
    if not hermes_client.is_available():
        raise HTTPException(
            status_code=503,
            detail="Hermes Agent 服务不可用"
        )
    
    logger.info(f"收到任务请求: {task_request.message[:50]}...")
    
    result = await hermes_client.send_message(
        message=task_request.message,
        file_id=task_request.file_id,
        user_id=task_request.user_id
    )
    
    return TaskResponse(
        success=result.success,
        message=result.message,
        output=result.output,
        error=result.error,
        task_id=None
    )


@router.post("/excel", response_model=TaskResponse)
async def process_excel(
    req: Request,
    excel_request: ExcelTaskRequest = Body(...),
):
    """
    处理任务（同步模式）
    
    支持多种任务类型：
    - Excel 处理：输出 xlsx/csv 格式文件
    - 数据分析：输出 txt/json 报告或直接回答
    - 数据提取：输出指定格式文件
    
    输出文件保存在 output_dir 目录，格式由任务内容决定。
    
    示例请求：
    ```json
    {
        "file_path": "/app/data/sessions/sess_xxx/uploads/example.xlsx",
        "task": "提取产品代码和规格型号，生成汇总表",
        "session_id": "sess_xxx",
        "output_dir": "/app/data/sessions/sess_xxx/outputs"
    }
    ```
    """
    hermes_client: HermesClient = req.app.state.hermes_client
    
    if not hermes_client.is_available():
        raise HTTPException(
            status_code=503,
            detail="Hermes Agent 服务不可用"
        )
    
    logger.info(f"收到 Excel 处理请求: {excel_request.file_path} - {excel_request.task[:50]}...")
    
    result = await hermes_client.process_excel(
        file_path=excel_request.file_path,
        task=excel_request.task,
        session_id=excel_request.session_id,
        output_dir=excel_request.output_dir
    )
    
    return TaskResponse(
        success=result.success,
        message=result.message,
        output=result.output,
        error=result.error
    )


@router.post("/excel/stream")
async def process_excel_stream(
    req: Request,
    excel_request: ExcelTaskRequest = Body(...),
):
    """
    处理任务（SSE 流式模式）
    
    返回 Server-Sent Events 流，实时推送处理进度。
    
    输出文件格式根据任务内容自动决定：
    - xlsx/csv: 数据表格处理
    - txt/json: 分析报告
    - 无文件: 查询/分析类任务直接回答
    
    事件类型：
    - thinking: Agent 思考过程
    - tool: 工具准备/执行
    - tool_result: 工具执行结果
    - api_call: API 调用信息
    - response: Agent 响应内容
    - progress: 进度更新
    - error: 错误信息
    - done: 完成（包含 output_file 字段）
    """
    hermes_client: HermesClient = req.app.state.hermes_client
    
    if not hermes_client.is_available():
        raise HTTPException(
            status_code=503,
            detail="Hermes Agent 服务不可用"
        )
    
    logger.info(f"收到 Excel 流式处理请求: {excel_request.file_path} - {excel_request.task[:50]}...")
    
    async def event_generator():
        """SSE 事件生成器"""
        try:
            async for event in hermes_client.process_excel_stream(
                file_path=excel_request.file_path,
                task=excel_request.task,
                session_id=excel_request.session_id,
                output_dir=excel_request.output_dir,
                hermes_session_id=excel_request.hermes_session_id
            ):
                # 格式化为 SSE
                event_type = event.get("type", "message")
                content = event.get("content", "")
                hermes_sid = event.get("hermes_session_id")  # 获取 Hermes 会话 ID
                
                # SSE 格式: data: {json}\n\n
                event_data = {'type': event_type, 'content': content}
                if hermes_sid:
                    event_data['hermes_session_id'] = hermes_sid
                
                yield f"data: {json.dumps(event_data)}\n\n"
                
        except Exception as e:
            logger.error(f"SSE 流异常: {e}")
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # 禁用 nginx 缓冲
        }
    )


@router.get("/status")
async def get_status(req: Request):
    """获取 Hermes Agent 状态"""
    hermes_client: HermesClient = req.app.state.hermes_client
    return {
        "available": hermes_client.is_available(),
        "container": hermes_client.CONTAINER_NAME
    }
