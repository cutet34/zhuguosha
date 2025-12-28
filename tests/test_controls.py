"""Control 系统测试：AI 控制与玩家（Human）控制。

本文件覆盖两类控制器：
1) AdaptiveAIControl / BasicAIControl：验证策略选择逻辑与难度分发。
2) HumanControl：验证与前端通信事件（InputRequestEvent/InputResponseEvent）的交互闭环。

说明：
HumanControl 在无前端通信对象时会退化到 console input()，测试环境必须走事件模式。
本项目默认全局 communicator 已初始化，因此测试可通过读取 backend->frontend 队列并注入响应事件来驱动。
"""

from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional

import pytest

from backend.card.card import Card
from backend.control.adaptive_ai_control import AdaptiveAIControl
from backend.control.basic_ai_control import BasicAIControl
from backend.control.hard_ai_control import HardAIControl
from backend.control.ai_difficulty import AIDifficulty
from backend.control.control import Control
from backend.control.human_control import HumanControl
from backend.control.simple_control import SimpleControl
from backend.control.rl.rl_control import ExpertAIControl
from backend.control.rl.action_space import PASS_ACTION
from communicator.comm_event import InputRequestEvent, InputResponseEvent
from communicator.communicator import communicator
from config.enums import CardName, CardSuit, TargetType


def _drain_communicator_queues() -> None:
    """清空 communicator 的前后端队列，避免测试间相互干扰。

    Args:
        None

    Returns:
        None
    """
    # backend -> frontend
    while communicator.receive_from_backend() is not None:
        pass
    # frontend -> backend
    while communicator.receive_from_frontend() is not None:
        pass


@pytest.fixture(autouse=True)
def _isolate_comm_queues() -> None:
    """自动隔离通信队列（每个测试前后都清空）。

    Args:
        None

    Returns:
        None
    """
    _drain_communicator_queues()
    yield
    _drain_communicator_queues()


def _run_in_thread(fn, *args, **kwargs) -> Dict[str, Any]:
    """在子线程中执行函数并收集返回值。

    Args:
        fn: 需要在子线程执行的函数。
        *args: 位置参数。
        **kwargs: 关键字参数。

    Returns:
        Dict[str, Any]: 包含键 "result" 的字典。
    """
    box: Dict[str, Any] = {}

    def _target() -> None:
        box["result"] = fn(*args, **kwargs)

    t = threading.Thread(target=_target, daemon=True)
    t.start()
    box["thread"] = t
    return box


def _await_request(timeout: float = 1.0) -> InputRequestEvent:
    """从 backend->frontend 队列中取出一条 InputRequestEvent。

    Args:
        timeout: 最大等待秒数。

    Returns:
        InputRequestEvent: 取到的请求事件。

    Raises:
        AssertionError: 超时或事件类型不匹配。
    """
    evt = communicator.get_from_backend(timeout=timeout)
    assert evt is not None, "未收到 InputRequestEvent（可能卡在 console 模式或未发出请求）"
    assert isinstance(evt, InputRequestEvent)
    return evt


def _join_thread(box: Dict[str, Any], timeout: float = 1.0) -> Any:
    """等待子线程结束并返回其结果。

    Args:
        box: _run_in_thread 返回的盒子。
        timeout: 最大等待秒数。

    Returns:
        Any: 子线程函数的返回值。
    """
    t: threading.Thread = box["thread"]
    t.join(timeout=timeout)
    assert not t.is_alive(), "子线程未退出（HumanControl 可能未收到响应事件）"
    return box.get("result")


def test_basic_ai_selects_equipment_first() -> None:
    """BasicAIControl：优先选择装备牌。

    Args:
        None

    Returns:
        None
    """
    ai = BasicAIControl(player_id=1)

    cards = [
        Card(CardSuit.HEARTS, 7, CardName.SHA),
        Card(CardSuit.SPADES, 6, CardName.QING_GANG_JIAN),  # 装备
        Card(CardSuit.HEARTS, 2, CardName.SHAN),
    ]
    picked = ai.select_card(cards, available_targets={"all": [2], "attackable": [2]})
    assert picked is cards[1]


def test_basic_ai_prefers_aoe_when_many_targets() -> None:
    """BasicAIControl：目标多时优先选择群体锦囊。

    Args:
        None

    Returns:
        None
    """
    ai = BasicAIControl(player_id=1)

    cards = [
        Card(CardSuit.HEARTS, 8, CardName.NAN_MAN_RU_QIN),
        Card(CardSuit.HEARTS, 7, CardName.SHA),
    ]
    picked = ai.select_card(cards, available_targets={"all": [2, 3], "attackable": [2, 3]})
    assert picked is cards[0]


