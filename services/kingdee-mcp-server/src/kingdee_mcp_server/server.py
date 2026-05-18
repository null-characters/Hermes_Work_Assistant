"""MCP Server entry point for Kingdee ERP integration."""

import logging
import os

from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

from .kingdee_client import get_client, reset_client
from .audit_logger import get_audit_logger
from .cache import get_query_cache

# Load environment variables
load_dotenv()

# Configure logging - filter sensitive data
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Create MCP Server instance
mcp = FastMCP("Kingdee ERP MCP Server")


@mcp.tool()
def query_erp_data(
    form_id: str,
    filter_string: str = "",
    field_keys: str = "",
    limit: int = 100,
    user_id: str = "",
    session_id: str = "",
) -> dict:
    """Query data from Kingdee ERP.

    IMPORTANT: Always call this tool before create_erp_bill to:
    1. Verify the entity exists (e.g., customer, material)
    2. Get the correct FNumber/FId to prevent hallucination

    Args:
        form_id: Form identifier. Common values:
            - BD_MATERIAL: 物料基础资料
            - BD_CUSTOMER: 客户基础资料
            - BD_STOCK: 仓库基础资料
            - BD_SUPPLIER: 供应商基础资料
        filter_string: SQL-like filter. Examples:
            - "FNumber like '%KM%'" - 编号包含 KM
            - "FName like '%电机%'" - 名称包含电机
            - "FNumber = 'M001'" - 编号等于 M001
        field_keys: Comma-separated fields. For BD_MATERIAL use:
            "FNumber,FName,FMaterialId,FSpecification"
        limit: Max records (default 100, max 2000)

    Returns:
        Query results with data array and has_more flag

    Examples:
        # 查询物料编号包含 "1.LA" 的物料
        query_erp_data(
            form_id="BD_MATERIAL",
            filter_string="FNumber like '%1.LA%'",
            field_keys="FNumber,FName,FMaterialId"
        )

        # 查询名称包含 "电机" 的物料
        query_erp_data(
            form_id="BD_MATERIAL",
            filter_string="FName like '%电机%'"
        )
    """
    audit = get_audit_logger()
    cache = get_query_cache()
    try:
        client = get_client()
        
        # Default field_keys based on form_id
        if not field_keys:
            # 不同表单的主键字段名不同
            default_fields = {
                "BD_MATERIAL": "FNumber,FName,FMaterialId",
                "BD_CUSTOMER": "FNumber,FName,FCustomerId",
                "BD_STOCK": "FNumber,FName,FStockId",
                "BD_SUPPLIER": "FNumber,FName,FSupplierId",
            }
            field_keys = default_fields.get(form_id, "FNumber,FName,FId")
        
        # Enforce limit cap
        actual_limit = min(limit, 2000)
        
        # Check cache first
        cached_result = cache.get(form_id, field_keys, filter_string, actual_limit)
        if cached_result is not None:
            logger.info(f"Cache hit for query: form_id={form_id}")
            audit.log_query(
                form_id=form_id,
                filter_string=filter_string,
                result_count=len(cached_result.get("data", [])),
                user_id=user_id or None,
                session_id=session_id or None,
                cached=True,
            )
            return cached_result
        
        logger.info(f"Querying ERP: form_id={form_id}, limit={actual_limit}")
        
        result = client.execute_bill_query(
            form_id=form_id,
            field_keys=field_keys,
            filter_string=filter_string if filter_string else None,
            limit=actual_limit,
        )
        
        # Result is a 2D array: [[field1, field2, ...], ...]
        # Parse field keys for response
        fields = field_keys.split(",")
        
        # Convert to list of dicts for readability
        data = []
        if isinstance(result, list):
            for row in result[:actual_limit]:
                if isinstance(row, list) and len(row) == len(fields):
                    data.append(dict(zip(fields, row)))
        
        # 记录审计日志
        audit.log_query(
            form_id=form_id,
            filter_string=filter_string,
            result_count=len(data),
            user_id=user_id or None,
            session_id=session_id or None,
        )
        
        result_dict = {
            "success": True,
            "form_id": form_id,
            "count": len(data),
            "has_more": len(result) >= actual_limit if isinstance(result, list) else False,
            "data": data,
        }
        
        # Cache the result
        cache.set(form_id, field_keys, result_dict, filter_string, actual_limit)
        
        return result_dict
        
    except Exception as e:
        logger.error(f"Query failed: {e}")
        audit.log_operation(
            operation="query",
            tool_name="query_erp_data",
            parameters={"form_id": form_id},
            success=False,
            error=str(e),
        )
        return {
            "success": False,
            "error": str(e),
            "form_id": form_id,
        }


