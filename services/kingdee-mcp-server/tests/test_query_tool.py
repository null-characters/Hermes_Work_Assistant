"""Tests for query_erp_data tool."""

import pytest
from unittest.mock import patch, MagicMock


class TestQueryErpData:
    """Test cases for query_erp_data tool."""
    
    @patch("kingdee_mcp_server.server.get_client")
    def test_query_success(self, mock_get_client):
        """Test successful query returns data."""
        # Arrange
        mock_client = MagicMock()
        mock_client.execute_bill_query.return_value = [
            ["M001", "Material A", 1001],
            ["M002", "Material B", 1002],
        ]
        mock_get_client.return_value = mock_client
        
        from kingdee_mcp_server.server import query_erp_data
        
        # Act
        result = query_erp_data(
            form_id="BD_MATERIAL",
            field_keys="FNumber,FName,FId",
            limit=100,
        )
        
        # Assert
        assert result["success"] is True
        assert result["form_id"] == "BD_MATERIAL"
        assert result["count"] == 2
        assert result["has_more"] is False
        assert len(result["data"]) == 2
        assert result["data"][0]["FNumber"] == "M001"
        
        # Verify client was called correctly
        mock_client.execute_bill_query.assert_called_once_with(
            form_id="BD_MATERIAL",
            field_keys="FNumber,FName,FId",
            filter_string=None,
            limit=100,
        )
    
    @patch("kingdee_mcp_server.server.get_client")
    def test_query_with_filter(self, mock_get_client):
        """Test query with filter condition."""
        mock_client = MagicMock()
        mock_client.execute_bill_query.return_value = [
            ["M001", "Material A"],  # 2 fields matching field_keys
        ]
        mock_get_client.return_value = mock_client
        
        from kingdee_mcp_server.server import query_erp_data
        
        result = query_erp_data(
            form_id="BD_MATERIAL",
            filter_string="FNumber like '%M001%'",
            field_keys="FNumber,FName",
        )
        
        assert result["success"] is True
        assert result["count"] == 1
        
        mock_client.execute_bill_query.assert_called_once_with(
            form_id="BD_MATERIAL",
            field_keys="FNumber,FName",
            filter_string="FNumber like '%M001%'",
            limit=100,
        )
    
    @patch("kingdee_mcp_server.server.get_client")
    def test_query_limit_cap(self, mock_get_client):
        """Test query limit is capped at 2000."""
        mock_client = MagicMock()
        mock_client.execute_bill_query.return_value = []
        mock_get_client.return_value = mock_client
        
        from kingdee_mcp_server.server import query_erp_data
        
        result = query_erp_data(
            form_id="BD_MATERIAL",
            limit=5000,  # Exceeds cap
        )
        
        # Should be capped at 2000
        mock_client.execute_bill_query.assert_called_once()
        call_args = mock_client.execute_bill_query.call_args
        assert call_args.kwargs["limit"] == 2000
    
    @patch("kingdee_mcp_server.server.get_client")
    def test_query_error_handling(self, mock_get_client):
        """Test query handles errors gracefully."""
        mock_client = MagicMock()
        mock_client.execute_bill_query.side_effect = Exception("Connection failed")
        mock_get_client.return_value = mock_client
        
        from kingdee_mcp_server.server import query_erp_data
        
        result = query_erp_data(form_id="BD_MATERIAL")
        
        assert result["success"] is False
        assert "Connection failed" in result["error"]
    
    @patch("kingdee_mcp_server.server.get_client")
    def test_query_has_more_flag(self, mock_get_client):
        """Test has_more flag when results reach limit."""
        mock_client = MagicMock()
        # Return exactly limit results
        mock_client.execute_bill_query.return_value = [
            ["M001", "Material A", 1001],
        ] * 100
        mock_get_client.return_value = mock_client
        
        from kingdee_mcp_server.server import query_erp_data
        
        result = query_erp_data(form_id="BD_MATERIAL", limit=100)
        
        assert result["has_more"] is True