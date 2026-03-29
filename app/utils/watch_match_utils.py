from typing import Dict, Any
from app.core.world import TERRITORIES


class WatchMatchUtils:
    @staticmethod
    def get_reward_reason(action_type: str, reward: int, info: Dict[str, Any]) -> str:
        from config import Config

        if 'error' in info:
            return f"ERROR: {info['error']}"
        if reward >= Config.REWARD['WIN']:
            return 'VITTORIA'

        reasons = []

        # --- REINFORCE ---
        if action_type == 'REINFORCE':
            if info.get('reinforce_chokepoint'):
                reasons.append('Bonus Chokepoint')
            if info.get('reinforce_safe_penalty'):
                reasons.append('Penalità interno')
            if info.get('reinforce_qty'):
                reasons.append(f"Piazzate {info['reinforce_qty']}")

        # --- ATTACK ---
        elif action_type == 'ATTACK':
            if info.get('conquered'):
                msg = 'CONQUISTA'
                if info.get('continent_complete'):
                    msg += ' + CONTINENTE'
                if info.get('continent_lost'):
                    msg += ' (rotto nemico)'
                reasons.append(msg)
            
            if info.get('player_eliminated'):
                reasons.append('GIOCATORE ELIMINATO')
                
            if info.get('risky_attack'):
                reasons.append('Attacco rischioso')
            
            if reward < 0 and not info.get('conquered'):
                # Perda armate ma senza conquistare
                reasons.append('esercito perso')

        # --- POST_ATTACK_MOVE ---
        elif action_type == 'POST_ATTACK_MOVE':
            if 'post_attack_move_qty' in info:
                reasons.append(f"spostate {info['post_attack_move_qty']}")

        # --- MANEUVER ---
        elif action_type == 'MANEUVER':
            if info.get('maneuver_strategic'):
                reasons.append('Al fronte')
            if info.get('maneuver_to_chokepoint'):
                reasons.append('Verso Chokepoint')
            if info.get('maneuver_away_from_front'):
                reasons.append('Ritirata')

        # --- PASS ---
        elif action_type == 'PASS':
            if info.get('passive_turn_penalty'):
                reasons.append('Malus PASS ripetuto')

        # --- FINE TURNO (Shared by PASS and MANEUVER) ---
        if action_type in ('PASS', 'MANEUVER'):
            if info.get('end_phase_left_one'):
                count = info.get('end_phase_left_one', 0)
                reasons.append(f'Confine scoperto (x{count})')
            if info.get('garrison_bonus'):
                reasons.append('Bonus presidio')
            if info.get('inactive_army_penalty'):
                details = info.get('inactive_details', '')
                if details:
                    reasons.append(f'Penalità inattive: {details}')
                else:
                    reasons.append('Penalità inattive')

        return " | ".join(reasons) if reasons else "OK"

    @staticmethod
    def format_log_line(player_id: int, action: Dict[str, Any], reward: int, reason: str) -> str:
        p_tag = f'P{player_id}'
        a_type = action['type']
        qty_pct = int(action.get('qty', 0) * 100)

        def get_name(t_id):
            if t_id is None: return "--"
            return TERRITORIES.get(t_id, {}).get("name", f"{t_id:02d}")
        TERRITORY_COL_WIDTH = 25

        if a_type == 'PASS':
            return f"{p_tag} | {a_type:<16} | {'-- -> --':<{TERRITORY_COL_WIDTH}} | {'----':<4} | Rew: {float(reward):>7.2f} | {reason}"

        if a_type == 'REINFORCE':
            dest_name = get_name(action.get('dest'))
            formatted_dest = f"-> {dest_name}"
            return f"{p_tag} | {a_type:<16} | {formatted_dest:<{TERRITORY_COL_WIDTH}} | x{qty_pct:02d}% | Rew: {float(reward):>7.2f} | {reason}"

        src_name = get_name(action.get('src'))
        dest_name = get_name(action.get('dest'))
        formatted_src_dest = f"{src_name} -> {dest_name}"
        
        # Struttura: P1 | ATTACK | NomeSorgente -> NomeDestinazione | x100% | Rew: 100.00 | Ragione
        return f"{p_tag} | {a_type:<16} | {formatted_src_dest:<{TERRITORY_COL_WIDTH}} | x{qty_pct:02d}% | Rew: {float(reward):>7.2f} | {reason}"
