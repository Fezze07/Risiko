from typing import Dict, Tuple, Any, Optional
from config import Config
from core.board import Board
from core.task import MissionManager
from core.validators import ActionValidator
from core.actions import ActionHandler


class RisikoEnvironment:
    def __init__(self) -> None:
        self.board: Board = Board()
        self.player_turn: int = 1
        self.current_turn: int = 0
        self.current_phase: str = 'REINFORCE'
        self.has_reinforced: bool = False
        self.armies_to_place: int = 0
        self.armies_to_place_total: int = 0
        self.conquest_streak: int = 0
        self.max_armies: int = Config.GAME['MAX_ARMIES_PER_TERRITORY']
        self.p1_setup_placed: int = 0
        self.p2_setup_placed: int = 0
        self.p1_mission: Dict[str, Any] = {}
        self.p2_mission: Dict[str, Any] = {}
        self.consecutive_invalid_moves = 0
        self.pending_attack_src: Optional[int] = None
        self.pending_attack_dest: Optional[int] = None
        self.action_handler = ActionHandler(self.max_armies)
        self.progress_cache = {1: 0, 2: 0}
        self.repeat_reinforce = {1: {"last": None, "count": 0}, 2: {"last": None, "count": 0}}
        self.repeat_pass = {1: 0, 2: 0}
        self.reset()

    def _has_reinforce_space(self, player_id: int) -> bool:
        return any(
            t.owner_id == player_id and t.armies < self.max_armies
            for t in self.board.territories.values()
        )

    def reset(self) -> Board:
        self.board.reset()
        self.player_turn = 1
        self.current_turn = 0
        self.current_phase = 'INITIAL_PLACEMENT'
        self.has_reinforced = False
        self.armies_to_place = Config.GAME['INITIAL_PLACEMENT_STEP']
        self.armies_to_place_total = Config.GAME['INITIAL_PLACEMENT_STEP']
        self.p1_setup_placed = 0
        self.p2_setup_placed = 0
        self.conquest_streak = 0
        self.consecutive_invalid_moves = 0
        self.pending_attack_src = None
        self.pending_attack_dest = None
        self.progress_cache = {1: 0, 2: 0}
        self.repeat_reinforce = {1: {"last": None, "count": 0}, 2: {"last": None, "count": 0}}
        self.repeat_pass = {1: 0, 2: 0}
        _, self.p1_mission = MissionManager.assign_mission()
        _, self.p2_mission = MissionManager.assign_mission()
        return self.board

    def step(self, action: Dict[str, Any], player_id: int) -> Tuple[int, bool, Dict[str, Any]]:
        reward: int = 0
        done: bool = False
        info: Dict[str, Any] = {'phase_before': self.current_phase}

        if self.current_phase == 'INITIAL_PLACEMENT':
            if action['type'] != 'REINFORCE':
                return self._handle_invalid_move(f"Fase {self.current_phase}: solo REINFORCE permesso", info)

            is_valid, err_msg = ActionValidator.validate_reinforce(
                self.board, player_id, action, self.armies_to_place, self.max_armies
            )
            if not is_valid:
                return self._handle_invalid_move(err_msg, info)

            # Esegui piazzamento (usa la logica standard di rinforzo)
            # Nota: In setup i reward potrebbero essere ridotti o nulli, ma per ora usiamo standard
            reward, placed, action_extra = self.action_handler.execute_reinforce(
                self.board, player_id, action, self.armies_to_place
            )
            info.update(action_extra)
            self.armies_to_place -= placed
            
            if player_id == 1:
                self.p1_setup_placed += placed
            else:
                self.p2_setup_placed += placed

            # Controllo cambio turno / fase
            if self.armies_to_place <= 0:
                # Turno finito per questo player nel setup
                total_needed = Config.GAME['INITIAL_PLACEMENT_TOTAL']
                if self.p1_setup_placed >= total_needed and self.p2_setup_placed >= total_needed:
                    # Setup finito per entrambi -> Inizia partita vera
                    self.current_phase = 'REINFORCE'
                    self.player_turn = 1
                    self.current_turn = 1
                    self.armies_to_place = 0
                    self.armies_to_place_total = 0
                    self.has_reinforced = False
                else:
                    # Passa turno all'avversario
                    self.player_turn = 3 - self.player_turn # 1->2, 2->1
                    self.armies_to_place = Config.GAME['INITIAL_PLACEMENT_STEP']
                    self.armies_to_place_total = Config.GAME['INITIAL_PLACEMENT_STEP']
                    
            return reward, done, info

        if self.current_phase == 'REINFORCE' and not self.has_reinforced:
            self.armies_to_place = self._get_available_bonus(player_id)
            self.armies_to_place_total = self.armies_to_place
            self.has_reinforced = True

            if self.armies_to_place < 0:
                reward += Config.REWARD['ARMY_LIMIT_PENALTY']
                info['error'] = 'Limite armate superato (Global Max)!'
                self.armies_to_place = 0

            if self.armies_to_place <= 0:
                self.current_phase = 'ATTACK'
                return reward, False, info

            if not self._has_reinforce_space(player_id):
                self.armies_to_place = 0
                self.current_phase = 'ATTACK'
                info['no_reinforce_space'] = True
                return reward, False, info

        if action['type'] == 'PASS':
            self.repeat_pass[player_id] += 1
            if self.current_phase == 'REINFORCE':
                if self.armies_to_place > 0 and self._has_reinforce_space(player_id):
                    return Config.REWARD['INVALID_MOVE'], False, {'error': 'Hai ancora truppe da piazzare'}
                self.current_phase = 'ATTACK'
                if self.repeat_pass[player_id] > 1:
                    reward += Config.REWARD['PASS_REPEAT_PENALTY']
                    info['repeat_pass_penalty'] = True
                return reward, False, info

            if self.current_phase == 'ATTACK':
                self.current_phase = 'MANEUVER'
                self.conquest_streak = 0
                if self.repeat_pass[player_id] > 1:
                    reward += Config.REWARD['PASS_REPEAT_PENALTY']
                    info['repeat_pass_penalty'] = True
                return reward, False, info

            if self.current_phase == 'POST_ATTACK_MOVE':
                return self._handle_invalid_move('Non puoi passare: devi scegliere quante truppe spostare', info)

            if self.current_phase == 'MANEUVER':
                self._end_turn()
                if self.repeat_pass[player_id] > 1:
                    reward += Config.REWARD['PASS_REPEAT_PENALTY']
                    info['repeat_pass_penalty'] = True
                return reward, False, info

        if action['type'] != self.current_phase:
            invalid_reward = self._get_invalid_move_reward()
            return invalid_reward, False, {
                'error': f"Mossa {action['type']} non permessa in {self.current_phase}"
            }

        if self.current_phase == 'REINFORCE':
            is_valid, err_msg = ActionValidator.validate_reinforce(
                self.board,
                player_id,
                action,
                self.armies_to_place,
                self.max_armies,
            )
            if not is_valid:
                return self._handle_invalid_move(err_msg, info)

            self.consecutive_invalid_moves = 0
            self.repeat_pass[player_id] = 0
            last = self.repeat_reinforce[player_id]["last"]
            if action.get("dest") == last:
                self.repeat_reinforce[player_id]["count"] += 1
            else:
                self.repeat_reinforce[player_id]["last"] = action.get("dest")
                self.repeat_reinforce[player_id]["count"] = 1
            original_qty = action.get('qty', 0.0)
            if original_qty > 0 and self.armies_to_place_total > 0 and self.armies_to_place > 0:
                requested = max(1, int(self.armies_to_place_total * original_qty))
                if requested > self.armies_to_place:
                    requested = self.armies_to_place
                action['qty'] = min(1.0, requested / self.armies_to_place)
            reward, placed, action_extra = self.action_handler.execute_reinforce(
                self.board,
                player_id,
                action,
                self.armies_to_place,
            )
            info.update(action_extra)
            self.armies_to_place -= placed
            if self.repeat_reinforce[player_id]["count"] > 1:
                multiplier = self.repeat_reinforce[player_id]["count"] - 1
                reward += Config.REWARD['REINFORCE_REPEAT_PENALTY'] * multiplier
                info['repeat_reinforce_penalty'] = True
                info['repeat_reinforce_count'] = self.repeat_reinforce[player_id]["count"]

            if self.has_reinforced and not hasattr(self, '_continent_reward_given'):
                for _, data in Config.CONTINENTS.items():
                    if all(self.board.territories[t_id].owner_id == player_id for t_id in data['t_ids']):
                        reward += Config.REWARD['HOLD_CONTINENT']
                        self._continent_reward_given = True
                        info['continent_held'] = True
                        break

            if self.armies_to_place <= 0:
                self.current_phase = 'ATTACK'

        elif self.current_phase == 'ATTACK':
            self.repeat_pass[player_id] = 0
            is_valid, err_msg = ActionValidator.validate_attack(self.board, player_id, action)
            if not is_valid:
                return self._handle_invalid_move(err_msg, info)

            self.consecutive_invalid_moves = 0
            combat_reward, conquered, opponent_reward, extra = self.action_handler.execute_attack(
                self.board,
                player_id,
                action,
            )
            reward = combat_reward
            if opponent_reward != 0:
                info['opponent_reward'] = opponent_reward
            info.update(extra)

            if conquered:
                self.conquest_streak += 1
                reward += Config.REWARD['CONQUER_TERRITORY'] * min(
                    self.conquest_streak,
                    Config.REWARD['CONQUEST_STREAK_CAP'],
                )
                if extra.get('continent_complete'):
                    reward += Config.REWARD['CONQUER_CONTINENT']

                self.pending_attack_src = action['src']
                self.pending_attack_dest = action['dest']
                self.current_phase = 'POST_ATTACK_MOVE'
                info['post_attack_move_required'] = True

        elif self.current_phase == 'POST_ATTACK_MOVE':
            self.repeat_pass[player_id] = 0
            if self.pending_attack_src is None or self.pending_attack_dest is None:
                return self._handle_invalid_move('Stato post conquista non valido', info)

            # Per logging coerente, agganciamo la mossa ai territori reali
            action['src'] = self.pending_attack_src
            action['dest'] = self.pending_attack_dest

            is_valid, err_msg = ActionValidator.validate_post_attack_move(
                self.board,
                player_id,
                self.pending_attack_src,
                self.pending_attack_dest,
            )
            if not is_valid:
                return self._handle_invalid_move(err_msg, info)

            self.consecutive_invalid_moves = 0
            move_reward, move_info = self.action_handler.execute_post_attack_move(
                self.board,
                player_id,
                self.pending_attack_src,
                self.pending_attack_dest,
                action.get('qty', 1.0),
            )
            reward += move_reward
            info.update(move_info)
            info['post_attack_move_done'] = True
            self._clear_pending_attack_move()
            self.current_phase = 'ATTACK'

        elif self.current_phase == 'MANEUVER':
            self.repeat_pass[player_id] = 0
            is_valid, err_msg = ActionValidator.validate_maneuver(
                self.board,
                player_id,
                action,
                self.max_armies,
            )
            if not is_valid:
                return self._handle_invalid_move(err_msg, info)

            self.consecutive_invalid_moves = 0
            reward, action_extra = self.action_handler.execute_maneuver(self.board, player_id, action)
            info.update(action_extra)
            t_src = self.board.territories[action['src']]
            if t_src.armies == 1 and any(
                self.board.territories[n].owner_id != player_id for n in t_src.neighbors
            ):
                info['left_one_army_src'] = True
            reward += self._get_frontline_stability_reward(player_id, info)
            self._end_turn()

        reward += self._get_safe_action_bonus(action, info)
        reward += self._get_progress_reward(player_id, info)

        winner, _ = self.is_game_over()
        if winner != 0:
            done = True
            if winner == player_id:
                reward += Config.REWARD['WIN']
            elif winner != -1:
                reward += Config.REWARD['LOSS']

        return reward, done, info

    def _handle_invalid_move(self, err_msg: str, info: Dict[str, Any]) -> Tuple[int, bool, Dict[str, Any]]:
        self.consecutive_invalid_moves += 1
        reward = self._get_invalid_move_reward()

        if self.consecutive_invalid_moves >= 10:
            reward = Config.REWARD['CONSECUTIVE_INVALID_MOVE']
            info['error'] = f"TROPPI ERRORI ({self.consecutive_invalid_moves}): {err_msg}. Turno gestito forzatamente."
            self.consecutive_invalid_moves = 0

            if self.current_phase == 'REINFORCE':
                self.current_phase = 'ATTACK'
            elif self.current_phase == 'ATTACK':
                self.current_phase = 'MANEUVER'
            elif self.current_phase == 'POST_ATTACK_MOVE':
                if self.pending_attack_src is not None and self.pending_attack_dest is not None:
                    forced_reward, forced_info = self.action_handler.execute_post_attack_move(
                        self.board,
                        self.player_turn,
                        self.pending_attack_src,
                        self.pending_attack_dest,
                        1.0,
                    )
                    reward += forced_reward
                    info.update(forced_info)
                    info['forced_post_attack_move'] = True
                self._clear_pending_attack_move()
                self.current_phase = 'ATTACK'
            elif self.current_phase == 'MANEUVER':
                self._end_turn()

            return reward, False, info

        return reward, False, {'error': err_msg}

    def _get_invalid_move_reward(self) -> int:
        if self.current_phase in ('ATTACK', 'POST_ATTACK_MOVE'):
            return Config.REWARD['INVALID_MOVE_ATTACK']
        return Config.REWARD['INVALID_MOVE']

    def _get_frontline_stability_reward(self, player_id: int, info: Dict[str, Any]) -> int:
        frontline = [
            t for t in self.board.territories.values()
            if t.owner_id == player_id and any(
                self.board.territories[n].owner_id != player_id for n in t.neighbors
            )
        ]
        if not frontline:
            return 0

        armies = [t.armies for t in frontline]
        risky_front = any(a <= 1 for a in armies)
        bonus = 0

        if not risky_front:
            bonus += Config.REWARD['FRONTLINE_STABLE_BONUS']
            info['frontline_stable'] = True

        if min(armies) >= 3:
            bonus += Config.REWARD['FRONTLINE_FORTIFIED_BONUS']
            info['frontline_fortified'] = True

        return bonus

    def _get_safe_action_bonus(self, action: Dict[str, Any], info: Dict[str, Any]) -> int:
        a_type = action.get('type')
        if a_type in ('PASS', 'MANEUVER'):
            return 0
        
        # Rinforzo: Bonus solo se il territorio è veramente sicuro (non di confine)
        if a_type == 'REINFORCE' and info.get('is_frontline'):
            return 0

        if 'error' in info:
            return 0
        if info.get('requires_post_attack_move'):
            return 0
        if info.get('risky_attack') or info.get('risky_attack_conquer'):
            return 0
        if info.get('left_one_army_src') or info.get('left_one_army_dest'):
            return 0
        if action.get('type') in ('ATTACK', 'POST_ATTACK_MOVE') and not info.get('avoid_risk'):
            return 0
        info['safe_action_bonus'] = True
        return Config.REWARD['VALID_SAFE_ACTION_BONUS']

    def _get_progress_reward(self, player_id: int, info: Dict[str, Any]) -> int:
        if 'error' in info:
            return 0

        lands = len(self.board.get_player_territories(player_id))
        territory_ratio = lands / float(self.board.n) if self.board.n else 0.0
        territory_reward = int(territory_ratio * Config.REWARD['PROGRESS_TERRITORY_SCALE'])

        continent_ratio_sum = 0.0
        for _, data in Config.CONTINENTS.items():
            owned = sum(
                1
                for t_id in data['t_ids']
                if self.board.territories[t_id].owner_id == player_id
            )
            continent_ratio_sum += owned / float(len(data['t_ids']))
        continent_reward = int(continent_ratio_sum * Config.REWARD['PROGRESS_CONTINENT_SCALE'])

        total = territory_reward + continent_reward
        previous = self.progress_cache.get(player_id, 0)
        delta = total - previous
        self.progress_cache[player_id] = total
        if delta != 0:
            info['progress_reward'] = delta
        return delta

    def _get_available_bonus(self, player_id: int) -> int:
        lands = len(self.board.get_player_territories(player_id))
        bonus = max(Config.GAME['MIN_BONUS'], lands // Config.GAME['BONUS_ARMIES_DIVISOR'])
        for _, data in Config.CONTINENTS.items():
            if all(self.board.territories[t_id].owner_id == player_id for t_id in data['t_ids']):
                bonus += data['bonus']

        current_total = sum(t.armies for t in self.board.territories.values() if t.owner_id == player_id)
        max_total = Config.GAME['MAX_TOTAL_ARMIES']

        if current_total + bonus > max_total:
            return max_total - (current_total + bonus)

        return bonus

    def next_turn(self) -> None:
        self.player_turn = 2 if self.player_turn == 1 else 1
        self.current_turn += 1

    def _end_turn(self) -> None:
        self.has_reinforced = False
        self.armies_to_place = 0
        self.armies_to_place_total = 0
        self._clear_pending_attack_move()
        self.repeat_reinforce = {1: {"last": None, "count": 0}, 2: {"last": None, "count": 0}}
        if hasattr(self, '_continent_reward_given'):
            del self._continent_reward_given
        self.next_turn()
        self.current_phase = 'REINFORCE'

    def _clear_pending_attack_move(self) -> None:
        self.pending_attack_src = None
        self.pending_attack_dest = None

    def is_game_over(self) -> Tuple[int, int]:
        p1_lands = self.board.get_player_territories(1)
        p2_lands = self.board.get_player_territories(2)
        if not p2_lands:
            return 1, 2
        if not p1_lands:
            return 2, 1

        if MissionManager.check_completion(self.p1_mission, self.board, 1):
            return 1, 2
        if MissionManager.check_completion(self.p2_mission, self.board, 2):
            return 2, 1

        if self.current_turn >= Config.GAME['MAX_TURNS']:
            return -1, -1
        return 0, 0
