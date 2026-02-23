from typing import Dict, Tuple, Any, Optional
from config import Config
from core.board import Board
from core.task import MissionManager
from core.validators import ActionValidator
from core.actions import ActionHandler


class RisikoEnvironment:
    def __init__(self, num_players: Optional[int] = None) -> None:
        configured_players = int(Config.GAME.get("NUM_PLAYERS", 2))
        resolved_players = num_players if num_players is not None else configured_players
        self.num_players: int = max(2, int(resolved_players))

        self.board: Board = Board(num_players=self.num_players)
        self.player_turn: int = 1
        self.current_turn: int = 0
        self.current_phase: str = 'REINFORCE'
        self.has_reinforced: bool = False
        self.armies_to_place: int = 0
        self.armies_to_place_total: int = 0
        self.initial_placement_total: int = 0
        self.initial_placement_step: int = 0
        self.conquest_streak: int = 0
        self.max_armies: int = Config.GAME['MAX_ARMIES_PER_TERRITORY']
        self.setup_placed: Dict[int, int] = {}
        self.player_missions: Dict[int, Dict[str, Any]] = {}
        # Compat legacy (training a 2 player).
        self.p1_setup_placed: int = 0
        self.p2_setup_placed: int = 0
        self.p1_mission: Dict[str, Any] = {}
        self.p2_mission: Dict[str, Any] = {}
        self.consecutive_invalid_moves = 0
        self.pending_attack_src: Optional[int] = None
        self.pending_attack_dest: Optional[int] = None
        self.action_handler = ActionHandler(self.max_armies)
        self.progress_cache: Dict[int, int] = {}
        self.repeat_reinforce: Dict[int, Dict[str, Any]] = {}
        self.repeat_pass: Dict[int, int] = {}
        self.reset()

    def _player_ids(self):
        return range(1, self.num_players + 1)

    def _next_player_id(self, current: int) -> int:
        if self.num_players <= 1:
            return 1
        return (current % self.num_players) + 1

    def get_player_mission(self, player_id: int) -> Dict[str, Any]:
        return self.player_missions.get(player_id, {})

    def _sync_legacy_aliases(self) -> None:
        self.p1_setup_placed = self.setup_placed.get(1, 0)
        self.p2_setup_placed = self.setup_placed.get(2, 0)
        self.p1_mission = self.player_missions.get(1, {})
        self.p2_mission = self.player_missions.get(2, {})

    def _has_reinforce_space(self, player_id: int) -> bool:
        return any(
            t.owner_id == player_id and t.armies < self.max_armies
            for t in self.board.territories.values()
        )

    def _compute_initial_placement(self) -> None:
        num_territories = int(getattr(self.board, "n", 0))
        total_players = max(2, int(self.num_players))
        armies_per_territory = float(Config.GAME.get("INITIAL_PLACEMENT_ARMIES_PER_TERRITORY", 1.0))
        step_divisor = float(Config.GAME.get("INITIAL_PLACEMENT_STEP_DIVISOR", 4.0))

        base = (num_territories / float(total_players)) * armies_per_territory
        self.initial_placement_total = max(1, int(round(base)))
        self.initial_placement_step = max(1, int(round(self.initial_placement_total / step_divisor)))

    def _has_easy_attack(self, player_id: int) -> bool:
        min_ratio = float(Config.NN.get("ATTACK_MIN_RATIO", 1.0))
        min_adv = int(Config.REWARD.get("PASS_ATTACK_MIN_ADVANTAGE", 0))
        for t in self.board.territories.values():
            if t.owner_id != player_id:
                continue
            attacker_armies = t.armies
            if attacker_armies < 3:
                continue
            for n in t.neighbors:
                neigh = self.board.territories[n]
                if neigh.owner_id == player_id:
                    continue
                defender_armies = max(1, neigh.armies)
                if attacker_armies / defender_armies < min_ratio:
                    continue
                if attacker_armies <= defender_armies + min_adv:
                    continue
                return True
        return False

    def reset(self) -> Board:
        self.board.reset(self.num_players)
        self.player_turn = 1
        self.current_turn = 0
        self.current_phase = 'INITIAL_PLACEMENT'
        self.has_reinforced = False
        self._compute_initial_placement()
        self.armies_to_place = self.initial_placement_step
        self.armies_to_place_total = self.initial_placement_step
        self.setup_placed = {p_id: 0 for p_id in self._player_ids()}
        self.player_missions = {}
        for p_id in self._player_ids():
            _, mission = MissionManager.assign_mission()
            self.player_missions[p_id] = mission
        self.conquest_streak = 0
        self.consecutive_invalid_moves = 0
        self.pending_attack_src = None
        self.pending_attack_dest = None
        self.progress_cache = {p_id: 0 for p_id in self._player_ids()}
        self.repeat_reinforce = {
            p_id: {"last": None, "count": 0} for p_id in self._player_ids()
        }
        self.repeat_pass = {p_id: 0 for p_id in self._player_ids()}
        self._sync_legacy_aliases()
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
            self.setup_placed[player_id] = self.setup_placed.get(player_id, 0) + placed
            self._sync_legacy_aliases()

            # Controllo cambio turno / fase
            if self.armies_to_place <= 0:
                # Turno finito per questo player nel setup
                total_needed = self.initial_placement_total
                if all(
                    self.setup_placed.get(p_id, 0) >= total_needed
                    for p_id in self._player_ids()
                ):
                    # Setup finito per entrambi -> Inizia partita vera
                    self.current_phase = 'REINFORCE'
                    self.player_turn = 1
                    self.current_turn = 1
                    self.armies_to_place = 0
                    self.armies_to_place_total = 0
                    self.has_reinforced = False
                else:
                    # Passa turno all'avversario
                    self.player_turn = self._next_player_id(self.player_turn)
                    self.armies_to_place = self.initial_placement_step
                    self.armies_to_place_total = self.initial_placement_step
                    
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
            if self.current_phase == 'REINFORCE':
                if self.armies_to_place > 0 and self._has_reinforce_space(player_id):
                    return Config.REWARD['INVALID_MOVE'], False, {'error': 'Hai ancora truppe da piazzare (regola Risiko: no PASS in REINFORCE)'}
                self.current_phase = 'ATTACK'
                return 0, False, info

            if self.current_phase == 'ATTACK':
                # Transizione gratuita alla manovra
                self.current_phase = 'MANEUVER'
                self.conquest_streak = 0
                if self._has_easy_attack(player_id):
                    reward += Config.REWARD.get('PASS_ATTACK_PENALTY', 0)
                    if reward:
                        info['pass_attack_penalty'] = True
                return reward, False, info

            if self.current_phase == 'POST_ATTACK_MOVE':
                return self._handle_invalid_move('Non puoi passare: devi scegliere quante truppe spostare', info)

            if self.current_phase == 'MANEUVER':
                # Incrementiamo solo qui se decidono di non fare manovre e finire il turno
                self.repeat_pass[player_id] += 1
                self._end_turn()
                reward_p = 0
                if self.repeat_pass[player_id] > 1:
                    # Penalità progressiva
                    multiplier = self.repeat_pass[player_id] - 1
                    pass_penalty = Config.REWARD['PASS_REPEAT_PENALTY'] * multiplier
                    pass_penalty = max(pass_penalty, Config.REWARD.get('PASS_PENALTY_CAP', -100))
                    reward_p = pass_penalty
                    info['repeat_pass_penalty'] = True
                return reward_p, False, info

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
            
            # Reset passività se il piazzamento è avvenuto
            if placed > 0:
                self.repeat_pass[player_id] = 0
                
            info.update(action_extra)
            self.armies_to_place -= placed
            if self.repeat_reinforce[player_id]["count"] > 1:
                multiplier = self.repeat_reinforce[player_id]["count"] - 1
                reward += Config.REWARD['REINFORCE_REPEAT_PENALTY'] * multiplier
                info['repeat_reinforce_penalty'] = True
                info['repeat_reinforce_count'] = self.repeat_reinforce[player_id]["count"]

            if self.armies_to_place <= 0:
                self.current_phase = 'ATTACK'
            return reward, False, info

        elif self.current_phase == 'ATTACK':
            # Reset pass solo se l'attacco è valido (ma non necessariamente vincente)
            # In questo modo, "provare" ad attaccare interrompe la serie di passività
            is_valid, err_msg = ActionValidator.validate_attack(self.board, player_id, action)
            if not is_valid:
                return self._handle_invalid_move(err_msg, info)

            self.repeat_pass[player_id] = 0

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
            is_valid, err_msg = ActionValidator.validate_maneuver(
                self.board,
                player_id,
                action,
                self.max_armies,
            )
            if not is_valid:
                return self._handle_invalid_move(err_msg, info)

            self.repeat_pass[player_id] = 0

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
            elif winner == -1:
                reward += Config.REWARD.get('STALEMATE_PENALTY', -4000)
            elif winner != 0:
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
            return max(0, max_total - current_total)

        return bonus

    def next_turn(self) -> None:
        self.player_turn = self._next_player_id(self.player_turn)
        self.current_turn += 1

    def _end_turn(self) -> None:
        self.has_reinforced = False
        self.armies_to_place = 0
        self.armies_to_place_total = 0
        self._clear_pending_attack_move()
        self.repeat_reinforce = {
            p_id: {"last": None, "count": 0} for p_id in self._player_ids()
        }
        if hasattr(self, '_continent_reward_given'):
            del self._continent_reward_given
        self.next_turn()
        self.current_phase = 'REINFORCE'

    def _clear_pending_attack_move(self) -> None:
        self.pending_attack_src = None
        self.pending_attack_dest = None

    def is_game_over(self) -> Tuple[int, int]:
        alive_players = [
            p_id for p_id in self._player_ids() if self.board.get_player_territories(p_id)
        ]
        if len(alive_players) == 1:
            winner = alive_players[0]
            runner_up = next((p for p in self._player_ids() if p != winner), 0)
            return winner, runner_up

        for p_id in alive_players:
            mission = self.player_missions.get(p_id)
            if mission and MissionManager.check_completion(mission, self.board, p_id):
                runner_up = next((p for p in alive_players if p != p_id), 0)
                return p_id, runner_up

        if self.current_turn >= Config.GAME['MAX_TURNS']:
            return -1, -1
        return 0, 0

