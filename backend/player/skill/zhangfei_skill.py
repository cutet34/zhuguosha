from typing import Any, Dict


class ZhangFeiSkill:
    """张飞：咆哮（锁定技，被动规则修正：杀次数不受限制）"""

    name: str = "咆哮"
    is_locked: bool = True
    need_ask: bool = False
    # 中文注释：兼容旧实现（与现有测试用例）：出【杀】后重置 sha_used_this_turn 标记。
    reset_sha_used_flag_after_sha: bool = True

    def can_activate(self, player, context: Dict[str, Any]) -> bool:
        """判断技能是否需要走“显式触发”流程。

        中文说明：咆哮属于被动规则修正，不需要通过 trigger_skills 显式触发。

        Args:
            player: 玩家对象。
            context: 上下文字典。

        Returns:
            bool: False（不走显式触发）。
        """
        return False

    def activate(self, player, context: Dict[str, Any]) -> None:
        """显式触发时的执行入口（本技能不使用）。

        Args:
            player: 玩家对象。
            context: 上下文字典。

        Returns:
            None
        """
        return None

    def modify_sha_limit(self, player, current_limit: int, context: Dict[str, Any]) -> int:
        """修改【杀】的使用次数上限。

        Args:
            player: 玩家对象。
            current_limit: 当前计算出的【杀】次数上限。
            context: 上下文字典。

        Returns:
            int: 修改后的【杀】次数上限（无限，用极大值表示）。
        """
        # 中文注释：用极大值表达“无限”
        return 10**9
