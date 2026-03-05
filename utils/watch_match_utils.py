from typing import Dict, Any
from core.world import TERRITORIES


class WatchMatchUtils:
    @staticmethod
    def get_reward_reason(action_type: str, reward: int, info: Dict[str, Any]) -> str:
        from config import Config

        if 'error' in info:
            return f"ERROR: {info['error']}"
        if reward >= Config.REWARD['WIN']:
            return 'VITTORIA'

        reasons = []

        if action_type == 'REINFORCE':
            if info.get('continent_held'):
                reasons.append('Bonus continente')
            
            if info.get('is_frontline'):
                reasons.append('Rinforzo strategico')
            else:
                reasons.append('Rinforzo sicuro')
                if info.get('safe_action_bonus'):
                    reasons.append('Bonus azione sicura')
                if info.get('reinforce_safe_penalty'):
                    reasons.append('Malus rinforzo non strategico')
                if info.get('attack_risk_penalty'):
                    reasons.append('Malus rischio attacco (interno)')
            
            if info.get('stack_penalty'):
                excess = info.get('stack_excess', '')
                reasons.append(f'Malus stacking (eccesso: {excess})' if excess else 'Malus stacking')
            if info.get('repeat_reinforce_penalty'):
                count = info.get('repeat_reinforce_count', '')
                reasons.append(f'Malus ripetizione (n.{count})' if count else 'Malus ripetizione')

        elif action_type == 'ATTACK':
            if info.get('conquered'):
                msg = 'Conquista'
                if info.get('continent_complete'):
                    msg = 'Continente preso'
                if info.get('continent_lost'):
                    msg += ' + continente rotto'
                if info.get('post_attack_move_required'):
                    msg += ' | scegli spostamento'
                reasons.append(msg)
            else:
                if info.get('defended'):
                    reasons.append('difesa riuscita')
                if info.get('risky_attack'):
                    reasons.append('attacco rischioso')
                if info.get('left_one_army_src'):
                    reasons.append('1 armata sorgente')
                if info.get('avoid_risk'):
                    reasons.append('evita rischio')
                if info.get('safe_action_bonus'):
                    reasons.append('bonus azione sicura')
                if reward < 0:
                    reasons.append('persa armata')
                elif reward > 0:
                    reasons.append('uccisa armata nemica')

        elif action_type == 'POST_ATTACK_MOVE':
            if 'post_attack_move_qty' in info:
                reasons.append(f"spostate {info['post_attack_move_qty']}")
            if info.get('risky_attack_conquer'):
                reasons.append('nuovo territorio rischioso')
            if info.get('left_one_army_src'):
                reasons.append('1 armata sorgente')
            if info.get('left_one_army_dest'):
                reasons.append('1 armata nuovo territorio')
            if info.get('avoid_risk'):
                reasons.append('evita rischio')
            if info.get('safe_action_bonus'):
                reasons.append('bonus azione sicura')
            if info.get('forced_post_attack_move'):
                reasons.append('forzato')

        elif action_type == 'MANEUVER':
            if info.get('maneuver_strategic'):
                reasons.append('Mossa strategica (fronte)')
            elif info.get('maneuver_strategic_stacked'):
                reasons.append('Eccesso truppe al fronte (malus)')
            elif info.get('maneuver_safe_to_safe'):
                reasons.append('Spostamento interno')
            elif info.get('maneuver_away_from_front'):
                reasons.append('Ritirata (malus)')
            
            if info.get('stack_penalty'):
                excess = info.get('stack_excess', '')
                reasons.append(f'Malus stacking (eccesso: {excess})' if excess else 'Malus stacking')
            
            if info.get('left_one_army_src'):
                reasons.append('1 armata sorgente')
            if info.get('frontline_stable'):
                reasons.append('fronte stabile')
            if info.get('frontline_fortified'):
                reasons.append('fronte fortificato')
        
        # Add global reasons to any action
        if info.get('safe_action_bonus') and not any('azione sicura' in r.lower() for r in reasons):
            reasons.append('bonus azione sicura')
        
        if info.get('progress_reward'):
            reasons.append('Progresso mappa')
        if info.get('game_length_penalty'):
            reasons.append('Penalità tempo')
        
        if reasons:
            return ' | '.join(reasons)
        
        return 'OK'

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
