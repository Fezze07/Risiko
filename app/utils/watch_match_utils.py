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
                qty = info.get('reinforce_qty', 0)
                pen_base = Config.REWARD.get('REINFORCE_SAFE_PENALTY', -15)
                pen_per = Config.REWARD.get('REINFORCE_SAFE_PENALTY_PER_ARMY', -3)
                total_pen = pen_base + qty * pen_per
                reasons.append(f'Penaltà zona sicura ({total_pen:.0f})')
            if info.get('reinforce_qty'):
                reasons.append(f"Piazzate {info['reinforce_qty']}")
            if info.get('setup_overstack_penalty'):
                reasons.append(f"Overstacking Setup ({info['setup_overstack_penalty']:.0f})")

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
                reasons.append('esercito perso')

        # --- POST_ATTACK_MOVE ---
        elif action_type == 'POST_ATTACK_MOVE':
            if 'post_attack_move_qty' in info:
                reasons.append(f"spostate {info['post_attack_move_qty']}")
            if info.get('post_attack_abandon_penalty'):
                reasons.append(f"Frontiera abbandonata ({info['post_attack_abandon_penalty']:.0f})")

        # --- MANEUVER ---
        elif action_type == 'MANEUVER':
            qty = info.get('maneuver_qty', 0)
            if info.get('maneuver_strategic'):
                base = Config.REWARD.get('MANEUVER_TO_FRONT_BASE', 10)
                per = Config.REWARD.get('MANEUVER_TO_FRONT_PER_ARMY', 4)
                total = base + qty * per
                reasons.append(f'Retrovie->Fronte (+{total:.0f})')
            if info.get('maneuver_proximity'):
                prox = Config.REWARD.get('MANEUVER_PROXIMITY_BONUS', 5)
                reasons.append(f'Verso Minaccia (+{prox})')
            if info.get('maneuver_away_from_front'):
                pen = Config.REWARD.get('END_PHASE_LEAVE_ONE_PENALTY', -150) * 0.5
                reasons.append(f'Fronte->Retrovie ({pen:.0f})')

        # --- PASS ---
        elif action_type == 'PASS':
            if info.get('passive_turn_penalty'):
                reasons.append(f"Malus PASS ripetuto ({info['passive_turn_penalty']:.0f})")

        # --- FINE TURNO: Penalità di Manovra (PASS e MANEUVER) ---
        if action_type in ('PASS', 'MANEUVER'):
            if info.get('end_phase_left_one'):
                count = info.get('end_phase_left_one', 0)
                pen = Config.REWARD.get('END_PHASE_LEAVE_ONE_PENALTY', -150)
                total_pen = count * pen
                reasons.append(f'Confine scoperto x{count} ({total_pen:.0f})')
            if info.get('garrison_bonus'):
                gb = info.get('garrison_bonus', 0)
                reasons.append(f'Bonus presidio (+{gb})')
            if info.get('inactive_army_penalty'):
                total_pen = info.get('inactive_army_penalty', 0.0)
                count = info.get('inactive_army_count', '?')
                details = info.get('inactive_details', '')
                detail_str = f' [{details}]' if details else ''
                reasons.append(f'Inattive x{count} ({total_pen:.0f}){detail_str}')

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
