"""Audit Logger for ERP operations."""

import json
import logging
import os
from datetime import datetime
from typing import Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)


class AuditLogger:
    """ERP 操作审计日志记录器"""
    
    def __init__(self, log_dir: str = "/app/data/audit"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.current_file = self._get_log_file()
    
    def _get_log_file(self) -> Path:
        """获取当前日志文件路径（按日期分割）"""
        date_str = datetime.now().strftime("%Y-%m-%d")
        return self.log_dir / f"erp_audit_{date_str}.jsonl"
    
    def _write_record(self, record: dict[str, Any]) -> None:
        """写入审计记录（JSONL 格式）"""
        try:
            # 检查日期是否变化，更新文件
            new_file = self._get_log_file()
            if new_file != self.current_file:
                self.current_file = new_file
            
            with open(self.current_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"写入审计日志失败: {e}")
    
    def log_operation(
        self,
        operation: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        tool_name: Optional[str] = None,
        parameters: Optional[dict] = None,
        result: Optional[dict] = None,
        success: bool = True,
        error: Optional[str] = None,
    ) -> None:
        """记录 ERP 操作
        
        Args:
            operation: 操作类型 (query/create/upload)
            user_id: 用户 ID
            session_id: 会话 ID
            tool_name: 工具名称
            parameters: 操作参数（敏感字段已脱敏）
            result: 操作结果
            success: 是否成功
            error: 错误信息
        """
        record = {
            "timestamp": datetime.now().isoformat(),
            "operation": operation,
            "user_id": user_id,
            "session_id": session_id,
            "tool_name": tool_name,
            "parameters": self._sanitize_params(parameters),
            "success": success,
            "error": error,
        }
        
        # 结果摘要（不记录完整数据，防止日志过大）
        if result:
            record["result_summary"] = {
                "success": result.get("success"),
                "count": result.get("count"),
                "bill_no": result.get("bill_no"),
            }
        
        self._write_record(record)
        logger.info(f"审计记录: {operation} - {'成功' if success else '失败'}")
    
    def _sanitize_params(self, params: Optional[dict]) -> Optional[dict]:
        """脱敏敏感参数"""
        if not params:
            return params
        
        # 复制参数，避免修改原始数据
        sanitized = params.copy()
        
        # 脱敏敏感字段
        sensitive_fields = ["password", "app_secret", "app_id", "token", "secret"]
        for field in sensitive_fields:
            if field in sanitized:
                sanitized[field] = "***REDACTED***"
        
        return sanitized
    
    def log_query(
        self,
        form_id: str,
        filter_string: Optional[str] = None,
        result_count: int = 0,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        cached: bool = False,
    ) -> None:
        """记录查询操作"""
        self.log_operation(
            operation="query",
            user_id=user_id,
            session_id=session_id,
            tool_name="query_erp_data",
            parameters={
                "form_id": form_id,
                "filter_string": filter_string,
                "cached": cached,
            },
            result={"count": result_count},
            success=True,
        )
    
    def log_create(
        self,
        form_id: str,
        bill_no: Optional[str] = None,
        dry_run: bool = False,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        success: bool = True,
        error: Optional[str] = None,
    ) -> None:
        """记录创建操作"""
        self.log_operation(
            operation="create",
            user_id=user_id,
            session_id=session_id,
            tool_name="create_erp_bill",
            parameters={
                "form_id": form_id,
                "dry_run": dry_run,
            },
            result={"bill_no": bill_no},
            success=success,
            error=error,
        )
    
    def log_upload(
        self,
        file_name: str,
        form_id: str,
        bill_no: str,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        success: bool = True,
        error: Optional[str] = None,
    ) -> None:
        """记录上传操作"""
        self.log_operation(
            operation="upload",
            user_id=user_id,
            session_id=session_id,
            tool_name="upload_erp_attachment",
            parameters={
                "file_name": file_name,
                "form_id": form_id,
                "bill_no": bill_no,
            },
            success=success,
            error=error,
        )


# 全局审计日志实例
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """获取全局审计日志实例"""
    global _audit_logger
    if _audit_logger is None:
        # 优先使用环境变量，其次使用本地 data 目录
        log_dir = os.getenv("AUDIT_LOG_DIR")
        if log_dir is None:
            # 本地开发：使用项目根目录下的 data/audit
            project_root = Path(__file__).parent.parent.parent.parent.parent
            log_dir = str(project_root / "data" / "audit")
        _audit_logger = AuditLogger(log_dir=log_dir)
    return _audit_logger