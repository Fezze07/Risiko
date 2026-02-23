import asyncio
from typing import Dict, List, Any, Optional

from fastapi import WebSocket

from ai.processor import Processor
from core.environment import RisikoEnvironment
from utils.watch_match_utils import WatchMatchUtils
from web.utils import serialize_board


def build_player_stats(
    env: RisikoEnvironment,
    player_scores: Dict[int, int],
    player_map: Optional[Dict[int, Dict[str, Any]]] = None,
) -> List[Dict[str, Any]]:
    stats: List[Dict[str, Any]] = []
    for p_id in range(1, env.num_players + 1):
        territories = [
            t for t in env.board.territories.values() if t.owner_id == p_id
        ]
        meta = player_map.get(p_id) if player_map else {}
        stats.append(
            {
                "id": p_id,
                "type": meta.get("type", "AI"),
                "color": meta.get("color", "#888888"),
                "territories": len(territories),
                "armies": sum(t.armies for t in territories),
                "score": int(player_scores.get(p_id, 0)),
            }
        )
    return stats


async def play_ai_turn(
    env: RisikoEnvironment,
    ai_agent,
    processor: Processor,
    coords: Dict[int, Dict[str, float]],
    ws: WebSocket,
    send_json,
    send_state_update,
    action_log: List[str],
    player_scores: Dict[int, int],
    player_id: int,
    *,
    player_map: Optional[Dict[int, Dict[str, Any]]] = None,
    delay_seconds: float = 1.2,
) -> None:
    # Esegue l'intero turno dell'AI (REINFORCE → ATTACK → MANEUVER).
    max_actions = 200

    for _ in range(max_actions):
        if env.player_turn != player_id:
            break

        winner_check, _ = env.is_game_over()
        if winner_check != 0:
            break

        mission = env.get_player_mission(player_id)
        phase = env.current_phase

        await asyncio.sleep(delay_seconds)

        action = ai_agent.think(env.board, player_id, env.current_turn, phase, mission)
        reward, done, info = env.step(action, player_id)

        player_scores[player_id] = int(player_scores.get(player_id, 0) + reward)
        opponent_reward = int(info.get("opponent_reward", 0))
        defender_id = info.get("defender_id")
        if opponent_reward and isinstance(defender_id, int) and defender_id != player_id:
            player_scores[defender_id] = int(
                player_scores.get(defender_id, 0) + opponent_reward
            )

        reason = WatchMatchUtils.get_reward_reason(action["type"], reward, info)
        log_entry = WatchMatchUtils.format_log_line(player_id, action, reward, reason)
        action_log.append(log_entry)

        await send_json(
            {"type": "log", "entry": log_entry, "reward": reward, "player": player_id}
        )

        # Send state update BEFORE long pauses so user sees the action result (including dice)
        await send_json(
            {
                "type": "state_update",
                "board": {"territories": serialize_board(env, coords)},
                "current_player": env.player_turn,
                "phase": env.current_phase,
                "turn": env.current_turn,
                "player_stats": build_player_stats(env, player_scores, player_map),
                "action_log": action_log[-30:],
                "ai_playing": True,
                "extra": info,
            }
        )

        if action["type"] == "ATTACK":
            # Give player time to see the battle result modal
            await asyncio.sleep(2.5)

        if done:
            break

        # Gestisce il POST_ATTACK_MOVE
        if info.get("requires_post_attack_move") or info.get("post_attack_move_required"):
            await asyncio.sleep(0.5)
            post_action = ai_agent.think(
                env.board, player_id, env.current_turn, env.current_phase, mission
            )
            post_action["type"] = "POST_ATTACK_MOVE"
            reward2, done2, info2 = env.step(post_action, player_id)
            player_scores[player_id] = int(player_scores.get(player_id, 0) + reward2)
            opponent_reward2 = int(info2.get("opponent_reward", 0))
            defender_id = info2.get("defender_id")
            if opponent_reward2 and isinstance(defender_id, int) and defender_id != player_id:
                player_scores[defender_id] = int(
                    player_scores.get(defender_id, 0) + opponent_reward2
                )
            reason2 = WatchMatchUtils.get_reward_reason(post_action["type"], reward2, info2)
            log2 = WatchMatchUtils.format_log_line(player_id, post_action, reward2, reason2)
            action_log.append(log2)
            await send_json({"type": "log", "entry": log2, "reward": reward2, "player": player_id})
            
            # Update state after post_attack_move
            await send_json(
                {
                    "type": "state_update",
                    "board": {"territories": serialize_board(env, coords)},
                    "current_player": env.player_turn,
                    "phase": env.current_phase,
                    "turn": env.current_turn,
                    "player_stats": build_player_stats(env, player_scores, player_map),
                    "action_log": action_log[-30:],
                    "ai_playing": True,
                    "extra": info2,
                }
            )
            
            if done2:
                break

    await send_json({"type": "ai_done"})