def test_basic_ai_chooses_sha_when_attackable_exists() -> None:
    """BasicAIControl：存在可攻击目标时优先选择【杀】。

    Args:
        None

    Returns:
        None
    """
    ai = BasicAIControl(player_id=1)

    cards = [
        Card(CardSuit.HEARTS, 7, CardName.SHA),
        Card(CardSuit.HEARTS, 4, CardName.TAO),
    ]
    picked = ai.select_card(cards, available_targets={"attackable": [2], "all": [2]})
    assert picked is cards[0]


def test_basic_ai_select_targets_all_for_aoe() -> None:
    """BasicAIControl：群体牌（TargetType.ALL）应选择所有目标。

    Args:
        None

    Returns:
        None
    """
    ai = BasicAIControl(player_id=1)
    card = Card(CardSuit.HEARTS, 8, CardName.NAN_MAN_RU_QIN)
    assert card.target_type == TargetType.ALL
    targets = ai.select_targets([2, 3], card)
    assert targets == [2, 3]




def test_simple_control_picks_equipment_first() -> None:
    """SimpleControl（用于 EASY）：有装备时应优先装备。

    Args:
        None

    Returns:
        None
    """
    ctrl = SimpleControl(player_id=1)
    cards = [
        Card(CardSuit.SPADES, 6, CardName.QING_GANG_JIAN),
        Card(CardSuit.HEARTS, 7, CardName.SHA),
        Card(CardSuit.HEARTS, 2, CardName.SHAN),
    ]
    picked = ctrl.select_card(cards, available_targets={"all": [2], "attackable": [2]})
    assert picked is cards[0]


def test_hard_ai_prefers_tao_by_value() -> None:
    """HardAIControl（用于 HARD）：在可用时应优先【桃】。

    Args:
        None

    Returns:
        None
    """
    ai = AdaptiveAIControl(player_id=1, difficulty=AIDifficulty.HARD)
    # 提供自己的 hp 信息，避免“满血降权”影响
    ai.sync_state({"self": {"hp": 1, "max_hp": 4}, "players": []})

    tao = Card(CardSuit.HEARTS, 4, CardName.TAO)
    sha = Card(CardSuit.SPADES, 7, CardName.SHA)
    picked = ai.select_card([sha, tao], available_targets={"all": [2], "attackable": [2]})
    assert picked is tao


def test_hard_ai_loyalist_avoids_aoe_when_lord_in_danger() -> None:
    """HARD：忠臣在主公残血且 AOE 可能伤到主公时，应避免 AOE。

    Args:
        None

    Returns:
        None
    """
    ai = HardAIControl(player_id=1)
    # 自己忠臣；主公 1 血且手牌=0 -> 估计会被 AOE 伤到
    ai.sync_state(
        {
            "self": {"player_id": 1, "identity": "忠臣", "hp": 3, "max_hp": 4, "hand_count": 1, "status": "存活"},
            "players": [
                {"player_id": 2, "identity": "主公", "hp": 1, "hand_count": 0, "status": "存活"},
                {"player_id": 3, "identity": "反贼", "hp": 3, "hand_count": 0, "status": "存活"},
            ],
        }
    )

    aoe = Card(CardSuit.HEARTS, 8, CardName.WAN_JIAN_QI_FA)
    sha = Card(CardSuit.SPADES, 7, CardName.SHA)
    picked = ai.select_card([aoe, sha], available_targets={"all": [2, 3], "attackable": [3]})
    assert picked is sha


def test_hard_ai_rebel_prefers_aoe_when_many_enemies() -> None:
    """HARD：反贼在敌人多且 AOE 优势明显时，应优先 AOE。

    Args:
        None

    Returns:
        None
    """
    ai = HardAIControl(player_id=1)
    ai.sync_state(
        {
            "self": {"player_id": 1, "identity": "反贼", "hp": 3, "max_hp": 4, "hand_count": 1, "status": "存活"},
            "players": [
                # 敌人(主公/忠臣/内奸)都手牌=0，估计都会被 AOE 伤到
                {"player_id": 2, "identity": "主公", "hp": 3, "hand_count": 0, "status": "存活"},
                {"player_id": 3, "identity": "忠臣", "hp": 3, "hand_count": 0, "status": "存活"},
                {"player_id": 4, "identity": "内奸", "hp": 3, "hand_count": 0, "status": "存活"},
                # 盟友反贼手牌=1，估计不会被 AOE 伤到
                {"player_id": 5, "identity": "反贼", "hp": 3, "hand_count": 1, "status": "存活"},
            ],
        }
    )

    aoe = Card(CardSuit.HEARTS, 8, CardName.NAN_MAN_RU_QIN)
    sha = Card(CardSuit.SPADES, 7, CardName.SHA)
    picked = ai.select_card([sha, aoe], available_targets={"all": [2, 3, 4, 5], "attackable": [2, 3, 4, 5]})
    assert picked is aoe


