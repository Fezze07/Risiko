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


def run_parallel_match(data: Tuple[Any, ...]) -> Tuple[Dict[int, int], Dict[str, int]]:
    agents_list = data
    env = RisikoEnvironment()
    env.reset()
    num_players = env.num_players

    # Fitness per ogni giocatore
    fitness_map: Dict[int, int] = {p_id: 0 for p_id in range(1, num_players + 1)}
    consecutive_errors: Dict[int, int] = {p_id: 0 for p_id in range(1, num_players + 1)}
    
    stats: Dict[str, int] = {
        'post_move_count': 0,
        'post_move_risky': 0,
    }
    stats.update(_init_phase_stats())

    for _ in range(Config.GAME['MAX_TURNS']):
        curr_p = env.player_turn
        phase = env.current_phase
        
        # Seleziona l'agente corrispondente allo slot del giocatore
        agent_idx = (curr_p - 1) % len(agents_list)
        agent = agents_list[agent_idx]
        mission = env.get_player_mission(curr_p)

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
            if info.get('risky_attack_conquer') or info.get('left_one_army_src') or info.get('left_one_army_dest'):
                stats['post_move_risky'] += 1

        if 'error' in info:
            consecutive_errors[curr_p] += 1
        else:
            consecutive_errors[curr_p] = 0

        if consecutive_errors[curr_p] >= 10:
            fitness_map[curr_p] += Config.REWARD['CONSECUTIVE_INVALID_MOVE']
            # Opzionale: potremmo chiudere il match se un player è bloccato
            break

        fitness_map[curr_p] += reward

        # Gestione reward avversario
        opponent_reward = info.get('opponent_reward', 0)
        defender_id = info.get('defender_id')
        if opponent_reward and defender_id:
            fitness_map[defender_id] += opponent_reward

        if done:
            break

    return fitness_map, stats


