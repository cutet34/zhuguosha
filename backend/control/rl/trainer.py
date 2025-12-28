from __future__ import annotations

import argparse
import os
import random
from typing import Dict, List, Optional

from config.enums import ControlType, PlayerIdentity
from config.simple_detailed_config import load_config

from backend.game_controller.game_controller import GameController
from backend.control.rl.rl_control import ExpertAIControl


def _winner_to_side(winner_str: Optional[str]) -> str:
    if not winner_str:
        return "DRAW"
    if winner_str.startswith("反贼胜利"):
        return "REBEL"
    if winner_str.startswith("主公，忠臣胜利"):
        return "LORD"
    if winner_str.startswith("内奸胜利"):
        return "TRAITOR"
    return "DRAW"


def _reward_for(player_identity: PlayerIdentity, winner_side: str) -> float:
    if winner_side == "DRAW":
        return 0.0
    if player_identity == PlayerIdentity.REBEL:
        return 1.0 if winner_side == "REBEL" else -1.0
    if player_identity in (PlayerIdentity.LORD, PlayerIdentity.LOYALIST):
        return 1.0 if winner_side == "LORD" else -1.0
    if player_identity == PlayerIdentity.TRAITOR:
        return 1.0 if winner_side == "TRAITOR" else -1.0
    return 0.0


def _set_rl_players(config, rl_player_ids: List[int]) -> None:
    for i, p in enumerate(config.players_config):
        if i in rl_player_ids:
            # 训练时统一使用 AI.EXPERT（内部委托 ExpertAIControl）
            p.control_type = ControlType.AI
            setattr(p, "ai_difficulty", "expert")


def _collect_rl_controls(game: GameController) -> Dict[int, ExpertAIControl]:
    pc = game.player_controller
    if pc is None:
        return {}
    out: Dict[int, ExpertAIControl] = {}
    for p in pc.players:
        # EXPERT 模式：Player.control 为 AdaptiveAIControl，其内部 delegate 才是 ExpertAIControl
        ctrl = p.control
        if isinstance(ctrl, ExpertAIControl):
            out[p.player_id] = ctrl
            continue
        delegate = getattr(ctrl, "_delegate", None)
        if isinstance(delegate, ExpertAIControl):
            out[p.player_id] = delegate
    return out


def train(
    *,
    config_name: str,
    episodes: int,
    rl_player_ids: List[int],
    q_table_path: str,
    epsilon: float,
    epsilon_decay: float,
    epsilon_min: float,
    alpha: float,
    gamma: float,
    seed: Optional[int],
) -> None:
    if seed is not None:
        random.seed(seed)

    os.makedirs(os.path.dirname(q_table_path) or ".", exist_ok=True)

    eps = float(epsilon)
    for ep in range(1, episodes + 1):
        # fresh config per episode
        config = load_config(config_name)
        _set_rl_players(config, rl_player_ids)

        game = GameController(config)
        game.initialize()

        rl_controls = _collect_rl_controls(game)
        for ctrl in rl_controls.values():
            ctrl.set_training_params(
                q_table_path=q_table_path,
                epsilon=eps,
                alpha=alpha,
                gamma=gamma,
            )
            ctrl.begin_episode()

        game.start_game()

        pc = game.player_controller
        winner_str = pc.get_winner() if pc else None
        winner_side = _winner_to_side(winner_str)

        # Apply terminal rewards
        if pc:
            for pid, ctrl in rl_controls.items():
                player = pc.get_player(pid)
                if player is None or player.identity is None:
                    r = 0.0
                else:
                    r = _reward_for(player.identity, winner_side)
                ctrl.end_episode(r)

        # Decay epsilon
        eps = max(epsilon_min, eps * epsilon_decay)

        if ep % 10 == 0 or ep == 1 or ep == episodes:
            print(
                f"[RL] episode={ep}/{episodes} winner={winner_str} "
                f"eps={eps:.4f} q={q_table_path}"
            )


def main() -> None:
    ap = argparse.ArgumentParser(description="Tabular RL trainer (no third-party deps)")
    ap.add_argument("--config", default="default_game_config", help="config file name (without .json)")
    ap.add_argument("--episodes", type=int, default=50)
    ap.add_argument("--rl-player-ids", default="0", help="comma-separated player ids to train, e.g. 0,2")
    ap.add_argument(
        "--q-table",
        default=os.path.join("q_table.json"),
        help="path to q_table json",
    )
    ap.add_argument("--epsilon", type=float, default=0.2)
    ap.add_argument("--epsilon-decay", type=float, default=0.995)
    ap.add_argument("--epsilon-min", type=float, default=0.02)
    ap.add_argument("--alpha", type=float, default=0.1)
    ap.add_argument("--gamma", type=float, default=0.95)
    ap.add_argument("--seed", type=int, default=None)
    args = ap.parse_args()

    rl_ids = [int(x) for x in args.rl_player_ids.split(",") if x.strip() != ""]

    train(
        config_name=args.config,
        episodes=args.episodes,
        rl_player_ids=rl_ids,
        q_table_path=args.q_table,
        epsilon=args.epsilon,
        epsilon_decay=args.epsilon_decay,
        epsilon_min=args.epsilon_min,
        alpha=args.alpha,
        gamma=args.gamma,
        seed=args.seed,
    )


if __name__ == "__main__":
    main()
