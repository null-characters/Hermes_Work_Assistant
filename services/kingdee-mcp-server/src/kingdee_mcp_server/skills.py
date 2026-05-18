"""Skills Registry - ERP 操作技能注册与调用"""

import re
import yaml
import logging
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)


class SkillRegistry:
    """Skills 注册与调用管理器"""
    
    def __init__(self, skills_path: str = "./config/skills"):
        self.skills_path = Path(skills_path)
        self.skills: dict[str, dict] = {}
        self._load_skills()
    
    def _load_skills(self) -> None:
        """加载所有 Skills 配置"""
        if not self.skills_path.exists():
            logger.warning(f"Skills path not found: {self.skills_path}")
            return
        
        for yaml_file in self.skills_path.glob("*.yaml"):
            try:
                with open(yaml_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
                    if data and "skills" in data:
                        self.skills.update(data["skills"])
                        logger.info(f"Loaded {len(data['skills'])} skills from {yaml_file}")
            except Exception as e:
                logger.error(f"Failed to load skills from {yaml_file}: {e}")
    
    def match_skill(self, user_input: str) -> tuple[str | None, dict[str, str]]:
        """根据用户输入匹配 Skill
        
        Returns:
            (skill_id, extracted_params) 或 (None, {})
        """
        user_input_lower = user_input.lower()
        
        for skill_id, skill in self.skills.items():
            trigger = skill.get("trigger", {})
            patterns = trigger.get("patterns", [])
            
            # 检查是否匹配任何模式
            for pattern in patterns:
                # 转换简单模式为正则
                regex_pattern = pattern.replace(".*", "(.+?)")
                if re.search(regex_pattern, user_input_lower):
                    # 提取实体参数
                    params = self._extract_entities(user_input, trigger.get("entities", []))
                    return skill_id, params
        
        return None, {}
    
    def _extract_entities(self, text: str, entities: list[str]) -> dict[str, str]:
        """从文本中提取实体参数"""
        params = {}
        
        # 简单的实体提取规则
        entity_patterns = {
            "material_number": r"物料\s*([A-Za-z0-9\-]+)",
            "customer_number": r"客户\s*([A-Za-z0-9\-]+)",
            "customer_name": r"客户\s*(\S+)",
            "warehouse": r"仓库\s*(\S+)",
            "quantity": r"(\d+)\s*(?:个|件|台|箱)",
            "delivery_date": r"(\d{4}[-/]\d{1,2}[-/]\d{1,2})",
        }
        
        for entity in entities:
            if entity in entity_patterns:
                match = re.search(entity_patterns[entity], text)
                if match:
                    params[entity] = match.group(1)
        
        return params
    
    def get_skill(self, skill_id: str) -> dict | None:
        """获取指定 Skill 配置"""
        return self.skills.get(skill_id)
    
    def list_skills(self) -> list[dict]:
        """列出所有 Skills"""
        return [
            {"id": skill_id, "name": skill.get("name"), "description": skill.get("description")}
            for skill_id, skill in self.skills.items()
        ]
    
    def execute(
        self, 
        skill_id: str, 
        params: dict[str, Any],
        action_handlers: dict[str, Callable]
    ) -> dict[str, Any]:
        """执行 Skill
        
        Args:
            skill_id: Skill ID
            params: 参数
            action_handlers: 动作处理器映射
        
        Returns:
            执行结果
        """
        skill = self.get_skill(skill_id)
        if not skill:
            return {"success": False, "error": f"Skill not found: {skill_id}"}
        
        results = []
        steps = skill.get("steps", [])
        
        for step in steps:
            action = step.get("action")
            step_params = step.get("params", {})
            
            # 替换参数占位符
            resolved_params = self._resolve_params(step_params, params)
            
            if action in action_handlers:
                try:
                    result = action_handlers[action](**resolved_params)
                    results.append({"step": step.get("description", action), "result": result})
                except Exception as e:
                    logger.error(f"Skill step failed: {action} - {e}")
                    return {"success": False, "error": str(e), "skill": skill_id}
            else:
                logger.error(f"Action handler not found: {action}")
                return {"success": False, "error": f"Action handler not found: {action}", "skill": skill_id}
        
        return {
            "success": True,
            "skill": skill_id,
            "results": results
        }
    
    def _resolve_params(self, template: Any, context: dict[str, Any]) -> Any:
        """递归解析参数模板"""
        if isinstance(template, str):
            # 替换 {param} 占位符
            for key, value in context.items():
                template = template.replace(f"{{{key}}}", str(value))
            return template
        elif isinstance(template, dict):
            return {k: self._resolve_params(v, context) for k, v in template.items()}
        elif isinstance(template, list):
            return [self._resolve_params(item, context) for item in template]
        return template


# 全局 Skills 注册表
_skills_registry: SkillRegistry | None = None


def get_skills_registry() -> SkillRegistry:
    """获取全局 Skills 注册表"""
    global _skills_registry
    if _skills_registry is None:
        import os
        skills_path = os.getenv("SKILLS_PATH", "./config/skills")
        _skills_registry = SkillRegistry(skills_path)
    return _skills_registry
