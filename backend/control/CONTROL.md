# Control（操控）系统说明：AI 控制与玩家控制

本项目把“玩家如何做选择”从 `Player` / `GameController` 中抽离，统一收敛到 **Control** 模块。
这样做的直接收益是：

- 同一套游戏规则下，可以无缝切换 **真人交互**、**简单 AI**、**更强 AI**。
- `Player` 只关心“流程”（阶段、结算），不关心“输入来源”。

---

## 1. 总体入口：ControlFactory

玩家对象在初始化时通过工厂创建控制器：

- `backend/control/control_factory.py`
  - `ControlType.HUMAN` → `HumanControl`
  - `ControlType.AI` / `ControlType.SIMPLE_AI` → `AdaptiveAIControl`

对应代码位置：`backend/player/player.py`：

```text
self.control = ControlFactory.create_control(control_type, player_id)
```

---

## 2. 玩家控制：HumanControl（事件驱动）

### 2.1 设计目标

HumanControl 的目标不是“从控制台读入字符串”，而是：

1) 后端把“需要玩家决策”的信息打包成 `InputRequestEvent`
2) 前端把玩家的选择回传为 `InputResponseEvent`
3) HumanControl 在收到响应后返回具体决策结果（Card/targets/...）

这使得真人交互不依赖命令行，能够接入你们的前端。

### 2.2 关键交互点

HumanControl 对外提供的核心接口（Player 会调用它们）：

- `select_card(available_cards, context, available_targets) -> Optional[Card]`
- `select_targets(targets, selected_card, context) -> List[int]`
- `select_cards_to_discard(hand_cards, count, context) -> List[Card]`
- `ask_use_card_response(card_name, available_cards, context) -> Optional[Card]`
- `ask_activate_skill(skill_name, context) -> bool`

内部实现要点：

- `send_to_frontend(InputRequestEvent(...))`
- `Condition` 等待响应（通过 `request_id` 对齐请求-响应）
- `on_event(InputResponseEvent)` 写入 payload 并唤醒等待线程

### 2.3 为什么测试要“事件回环”

HumanControl 在 `communicator is None` 时会退化为 `input()`（console 模式）。
测试环境下如果走 console，会卡住。因此测试必须：

1) 在子线程调用 HumanControl 的选择函数（让它发出请求并等待）
2) 主线程从 `communicator` 的 backend->frontend 队列中取出 `InputRequestEvent`
3) 用相同 `request_id` 构造 `InputResponseEvent`，再 `ctrl.on_event(...)`

对应测试文件：`tests/test_controls.py`。

---

## 3. AI 控制：AdaptiveAIControl（策略分发）

### 3.1 设计目标

AI 控制不是单一实现，而是一个“包装器”：

- `AdaptiveAIControl` 根据难度选择内部 delegate：
  - EASY：`Control`（基类默认随机/保守）
  - MEDIUM：`BasicAIControl`（轻量规则：优先装备、群攻、杀/决斗等）
  - HARD：`SimpleControl`（更细的规则集）

这让你可以在不改 Player 逻辑的情况下，直接切换 AI 强度。

### 3.2 关键交互点

`AdaptiveAIControl` 会把请求转发给 delegate：

- `select_card / select_targets / select_cards_to_discard`
- `ask_use_card_response / ask_activate_skill`

并且会同步 `use_skill` 开关：

```text
AdaptiveAIControl.set_use_skill(False)  -> delegate.use_skill = False
```

对应测试：`tests/test_controls.py::test_adaptive_ai_syncs_use_skill_flag`。

---

## 4. Player 是如何调用 Control 的

典型调用路径（出牌阶段）：

1) `Player.play_card_default(...)`
2) 计算可出牌列表 `playable_cards`
3) `selected_card = self.control.select_card(playable_cards, ..., available_targets)`
4) 计算目标集合 `targets`
5) `selected_targets = self.control.select_targets(targets, selected_card, ...)`

弃牌、响应、技能询问同理。

---

## 5. 相关测试入口

- AI 与 Human 控制：`tests/test_controls.py`
- 武将技能（含新增周瑜/孙权/黄盖）：`tests/test_character_skills.py`
