import asyncio
from typing import Dict, List, Any
from fastapi import WebSocket
from core.environment import RisikoEnvironment
from ai.processor import Processor
from utils.watch_match_utils import WatchMatchUtils
from web.utils import serialize_board

_ai_p1 = 0
_ai_p2 = 0

def get_scores_ref(p1, p2):
    global _ai_p1, _ai_p2
    result = (p1 + _ai_p1, p2 + _ai_p2)
    _ai_p1 = 0
    _ai_p2 = 0
    return result

async def play_ai_turn(
    env: RisikoEnvironment,
    ai_agent,
    processor: Processor,
    coords: Dict[int, Dict[str, float]],
    ws: WebSocket,
    send_json,
    send_state_update,
    action_log: List[str],
    p1_total_reward: int,
    p2_total_reward: int,
):
    #Esegue l'intero turno dell'AI (REINFORCE → ATTACK → MANEUVER).
    global _ai_p1, _ai_p2
    _ai_p1 = 0
    _ai_p2 = 0
    max_actions = 200

    for _ in range(max_actions):
        if env.player_turn != 2:
            break

        winner_check, _ = env.is_game_over()
        if winner_check != 0:
            break

        mission = env.p2_mission
        phase = env.current_phase

        await asyncio.sleep(1.2)  # Normal AI action delay

        action = ai_agent.think(env.board, 2, env.current_turn, phase, mission)
        reward, done, info = env.step(action, 2)

        _ai_p2 += reward
        if "opponent_reward" in info:
            _ai_p1 += info["opponent_reward"]

        reason = WatchMatchUtils.get_reward_reason(action["type"], reward, info)
        log_entry = WatchMatchUtils.format_log_line(2, action, reward, reason)
        action_log.append(log_entry)

        await send_json({"type": "log", "entry": log_entry, "reward": reward, "player": 2})

        # Send state update BEFORE long pauses so user sees the action result (including dice)
        await send_json({
            "type": "state_update",
            "board": {"territories": serialize_board(env, coords)},
            "current_player": env.player_turn,
            "phase": env.current_phase,
            "turn": env.current_turn,
            "p1_score": p1_total_reward + _ai_p1,
            "p2_score": p2_total_reward + _ai_p2,
            "armies_to_place": env.armies_to_place,
            "action_log": action_log[-30:],
            "ai_playing": True,
            "extra": info # MUST include info for dice rolls
        })

        if action["type"] == "ATTACK":
            # Give player time to see the battle result modal
            await asyncio.sleep(2.5)

        if done:
            break

        #Gestisce il POST_ATTACK_MOVE
        if info.get("requires_post_attack_move") or info.get("post_attack_move_required"):
            await asyncio.sleep(0.5)
            post_action = ai_agent.think(env.board, 2, env.current_turn, env.current_phase, mission)
            post_action["type"] = "POST_ATTACK_MOVE"
            reward2, done2, info2 = env.step(post_action, 2)
            _ai_p2 += reward2
            if "opponent_reward" in info2:
                _ai_p1 += info2["opponent_reward"]
            reason2 = WatchMatchUtils.get_reward_reason(post_action["type"], reward2, info2)
            log2 = WatchMatchUtils.format_log_line(2, post_action, reward2, reason2)
            action_log.append(log2)
            await send_json({"type": "log", "entry": log2, "reward": reward2, "player": 2})
            
            # Update state after post_attack_move
            await send_json({
                "type": "state_update",
                "board": {"territories": serialize_board(env, coords)},
                "current_player": env.player_turn,
                "phase": env.current_phase,
                "turn": env.current_turn,
                "p1_score": p1_total_reward + _ai_p1,
                "p2_score": p2_total_reward + _ai_p2,
                "armies_to_place": env.armies_to_place,
                "action_log": action_log[-30:],
                "ai_playing": True,
                "extra": info2
            })
            
            if done2:
                break

    await send_json({"type": "ai_done"})
