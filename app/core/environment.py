from typing import Dict, Tuple, Any, Optional
from config import Config
from app.core.board import Board
from app.core.task import MissionManager
from app.core.validators import ActionValidator
from app.core.actions import ActionHandler
from app.core.cards import DeckManager, CardManager


# Pre-calcolo dei chokepoint (territori con connessioni cross-continente)
def _build_chokepoint_map():
    from app.core.world import TERRITORIES as WORLD_T
    chokepoints = set()
    for t_id, t_data in WORLD_T.items():
        t_continent = t_data.get('continent', '')
        for n_id in t_data.get('neighbors', []):
            if WORLD_T.get(n_id, {}).get('continent', '') != t_continent:
                chokepoints.add(t_id)
                break
    return chokepoints

_CHOKEPOINT_IDS = _build_chokepoint_map()


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
        self.setup_placed: Dict[int, int] = {}
        self.player_missions: Dict[int, Dict[str, Any]] = {}
        self.consecutive_invalid_moves = 0
        self.pending_attack_src: Optional[int] = None
        self.pending_attack_dest: Optional[int] = None
        self.action_handler = ActionHandler()
        self.progress_cache: Dict[int, int] = {}
        self.repeat_reinforce: Dict[int, Dict[str, Any]] = {}
        self.repeat_pass: Dict[int, int] = {}
        self.consecutive_passive_turns: Dict[int, int] = {}
        self.has_attacked_this_turn: bool = False
        self.attacked_territories_this_turn: set = set()
        self.moved_from_territories: set = set()
        self.conquests_this_turn: Dict[int, int] = {}
        self.deck_manager: Optional[DeckManager] = None
        self.card_manager: Optional[CardManager] = None
        self._continent_reward_given = False
        
        self.reset()

    def _player_ids(self):
        return range(1, self.num_players + 1)

    def _next_player_id(self, current: int) -> int:
        return (current % self.num_players) + 1

    def get_player_mission(self, player_id: int) -> Dict[str, Any]:
        return self.player_missions.get(player_id, {})

    def _has_reinforce_space(self, player_id: int) -> bool:
        return any(t.owner_id == player_id for t in self.board.territories.values())

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
        self.deck_manager = DeckManager(self.board.territories)
        self.card_manager = CardManager(self.num_players, self.deck_manager)
        
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
        self.consecutive_invalid_moves = 0
        self.pending_attack_src = None
        self.pending_attack_dest = None
        self.progress_cache = {p_id: 0 for p_id in self._player_ids()}
        self.repeat_pass = {p_id: 0 for p_id in self._player_ids()}
        self.consecutive_passive_turns = {p_id: 0 for p_id in self._player_ids()}
        self.has_attacked_this_turn = False
        self.attacked_territories_this_turn: set = set()
        self.moved_from_territories: set = set()
        self.conquests_this_turn: Dict[int, int] = {p_id: 0 for p_id in self._player_ids()}
        self._continent_reward_given = False
        self.chokepoint_bonus_given: set = set()  # (player_id, territory_id) già premiati questo rinforzo
        return self.board

    def step(self, action: Dict[str, Any], player_id: int) -> Tuple[float, bool, Dict[str, Any]]:
        reward: float = 0.0
        done: bool = False
        info: Dict[str, Any] = {'phase_before': self.current_phase}

        # --- SETUP: INITIAL PLACEMENT ---
        if self.current_phase == 'INITIAL_PLACEMENT':
            if action['type'] != 'REINFORCE':
                return self._handle_invalid_move(f"Fase {self.current_phase}: solo REINFORCE permesso", info)
            
            # Garantiamo almeno 1 armata prima della validazione
            if self.armies_to_place > 0:
                if action.get('qty', 0.0) * self.armies_to_place < 1.0:
                    action['qty'] = 1.0 / self.armies_to_place

            is_valid, err_msg = ActionValidator.validate_reinforce(self.board, player_id, action, self.armies_to_place)
            if not is_valid: return self._handle_invalid_move(err_msg, info)

            reward, placed, a_extra = self.action_handler.execute_reinforce(self.board, player_id, action, self.armies_to_place)
            info.update(a_extra)
            
            # Bonus Chokepoint: solo UNA volta per territorio per turno di rinforzo
            dest_id = action.get('dest')
            if dest_id in _CHOKEPOINT_IDS:
                bonus_key = (player_id, dest_id)
                if bonus_key not in self.chokepoint_bonus_given:
                    reward += Config.REWARD.get('REINFORCE_CHOKEPOINT_BONUS', 15)
                    info['reinforce_chokepoint'] = True
                    self.chokepoint_bonus_given.add(bonus_key)
                
            self.armies_to_place -= placed
            self.setup_placed[player_id] += placed
            if self.armies_to_place <= 0:
                if all(self.setup_placed[p] >= self.initial_placement_total for p in self._player_ids()):
                    self.current_phase, self.player_turn, self.current_turn = 'REINFORCE', 1, 1
                    self.armies_to_place = 0
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
                    
                    # Penalità esponenziale per scoraggiare la passività prolungata
                    if self.consecutive_passive_turns[player_id] >= 2:
                        base_pen = Config.REWARD.get('PASSIVE_TURN_PENALTY', -40)
                        # Moltiplicatore esponenziale basato sui turni consecutivi passati
                        multiplier = 2 ** (self.consecutive_passive_turns[player_id] - 2)
                        pass_penalty = base_pen * multiplier
                        
                        # Limite massimo (Capping) alla penalità per evitare drop eccessivi di fitness
                        pass_penalty = max(pass_penalty, Config.REWARD.get('PASS_PENALTY_CAP', -1000))
                        
                        reward += pass_penalty
                        info['passive_turn_penalty'] = pass_penalty
                
                self.current_phase = 'MANEUVER'
            elif self.current_phase == 'MANEUVER':
                # Al termine del turno valutiamo l'abbandono delle frontiere
                pen = Config.REWARD.get('END_PHASE_LEAVE_ONE_PENALTY', -150)
                exposed = 0
                for t_id in self.moved_from_territories:
                    t = self.board.territories.get(t_id)
                    if t and t.owner_id == player_id and t.armies == 1:
                        if any(self.board.territories[n].owner_id != player_id for n in t.neighbors):
                            exposed += 1
                if exposed > 0:
                    reward += exposed * pen
                    info['end_phase_left_one'] = exposed

                # Bonus se almeno un territorio di frontiera ha più di 2 armate
                has_garrisoned_border = any(
                    t.owner_id == player_id and t.armies > 2 and
                    any(self.board.territories[n].owner_id != player_id for n in t.neighbors)
                    for t in self.board.territories.values()
                )
                if has_garrisoned_border:
                    garrison_bonus = Config.REWARD.get('END_TURN_WITH_2_GARRISON_ARMY', 30)
                    reward += garrison_bonus
                    info['garrison_bonus'] = garrison_bonus

                self._end_turn()
            elif self.current_phase == 'POST_ATTACK_MOVE':
                return self._handle_invalid_move('Devi scegliere quante truppe spostare', info)
            elif self.current_phase == 'PLAY_CARDS':
                info['action'] = 'Pass in PLAY_CARDS phase'
                self._start_reinforce_phase(player_id)
            return self._finalize_step(reward, done, info, player_id, action)

        # --- ACTION: PLAY CARDS ---
        if self.current_phase == 'PLAY_CARDS':
            if action.get('type') == 'PLAY_CARDS':
                card_indices = action.get('cards', [])
                if not card_indices:
                    # L'AI lancia un intent generico, noi calcoliamo la combo migliore per lei
                    card_indices = self.card_manager.get_best_combination(player_id, self.board)
                
                if not card_indices:
                    return self._handle_invalid_move('Nessuna combinazione valida possibile', info)

                bonus_armies, t_bonuses = self.card_manager.play_combination(player_id, card_indices, self.board)
                if bonus_armies > 0:
                    self.armies_to_place += bonus_armies
                    self.armies_to_place_total += bonus_armies
                    
                    for t_id, bonus in t_bonuses.items():
                        self.board.territories[t_id].armies += bonus
                        
                    reward += Config.REWARD.get('PLAY_CARDS_BONUS', 150)
                    info['cards_played'] = True
                    info['bonus_armies'] = bonus_armies
                    info['territory_bonuses'] = t_bonuses
                else:
                    return self._handle_invalid_move('Combinazione carte non valida', info)
                    
            self._start_reinforce_phase(player_id)
            return self._finalize_step(reward, done, info, player_id, action)

        # --- ACTION: REINFORCE ---
        if self.current_phase == 'REINFORCE':
            # Correzione quantità prima della validazione
            if self.armies_to_place > 0:
                t_dest_in = self.board.territories.get(action.get('dest'))
                
                t_dest = self.board.territories.get(action.get('dest'))
                # Usa armies_to_place_total per calcolare la quantità minima per avere 1 armata
                min_qty = 1.0 / self.armies_to_place_total
                if action.get('qty', 0.0) < min_qty:
                    action['qty'] = min_qty
                
                req = max(1, int(self.armies_to_place_total * action.get('qty', 0.0)))
                # Cap basato sia su truppe disponibili che su spazio rimasto nel territorio
                req = min(req, self.armies_to_place)
                action['qty'] = min(1.0, req / self.armies_to_place) if self.armies_to_place > 0 else 0.0

            is_valid, err_msg = ActionValidator.validate_reinforce(self.board, player_id, action, self.armies_to_place)
            if not is_valid: return self._handle_invalid_move(err_msg, info)
            
            self.consecutive_invalid_moves = 0
            
            r_r, placed, e_r = self.action_handler.execute_reinforce(self.board, player_id, action, self.armies_to_place)
            reward += r_r
            info.update(e_r)
            
            # Bonus Chokepoint: solo UNA volta per territorio per turno di rinforzo
            if action.get('dest') in _CHOKEPOINT_IDS:
                bonus_key = (player_id, action.get('dest'))
                if bonus_key not in self.chokepoint_bonus_given:
                    reward += Config.REWARD.get('REINFORCE_CHOKEPOINT_BONUS', 15)
                    info['reinforce_chokepoint'] = True
                    self.chokepoint_bonus_given.add(bonus_key)
                
            self.armies_to_place -= placed
            if placed > 0: self.repeat_pass[player_id] = 0
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
            # Tracciamo src e dest di ogni attacco per la valutazione finale
            self.attacked_territories_this_turn.add(action['src'])
            self.attacked_territories_this_turn.add(action['dest'])
            # Tracciamo il territorio sorgente (da cui abbiamo tolto truppe)
            self.moved_from_territories.add(action['src'])


            if conquered:
                self.has_attacked_this_turn = True
                self.card_manager.mark_conquest(player_id)
                
                # Reward con Diminishing Returns
                base_conquer = int(Config.REWARD.get('CONQUER_TERRITORY', 100))
                decay = float(Config.REWARD.get('CONQUEST_DECAY_FACTOR', 0.65))
                n = self.conquests_this_turn.get(player_id, 0)
                scaled_reward = float(base_conquer * (decay ** n))
                reward += scaled_reward
                self.conquests_this_turn[player_id] = n + 1
                info['conquest_reward'] = scaled_reward
                info['conquest_number'] = n + 1
                
                # Bonus Chokepoint
                if action['dest'] in _CHOKEPOINT_IDS:
                    choke_bonus = int(Config.REWARD.get('CONQUER_CHOKEPOINT_BONUS', 60))
                    reward += choke_bonus
                    info['chokepoint_captured'] = True
                
                if a_e.get('continent_complete'): reward += Config.REWARD.get('CONQUER_CONTINENT', 150)
                self.pending_attack_src, self.pending_attack_dest = action['src'], action['dest']
                self.current_phase, info['post_attack_move_required'] = 'POST_ATTACK_MOVE', True
            return self._finalize_step(reward, done, info, player_id, action)

        # --- ACTION: POST_ATTACK_MOVE ---
        elif self.current_phase == 'POST_ATTACK_MOVE':
            self.repeat_pass[player_id] = 0
            if self.pending_attack_src is None: return self._handle_invalid_move('Stato post conquista non valido', info)
            
            t_src = self.board.territories.get(self.pending_attack_src)
            t_dest = self.board.territories.get(self.pending_attack_dest)

            action['src'], action['dest'] = self.pending_attack_src, self.pending_attack_dest
            is_valid, err_msg = ActionValidator.validate_post_attack_move(self.board, player_id, action['src'], action['dest'])
            if not is_valid: return self._handle_invalid_move(err_msg, info)
            self.consecutive_invalid_moves = 0
            m_r, m_i = self.action_handler.execute_post_attack_move(self.board, player_id, action['src'], action['dest'], action.get('qty', 1.0))
            reward += m_r
            info.update(m_i)
            # Tracciamo il territorio sorgente del post-conquista (da cui abbiamo mosso truppe)
            self.moved_from_territories.add(action['src'])
            self._clear_pending_attack_move()
            self.current_phase = 'ATTACK'
            return self._finalize_step(reward, done, info, player_id, action)

        # --- ACTION: MANEUVER ---
        elif self.current_phase == 'MANEUVER':
            if action.get('type') == 'PASS':
                info['action'] = 'Pass in MANEUVER phase'
                # ... (rest of pass logic)
                # Note: The pass logic is handled earlier in the 'if action[type] == PASS' block
                pass 

            # Assicuriamoci che se l'IA decide di manovrare, sposti almeno 1 armata
            t_src = self.board.territories.get(action.get('src'))
            t_dest = self.board.territories.get(action.get('dest'))
            
            if t_src and t_dest and t_src.armies > 1:
                movable = t_src.armies - 1
                
                # Minimo 1 armata
                if action.get('qty', 0.0) * movable < 1.0:
                    action['qty'] = 1.0 / movable if movable > 0 else 0.0
            
            is_valid, err_msg = ActionValidator.validate_maneuver(self.board, player_id, action)
            if not is_valid: return self._handle_invalid_move(err_msg, info)
            self.repeat_pass[player_id], self.consecutive_invalid_moves = 0, 0
            m_r, m_e = self.action_handler.execute_maneuver(self.board, player_id, action)
            reward += m_r
            # Tracciamo il territorio sorgente della manovra
            self.moved_from_territories.add(action['src'])
            if self.board.territories[action['src']].armies == 1:
                if any(self.board.territories[n].owner_id != player_id for n in self.board.territories[action['src']].neighbors):
                    info['left_one_army_src'] = True
            reward += self._get_frontline_stability_reward(player_id, info)
            info.update(m_e)
            
            # Al termine del turno valutiamo l'abbandono delle frontiere
            pen = Config.REWARD.get('END_PHASE_LEAVE_ONE_PENALTY', -150)
            exposed = 0
            for t_id in self.moved_from_territories:
                t = self.board.territories.get(t_id)
                if t and t.owner_id == player_id and t.armies == 1:
                    if any(self.board.territories[n].owner_id != player_id for n in t.neighbors):
                        exposed += 1
            if exposed > 0:
                reward += exposed * pen
                info['end_phase_left_one'] = exposed

            # Penalità truppe inattive applicate a fine turno
            reward += self._get_inactive_army_penalty(player_id, info)
            
            # Bonus Manovra verso Chokepoint
            dest_id = action.get('dest')
            if dest_id is not None and dest_id in _CHOKEPOINT_IDS:
                choke_man_bonus = int(Config.REWARD.get('MANEUVER_TO_CHOKEPOINT', 50))
                reward += choke_man_bonus
                info['maneuver_to_chokepoint'] = True

            self._end_turn()
            return self._finalize_step(reward, done, info, player_id, action)

        return self._finalize_step(reward, done, info, player_id, action)

    def _finalize_step(self, reward: float, done: bool, info: Dict[str, Any], player_id: int, action: Dict[str, Any]) -> Tuple[float, bool, Dict[str, Any]]:
        lp = Config.REWARD.get('GAME_LENGTH_PENALTY', -10)
        is_attack_action = action.get('type') == 'ATTACK'
        if lp != 0 and is_attack_action:
            reward += lp
            info['game_length_penalty'] = lp
        winner, _ = self.is_game_over()
        if winner != 0:
            done = True
            if winner == player_id: reward += Config.REWARD.get('WIN', 7000)
            elif winner == -1: reward += Config.REWARD.get('STALEMATE_PENALTY', -6000)
            else: reward += Config.REWARD.get('LOSS', -8000)
        return float(reward), done, info

    def _handle_invalid_move(self, err_msg: str, info: Dict[str, Any]) -> Tuple[int, bool, Dict[str, Any]]:
        self.consecutive_invalid_moves += 1
        reward = Config.REWARD.get('INVALID_MOVE_ATTACK', -200) if self.current_phase in ('ATTACK', 'POST_ATTACK_MOVE') else Config.REWARD.get('INVALID_MOVE', -100)
        if self.consecutive_invalid_moves >= 10:
            reward, self.consecutive_invalid_moves = Config.REWARD.get('CONSECUTIVE_INVALID_MOVE', -500), 0
            info['error'] = f"TROPPI ERRORI ({self.consecutive_invalid_moves}): {err_msg}. Turno gestito forzatamente."
            if self.current_phase == 'REINFORCE': self.current_phase = 'ATTACK'
            elif self.current_phase == 'PLAY_CARDS': self._start_reinforce_phase(self.player_turn)
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


    def _get_frontline_stability_reward(self, player_id: int, info: Dict[str, Any]) -> float:
        frontline = [t for t in self.board.territories.values() if t.owner_id == player_id and any(self.board.territories[n].owner_id != player_id for n in t.neighbors)]
        if not frontline: return 0.0
        bonus = 0.0
        stable_count = 0
        garrison_bonus = float(Config.REWARD.get('FRONTLINE_GARRISON_BONUS', 20))
        for t in frontline:
            if t.armies >= 2:
                bonus += garrison_bonus
                stable_count += 1
        if stable_count > 0:
            info['frontline_garrisoned'] = stable_count
        return bonus

    def _get_inactive_army_penalty(self, player_id: int, info: Dict[str, Any]) -> float:
        penalty_per_army = float(Config.REWARD.get('INTERNAL_ARMY_PENALTY', -15))
        total_penalty = 0.0
        inactive_count = 0
        
        for t in self.board.territories.values():
            if t.owner_id == player_id:
                is_frontline = any(self.board.territories[n].owner_id != player_id for n in t.neighbors)
                if not is_frontline and t.armies > 1:
                    inactive_armies = t.armies - 1
                    total_penalty += inactive_armies * penalty_per_army
                    inactive_count += inactive_armies
        
        if total_penalty != 0:
            info['inactive_army_penalty'] = total_penalty
            info['inactive_army_count'] = inactive_count
        return total_penalty

    def _get_available_bonus(self, player_id: int) -> int:
        lands = len(self.board.get_player_territories(player_id))
        bonus = max(Config.GAME['MIN_BONUS'], lands // Config.GAME['BONUS_ARMIES_DIVISOR'])
        for _, data in Config.CONTINENTS.items():
            if all(self.board.territories[t_id].owner_id == player_id for t_id in data['t_ids']): bonus += data['bonus']
        curr = sum(t.armies for t in self.board.territories.values() if t.owner_id == player_id)
        return max(0, min(bonus, Config.GAME['MAX_TOTAL_ARMIES'] - curr))

    def next_turn(self) -> None:
        self.player_turn, self.current_turn = self._next_player_id(self.player_turn), self.current_turn + 1

    def _start_play_cards_phase(self, player_id: int) -> None:
        self.current_phase = 'PLAY_CARDS'
        # Se non ha combinazioni valide, passiamo subito a reinforce
        if not Config.CARDS.get('ENABLED', False) or not self.card_manager.has_valid_combination(player_id):
            self._start_reinforce_phase(player_id)

    def _start_reinforce_phase(self, player_id: int) -> None:
        self.current_phase = 'REINFORCE'
        self.armies_to_place = max(0, self.armies_to_place) + self._get_available_bonus(player_id)
        self.armies_to_place_total, self.has_reinforced = self.armies_to_place, True
        # Resetta il set dei chokepoint già premiati per il nuovo turno di rinforzo
        self.chokepoint_bonus_given = set()
        if self.armies_to_place <= 0 or not self._has_reinforce_space(player_id):
            self.armies_to_place, self.current_phase = 0, 'ATTACK'

    def _end_turn(self) -> None:
        # Se ha conquistato, ottiene 1 carta in regalo
        if Config.CARDS.get('ENABLED', False):
            self.card_manager.give_card_if_eligible(self.player_turn)

        self.has_attacked_this_turn = False
        self.attacked_territories_this_turn = set()
        self.moved_from_territories = set()
        self.conquests_this_turn = {p_id: 0 for p_id in self._player_ids()}
        self.has_reinforced, self.armies_to_place = False, 0
        self.repeat_pass = {p_id: 0 for p_id in self._player_ids()}
        if hasattr(self, '_continent_reward_given'): del self._continent_reward_given
        self.next_turn()
        self._start_play_cards_phase(self.player_turn)

    def _clear_pending_attack_move(self) -> None:
        self.pending_attack_src = self.pending_attack_dest = None

    def is_game_over(self) -> Tuple[int, int]:
        alive = [p for p in self._player_ids() if len(self.board.get_player_territories(p)) > 0]
        
        # Se un giocatore è appena morto in questo turno, trasferiamo le sue carte al giocatore di turno.
        # Possiamo dedurlo se "alive" non contiene tutti, e c'è gente che ha 0 territori.
        dead_players = [p for p in self._player_ids() if p not in alive]
        if Config.CARDS.get('ENABLED', False):
            for dp in dead_players:
                if len(self.card_manager.player_hands[dp]) > 0:
                    self.card_manager.transfer_cards(dp, self.player_turn)

        if len(alive) == 1: return alive[0], next((p for p in self._player_ids() if p != alive[0]), 0)
        for p in alive:
            if MissionManager.check_completion(self.player_missions.get(p), self.board, p): return p, next((p2 for p2 in alive if p2 != p), 0)
        return (-1, -1) if self.current_turn >= Config.GAME['MAX_TURNS'] else (0, 0)
