# 操控模块
from backend.control.control import Control
from backend.control.simple_control import SimpleControl
from backend.control.control_factory import ControlFactory
# ControlManager 不在 __init__.py 中导入，避免循环导入
# 需要使用时直接从 backend.control.control_manager 导入
from backend.control.event_handler import EventHandler
from backend.control.simple_event_handler import (
    SimpleDrawCardEventHandler, SimplePlayCardEventHandler, SimpleHPChangeEventHandler,
    SimpleDiscardCardEventHandler, SimpleEquipChangeEventHandler, SimpleDeathEventHandler
)
from backend.control.human_control import HumanControl
from backend.control.adaptive_ai_control import AdaptiveAIControl, AIDifficulty
from backend.control.human_control import HumanControl
from backend.control.adaptive_ai_control import AdaptiveAIControl, AIDifficulty