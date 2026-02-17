from typing import Dict, Any


class WatchMatchUtils:
    @staticmethod
    def get_reward_reason(action_type: str, reward: int, info: Dict[str, Any]) -> str:
        from core.config import Config

        if 'error' in info:
            return f"ERROR: {info['error']}"
        if reward >= Config.REWARD['WIN']:
            return 'VITTORIA'

        if action_type == 'REINFORCE':
            reasons = []
            if info.get('continent_held'):
                reasons.append('Bonus continente')
            
            if info.get('is_frontline'):
                reasons.append('Rinforzo strategico')
            else:
                reasons.append('Rinforzo sicuro')
                if info.get('safe_action_bonus'):
                    reasons.append('Bonus azione sicura')
                if info.get('attack_risk_penalty'):
                    reasons.append('Malus rischio attacco (interno)')
            
            if info.get('stack_penalty'):
                reasons.append('Malus stacking')
            if info.get('repeat_reinforce_penalty'):
                reasons.append('Malus ripetizione')
            
            return ' | '.join(reasons) if reasons else 'Rinforzo'

        if action_type == 'ATTACK':
            if info.get('conquered'):
                msg = 'Conquista'
                if info.get('continent_complete'):
                    msg = 'Continente preso'
                if info.get('continent_lost'):
                    msg += ' + continente rotto'
                if info.get('post_attack_move_required'):
                    msg += ' | scegli spostamento'
                return msg

            parts = []
            if info.get('defended'):
                parts.append('difesa riuscita')
            if info.get('risky_attack'):
                parts.append('attacco rischioso')
            if info.get('left_one_army_src'):
                parts.append('1 armata sorgente')
            if info.get('avoid_risk'):
                parts.append('evita rischio')
            if info.get('safe_action_bonus'):
                parts.append('bonus azione sicura')
            if reward < 0:
                parts.append('persa armata')
            elif reward > 0:
                parts.append('uccisa armata nemica')
            if parts:
                return ' | '.join(parts)
            return 'Nulla di fatto'

        if action_type == 'POST_ATTACK_MOVE':
            parts = []
            if 'post_attack_move_qty' in info:
                parts.append(f"spostate {info['post_attack_move_qty']}")
            if info.get('risky_attack_conquer'):
                parts.append('nuovo territorio rischioso')
            if info.get('left_one_army_src'):
                parts.append('1 armata sorgente')
            if info.get('left_one_army_dest'):
                parts.append('1 armata nuovo territorio')
            if info.get('avoid_risk'):
                parts.append('evita rischio')
            if info.get('safe_action_bonus'):
                parts.append('bonus azione sicura')
            if info.get('forced_post_attack_move'):
                parts.append('forzato')
            if parts:
                return ' | '.join(parts)
            return 'Spostamento post conquista'

        if action_type == 'MANEUVER':
            parts = []
            if info.get('maneuver_strategic'):
                parts.append('Mossa strategica (fronte)')
            elif info.get('maneuver_safe_to_safe'):
                parts.append('Spostamento interno')
            elif info.get('maneuver_away_from_front'):
                parts.append('Ritirata (malus)')
            
            if info.get('left_one_army_src'):
                parts.append('1 armata sorgente')
            if info.get('frontline_stable'):
                parts.append('fronte stabile')
            if info.get('frontline_fortified'):
                parts.append('fronte fortificato')
            
            if parts:
                return ' | '.join(parts)
            return 'OK'

        if info.get('safe_action_bonus'):
            return 'bonus azione sicura'
        return 'OK'

    @staticmethod
    def format_log_line(player_id: int, action: Dict[str, Any], reward: int, reason: str) -> str:
        p_tag = f'P{player_id}'
        a_type = action['type']
        qty_pct = int(action.get('qty', 0) * 100)

        if a_type == 'PASS':
            return f"{p_tag} | {a_type:<16} | -- -> -- | ---- | Rew: {float(reward):>7.2f} | {reason}"

        if a_type == 'REINFORCE':
            return f"{p_tag} | {a_type:<16} | -> {action['dest']:02d}    | x{qty_pct:02d}% | Rew: {float(reward):>7.2f} | {reason}"

        if a_type == 'POST_ATTACK_MOVE':
            return f"{p_tag} | {a_type:<16} | {action['src']:02d} -> {action['dest']:02d} | x{qty_pct:02d}% | Rew: {float(reward):>7.2f} | {reason}"

        return f"{p_tag} | {a_type:<16} | {action['src']:02d} -> {action['dest']:02d} | x{qty_pct:02d}% | Rew: {float(reward):>7.2f} | {reason}"