def test_expert_ai_uses_qtable_to_choose_non_pass() -> None:
    """ExpertAIControl（用于 EXPERT）：当 Q 表偏好某动作时，应选择对应牌而非 PASS。

    Args:
        None

    Returns:
        None
    """
    ai = AdaptiveAIControl(player_id=1, difficulty=AIDifficulty.EXPERT)
    assert isinstance(ai._delegate, ExpertAIControl)
    # 同步最小状态，并手工给 Q 表一个偏好
    ai.sync_state({})
    delegate: ExpertAIControl = ai._delegate
    state = delegate.encoder.encode(delegate.game_state)
    delegate.q_table.set(state, PASS_ACTION, 0.0)
    delegate.q_table.set(state, CardName.TAO.name, 1.0)
    delegate.epsilon = 0.0

    tao = Card(CardSuit.HEARTS, 4, CardName.TAO)
    picked = ai.select_card([tao], available_targets={"all": [2], "attackable": [2]})
    assert picked is tao


def test_adaptive_ai_delegates_by_difficulty() -> None:
    """AdaptiveAIControl：根据难度选择 delegate。

    Args:
        None

    Returns:
        None
    """
    ai_easy = AdaptiveAIControl(player_id=1, difficulty=AIDifficulty.EASY)
    assert isinstance(ai_easy._delegate, SimpleControl)

    ai_medium = AdaptiveAIControl(player_id=1, difficulty=AIDifficulty.MEDIUM)
    assert isinstance(ai_medium._delegate, BasicAIControl)

    ai_hard = AdaptiveAIControl(player_id=1, difficulty=AIDifficulty.HARD)
    assert isinstance(ai_hard._delegate, HardAIControl)

    ai_expert = AdaptiveAIControl(player_id=1, difficulty=AIDifficulty.EXPERT)
    assert isinstance(ai_expert._delegate, ExpertAIControl)


def test_adaptive_ai_syncs_use_skill_flag() -> None:
    """AdaptiveAIControl：use_skill 应同步到 delegate。

    Args:
        None

    Returns:
        None
    """
    ai = AdaptiveAIControl(player_id=1, difficulty=AIDifficulty.EASY)
    ai.set_use_skill(False)
    assert ai.ask_activate_skill("任意技能", {"event_type": "TEST"}) is False


def test_simple_control_prefers_equipment() -> None:
    """SimpleControl（EASY delegate）：优先选择装备牌。

    Args:
        None

    Returns:
        None
    """
    ai = SimpleControl(player_id=1)
    cards = [
        Card(CardSuit.SPADES, 6, CardName.QING_GANG_JIAN),
        Card(CardSuit.HEARTS, 7, CardName.SHA),
        Card(CardSuit.HEARTS, 2, CardName.SHAN),
    ]
    picked = ai.select_card(cards, available_targets={"all": [2], "attackable": [2]})
    assert picked is cards[0]


def test_hard_ai_prefers_tao_when_available() -> None:
    """HardAIControl：当【桃】可用时，默认优先级最高。

    Args:
        None

    Returns:
        None
    """
    ai = HardAIControl(player_id=1)
    # 模拟自己残血：避免“满血降权”干扰
    ai.sync_state({"self": {"hp": 1, "max_hp": 4}, "players": []})

    tao = Card(CardSuit.HEARTS, 4, CardName.TAO)
    sha = Card(CardSuit.SPADES, 7, CardName.SHA)
    picked = ai.select_card([sha, tao], available_targets={"all": [2], "attackable": [2]})
    assert picked is tao


