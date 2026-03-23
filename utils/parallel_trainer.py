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
    
    # New Offensive Metrics
    stats['consecutive_attacks_max'] = 0
    stats['territories_captured'] = 0
    stats['frontline_weakness_penalties'] = 0
    stats['end_phase_eval_count'] = 0
    
    return stats


def run_parallel_match(data: Tuple[Any, ...]) -> Tuple[Dict[int, int], Dict[str, int]]:
    agents_list = data
    env = RisikoEnvironment()
    env.reset()
    num_players = env.num_players

    # Resetta la memoria temporale degli agenti (delta features)
    for a in agents_list:
        if hasattr(a, 'reset_memory'):
            a.reset_memory()

    # Fitness per ogni giocatore
    fitness_map: Dict[int, int] = {p_id: 0 for p_id in range(1, num_players + 1)}
    consecutive_errors: Dict[int, int] = {p_id: 0 for p_id in range(1, num_players + 1)}
    
    stats: Dict[str, int] = {
        'post_move_count': 0,
        'post_move_high_threat': 0,   # Turni in cui un territorio era sotto minaccia tattica reale (> ratio)
        'post_move_weak_front': 0,    # Turni in cui un territorio aveva 1 sola armata sul fronte
    }
    stats.update(_init_phase_stats())

    # Limite massimo di azioni per evitare loop infiniti, ma molto più alto di MAX_TURNS 
    # per permettere di raggiungere effettivamente lo stallo o la vittoria.
    max_actions = Config.GAME.get('MAX_ACTIONS_PER_MATCH', 10000)
    for _ in range(max_actions):
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
        
        if 'end_phase_frontline_weakness' in info:
            stats['end_phase_eval_count'] += 1
            if info.get('end_phase_risky', 0) > 0:
                stats['post_move_high_threat'] += 1
            if info.get('end_phase_left_one', 0) > 0:
                stats['post_move_weak_front'] += 1

        if action_type == 'attack' and info.get('conquered'):
            stats['territories_captured'] += 1

        if 'end_phase_frontline_weakness' in info:
            stats['frontline_weakness_penalties'] += info['end_phase_frontline_weakness']

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

    # --- FINE PARTITA: Distributore Reward Finali ---
    # Se la partita è finita (per vittoria o stallo), assicuriamoci che TUTTI ricevano i punti.
    # Nota: env.step() ha già dato i punti a chi ha fatto l'ultima mossa, ma solo se done=True.
    winner, _ = env.is_game_over()
    if winner != 0:
        for p_id_dist in range(1, num_players + 1):
            # Se la partita è finita per timeout del loop (done=False), nessuno ha preso i punti.
            # Se finita per done=True, curr_k li ha già presi.
            
            # Gestiamo il caso in cui il loop è finito senza done=True: diamo a tutti lo STALEMATE o altro
            if not done or p_id_dist != curr_p:
                if winner == p_id_dist:
                    fitness_map[p_id_dist] += Config.REWARD.get('WIN', 7000)
                elif winner == -1:
                    fitness_map[p_id_dist] += Config.REWARD.get('STALEMATE_PENALTY', -6000)
                else:
                    fitness_map[p_id_dist] += Config.REWARD.get('LOSS', -8000)

    return fitness_map, stats