"""性能测试 - 验证 P95 延迟 < 3s"""

import time
import statistics
from unittest.mock import MagicMock, patch
import pytest


class TestToolLatency:
    """测试 Tool 调用延迟"""
    
    @patch("kingdee_mcp_server.server.get_client")
    def test_query_latency_p95(self, mock_get_client):
        """验证 query_erp_data P95 延迟 < 3s"""
        # Mock 客户端
        mock_client = MagicMock()
        mock_client.execute_bill_query.return_value = [
            ["M001", "Material A", 1001],
        ] * 100  # 100 条记录
        mock_get_client.return_value = mock_client
        
        from kingdee_mcp_server.server import query_erp_data
        
        # 运行 100 次，收集延迟数据
        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            result = query_erp_data(
                form_id="BD_MATERIAL",
                field_keys="FNumber,FName,FId",
                limit=100,
            )
            end = time.perf_counter()
            latencies.append(end - start)
        
        # 计算统计数据
        avg_latency = statistics.mean(latencies)
        p50_latency = statistics.median(latencies)
        p95_latency = sorted(latencies)[int(len(latencies) * 0.95)]
        
        print(f"\nQuery Latency Stats:")
        print(f"  Avg: {avg_latency*1000:.2f}ms")
        print(f"  P50: {p50_latency*1000:.2f}ms")
        print(f"  P95: {p95_latency*1000:.2f}ms")
        
        # 验证 P95 < 3s (3000ms)
        assert p95_latency < 3.0, f"P95 latency {p95_latency}s exceeds 3s threshold"
    
    @patch("kingdee_mcp_server.server.get_client")
    def test_create_latency_p95(self, mock_get_client):
        """验证 create_erp_bill P95 延迟 < 3s"""
        # Mock 客户端
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
        
        # 运行 100 次，收集延迟数据
        latencies = []
        for _ in range(100):
            start = time.perf_counter()
            result = create_erp_bill(
                form_id="SAL_ORDER",
                json_data={"FBillNo": "SO2026001"},
            )
            end = time.perf_counter()
            latencies.append(end - start)
        
        # 计算统计数据
        avg_latency = statistics.mean(latencies)
        p50_latency = statistics.median(latencies)
        p95_latency = sorted(latencies)[int(len(latencies) * 0.95)]
        
        print(f"\nCreate Latency Stats:")
        print(f"  Avg: {avg_latency*1000:.2f}ms")
        print(f"  P50: {p50_latency*1000:.2f}ms")
        print(f"  P95: {p95_latency*1000:.2f}ms")
        
        # 验证 P95 < 3s (3000ms)
        assert p95_latency < 3.0, f"P95 latency {p95_latency}s exceeds 3s threshold"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])