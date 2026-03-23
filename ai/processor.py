import numpy as np
from typing import Dict, List, Any, Optional

from core.board import Board
from config import Config


class Processor:
    FEATURES_PER_TERRITORY = 13  # mine, armies, enemy, threat, front, cont, vuln, gate, choke, cont_ratio, attack, defense, cluster
    GLOBAL_FEATURES = 18        # orig(10) + ratios(5) + consecutive_att, gained_this_turn, lost_last_turn

    def __init__(self, board: Board):
        self.num_territories: int = board.n
        self.features_per_territory: int = self.FEATURES_PER_TERRITORY
        self.num_global_features: int = self.GLOBAL_FEATURES
        # Input size: (territories * 8) + global
        self.input_size: int = (self.num_territories * self.features_per_territory) + self.num_global_features

        # Pre-calcolo mappa continenti (0-1)
        continent_names = list(Config.CONTINENTS.keys())
        self._territory_continent = {} 
        for i, (c_name, data) in enumerate(Config.CONTINENTS.items()):
            c_norm = (i + 1) / max(1, len(continent_names))
            for t_id in data['t_ids']:
                self._territory_continent[t_id] = c_norm

        # Pre-calcolo Gateway, Chokepoint e Centralità
        from core.world import TERRITORIES as WORLD_T
        self._gateway_score = {}  # Connettività cross-continente
        self._chokepoint_score = {} # Nodo di transito critico (degree centrality)
        
        for t_id, t_data in WORLD_T.items():
            t_continent = t_data.get('continent', '')
            neighbors = t_data.get('neighbors', [])
            
            # Gateway: quanto connette altri continenti (pesato)
            cross = sum(1 for n_id in neighbors if WORLD_T.get(n_id, {}).get('continent', '') != t_continent)
            self._gateway_score[t_id] = min(1.0, cross / 2.5) # 1 cross = 0.4, 2+ = 0.8+
            
            # Chokepoint: basato sul numero di connessioni totali (degree)
            # Un territorio con molti vicini è un nodo critico in Risiko
            self._chokepoint_score[t_id] = min(1.0, len(neighbors) / 6.0)

        # Memoria temporale
        self._prev_army_count = -1
        self._prev_territory_count = -1
        
        # Tracking Turnale
        self._current_turn_id = -1
        self._turn_start_territories = -1
        self._consecutive_attacks = 0
        self._territories_lost_last_turn = 0
        self._last_game_territory_count = -1

    @staticmethod
    def _normalize_phase(phase: str) -> float:
        phases = {
            "INITIAL_PLACEMENT": 0.0,
            "PLAY_CARDS": 0.2,
            "REINFORCE": 0.4,
            "ATTACK": 0.6,
            "POST_ATTACK_MOVE": 0.8,
            "MANEUVER": 1.0
        }
        return phases.get(phase, 0.0)

    @staticmethod
    def _normalize_enemy_relative(relative_enemy_id: int, total_players: int) -> float:
        if relative_enemy_id <= 0:
            return 0.0
        if total_players <= 2:
            return 1.0
        denominator = total_players - 1 # Adjusted denominator
        if denominator <= 0:
            return 1.0
        normalized = 0.1 + ((relative_enemy_id - 1) / denominator) * 0.9
        return float(min(1.0, max(0.1, normalized)))

    @staticmethod
    def _resolve_total_players(board: Board, current_player_id: int) -> int:
        configured_players = int(Config.GAME.get("NUM_PLAYERS", 2))
        observed_max_owner = max(
            (t.owner_id for t in board.territories.values() if t.owner_id is not None),
            default=0,
        )
        return max(2, configured_players, observed_max_owner, current_player_id)

    def encode_state(
        self,
        board: Board,
        current_player_id: int,
        current_turn: int = 0,
        current_phase: str = "",
        mission_data: Optional[Dict[str, Any]] = None,
    ) -> np.ndarray:
        state_vector = np.zeros(self.input_size, dtype=np.float32)
        max_armies = max(1, int(Config.GAME["MAX_ARMIES_PER_TERRITORY"]))
        total_players = self._resolve_total_players(board, current_player_id)

        # 1) Pre-calcolo dati globali e di proprietà
        my_territories_ids = [t_id for t_id, t in board.territories.items() if t.owner_id == current_player_id]
        my_territory_count = len(my_territories_ids)
        my_army_count = sum(board.territories[tid].armies for tid in my_territories_ids)
        
        # Statistiche continenti per il giocatore attuale
        cont_stats = {} # c_name -> {'total': n, 'mine': n, 'ratio': f}
        full_continents = 0
        partial_continents = 0
        for c_name, data in Config.CONTINENTS.items():
            t_ids = data['t_ids']
            mine = sum(1 for tid in t_ids if board.territories[tid].owner_id == current_player_id)
            ratio = mine / len(t_ids)
            cont_stats[c_name] = ratio
            if ratio == 1.0: full_continents += 1
            elif ratio > 0: partial_continents += 1

        # Mappa territorio -> nome continente per lookup veloce
        t_to_cname = {}
        for c_name, data in Config.CONTINENTS.items():
            for tid in data['t_ids']: t_to_cname[tid] = c_name

        # 2) Territory Features (13 per territorio)
        frontline_count = 0
        for territory_id in range(self.num_territories):
            territory = board.territories[territory_id]
            base = territory_id * self.features_per_territory
            is_mine = (territory.owner_id == current_player_id)

            # [0] is_mine
            state_vector[base] = 1.0 if is_mine else 0.0
            # [1] army_count_normalized
            state_vector[base + 1] = min(1.0, territory.armies / max_armies)
            # [2] enemy_id_relative
            if not is_mine and territory.owner_id is not None:
                relative_id = (territory.owner_id - current_player_id) % total_players
                if relative_id == 0: relative_id = total_players - 1
                state_vector[base + 2] = self._normalize_enemy_relative(relative_id, total_players)
            
            # Analisi vicinato
            enemy_neighbor_armies = 0
            ally_neighbor_armies = 0
            max_enemy_neighbor = 0
            max_attack_opp = 0
            has_enemy_neighbor = False
            
            for n_id in territory.neighbors:
                neigh = board.territories[n_id]
                if neigh.owner_id not in (None, current_player_id):
                    enemy_neighbor_armies += neigh.armies
                    has_enemy_neighbor = True
                    max_enemy_neighbor = max(max_enemy_neighbor, neigh.armies)
                    if is_mine: # Se è mio, quanto è facile attaccare lui?
                        max_attack_opp = max(max_attack_opp, territory.armies / (neigh.armies + 0.1))
                elif neigh.owner_id == current_player_id:
                    ally_neighbor_armies += neigh.armies

            # [3] threat_level
            total_possible_threat = max_armies * max(1, len(territory.neighbors))
            state_vector[base + 3] = min(1.0, enemy_neighbor_armies / total_possible_threat)
            # [4] is_frontline
            if has_enemy_neighbor:
                state_vector[base + 4] = 1.0
                if is_mine: frontline_count += 1
            # [5] continent_id
            state_vector[base + 5] = self._territory_continent.get(territory_id, 0.0)
            # [6] vulnerability_ratio (Log scaling per evitare saturazione immediata)
            vuln = enemy_neighbor_armies / (territory.armies + 1.0)
            state_vector[base + 6] = min(1.0, np.log1p(vuln) / 2.0) # log(1+10)/2 ~ 1.2, log(1+3)/2 ~ 0.7
            # [7] gateway_score
            state_vector[base + 7] = self._gateway_score.get(territory_id, 0.0)
            # [8] chokepoint_score
            state_vector[base + 8] = self._chokepoint_score.get(territory_id, 0.0)
            # [9] continent_control_ratio
            c_name = t_to_cname.get(territory_id)
            state_vector[base + 9] = cont_stats.get(c_name, 0.0)
            # [10] local_attack_opportunity
            state_vector[base + 10] = min(1.0, max_attack_opp / 3.0)
            # [11] defensive_pressure
            state_vector[base + 11] = min(1.0, max_enemy_neighbor / max_armies)
            # [12] cluster_strength (Supporto alleato relativo)
            state_vector[base + 12] = min(1.0, ally_neighbor_armies / (max_armies * 3))

        # 3) Global Features (18)
        global_base = self.num_territories * self.features_per_territory
        # Sweep unico: non pre-seediamo per evitare problemi con giocatori eliminati
        all_counts: Dict[int, int] = {}
        all_armies: Dict[int, int] = {}
        total_world_armies = 0
        for t in board.territories.values():
            if t.owner_id is not None:
                all_counts[t.owner_id] = all_counts.get(t.owner_id, 0) + 1
                all_armies[t.owner_id] = all_armies.get(t.owner_id, 0) + t.armies
                total_world_armies += t.armies
        
        best_enemy_count = max((v for p, v in all_counts.items() if p != current_player_id), default=1)
        best_enemy_armies = max((v for p, v in all_armies.items() if p != current_player_id), default=1)

        # 0-9: Esistenti
        state_vector[global_base] = min(1.0, total_players / 8.0)
        state_vector[global_base + 1] = min(1.0, current_turn / Config.GAME.get("MAX_TURNS", 100))
        state_vector[global_base + 2] = self._normalize_phase(current_phase)
        state_vector[global_base + 3] = current_player_id / 8.0
        
        # Mission Progress (semplificato)
        mission_prog = 0.0
        if mission_data:
            m_type = mission_data.get('type', '')
            if m_type == 'territory_count':
                mission_prog = min(1.0, (my_territory_count / board.n) / max(0.01, float(mission_data.get('target', 1.0))))
            elif m_type == 'continent_count':
                mission_prog = full_continents / max(1, int(mission_data.get('target', 1)))
        state_vector[global_base + 4] = mission_prog
        
        state_vector[global_base + 5] = min(1.0, (my_territory_count / max(1, best_enemy_count)) / 2.0)
        
        # Delta (Temporali)
        if self._prev_army_count >= 0:
            d_a = (my_army_count - self._prev_army_count) / max(10, my_army_count + 1)
            d_t = (my_territory_count - self._prev_territory_count) / max(1, my_territory_count + 1)
            state_vector[global_base + 6] = min(1.0, max(-1.0, d_a)) * 0.5 + 0.5
            state_vector[global_base + 7] = min(1.0, max(-1.0, d_t)) * 0.5 + 0.5
        else:
            state_vector[global_base + 6] = 0.5
            state_vector[global_base + 7] = 0.5
        
        state_vector[global_base + 8] = min(1.0, total_world_armies / (board.n * 20))
        state_vector[global_base + 9] = min(1.0, best_enemy_count / board.n)

        # 10-14: Nuove Globali Ratios
        state_vector[global_base + 10] = my_army_count / max(1, total_world_armies)
        state_vector[global_base + 11] = best_enemy_armies / max(1, total_world_armies)
        state_vector[global_base + 12] = full_continents / len(Config.CONTINENTS)
        state_vector[global_base + 13] = partial_continents / len(Config.CONTINENTS)
        state_vector[global_base + 14] = frontline_count / max(1, my_territory_count)

        # 15-17: Tracking Temporale Avanzato
        # Gestione cambio turno
        if current_turn != self._current_turn_id:
            if self._current_turn_id != -1: # Non è il primo turno assoluto
                # Calcola quanto abbiamo perso dall'ultimo nostro stato visto
                if self._last_game_territory_count > 0:
                    lost = max(0, self._last_game_territory_count - my_territory_count)
                    self._territories_lost_last_turn = lost
            
            self._current_turn_id = current_turn
            self._turn_start_territories = my_territory_count
            self._consecutive_attacks = 0
            
        # Incremento attacchi se siamo in fase ATTACK o POST_ATTACK
        if current_phase in ('ATTACK', 'POST_ATTACK_MOVE'):
            self._consecutive_attacks += 1
            
        # Guarda: _turn_start_territories può essere -1 al primissimo call prima di un cambio turno
        gained_this_turn = max(0, my_territory_count - self._turn_start_territories) if self._turn_start_territories >= 0 else 0
        
        state_vector[global_base + 15] = min(1.0, self._consecutive_attacks / 20.0)
        state_vector[global_base + 16] = min(1.0, gained_this_turn / 5.0)
        state_vector[global_base + 17] = min(1.0, self._territories_lost_last_turn / 3.0)

        # Update Memoria
        self._prev_army_count = my_army_count
        self._prev_territory_count = my_territory_count
        self._last_game_territory_count = my_territory_count

        return state_vector

    def decode_output(
        self, nn_output: np.ndarray, current_phase: str, board: Board, player_id: int
    ) -> Dict[str, Any]:
        #Trasforma l'output della NN in azioni legali filtrando i territori validi.

        #Recuperiamo i territori di proprietà del giocatore
        my_territories: List[int] = []
        for i in range(self.num_territories):
            t = board.territories[i]
            if t.owner_id == player_id:
                my_territories.append(i)
        if not my_territories:
            return {"type": "PASS", "src": 0, "dest": 0, "qty": 0}

        # Estraiamo i neuroni grezzi
        raw_decision = nn_output[0]  # Decisione se agire o passare
        raw_src = nn_output[1]  # Scelta del territorio sorgente
        raw_dest = nn_output[2]  # Scelta del territorio destinazione
        qty_percent = nn_output[3]  # Quantità (0.0 a 1.0)

        # Inizializziamo l'azione di default
        action = {"type": "PASS", "src": 0, "dest": 0, "qty": 0}

        if current_phase == "REINFORCE" or current_phase == "INITIAL_PLACEMENT":
            valid_targets = [
                t_id
                for t_id in my_territories
                if board.territories[t_id].armies < Config.GAME["MAX_ARMIES_PER_TERRITORY"]
            ]
            stack_threshold = Config.REWARD.get("REINFORCE_STACK_THRESHOLD", 0)
            if stack_threshold:
                preferred_targets = [
                    t_id
                    for t_id in valid_targets
                    if board.territories[t_id].armies < stack_threshold
                ]
                if preferred_targets:
                    valid_targets = preferred_targets
            if not valid_targets:
                return {"type": "PASS", "src": 0, "dest": 0, "qty": 0}
            idx = int(raw_src * len(valid_targets))
            target_id = valid_targets[min(idx, len(valid_targets) - 1)]
            action = {
                "type": "REINFORCE",
                "src": target_id,
                "dest": target_id,
                "qty": qty_percent,
            }

        elif current_phase == "PLAY_CARDS":
            play_cards_threshold = Config.NN.get("PLAY_CARDS_THRESHOLD", 0.5)
            if raw_decision > play_cards_threshold:
                action = {
                    "type": "PLAY_CARDS",
                    "src": 0, "dest": 0, "qty": 0
                }
            else:
                action = {"type": "PASS", "src": 0, "dest": 0, "qty": 0}

        elif current_phase == "ATTACK":
            attack_threshold = Config.NN.get("ATTACK_DECISION_THRESHOLD", 0.4)
            valid_sources = [t_id for t_id in my_territories if board.territories[t_id].armies > 1]
            min_ratio = float(Config.NN.get("ATTACK_MIN_RATIO", 1.0))
            min_adv = int(Config.REWARD.get("PASS_ATTACK_MIN_ADVANTAGE", 0))

            candidates = []
            for src_id in valid_sources:
                enemies = [
                    n for n in board.territories[src_id].neighbors
                    if board.territories[n].owner_id != player_id
                ]
                if not enemies:
                    continue
                attacker_armies = board.territories[src_id].armies
                for dest_id in enemies:
                    defender_armies = board.territories[dest_id].armies
                    ratio = attacker_armies / max(1, defender_armies)
                    advantage = attacker_armies - defender_armies

                    if ratio < min_ratio:
                        continue
                    if advantage <= min_adv:
                        continue
                    # Valuta anche la pressione nemica residua sul territorio sorgente.
                    src_enemy_pressure = 0
                    for n in board.territories[src_id].neighbors:
                        if n == dest_id:
                            continue
                        neigh = board.territories[n]
                        if neigh.owner_id != player_id:
                            src_enemy_pressure = max(src_enemy_pressure, neigh.armies)

                    score = (2.0 * ratio) + float(advantage) - (0.5 * src_enemy_pressure)
                    entry = (score, src_id, dest_id, ratio, advantage)
                    candidates.append(entry)

            should_attack = raw_decision > attack_threshold
            if should_attack and candidates:
                idx = int(raw_src * len(candidates))
                picked = candidates[min(idx, len(candidates) - 1)]
                src_id, dest_id = picked[1], picked[2]
                action = {
                    "type": "ATTACK",
                    "src": src_id,
                    "dest": dest_id,
                    "qty": qty_percent,
                }

        elif current_phase == "POST_ATTACK_MOVE":
            action = {
                "type": "POST_ATTACK_MOVE",
                "src": 0,
                "dest": 0,
                "qty": qty_percent,
            }

        elif current_phase == "MANEUVER":
            maneuver_threshold = Config.NN.get("MANEUVER_DECISION_THRESHOLD", 0.5)
            if raw_decision > maneuver_threshold:
                # Filtriamo sorgenti valide (miei territori con truppe > 1)
                valid_sources = [t_id for t_id in my_territories if board.territories[t_id].armies > 1]

                if valid_sources:
                    idx_s = int(raw_src * len(valid_sources))
                    src_id = valid_sources[min(idx_s, len(valid_sources) - 1)]

                    # Filtriamo vicini alleati per lo spostamento
                    friends = [n for n in board.territories[src_id].neighbors if board.territories[n].owner_id == player_id]
                    if friends:
                        idx_d = int(raw_dest * len(friends))
                        dest_id = friends[min(idx_d, len(friends) - 1)]
                        action = {
                            "type": "MANEUVER",
                            "src": src_id,
                            "dest": dest_id,
                            "qty": qty_percent
                        }

        return action
