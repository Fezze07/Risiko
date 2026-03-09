from typing import Dict, Any, Tuple
from core.board import Board
from config import Config
from utils.dice import get_random_dice


class ActionHandler:

    # Esegue le azioni di gioco (logica e aggiornamento stato board)
    def __init__(self, max_armies: int):
        self.max_armies = max_armies

    def execute_reinforce(
        self,
        board: Board,
        player_id: int,
        action: Dict[str, Any],
        armies_to_place: int,
    ) -> Tuple[int, int, Dict[str, Any]]:
        t_dest = board.territories[action['dest']]

        qty = action.get('qty', 0.0)
        if qty <= 0 or qty < Config.GAME.get('MIN_REINFORCE_QTY', 0.0):
            return Config.REWARD['INVALID_MOVE'], 0, {}

        to_add = max(1, int(armies_to_place * qty))
        space_in_territory = self.max_armies - t_dest.armies
        to_add = min(to_add, armies_to_place, space_in_territory)

        if to_add <= 0:
            return Config.REWARD['INVALID_MOVE'], 0, {}

        t_dest.armies += to_add

        # Calcolo reward
        is_frontline = any(
            board.territories[n].owner_id != player_id for n in t_dest.neighbors
        )
        has_frontline_any = any(
            t.owner_id == player_id and any(
                board.territories[n].owner_id != player_id for n in t.neighbors
            )
            for t in board.territories.values()
        )

        extra_info = {'is_frontline': is_frontline, 'reinforce_qty': to_add}
        reward = 0

        if not is_frontline:
            if has_frontline_any:
                reward += Config.REWARD.get('REINFORCE_SAFE_PENALTY', -50)
                extra_info['reinforce_safe_penalty'] = True

        # Smart Stacking Reward
        stack_threshold = Config.REWARD.get('REINFORCE_STACK_THRESHOLD', 12)
        armies_before = t_dest.armies - to_add
        if stack_threshold and armies_before >= stack_threshold:
            has_alternative = any(
                t.owner_id == player_id and t.armies < stack_threshold
                for t in board.territories.values()
            )
            excess = t_dest.armies - stack_threshold
            penalty = Config.REWARD.get('REINFORCE_STACK_PENALTY', -25) * excess
            if not has_alternative:
                penalty = int(penalty * 0.2)
                extra_info['inevitable_stacking'] = True
            reward += penalty
            extra_info['stack_penalty'] = True
            extra_info['stack_excess'] = excess

        return reward, to_add, extra_info

    def execute_attack(
        self,
        board: Board,
        player_id: int,
        action: Dict[str, Any],
    ) -> Tuple[int, bool, int, Dict[str, Any]]:
        t_att = board.territories[action['src']]
        t_def = board.territories[action['dest']]
        defender_id = t_def.owner_id

        reward = 0
        conquered = False
        opponent_reward = 0

        n_dice_att = self._get_attack_dice_count(t_att.armies)
        n_dice_def = min(3, t_def.armies)
        rolls_att = get_random_dice(n_dice_att)
        rolls_def = get_random_dice(n_dice_def)
        extra_info: Dict[str, Any] = {
            'rolls_att': rolls_att,
            'rolls_def': rolls_def,
            'defender_id': defender_id,
        }
        couples = min(len(rolls_att), len(rolls_def))

        for i in range(couples):
            if rolls_att[i] > rolls_def[i]:
                t_def.armies -= 1
                reward += Config.REWARD['KILL_ENEMY_ARMY']
            else:
                t_att.armies -= 1
                reward += Config.REWARD['LOSE_ARMY']
                opponent_reward += Config.REWARD['DEFEND_BONUS']

        other_enemies = [
            n for n in t_att.neighbors
            if board.territories[n].owner_id != player_id and n != t_def.id
        ]
        if other_enemies and t_att.armies <= 3:
            max_threat = max((board.territories[n].armies for n in other_enemies), default=0)
            if max_threat >= t_att.armies:
                reward += Config.REWARD['ATTACK_RISK_PENALTY']
                extra_info['risky_attack'] = True
        elif not other_enemies:
            reward += Config.REWARD['AVOID_RISK_BONUS']
            extra_info['avoid_risk'] = True

        if t_att.armies * Config.GAME.get('RISK_RATIO', 2.0) < t_def.armies and not extra_info.get('risky_attack'):
            reward += Config.REWARD['ATTACK_RISK_PENALTY']
            extra_info['risky_attack'] = True
            extra_info['risky_attack_odds'] = True

        if t_def.armies <= 0:
            conquered = True
            old_owner = defender_id
            t_def.owner_id = player_id
            t_def.armies = 0
            extra_info['conquered'] = True

            # Penalità per il difensore: ha perso un territorio
            opponent_reward += Config.REWARD.get('LOSE_TERRITORY', -300)

            # Controlla se l'attaccante ha completato un continente
            for c_name, data in Config.CONTINENTS.items():
                if t_def.id in data['t_ids']:
                    if all(board.territories[tid].owner_id == player_id for tid in data['t_ids']):
                        extra_info['continent_complete'] = True

            # Controlla se il difensore ha perso un continente che possedeva
            for c_name, data in Config.CONTINENTS.items():
                if t_def.id in data['t_ids']:
                    other_ids = [tid for tid in data['t_ids'] if tid != t_def.id]
                    if other_ids and all(board.territories[tid].owner_id == old_owner for tid in other_ids):
                        opponent_reward += Config.REWARD.get('LOSE_CONTINENT', -2000)
                        extra_info['continent_lost'] = True
        else:
            opponent_reward += Config.REWARD.get('DEFEND_HOLD_TERRITORY', 0)
            extra_info['defend_hold'] = True

        return reward, conquered, opponent_reward, extra_info

    def execute_post_attack_move(
        self,
        board: Board,
        player_id: int,
        src_id: int,
        dest_id: int,
        qty: float,
    ) -> Tuple[int, Dict[str, Any]]:
        t_src = board.territories[src_id]
        t_dest = board.territories[dest_id]
        
        movable = t_src.armies - 1
        min_move = min(movable, max(1, Config.GAME.get("MIN_POST_CONQUEST_MOVE", 1)))
        
        amount_ratio = qty
        amount = min_move + int((movable - min_move) * amount_ratio)
        
        reward = 0
        extra_info: Dict[str, Any] = {}
        
        # --- Heuristic di Bilanciamento ---
        ratio = Config.GAME.get('RISK_RATIO', 2.0)
        
        # Calcolo minacce
        enemies_src = [n for n in t_src.neighbors if board.territories[n].owner_id != player_id]
        enemies_dest = [n for n in t_dest.neighbors if board.territories[n].owner_id != player_id]
        
        max_threat_src = max((board.territories[n].armies for n in enemies_src), default=0)
        max_threat_dest = max((board.territories[n].armies for n in enemies_dest), default=0)
        
        # Quante truppe servirebbero per stare "sicuri" (ratio)
        needed_src = int(max_threat_src / ratio) if enemies_src else 0
        needed_dest = int(max_threat_dest / ratio) if enemies_dest else 0
        
        # Le truppe totali che abbiamo a disposizione sono (t_src.armies - 1) + 0 (t_dest.armies è 0 all'inizio della conquista)
        total_available = t_src.armies
        
        # Dobbiamo lasciare almeno 1 in src e muovere almeno min_move in dest
        movable_pool = total_available - 1
        
        # Calcoliamo la quantità desiderata dall'IA/Giocatore
        intent_amount = min_move + int((movable_pool - min_move) * qty)
        
        if needed_src + needed_dest > 0:
            # Distribuzione proporzionale alla minaccia
            weight_dest = needed_dest / (needed_src + needed_dest)
            suggested_move = int(movable_pool * weight_dest)
            
            # Se l'intento si avvicina al suggerimento di sicurezza (+/- 1), diamo un bonus
            if abs(suggested_move - intent_amount) <= 1:
                reward += Config.REWARD.get('AVOID_RISK_BONUS', 10)
                extra_info['balanced_move'] = True
        
        # Ora usiamo SEMPRE l'intento originale, limitato solo dai pool reali
        amount = max(min_move, min(intent_amount, movable_pool))

        extra_info['post_attack_move_qty'] = amount
        extra_info['max_threat_src'] = max_threat_src
        extra_info['max_threat_dest'] = max_threat_dest
        
        t_src.armies -= amount
        t_dest.armies += amount
        
        if not enemies_dest and not enemies_src:
            reward += Config.REWARD.get('AVOID_RISK_BONUS', 35)
            extra_info['avoid_risk'] = True

        return reward, extra_info

    def execute_maneuver(self, board: Board, player_id: int, action: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
        t_src = board.territories[action['src']]
        t_dest = board.territories[action['dest']]

        qty = action.get('qty', 0.0)
        movable = t_src.armies - 1
        amount = max(1, int(movable * qty))
        amount = min(amount, movable)

        src_is_frontline = any(
            board.territories[n].owner_id != player_id for n in t_src.neighbors
        )
        
        t_src.armies -= amount
        t_dest.armies += amount

        dest_is_frontline = any(
            board.territories[n].owner_id != player_id for n in t_dest.neighbors
        )

        extra_info = {
            'src_is_frontline': src_is_frontline,
            'dest_is_frontline': dest_is_frontline,
            'maneuver_qty': amount
        }

        reward = 0
        # Bonus per svuotamento retrovia (se src non era il fronte)
        if not src_is_frontline:
            reward += Config.REWARD.get('MANEUVER_FROM_SAFE_ZONE', 40)
            extra_info['cleared_safe_zone'] = True

        if dest_is_frontline:
            # Bonus strategico: portiamo truppe al fronte
            reward += Config.REWARD.get('MANEUVER_STRATEGIC', 80)
            extra_info['strategic_move'] = True
            
            stack_threshold = Config.REWARD.get('REINFORCE_STACK_THRESHOLD', 0)
            armies_before = t_dest.armies - amount
            is_stacked_before = stack_threshold and armies_before >= stack_threshold
            
            if not is_stacked_before:
                reward = Config.REWARD['MANEUVER_STRATEGIC']
                extra_info['maneuver_strategic'] = True
            else:
                reward = Config.REWARD['MANEUVER_PENALTY']
                extra_info['maneuver_strategic_stacked'] = True
                excess = t_dest.armies - stack_threshold
                reward += Config.REWARD['REINFORCE_STACK_PENALTY'] * excess
                extra_info['stack_penalty'] = True
                extra_info['stack_excess'] = excess
        elif not src_is_frontline:
            reward = Config.REWARD.get('MANEUVER_CORRECTLY', 10)
            extra_info['maneuver_safe_to_safe'] = True
        else:
            reward = Config.REWARD['MANEUVER_PENALTY']
            extra_info['maneuver_away_from_front'] = True

        return reward, extra_info

    @staticmethod
    def _has_enemy_neighbors(board: Board, player_id: int, territory_id: int) -> bool:
        return any(
            board.territories[n].owner_id != player_id 
            for n in board.territories[territory_id].neighbors
        )

    def _get_attack_dice_count(self, armies: int) -> int:
        if armies > 3:
            return 3
        return armies - 1
