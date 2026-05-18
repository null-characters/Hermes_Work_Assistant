"""MCP Server entry point for Kingdee ERP integration."""

import json
import logging
import os
from typing import Optional

from mcp.server.fastmcp import FastMCP
from dotenv import load_dotenv

from .kingdee_client import get_client, reset_client
from .audit_logger import get_audit_logger

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
        form_id: Form identifier (e.g., BD_MATERIAL, BD_CUSTOMER, BD_STOCK)
        filter_string: Filter condition (e.g., "FNumber like '%M001%'")
        field_keys: Comma-separated fields (e.g., "FNumber,FName,FId")
        limit: Max records (default 100, max 2000)
        user_id: User ID for audit logging
        session_id: Session ID for audit logging

    Returns:
        Query results with data array and has_more flag
    """
    audit = get_audit_logger()
    try:
        client = get_client()
        
        # Default field_keys if not provided
        if not field_keys:
            field_keys = "FNumber,FName,FId"
        
        # Enforce limit cap
        actual_limit = min(limit, 2000)
        
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
        
        return {
            "success": True,
            "form_id": form_id,
            "count": len(data),
            "has_more": len(result) >= actual_limit if isinstance(result, list) else False,
            "data": data,
        }
        
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
        if isinstance(save_result, dict):
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
        
        return {
            "success": True,
            "message": "Bill created",
            "form_id": form_id,
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
    """Run the MCP Server."""
    logger.info("Starting Kingdee MCP Server...")
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()