@mcp.tool()
def create_erp_bill(
    form_id: str,
    json_data: dict,
    dry_run: bool = False,
    user_id: str = "",
    session_id: str = "",
) -> dict:
    """Create and submit a bill in Kingdee ERP.

    WARNING: This is a WRITE operation. Always:
    1. Call query_erp_data first to verify entity FNumbers
    2. Set dry_run=True to preview before actual submission
    3. Get user confirmation before submitting

    Args:
        form_id: Form identifier (e.g., SAL_ORDER, PUR_ORDER)
        json_data: Bill data matching Kingdee API format
        dry_run: If True, validate only without creating
        user_id: User ID for audit logging
        session_id: Session ID for audit logging

    Returns:
        Creation result with bill_no and status
    """
    audit = get_audit_logger()
    try:
        client = get_client()
        
        logger.info(f"Creating bill: form_id={form_id}, dry_run={dry_run}")
        
        if dry_run:
            # Validate by attempting draft (no actual save)
            audit.log_create(
                form_id=form_id,
                dry_run=True,
                user_id=user_id or None,
                session_id=session_id or None,
            )
            return {
                "success": True,
                "message": "Dry run validation passed",
                "preview": json_data,
                "form_id": form_id,
            }
        
        # Step 1: Save the bill
        save_result = client.save(form_id, json_data)
        
        # Check save result
        if not isinstance(save_result, dict):
            audit.log_create(
                form_id=form_id,
                dry_run=False,
                user_id=user_id or None,
                session_id=session_id or None,
                success=False,
                error=f"Invalid save result type: {type(save_result)}",
            )
            return {
                "success": False,
                "error": f"Invalid save result: {save_result}",
                "form_id": form_id,
            }
        
        result_data = save_result.get("Result", {})
        response_status = result_data.get("ResponseStatus", {})
        
        if response_status.get("IsSuccess") == False:
            errors = response_status.get("Errors", [])
            error_msgs = [e.get("Message", "Unknown error") for e in errors]
            audit.log_create(
                form_id=form_id,
                dry_run=False,
                user_id=user_id or None,
                session_id=session_id or None,
                success=False,
                error="; ".join(error_msgs),
            )
            return {
                "success": False,
                "error": "Save failed",
                "details": error_msgs,
                "form_id": form_id,
            }
        
        # Get bill number from result
        bill_no = result_data.get("Number") or json_data.get("FBillNo", "")
        
        # Step 2: Submit the bill (atomic operation)
        submit_data = {"Numbers": [bill_no]} if bill_no else {}
        if submit_data:
            client.submit(form_id, submit_data)
        
        # 记录审计日志
        audit.log_create(
            form_id=form_id,
            bill_no=bill_no,
            dry_run=False,
            user_id=user_id or None,
            session_id=session_id or None,
        )
        
        return {
            "success": True,
            "message": "Bill created and submitted",
            "bill_no": bill_no,
            "form_id": form_id,
            "status": "submitted",
        }
        
    except Exception as e:
        logger.error(f"Create bill failed: {e}")
        audit.log_create(
            form_id=form_id,
            dry_run=dry_run,
            user_id=user_id or None,
            session_id=session_id or None,
            success=False,
            error=str(e),
        )
        return {
            "success": False,
            "error": str(e),
            "form_id": form_id,
        }


@mcp.tool()
def upload_erp_attachment(
    file_path: str,
    form_id: str,
    bill_no: str,
) -> dict:
    """Upload an attachment to a Kingdee ERP bill.

    Args:
        file_path: Path to the file to upload
        form_id: Form identifier
        bill_no: Bill number to attach to

    Returns:
        Upload result with attachment_id
    """
    try:
        client = get_client()
        
        if not os.path.exists(file_path):
            return {
                "success": False,
                "error": f"File not found: {file_path}",
            }
        
        logger.info(f"Uploading attachment: {file_path} to {bill_no}")
        
        result = client.upload_attachment(
            file_path=file_path,
            form_id=form_id,
            bill_no=bill_no,
        )
        
        return {
            "success": True,
            "message": "Attachment uploaded",
            "file_path": file_path,
            "bill_no": bill_no,
            "result": result,
        }
        
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        return {
            "success": False,
            "error": str(e),
            "file_path": file_path,
        }


def main():
    """Run the MCP Server.

    支持两种传输方式：
    - stdio: 本地进程通信（默认）
    - sse: HTTP/SSE 传输，用于远程连接

    通过环境变量 TRANSPORT 或命令行参数指定：
    - TRANSPORT=stdio python -m kingdee_mcp_server.server
    - TRANSPORT=sse python -m kingdee_mcp_server.server
    """
    import sys
    import uvicorn

    transport = os.getenv("TRANSPORT", "stdio").lower()

    # 命令行参数优先
    if len(sys.argv) > 1 and sys.argv[1] in ("stdio", "sse"):
        transport = sys.argv[1]

    if transport == "sse":
        # SSE 传输模式，监听 HTTP 端口
        port = int(os.getenv("PORT", "8080"))
        host = os.getenv("HOST", "0.0.0.0")
        logger.info(f"Starting Kingdee MCP Server (SSE) on {host}:{port}...")
        
        # 使用 uvicorn 直接运行 SSE app
        uvicorn.run(mcp.sse_app(), host=host, port=port)
    else:
        # stdio 传输模式（默认）
        logger.info("Starting Kingdee MCP Server (stdio)...")
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()