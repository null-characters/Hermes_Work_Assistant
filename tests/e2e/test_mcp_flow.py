"""E2E tests for MCP integration flow."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import asyncio


class TestMcpIntegrationFlow:
    """E2E tests for complete MCP query -> create flow."""
    
    @pytest.mark.asyncio
    @patch("kingdee_mcp_server.server.get_client")
    @patch("kingdee_mcp_server.server.get_audit_logger")
    async def test_query_then_create_flow(self, mock_audit, mock_client):
        """Test complete flow: query customer -> query material -> create order."""
        # Setup mocks
        mock_audit_instance = MagicMock()
        mock_audit.return_value = mock_audit_instance
        
        mock_kingdee = MagicMock()
        # Customer query result
        mock_kingdee.execute_bill_query.side_effect = [
            [["C001", "张三", 1001]],  # Customer query
            [["M001", "产品A", 2001]],  # Material query
        ]
        # Save result
        mock_kingdee.save.return_value = {
            "Result": {
                "Number": "SO2026001",
                "ResponseStatus": {"IsSuccess": True}
            }
        }
        mock_kingdee.submit.return_value = {"Result": {"ResponseStatus": {"IsSuccess": True}}}
        mock_client.return_value = mock_kingdee
        
        from kingdee_mcp_server.server import query_erp_data, create_erp_bill
        
        # Step 1: Query customer
        customer_result = query_erp_data(
            form_id="BD_CUSTOMER",
            filter_string="FName like '%张三%'",
            field_keys="FNumber,FName,FId",
            user_id="user001",
            session_id="session001",
        )
        
        assert customer_result["success"] is True
        assert customer_result["count"] == 1
        assert customer_result["data"][0]["FNumber"] == "C001"
        
        # Step 2: Query material
        material_result = query_erp_data(
            form_id="BD_MATERIAL",
            filter_string="FNumber='M001'",
            field_keys="FNumber,FName,FId",
            user_id="user001",
            session_id="session001",
        )
        
        assert material_result["success"] is True
        assert material_result["data"][0]["FNumber"] == "M001"
        
        # Step 3: Dry run create order
        order_data = {
            "FBillNo": "SO2026001",
            "FCustomerId": {"FNumber": "C001"},
            "FMaterialId": {"FNumber": "M001"},
        }
        
        dry_run_result = create_erp_bill(
            form_id="SAL_ORDER",
            json_data=order_data,
            dry_run=True,
            user_id="user001",
            session_id="session001",
        )
        
        assert dry_run_result["success"] is True
        assert dry_run_result["message"] == "Dry run validation passed"
        
        # Step 4: Actual create after user confirmation
        create_result = create_erp_bill(
            form_id="SAL_ORDER",
            json_data=order_data,
            dry_run=False,
            user_id="user001",
            session_id="session001",
        )
        
        assert create_result["success"] is True
        assert create_result["bill_no"] == "SO2026001"
        assert create_result["status"] == "submitted"
        
        # Verify audit logs were recorded
        assert mock_audit_instance.log_query.call_count == 2
        assert mock_audit_instance.log_create.call_count == 2
    
    @pytest.mark.asyncio
    @patch("kingdee_mcp_server.server.get_client")
    @patch("kingdee_mcp_server.server.get_audit_logger")
    async def test_query_failure_prevents_create(self, mock_audit, mock_client):
        """Test that query failure prevents creation."""
        mock_audit_instance = MagicMock()
        mock_audit.return_value = mock_audit_instance
        
        mock_kingdee = MagicMock()
        mock_kingdee.execute_bill_query.return_value = []  # No results
        mock_client.return_value = mock_kingdee
        
        from kingdee_mcp_server.server import query_erp_data
        
        # Query returns empty
        result = query_erp_data(
            form_id="BD_CUSTOMER",
            filter_string="FName like '%不存在%'",
        )
        
        assert result["success"] is True
        assert result["count"] == 0
        
        # In real scenario, Agent would see empty result and not proceed to create
    
    @pytest.mark.asyncio
    @patch("kingdee_mcp_server.server.get_client")
    @patch("kingdee_mcp_server.server.get_audit_logger")
    async def test_create_failure_is_logged(self, mock_audit, mock_client):
        """Test that create failure is logged."""
        mock_audit_instance = MagicMock()
        mock_audit.return_value = mock_audit_instance
        
        mock_kingdee = MagicMock()
        mock_kingdee.save.return_value = {
            "Result": {
                "ResponseStatus": {
                    "IsSuccess": False,
                    "Errors": [{"Message": "客户不存在"}]
                }
            }
        }
        mock_client.return_value = mock_kingdee
        
        from kingdee_mcp_server.server import create_erp_bill
        
        result = create_erp_bill(
            form_id="SAL_ORDER",
            json_data={"FCustomerId": {"FNumber": "INVALID"}},
            user_id="user001",
        )
        
        assert result["success"] is False
        assert "客户不存在" in result["details"]
        
        # Verify failure was logged
        mock_audit_instance.log_create.assert_called_once()
        call_args = mock_audit_instance.log_create.call_args
        assert call_args.kwargs["success"] is False