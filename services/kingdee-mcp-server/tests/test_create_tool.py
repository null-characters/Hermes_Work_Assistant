"""Tests for create_erp_bill tool."""

import pytest
from unittest.mock import patch, MagicMock, call


class TestCreateErpBill:
    """Test cases for create_erp_bill tool."""
    
    @patch("kingdee_mcp_server.server.get_client")
    def test_create_success(self, mock_get_client):
        """Test successful bill creation."""
        # Arrange
        mock_client = MagicMock()
        mock_client.save.return_value = {
            "Result": {
                "Number": "SO2026001",
                "ResponseStatus": {"IsSuccess": True}
            }
        }
        mock_client.submit.return_value = {"Result": {"ResponseStatus": {"IsSuccess": True}}}
        mock_get_client.return_value = mock_client
        
        from kingdee_mcp_server.server import create_erp_bill
        
        # Act
        result = create_erp_bill(
            form_id="SAL_ORDER",
            json_data={"FBillNo": "SO2026001", "FCustomerId": {"FNumber": "C001"}},
        )
        
        # Assert
        assert result["success"] is True
        assert result["bill_no"] == "SO2026001"
        assert result["status"] == "submitted"
        
        # Verify save and submit were called
        mock_client.save.assert_called_once()
        mock_client.submit.assert_called_once()
    
    @patch("kingdee_mcp_server.server.get_client")
    def test_create_dry_run(self, mock_get_client):
        """Test dry run mode does not create bill."""
        mock_client = MagicMock()
        mock_get_client.return_value = mock_client
        
        from kingdee_mcp_server.server import create_erp_bill
        
        result = create_erp_bill(
            form_id="SAL_ORDER",
            json_data={"FCustomerId": {"FNumber": "C001"}},
            dry_run=True,
        )
        
        assert result["success"] is True
        assert result["message"] == "Dry run validation passed"
        assert result["preview"] is not None
        
        # Verify no save was called
        mock_client.save.assert_not_called()
    
    @patch("kingdee_mcp_server.server.get_client")
    def test_create_save_failure(self, mock_get_client):
        """Test handling of save failure."""
        mock_client = MagicMock()
        mock_client.save.return_value = {
            "Result": {
                "ResponseStatus": {
                    "IsSuccess": False,
                    "Errors": [{"Message": "Customer not found"}]
                }
            }
        }
        mock_get_client.return_value = mock_client
        
        from kingdee_mcp_server.server import create_erp_bill
        
        result = create_erp_bill(
            form_id="SAL_ORDER",
            json_data={"FCustomerId": {"FNumber": "INVALID"}},
        )
        
        assert result["success"] is False
        assert "Customer not found" in result["details"]
        
        # Verify submit was not called after save failure
        mock_client.submit.assert_not_called()
    
    @patch("kingdee_mcp_server.server.get_client")
    def test_create_exception_handling(self, mock_get_client):
        """Test exception handling during creation."""
        mock_client = MagicMock()
        mock_client.save.side_effect = Exception("Network error")
        mock_get_client.return_value = mock_client
        
        from kingdee_mcp_server.server import create_erp_bill
        
        result = create_erp_bill(
            form_id="SAL_ORDER",
            json_data={},
        )
        
        assert result["success"] is False
        assert "Network error" in result["error"]
    
    @patch("kingdee_mcp_server.server.get_audit_logger")
    @patch("kingdee_mcp_server.server.get_client")
    def test_create_audit_logging(self, mock_get_client, mock_get_audit):
        """Test that audit log is called for create operations."""
        mock_client = MagicMock()
        mock_client.save.return_value = {
            "Result": {
                "Number": "SO2026001",
                "ResponseStatus": {"IsSuccess": True}
            }
        }
        mock_client.submit.return_value = {}
        mock_get_client.return_value = mock_client
        
        mock_audit = MagicMock()
        mock_get_audit.return_value = mock_audit
        
        from kingdee_mcp_server.server import create_erp_bill
        
        result = create_erp_bill(
            form_id="SAL_ORDER",
            json_data={"FBillNo": "SO2026001"},
            user_id="user123",
            session_id="session456",
        )
        
        # Verify audit log was called
        mock_audit.log_create.assert_called()
        call_args = mock_audit.log_create.call_args
        assert call_args.kwargs["form_id"] == "SAL_ORDER"
        assert call_args.kwargs["bill_no"] == "SO2026001"
        assert call_args.kwargs["user_id"] == "user123"
        # success defaults to True, may not be in kwargs
        assert call_args.kwargs.get("success", True) is True
    
    @patch("kingdee_mcp_server.server.get_audit_logger")
    @patch("kingdee_mcp_server.server.get_client")
    def test_create_invalid_save_result(self, mock_get_client, mock_get_audit):
        """Test handling of invalid save result type - should fail loudly (规则 12)."""
        mock_client = MagicMock()
        # Return non-dict result - should cause failure
        mock_client.save.return_value = "invalid_result"
        mock_get_client.return_value = mock_client
        
        mock_audit = MagicMock()
        mock_get_audit.return_value = mock_audit
        
        from kingdee_mcp_server.server import create_erp_bill
        
        result = create_erp_bill(
            form_id="SAL_ORDER",
            json_data={"FBillNo": "SO2026001"},
        )
        
        # Should fail loudly, not return None (规则 12: 大声失败)
        assert result["success"] is False
        assert "Invalid save result" in result["error"]