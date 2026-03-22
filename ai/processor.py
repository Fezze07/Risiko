import numpy as np
from typing import Dict, List, Any, Optional

from core.board import Board
from config import Config


class Processor:
    FEATURES_PER_TERRITORY = 4
    GLOBAL_FEATURES = 4

    def __init__(self, board: Board):
        self.num_territories: int = board.n
        self.features_per_territory: int = self.FEATURES_PER_TERRITORY
        self.num_global_features: int = self.GLOBAL_FEATURES
        # Input size: (territories * 4) + global
        self.input_size: int = (self.num_territories * self.features_per_territory) + self.num_global_features

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

        # 1) Territory Features
        for territory_id in range(self.num_territories):
            territory = board.territories[territory_id]
            base = territory_id * self.features_per_territory
            owner_id = territory.owner_id

            # is_mine
            state_vector[base] = 1.0 if owner_id == current_player_id else 0.0

            # army_count_normalized
            state_vector[base + 1] = min(1.0, territory.armies / max_armies)

            # enemy_id_relative
            enemy_relative = 0.0
            if owner_id is not None and owner_id != current_player_id:
                relative_id = (owner_id - current_player_id) % total_players
                if relative_id == 0:
                    relative_id = total_players - 1
                enemy_relative = self._normalize_enemy_relative(relative_id, total_players)
            state_vector[base + 2] = enemy_relative

            # threat_level
            enemy_neighbor_armies = sum(
                board.territories[n_id].armies
                for n_id in territory.neighbors
                if board.territories[n_id].owner_id not in (None, current_player_id)
            )
            max_threat = max_armies * max(1, len(territory.neighbors))
            state_vector[base + 3] = min(1.0, enemy_neighbor_armies / max_threat)

        # 2) Global Features
        global_base = self.num_territories * self.features_per_territory
        
        # Num Players (normalized 0-1 for 2-8 range)
        state_vector[global_base] = min(1.0, total_players / 8.0)
        
        # Turn progress
        max_turns = Config.GAME.get("MAX_TURNS", 100)
        state_vector[global_base + 1] = min(1.0, current_turn / max_turns)
        
        # Phase (normalized)
        state_vector[global_base + 2] = self._normalize_phase(current_phase)
        
        # Player ID (normalized)
        state_vector[global_base + 3] = current_player_id / 8.0

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
