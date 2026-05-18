"""Tests for Skills Registry"""

import pytest
from unittest.mock import MagicMock, patch
from pathlib import Path
import tempfile
import yaml

from kingdee_mcp_server.skills import SkillRegistry


class TestSkillRegistry:
    """Tests for SkillRegistry class"""
    
    @pytest.fixture
    def temp_skills_dir(self):
        """Create temporary skills directory"""
        with tempfile.TemporaryDirectory() as tmpdir:
            skills_dir = Path(tmpdir)
            
            # Create test skills file
            skills_data = {
                "skills": {
                    "test_skill": {
                        "name": "测试技能",
                        "description": "测试用技能",
                        "trigger": {
                            "patterns": ["查询.*库存", "物料.*数量"],
                            "entities": ["material_number"]
                        },
                        "steps": [
                            {
                                "action": "query_erp_data",
                                "params": {
                                    "form_id": "BD_MATERIAL",
                                    "filter_string": "FNumber = '{material_number}'"
                                }
                            }
                        ]
                    },
                    "create_order": {
                        "name": "创建订单",
                        "description": "创建销售订单",
                        "trigger": {
                            "patterns": ["创建.*订单", "新建.*订单"],
                            "entities": ["customer_number", "material_number"]
                        },
                        "steps": [
                            {
                                "action": "create_erp_bill",
                                "params": {
                                    "form_id": "SAL_SaleOrder"
                                }
                            }
                        ]
                    }
                }
            }
            
            with open(skills_dir / "test_skills.yaml", "w", encoding="utf-8") as f:
                yaml.dump(skills_data, f)
            
            yield str(skills_dir)
    
    def test_load_skills(self, temp_skills_dir):
        """Test skills loading from directory"""
        registry = SkillRegistry(temp_skills_dir)
        
        assert len(registry.skills) == 2
        assert "test_skill" in registry.skills
        assert "create_order" in registry.skills
    
    def test_match_skill_pattern(self, temp_skills_dir):
        """Test skill matching by pattern"""
        registry = SkillRegistry(temp_skills_dir)
        
        # Should match test_skill
        skill_id, params = registry.match_skill("查询物料 M001 的库存")
        assert skill_id == "test_skill"
        assert params.get("material_number") == "M001"
    
    def test_match_skill_create_order(self, temp_skills_dir):
        """Test create order skill matching"""
        registry = SkillRegistry(temp_skills_dir)
        
        # Pattern "创建.*订单" should match "创建销售订单"
        skill_id, params = registry.match_skill("创建销售订单")
        assert skill_id == "create_order"
    
    def test_no_match(self, temp_skills_dir):
        """Test no skill match"""
        registry = SkillRegistry(temp_skills_dir)
        
        skill_id, params = registry.match_skill("今天天气怎么样")
        assert skill_id is None
        assert params == {}
    
    def test_get_skill(self, temp_skills_dir):
        """Test getting skill by ID"""
        registry = SkillRegistry(temp_skills_dir)
        
        skill = registry.get_skill("test_skill")
        assert skill is not None
        assert skill["name"] == "测试技能"
    
    def test_list_skills(self, temp_skills_dir):
        """Test listing all skills"""
        registry = SkillRegistry(temp_skills_dir)
        
        skills = registry.list_skills()
        assert len(skills) == 2
        assert any(s["id"] == "test_skill" for s in skills)
    
    def test_execute_skill(self, temp_skills_dir):
        """Test skill execution"""
        registry = SkillRegistry(temp_skills_dir)
        
        # Mock action handlers
        mock_query = MagicMock(return_value={"success": True, "data": []})
        action_handlers = {
            "query_erp_data": mock_query,
            "create_erp_bill": MagicMock(return_value={"success": True})
        }
        
        result = registry.execute(
            "test_skill",
            {"material_number": "M001"},
            action_handlers
        )
        
        assert result["success"] is True
        assert result["skill"] == "test_skill"
        mock_query.assert_called_once()
    
    def test_resolve_params(self, temp_skills_dir):
        """Test parameter resolution"""
        registry = SkillRegistry(temp_skills_dir)
        
        template = "FNumber = '{material_number}' AND FName = '{customer_name}'"
        context = {"material_number": "M001", "customer_name": "测试客户"}
        
        resolved = registry._resolve_params(template, context)
        assert resolved == "FNumber = 'M001' AND FName = '测试客户'"
    
    def test_execute_skill_not_found(self, temp_skills_dir):
        """Test executing non-existent skill"""
        registry = SkillRegistry(temp_skills_dir)
        
        result = registry.execute(
            "non_existent",
            {},
            {}
        )
        
        assert result["success"] is False
        assert "not found" in result["error"]
    
    def test_execute_skill_missing_handler(self, temp_skills_dir):
        """Test skill execution with missing action handler - should fail loudly"""
        registry = SkillRegistry(temp_skills_dir)
        
        # Provide empty handlers - action will not be found
        result = registry.execute(
            "test_skill",
            {"material_number": "M001"},
            {}  # No handlers
        )
        
        # Should fail loudly, not silently skip (规则 12)
        assert result["success"] is False
        assert "Action handler not found" in result["error"]
