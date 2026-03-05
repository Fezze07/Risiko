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
        self.consecutive_invalid_moves = 0
        self.pending_attack_src: Optional[int] = None
        self.pending_attack_dest: Optional[int] = None
        self.action_handler = ActionHandler(self.max_armies)
        self.progress_cache: Dict[int, int] = {}
        self.repeat_reinforce: Dict[int, Dict[str, Any]] = {}
        self.repeat_pass: Dict[int, int] = {}
        self.consecutive_passive_turns: Dict[int, int] = {}
        self.has_attacked_this_turn: bool = False
        
        self.reset()

    def _player_ids(self):
        return range(1, self.num_players + 1)

    def _next_player_id(self, current: int) -> int:
        return (current % self.num_players) + 1

    def get_player_mission(self, player_id: int) -> Dict[str, Any]:
        return self.player_missions.get(player_id, {})

    def _has_reinforce_space(self, player_id: int) -> bool:
        return any(t.owner_id == player_id and t.armies < self.max_armies for t in self.board.territories.values())

    def _compute_initial_placement(self) -> None:
        num_territories = getattr(self.board, "n", 42)
        total_players = self.num_players
        armies_per_territory = float(Config.GAME.get("INITIAL_PLACEMENT_ARMIES_PER_TERRITORY", 1.5))
        step_divisor = float(Config.GAME.get("INITIAL_PLACEMENT_STEP_DIVISOR", 4.0))
        base = (num_territories / float(total_players)) * armies_per_territory
        self.initial_placement_total = max(1, int(round(base)))
        self.initial_placement_step = max(1, int(round(self.initial_placement_total / step_divisor)))


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
        self.repeat_reinforce = {p_id: {"last": None, "count": 0} for p_id in self._player_ids()}
        self.repeat_pass = {p_id: 0 for p_id in self._player_ids()}
        self.consecutive_passive_turns = {p_id: 0 for p_id in self._player_ids()}
        self.has_attacked_this_turn = False
        # Initialize progress cache with first state
        for p_id in self._player_ids():
            self._get_progress_reward(p_id, {})
        return self.board

    def step(self, action: Dict[str, Any], player_id: int) -> Tuple[int, bool, Dict[str, Any]]:
        reward: int = 0
        done: bool = False
        info: Dict[str, Any] = {'phase_before': self.current_phase}

        # --- SETUP: INITIAL PLACEMENT ---
        if self.current_phase == 'INITIAL_PLACEMENT':
            if action['type'] != 'REINFORCE':
                return self._handle_invalid_move(f"Fase {self.current_phase}: solo REINFORCE permesso", info)
            is_valid, err_msg = ActionValidator.validate_reinforce(self.board, player_id, action, self.armies_to_place, self.max_armies)
            if not is_valid: return self._handle_invalid_move(err_msg, info)

            reward, placed, a_extra = self.action_handler.execute_reinforce(self.board, player_id, action, self.armies_to_place)
            info.update(a_extra)
            self.armies_to_place -= placed
            self.setup_placed[player_id] += placed

            if self.armies_to_place <= 0:
                if all(self.setup_placed[p] >= self.initial_placement_total for p in self._player_ids()):
                    self.current_phase, self.player_turn, self.current_turn = 'REINFORCE', 1, 1
                    self._start_reinforce_phase(1)
                else:
                    self.player_turn = self._next_player_id(self.player_turn)
                    self.armies_to_place = self.initial_placement_step
            return self._finalize_step(reward, done, info, player_id, action)

        # --- ACTION: PASS ---
        if action['type'] == 'PASS':
            if self.current_phase == 'REINFORCE':
                if self.armies_to_place > 0 and self._has_reinforce_space(player_id):
                    return self._handle_invalid_move('Hai ancora truppe da piazzare', info)
                self.current_phase = 'ATTACK'
            elif self.current_phase == 'ATTACK':
                if not self.has_attacked_this_turn:
                    self.consecutive_passive_turns[player_id] += 1
                    idx = self.consecutive_passive_turns[player_id]
                    base_penalty = Config.REWARD.get('PASSIVE_TURN_PENALTY', -10)
                    pass_penalty = base_penalty * (2 ** (idx - 1))
                    pass_penalty = max(pass_penalty, -10000)
                    reward += pass_penalty
                    info['passive_turn_penalty'] = pass_penalty
                else:
                    self.consecutive_passive_turns[player_id] = 0
                self.current_phase, self.conquest_streak = 'MANEUVER', 0
            elif self.current_phase == 'MANEUVER':
                self.repeat_pass[player_id] += 1
                if self.repeat_pass[player_id] > 1:
                    pass_penalty = Config.REWARD.get('PASS_REPEAT_PENALTY', -10) * (self.repeat_pass[player_id] - 1)
                    reward += max(pass_penalty, Config.REWARD.get('PASS_PENALTY_CAP', -300))
                    info['repeat_pass_penalty'] = True
                self._end_turn()
            elif self.current_phase == 'POST_ATTACK_MOVE':
                return self._handle_invalid_move('Devi scegliere quante truppe spostare', info)
            return self._finalize_step(reward, done, info, player_id, action)

        # --- ACTION: REINFORCE ---
        if self.current_phase == 'REINFORCE':
            is_valid, err_msg = ActionValidator.validate_reinforce(self.board, player_id, action, self.armies_to_place, self.max_armies)
            if not is_valid: return self._handle_invalid_move(err_msg, info)
            self.consecutive_invalid_moves = 0
            if action.get("dest") == self.repeat_reinforce[player_id]["last"]: self.repeat_reinforce[player_id]["count"] += 1
            else: self.repeat_reinforce[player_id]["last"], self.repeat_reinforce[player_id]["count"] = action.get("dest"), 1
            if self.armies_to_place > 0:
                req = max(1, int(self.armies_to_place_total * action.get('qty', 0.0)))
                action['qty'] = min(1.0, min(req, self.armies_to_place) / self.armies_to_place)
            r_r, placed, e_r = self.action_handler.execute_reinforce(self.board, player_id, action, self.armies_to_place)
            reward += r_r
            info.update(e_r)
            self.armies_to_place -= placed
            if placed > 0: self.repeat_pass[player_id] = 0
            if self.repeat_reinforce[player_id]["count"] > 1:
                reward += Config.REWARD.get('REINFORCE_REPEAT_PENALTY', -30) * (self.repeat_reinforce[player_id]["count"] - 1)
                info['repeat_reinforce_penalty'] = True
            if self.armies_to_place <= 0: self.current_phase = 'ATTACK'
            return self._finalize_step(reward, done, info, player_id, action)

        # --- ACTION: ATTACK ---
        elif self.current_phase == 'ATTACK':
            is_valid, err_msg = ActionValidator.validate_attack(self.board, player_id, action)
            if not is_valid: return self._handle_invalid_move(err_msg, info)
            self.repeat_pass[player_id], self.consecutive_invalid_moves = 0, 0
            self.has_attacked_this_turn = True
            self.consecutive_passive_turns[player_id] = 0
            a_r, conquered, o_r, a_e = self.action_handler.execute_attack(self.board, player_id, action)
            reward += a_r
            if o_r != 0: info['opponent_reward'] = o_r
            info.update(a_e)
            if conquered:
                self.conquest_streak += 1
                reward += Config.REWARD.get('CONQUER_TERRITORY', 120) * min(self.conquest_streak, Config.REWARD.get('CONQUEST_STREAK_CAP', 3))
                if a_e.get('continent_complete'): reward += Config.REWARD.get('CONQUER_CONTINENT', 150)
                self.pending_attack_src, self.pending_attack_dest = action['src'], action['dest']
                self.current_phase, info['post_attack_move_required'] = 'POST_ATTACK_MOVE', True
            return self._finalize_step(reward, done, info, player_id, action)

        # --- ACTION: POST_ATTACK_MOVE ---
        elif self.current_phase == 'POST_ATTACK_MOVE':
            self.repeat_pass[player_id] = 0
            if self.pending_attack_src is None: return self._handle_invalid_move('Stato post conquista non valido', info)
            action['src'], action['dest'] = self.pending_attack_src, self.pending_attack_dest
            is_valid, err_msg = ActionValidator.validate_post_attack_move(self.board, player_id, action['src'], action['dest'])
            if not is_valid: return self._handle_invalid_move(err_msg, info)
            self.consecutive_invalid_moves = 0
            m_r, m_i = self.action_handler.execute_post_attack_move(self.board, player_id, action['src'], action['dest'], action.get('qty', 1.0))
            reward += m_r
            info.update(m_i)
            self._clear_pending_attack_move()
            self.current_phase = 'ATTACK'
            return self._finalize_step(reward, done, info, player_id, action)

        # --- ACTION: MANEUVER ---
        elif self.current_phase == 'MANEUVER':
            is_valid, err_msg = ActionValidator.validate_maneuver(self.board, player_id, action, self.max_armies)
            if not is_valid: return self._handle_invalid_move(err_msg, info)
            self.repeat_pass[player_id], self.consecutive_invalid_moves = 0, 0
            m_r, m_e = self.action_handler.execute_maneuver(self.board, player_id, action)
            reward += m_r
            if self.board.territories[action['src']].armies == 1:
                if any(self.board.territories[n].owner_id != player_id for n in self.board.territories[action['src']].neighbors):
                    info['left_one_army_src'] = True
            reward += self._get_frontline_stability_reward(player_id, info)
            info.update(m_e)
            self._end_turn()
            return self._finalize_step(reward, done, info, player_id, action)

        return self._finalize_step(reward, done, info, player_id, action)

    def _finalize_step(self, reward: int, done: bool, info: Dict[str, Any], player_id: int, action: Dict[str, Any]) -> Tuple[int, bool, Dict[str, Any]]:
        reward += self._get_safe_action_bonus(action, info)
        reward += self._get_progress_reward(player_id, info)
        lp = Config.REWARD.get('GAME_LENGTH_PENALTY', -10)
        is_attack_action = action.get('type') == 'ATTACK'
        if lp != 0 and is_attack_action:
            reward += lp
            info['game_length_penalty'] = lp
        winner, _ = self.is_game_over()
        if winner != 0:
            done = True
            if winner == player_id: reward += Config.REWARD.get('WIN', 6000)
            elif winner == -1: reward += Config.REWARD.get('STALEMATE_PENALTY', -4000)
            else: reward += Config.REWARD.get('LOSS', -8000)
        return int(reward), done, info

    def _handle_invalid_move(self, err_msg: str, info: Dict[str, Any]) -> Tuple[int, bool, Dict[str, Any]]:
        self.consecutive_invalid_moves += 1
        reward = Config.REWARD.get('INVALID_MOVE_ATTACK', -200) if self.current_phase in ('ATTACK', 'POST_ATTACK_MOVE') else Config.REWARD.get('INVALID_MOVE', -100)
        if self.consecutive_invalid_moves >= 10:
            reward, self.consecutive_invalid_moves = Config.REWARD.get('CONSECUTIVE_INVALID_MOVE', -500), 0
            info['error'] = f"TROPPI ERRORI ({self.consecutive_invalid_moves}): {err_msg}. Turno gestito forzatamente."
            if self.current_phase == 'REINFORCE': self.current_phase = 'ATTACK'
            elif self.current_phase == 'ATTACK': self.current_phase = 'MANEUVER'
            elif self.current_phase == 'POST_ATTACK_MOVE':
                if self.pending_attack_src is not None:
                    fr, fi = self.action_handler.execute_post_attack_move(self.board, self.player_turn, self.pending_attack_src, self.pending_attack_dest, 1.0)
                    reward += fr
                    info.update(fi)
                self._clear_pending_attack_move()
                self.current_phase = 'ATTACK'
            elif self.current_phase == 'MANEUVER':
                self._end_turn()
            return reward, False, info
        return reward, False, {'error': err_msg}

    def _get_frontline_stability_reward(self, player_id: int, info: Dict[str, Any]) -> int:
        frontline = [t for t in self.board.territories.values() if t.owner_id == player_id and any(self.board.territories[n].owner_id != player_id for n in t.neighbors)]
        if not frontline: return 0
        armies = [t.armies for t in frontline]
        bonus = 0
        if min(armies) > 1:
            bonus += Config.REWARD.get('FRONTLINE_STABLE_BONUS', 0)
            info['frontline_stable'] = True
        if min(armies) >= 3:
            bonus += Config.REWARD.get('FRONTLINE_FORTIFIED_BONUS', 0)
            info['frontline_fortified'] = True
        return bonus

    def _get_safe_action_bonus(self, action: Dict[str, Any], info: Dict[str, Any]) -> int:
        a_type = action.get('type')
        if a_type in ('PASS', 'MANEUVER') or 'error' in info: return 0
        if info.get('requires_post_attack_move') or info.get('risky_attack') or info.get('left_one_army_src'): return 0
        if a_type in ('ATTACK', 'POST_ATTACK_MOVE') and not info.get('avoid_risk'): return 0
        if a_type == 'REINFORCE' and info.get('is_frontline'): return 0
        info['safe_action_bonus'] = True
        return Config.REWARD.get('VALID_SAFE_ACTION_BONUS', 0)

    def _get_progress_reward(self, player_id: int, info: Dict[str, Any]) -> int:
        if 'error' in info: return 0
        lands = len(self.board.get_player_territories(player_id))
        t_reward = int((lands / float(self.board.n)) * Config.REWARD.get('PROGRESS_TERRITORY_SCALE', 0)) if self.board.n else 0
        c_sum = 0.0
        for _, data in Config.CONTINENTS.items():
            owned = sum(1 for t_id in data['t_ids'] if self.board.territories[t_id].owner_id == player_id)
            c_sum += owned / float(len(data['t_ids']))
        c_reward = int(c_sum * Config.REWARD.get('PROGRESS_CONTINENT_SCALE', 0))
        total = t_reward + c_reward
        delta = total - self.progress_cache.get(player_id, 0)
        self.progress_cache[player_id] = total
        if delta != 0: info['progress_reward'] = delta
        return delta

    def _get_available_bonus(self, player_id: int) -> int:
        lands = len(self.board.get_player_territories(player_id))
        bonus = max(Config.GAME['MIN_BONUS'], lands // Config.GAME['BONUS_ARMIES_DIVISOR'])
        for _, data in Config.CONTINENTS.items():
            if all(self.board.territories[t_id].owner_id == player_id for t_id in data['t_ids']): bonus += data['bonus']
        curr = sum(t.armies for t in self.board.territories.values() if t.owner_id == player_id)
        return max(0, min(bonus, Config.GAME['MAX_TOTAL_ARMIES'] - curr))

    def next_turn(self) -> None:
        self.player_turn, self.current_turn = self._next_player_id(self.player_turn), self.current_turn + 1

    def _start_reinforce_phase(self, player_id: int) -> None:
        self._get_progress_reward(player_id, {})
        self.armies_to_place = self._get_available_bonus(player_id)
        self.armies_to_place_total, self.has_reinforced = self.armies_to_place, True
        if self.armies_to_place <= 0 or not self._has_reinforce_space(player_id):
            self.armies_to_place, self.current_phase = 0, 'ATTACK'

    def _end_turn(self) -> None:
        self.has_attacked_this_turn = False
        self.has_reinforced, self.armies_to_place = False, 0
        self.repeat_reinforce = {p_id: {"last": None, "count": 0} for p_id in self._player_ids()}
        if hasattr(self, '_continent_reward_given'): del self._continent_reward_given
        self.next_turn()
        self.current_phase = 'REINFORCE'
        self._start_reinforce_phase(self.player_turn)

    def _clear_pending_attack_move(self) -> None:
        self.pending_attack_src = self.pending_attack_dest = None

    def is_game_over(self) -> Tuple[int, int]:
        alive = [p for p in self._player_ids() if len(self.board.get_player_territories(p)) > 0]
        if len(alive) == 1: return alive[0], next((p for p in self._player_ids() if p != alive[0]), 0)
        for p in alive:
            if MissionManager.check_completion(self.player_missions.get(p), self.board, p): return p, next((p2 for p2 in alive if p2 != p), 0)
        return (-1, -1) if self.current_turn >= Config.GAME['MAX_TURNS'] else (0, 0)
