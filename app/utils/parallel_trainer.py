from typing import Dict, Any, Tuple
from app.core.environment import RisikoEnvironment
from config import Config


PHASE_KEYS = (
    'reinforce',
    'attack',
    'post_attack_move',
    'maneuver',
)

def _init_phase_stats() -> Dict[str, float | int]:
    stats: Dict[str, float | int] = {}
    for key in PHASE_KEYS:
        stats[f'{key}_count'] = 0
        stats[f'{key}_reward_sum'] = 0.0
    stats['pass_count'] = 0
    stats['total_actions'] = 0
    
    # Outcomes
    stats['wins'] = 0
    stats['losses'] = 0
    stats['stalemates'] = 0
    
    # Offensive Metrics
    stats['consecutive_attacks_max'] = 0
    stats['territories_captured'] = 0
    stats['frontline_weakness_penalties'] = 0
    stats['end_phase_eval_count'] = 0
    
    # Debug Metrics
    stats['invalid_moves'] = 0
    stats['total_turns'] = 0
    stats['armies_placed'] = 0
    stats['players_eliminated'] = 0
    stats['inactive_penalties_sum'] = 0.0
    stats['setup_overstack_pen_sum'] = 0.0
    stats['post_attack_abandon_pen_sum'] = 0.0

    # Deep Maneuver Diagnosis
    stats['maneuver_inactive_pen_sum'] = 0.0   # Punti persi per armate inattive nelle retrovie
    stats['maneuver_leave_one_pen_sum'] = 0.0  # Punti persi per frontiere scoperte
    stats['maneuver_strategic_count'] = 0      # Manovre Retrovie->Fronte effettuate (positive)
    stats['maneuver_away_count'] = 0           # Manovre Fronte->Retrovie (negative)
    stats['maneuver_pass_count'] = 0           # Quante volte l'AI ha skippato la manovra
    stats['garrison_bonus_sum'] = 0.0          # Punti ottenuti per presidio stabile a fine turno

    return stats


def run_parallel_match(data: Tuple[Any, ...]) -> Tuple[Dict[int, float], Dict[str, float | int]]:
    agents_list = data
    env = RisikoEnvironment()
    env.reset()
    num_players = env.num_players

    # Resetta la memoria temporale degli agenti (delta features)
    for a in agents_list:
        if hasattr(a, 'reset_memory'):
            a.reset_memory()

    # Fitness per ogni giocatore (float per precisione)
    fitness_map: Dict[int, float] = {p_id: 0.0 for p_id in range(1, num_players + 1)}
    consecutive_errors: Dict[int, int] = {p_id: 0 for p_id in range(1, num_players + 1)}
    
    stats: Dict[str, float | int] = {
        'post_move_count': 0,
        'post_move_high_threat': 0,   # Turni in cui un territorio era sotto minaccia tattica reale (> ratio)
        'post_move_weak_front': 0,    # Turni in cui un territorio aveva 1 sola armata sul fronte
    }
    stats.update(_init_phase_stats())

    # La partita termina solo quando l'environment segnala done (MAX_TURNS o vittoria)
    # oppure se un giocatore fa 10 errori consecutivi.
    while True:
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
            stats[f'{action_type}_reward_sum'] += float(reward)

        if action.get('type') == 'POST_ATTACK_MOVE' and 'post_attack_move_qty' in info:
            stats['post_move_count'] += 1
        
        if action_type == 'attack' and info.get('conquered'):
            stats['territories_captured'] += 1

        if 'error' in info:
            stats['invalid_moves'] += 1

        if action_type == 'reinforce':
            stats['armies_placed'] += info.get('reinforce_qty', 0)

        if info.get('inactive_army_penalty'):
            stats['inactive_penalties_sum'] += info.get('inactive_army_penalty', 0.0)
        
        if info.get('setup_overstack_penalty'):
            stats['setup_overstack_pen_sum'] += float(info.get('setup_overstack_penalty', 0.0))
            
        if info.get('post_attack_abandon_penalty'):
            stats['post_attack_abandon_pen_sum'] += float(info.get('post_attack_abandon_penalty', 0.0))

        # --- Deep Maneuver Diagnosis ---
        if action_type == 'maneuver':
            if info.get('inactive_army_penalty'):
                stats['maneuver_inactive_pen_sum'] += float(info.get('inactive_army_penalty', 0.0))
            if info.get('end_phase_left_one'):
                pen = Config.REWARD.get('END_PHASE_LEAVE_ONE_PENALTY', -150)
                stats['maneuver_leave_one_pen_sum'] += float(info.get('end_phase_left_one', 0)) * pen
            if info.get('maneuver_strategic'):
                stats['maneuver_strategic_count'] += 1
            if info.get('maneuver_away_from_front'):
                stats['maneuver_away_count'] += 1
        
        # Il Garrison Bonus (END_TURN_WITH_2_GARRISON_ARMY) calcolato in info
        if info.get('garrison_bonus'):
            stats['garrison_bonus_sum'] += float(info.get('garrison_bonus', 0.0))

        if action_type == 'pass' and phase == 'MANEUVER':
            stats['maneuver_pass_count'] += 1
            # Anche il PASS in MANEUVER può aver subito penalità di fine turno
            if info.get('inactive_army_penalty'):
                stats['maneuver_inactive_pen_sum'] += float(info.get('inactive_army_penalty', 0.0))
            if info.get('end_phase_left_one'):
                pen = Config.REWARD.get('END_PHASE_LEAVE_ONE_PENALTY', -150)
                stats['maneuver_leave_one_pen_sum'] += float(info.get('end_phase_left_one', 0)) * pen
            
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
    winner, _ = env.is_game_over()
    
    # Se il loop è finito senza un vincitore reale o uno stallo temporale, lo forziamo a stallo (Timeout Azioni)
    if winner == 0:
        winner = -1
    
    stats['total_turns'] = env.current_turn
    # Conta quanti territori hanno owner_id != 0 per capire quanti sono vivi
    alive_count = len(set(t.owner_id for t in env.board.territories.values() if t.owner_id > 0))
    stats['players_eliminated'] = num_players - alive_count
    if winner != 0:
        for p_id_dist in range(1, num_players + 1):
            
            # 1) Aggiorniamo le STATISTICHE globali del match a prescindere
            if winner == p_id_dist:
                stats['wins'] += 1
            elif winner == -1:
                stats['stalemates'] += 1
            else:
                stats['losses'] += 1
                
            # 2) Diamo i PUNTI FITNESS solo a chi non li ha presi nel step() (cioè se non è il turno del vincitore o se è stato stallo)
            if not done or p_id_dist != curr_p:
                if winner == p_id_dist:
                    fitness_map[p_id_dist] += float(Config.REWARD.get('WIN', 7000))
                elif winner == -1:
                    fitness_map[p_id_dist] += float(Config.REWARD.get('STALEMATE_PENALTY', -6000))
                else:
                    fitness_map[p_id_dist] += float(Config.REWARD.get('LOSS', -8000))

    return fitness_map, stats