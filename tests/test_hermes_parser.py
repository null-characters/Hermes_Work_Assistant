"""
测试 Hermes 输出解析器 - 验证 response 类型事件正确识别
"""

import sys
import re
from pathlib import Path

# 添加 hermes-bridge 路径
_hermes_path = Path(__file__).parent.parent / "services" / "hermes-bridge"
if str(_hermes_path) not in sys.path:
    sys.path.insert(0, str(_hermes_path))

from app.services.hermes_client import HermesClient


def test_parse_response():
    """测试解析器正确识别 response 内容"""
    client = HermesClient()

    # 测试用例：(输入行, 期望类型, 期望内容包含)
    test_cases = [
        # 英文响应
        ("    OK", "response", "OK"),
        ("    Hello World", "response", "Hello World"),
        # 中文响应
        ("    这是嵌入式开发中关于ADC性能调优的实用经验总结。", "response", "ADC"),
        ("    这个文件是关于ADC测试的技术文档。", "response", "ADC"),
        # 多行响应中的某一行
        ("    6. PWM频率约束：定时器PWM周期必须大于ADC理论完整采集时间", "response", "PWM"),
        # 不应该被识别为 response 的行（这些是工具行）
        ("    ┊ 🔎 preparing search_files…", "tool", "search_files"),  # 工具准备行
        ("    $ ls -la 0.5s", "tool", "ls"),  # 命令行
        ("    Resume this session with:", None, None),  # 会话信息
        ("    Session:        20260515_084010_0179be", None, None),  # 会话信息
        ("    Duration:       33s", None, None),  # 会话信息
        ("    Messages:       4 (1 user, 2 tool calls)", None, None),  # 会话信息
        ("    08:40:43 - tools.terminal_tool - INFO - Cleaned 1 environments", None, None),  # 日志行
    ]

    passed = 0
    failed = 0

    for line, expected_type, expected_content in test_cases:
        result = client._parse_hermes_output(line)
        actual_type = result["type"] if result else None

        if actual_type == expected_type:
            if expected_content and result:
                if expected_content in result.get("content", ""):
                    passed += 1
                    print(f"  ✅ PASS: '{line[:50]}' → {actual_type}")
                else:
                    failed += 1
                    print(f"  ❌ FAIL: '{line[:50]}' → content mismatch: {result.get('content', '')}")
            else:
                passed += 1
                print(f"  ✅ PASS: '{line[:50]}' → {actual_type}")
        else:
            failed += 1
            print(f"  ❌ FAIL: '{line[:50]}' → expected {expected_type}, got {actual_type}")

    print(f"\n结果: {passed} passed, {failed} failed")
    return failed == 0


def test_full_hermes_output():
    """测试完整 Hermes 输出的解析"""
    client = HermesClient()

    # 模拟 Hermes Agent 的实际输出
    raw_output = """Query: 回复OK两个字符，不要输出其他内容
Initializing agent...
────────────────────────────────────────

╭─ ⚕ Hermes ───────────────────────────────────────────╮
    OK
╰──────────────────────────────────────────────────────╯

Resume this session with:
  hermes --resume 20260515_085935_5a7daa
Session:        20260515_085935_5a7daa
Duration:       5s
Messages:       2 (1 user, 0 tool calls)"""

    response_found = False
    response_content = ""

    for line in raw_output.split('\n'):
        result = client._parse_hermes_output(line)
        if result and result["type"] == "response":
            response_found = True
            response_content = result["content"]

    if response_found and "OK" in response_content:
        print(f"  ✅ PASS: 完整输出解析找到 response: {response_content}")
        return True
    else:
        print(f"  ❌ FAIL: 完整输出解析未找到 response (found={response_found}, content={response_content})")
        return False


if __name__ == "__main__":
    print("=== 测试1: 逐行解析 ===")
    r1 = test_parse_response()
    print()
    print("=== 测试2: 完整输出解析 ===")
    r2 = test_full_hermes_output()

    if r1 and r2:
        print("\n✅ 所有测试通过")
        sys.exit(0)
    else:
        print("\n❌ 测试失败")
        sys.exit(1)
