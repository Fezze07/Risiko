from typing import Dict, Any, Tuple
from core.environment import RisikoEnvironment
from config import Config


PHASE_KEYS = (
    'reinforce',
    'attack',
    'post_attack_move',
    'maneuver',
)


def _init_phase_stats() -> Dict[str, int]:
    stats: Dict[str, int] = {}
    for key in PHASE_KEYS:
        stats[f'{key}_count'] = 0
        stats[f'{key}_reward_sum'] = 0
    stats['pass_count'] = 0
    stats['total_actions'] = 0
    return stats


def run_parallel_match(data: Tuple[Any, Any]) -> Tuple[int, int, Dict[str, int]]:
    agent_p1, agent_p2 = data
    env = RisikoEnvironment()
    env.reset()

    fit1: int = 0
    fit2: int = 0
    consecutive_errors: int = 0
    last_player: Any = None

    stats: Dict[str, int] = {
        'post_move_count': 0,
        'post_move_qty_sum': 0,
        'post_move_risky': 0,
    }
    stats.update(_init_phase_stats())

    for _ in range(Config.GAME['MAX_TURNS']):
        curr_p = env.player_turn
        if curr_p != last_player:
            consecutive_errors = 0
            last_player = curr_p

        phase = env.current_phase
        agent = agent_p1 if curr_p == 1 else agent_p2
        mission = env.p1_mission if curr_p == 1 else env.p2_mission

        action = agent.think(env.board, curr_p, env.current_turn, phase, mission)
        reward, done, info = env.step(action, curr_p)

        stats['total_actions'] += 1

        action_type = action.get('type', '').lower()
        if action_type == 'pass':
            stats['pass_count'] += 1
        elif action_type in PHASE_KEYS:
            stats[f'{action_type}_count'] += 1
            stats[f'{action_type}_reward_sum'] += int(reward)

        if action.get('type') == 'POST_ATTACK_MOVE' and 'post_attack_move_qty' in info:
            stats['post_move_count'] += 1
            stats['post_move_qty_sum'] += int(info.get('post_attack_move_qty', 0))
            if info.get('risky_attack_conquer') or info.get('left_one_army_src') or info.get('left_one_army_dest'):
                stats['post_move_risky'] += 1

        if 'error' in info:
            consecutive_errors += 1
        else:
            consecutive_errors = 0

        if consecutive_errors >= 10:
            if curr_p == 1:
                fit1 += Config.REWARD['CONSECUTIVE_INVALID_MOVE']
            else:
                fit2 += Config.REWARD['CONSECUTIVE_INVALID_MOVE']
            break

        if curr_p == 1:
            fit1 += reward
        else:
            fit2 += reward

        opponent_reward = info.get('opponent_reward', 0)
        if opponent_reward:
            if curr_p == 1:
                fit2 += opponent_reward
            else:
                fit1 += opponent_reward
        if done:
            break

    return fit1, fit2, stats