def test_expert_ai_uses_qtable_to_choose_card() -> None:
    """ExpertAIControl（RL/RI）：当 Q 表对某动作赋更高值时，应选对应牌。

    Args:
        None

    Returns:
        None
    """
    ai = AdaptiveAIControl(player_id=1, difficulty=AIDifficulty.EXPERT)
    delegate: ExpertAIControl = ai._delegate  # type: ignore

    # 同步一个最小状态，得到可复现的编码 state
    ai.sync_state({})
    state = delegate.encoder.encode(delegate.game_state)

    # 让【桃】比 PASS 更优，且关闭随机探索
    delegate.q_table.set(state, PASS_ACTION, 0.0)
    delegate.q_table.set(state, CardName.TAO.name, 1.0)
    delegate.epsilon = 0.0

    tao = Card(CardSuit.HEARTS, 4, CardName.TAO)
    picked = ai.select_card([tao], available_targets={"all": [2], "attackable": [2]})
    assert picked is tao


def test_human_control_select_card_event_roundtrip() -> None:
    """HumanControl：select_card 应通过 InputRequest/Response 完成一次交互。

    Args:
        None

    Returns:
        None
    """
    ctrl = HumanControl(player_id=1)

    cards = [
        Card(CardSuit.HEARTS, 7, CardName.SHA),
        Card(CardSuit.HEARTS, 2, CardName.SHAN),
    ]

    box = _run_in_thread(ctrl.select_card, cards, "测试", {"all": [2], "attackable": [2]})
    req = _await_request()
    assert req.action == "select_card"
    assert req.player_id == 1

    # 选择 index=1 的【闪】
    ctrl.on_event(InputResponseEvent(req.request_id, 1, {"index": 1}))
    picked: Optional[Card] = _join_thread(box)
    assert picked is cards[1]


def test_human_control_select_targets_event_roundtrip() -> None:
    """HumanControl：select_targets 应通过 InputRequest/Response 完成一次交互。

    Args:
        None

    Returns:
        None
    """
    ctrl = HumanControl(player_id=1)
    card = Card(CardSuit.HEARTS, 7, CardName.SHA)

    # HumanControl 的 select_targets 接口不需要额外 context 字符串
    box = _run_in_thread(ctrl.select_targets, [2, 3], card)
    req = _await_request()
    assert req.action == "select_targets"
    assert req.player_id == 1

    ctrl.on_event(InputResponseEvent(req.request_id, 1, {"target_ids": [3]}))
    targets: List[int] = _join_thread(box)
    assert targets == [3]


def test_human_control_discard_event_roundtrip() -> None:
    """HumanControl：select_cards_to_discard 应通过 InputRequest/Response 返回指定弃牌。

    Args:
        None

    Returns:
        None
    """
    ctrl = HumanControl(player_id=1)
    cards = [
        Card(CardSuit.HEARTS, 7, CardName.SHA),
        Card(CardSuit.HEARTS, 2, CardName.SHAN),
        Card(CardSuit.HEARTS, 1, CardName.TAO),
    ]

    # HumanControl 的 select_cards_to_discard 接口不需要额外 context 字符串
    box = _run_in_thread(ctrl.select_cards_to_discard, cards, 2)
    req = _await_request()
    assert req.action == "discard"
    assert req.player_id == 1

    ctrl.on_event(InputResponseEvent(req.request_id, 1, {"indices": [0, 2]}))
    discarded: List[Card] = _join_thread(box)
    assert discarded == [cards[0], cards[2]]


def test_human_control_ask_use_card_response_roundtrip() -> None:
    """HumanControl：ask_use_card_response 应能通过事件选择响应牌。

    Args:
        None

    Returns:
        None
    """
    ctrl = HumanControl(player_id=1)
    shan_cards = [
        Card(CardSuit.HEARTS, 2, CardName.SHAN),
        Card(CardSuit.HEARTS, 3, CardName.SHAN),
    ]

    box = _run_in_thread(
        ctrl.ask_use_card_response,
        CardName.SHAN,
        shan_cards,
        "响应杀",
    )
    req = _await_request()
    assert req.action == "ask_use_card_response"
    assert req.player_id == 1

    ctrl.on_event(InputResponseEvent(req.request_id, 1, {"index": 0}))
    picked: Optional[Card] = _join_thread(box)
    assert picked is shan_cards[0]


def test_human_control_ask_activate_skill_roundtrip() -> None:
    """HumanControl：ask_activate_skill 应能通过事件返回是否发动。

    Args:
        None

    Returns:
        None
    """
    ctrl = HumanControl(player_id=1)

    box = _run_in_thread(ctrl.ask_activate_skill, "测试技能", {"event_type": "TEST"})
    req = _await_request()
    assert req.action == "ask_activate_skill"
    assert req.player_id == 1

    ctrl.on_event(InputResponseEvent(req.request_id, 1, {"activate": True}))
    result: bool = _join_thread(box)
    assert result is True