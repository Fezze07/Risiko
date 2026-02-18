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

        extra_info = {'is_frontline': is_frontline}

        if is_frontline:
            reward = to_add * Config.REWARD['REINFORCE_STRATEGIC_MULT']
        else:
            reward = to_add * Config.REWARD['REINFORCE_SAFE_MULT']
            if has_frontline_any:
                reward += Config.REWARD.get('REINFORCE_SAFE_PENALTY', -50)
                extra_info['reinforce_safe_penalty'] = True

        # Penalizza stacking su territori già molto pieni (progressivo)
        stack_threshold = Config.REWARD.get('REINFORCE_STACK_THRESHOLD', 0)
        armies_before = t_dest.armies - to_add
        if stack_threshold and armies_before >= stack_threshold:
            excess = t_dest.armies - stack_threshold
            reward += Config.REWARD['REINFORCE_STACK_PENALTY'] * excess
            extra_info['stack_penalty'] = True
            extra_info['stack_excess'] = excess

        return reward, to_add, extra_info

    def execute_attack(
        self,
        board: Board,
        player_id: int,
        action: Dict[str, Any],
    ) -> Tuple[int, bool, int, Dict[str, Any]]:
        # Esegue solo il combattimento. Lo spostamento post-conquista e' separato.
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
            'rolls_def': rolls_def
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

        if t_def.armies <= 0:
            conquered = True
            t_def.owner_id = player_id
            t_def.armies = 0  # Verranno mosse dopo
            
            # Check se il continente è ora completo
            continent_complete = False
            for c_name, data in Config.CONTINENTS.items():
                if t_def.id in data['t_ids']:
                    if all(board.territories[tid].owner_id == player_id for tid in data['t_ids']):
                        continent_complete = True
                        extra_info['continent_complete'] = True
            
            # Check se l'avversario ha perso un continente
            for c_name, data in Config.CONTINENTS.items():
                if t_def.id in data['t_ids']:
                    # Se prima l'avversario aveva tutto e ora abbiamo questo pezzo...
                    # (In realtà il check è più semplice: abbiamo appena conquistato, 
                    # quindi lui NON ha più il continente)
                    pass 

        if t_att.armies == 1 and self._has_enemy_neighbors(board, player_id, t_att.id):
            reward += Config.REWARD['LEAVE_ONE_ARMY_PENALTY']
            extra_info['left_one_army_src'] = True

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
        
        # Minimo 1 o quanto richiesto dal config
        movable = t_src.armies - 1
        min_move = min(movable, max(1, Config.GAME.get("MIN_POST_CONQUEST_MOVE", 1)))
        
        # Quante ne sposta effettivamente l'IA (qty è tra 0 e 1)
        # Se qty è 1.0 sposta tutto il possibile (movable)
        # Se qty è 0.0 sposta il minimo (min_move)
        amount_ratio = qty
        amount = min_move + int((movable - min_move) * amount_ratio)
        amount = max(min_move, min(amount, movable))
        
        t_src.armies -= amount
        t_dest.armies += amount
        
        reward = 0
        extra_info = {'post_attack_move_qty': amount}
        
        # Check se il nuovo territorio è rischioso
        enemies = [n for n in t_dest.neighbors if board.territories[n].owner_id != player_id]
        if enemies:
            max_threat = max((board.territories[n].armies for n in enemies), default=0)
            if max_threat >= t_dest.armies:
                reward += Config.REWARD['ATTACK_RISK_PENALTY']
                extra_info['risky_attack_conquer'] = True
        else:
            reward += Config.REWARD['AVOID_RISK_BONUS']
            extra_info['avoid_risk'] = True

        if t_src.armies == 1 and self._has_enemy_neighbors(board, player_id, t_src.id):
            reward += Config.REWARD['LEAVE_ONE_ARMY_PENALTY']
            extra_info['left_one_army_src'] = True
            
        if t_dest.armies == 1 and enemies:
            reward += Config.REWARD['LEAVE_ONE_ARMY_PENALTY']
            extra_info['left_one_army_dest'] = True

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
            'dest_is_frontline': dest_is_frontline
        }

        if dest_is_frontline:
            # Spostamento verso il fronte: premiato solo se non andiamo in over-stacking
            stack_threshold = Config.REWARD.get('REINFORCE_STACK_THRESHOLD', 0)
            armies_before = t_dest.armies - amount
            is_stacked_before = stack_threshold and armies_before >= stack_threshold
            
            if not is_stacked_before:
                reward = Config.REWARD['MANEUVER_STRATEGIC']
                extra_info['maneuver_strategic'] = True
            else:
                # Se era già pieno e aggiungiamo ancora, niente bonus e applichiamo malus progressivo
                reward = Config.REWARD['MANEUVER_PENALTY']
                extra_info['maneuver_strategic_stacked'] = True
                excess = t_dest.armies - stack_threshold
                reward += Config.REWARD['REINFORCE_STACK_PENALTY'] * excess
                extra_info['stack_penalty'] = True
                extra_info['stack_excess'] = excess
        elif not src_is_frontline:
            # Safe -> Safe: Inutile spostamento interno
            reward = Config.REWARD['REINFORCE_ARMY']
            extra_info['maneuver_safe_to_safe'] = True
        else:
            # Front -> Safe: Mossa sbagliata (ritirata non necessaria), penalità
            reward = Config.REWARD['MANEUVER_PENALTY']
            extra_info['maneuver_away_from_front'] = True

        if t_src.armies == 1 and src_is_frontline:
            reward += Config.REWARD['LEAVE_ONE_ARMY_PENALTY']
            extra_info['left_one_army_src'] = True

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
