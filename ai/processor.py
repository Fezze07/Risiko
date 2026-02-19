import numpy as np
from typing import Dict, List, Any, Optional

from core.board import Board
from config import Config


class Processor:
    FEATURES_PER_TERRITORY = 4

    def __init__(self, board: Board):
        self.num_territories: int = board.n
        self.features_per_territory: int = self.FEATURES_PER_TERRITORY
        # Input fisso: 4 feature per territorio.
        self.input_size: int = self.num_territories * self.features_per_territory

    @staticmethod
    def _normalize_enemy_relative(relative_enemy_id: int, total_players: int) -> float:
        if relative_enemy_id <= 0:
            return 0.0
        if total_players <= 2:
            return 1.0
        denominator = total_players - 2
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
        # Parametri mantenuti per compatibilita' con i call-site esistenti.
        _ = current_turn, current_phase, mission_data

        state_vector = np.zeros(self.input_size, dtype=np.float32)
        max_armies = max(1, int(Config.GAME["MAX_ARMIES_PER_TERRITORY"]))
        total_players = self._resolve_total_players(board, current_player_id)

        for territory_id in range(self.num_territories):
            territory = board.territories[territory_id]
            base = territory_id * self.features_per_territory
            owner_id = territory.owner_id

            # 1) is_mine
            state_vector[base] = 1.0 if owner_id == current_player_id else 0.0

            # 2) army_count_normalized
            state_vector[base + 1] = min(1.0, territory.armies / max_armies)

            # 3) enemy_id_relative (0 se territorio mio o owner non valido)
            enemy_relative = 0.0
            if owner_id is not None and owner_id != current_player_id:
                relative_id = (owner_id - current_player_id) % total_players
                if relative_id == 0:
                    relative_id = total_players - 1
                enemy_relative = self._normalize_enemy_relative(relative_id, total_players)
            state_vector[base + 2] = enemy_relative

            # 4) threat_level: somma armate nemiche confinanti normalizzata.
            enemy_neighbor_armies = sum(
                board.territories[n_id].armies
                for n_id in territory.neighbors
                if board.territories[n_id].owner_id not in (None, current_player_id)
            )
            max_threat = max_armies * max(1, len(territory.neighbors))
            state_vector[base + 3] = min(1.0, enemy_neighbor_armies / max_threat)

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

        elif current_phase == "ATTACK":
            attack_threshold = Config.NN.get("ATTACK_DECISION_THRESHOLD", 0.4)
            if raw_decision > attack_threshold:
                # Filtriamo i territori da cui può partire un attacco (miei e con truppe > 1)
                valid_sources = [t_id for t_id in my_territories if board.territories[t_id].armies > 1]

                if valid_sources:
                    # Scegliamo la sorgente tra quelle valide
                    idx_s = int(raw_src * len(valid_sources))
                    src_id = valid_sources[min(idx_s, len(valid_sources) - 1)]

                    # Filtriamo i vicini nemici della sorgente scelta
                    enemies = [n for n in board.territories[src_id].neighbors if board.territories[n].owner_id != player_id]
                    if enemies:
                        # Scegliamo il bersaglio tra i nemici confinanti
                        idx_d = int(raw_dest * len(enemies))
                        dest_id = enemies[min(idx_d, len(enemies) - 1)]
                        attacker_armies = board.territories[src_id].armies
                        defender_armies = board.territories[dest_id].armies
                        min_ratio = Config.NN.get("ATTACK_MIN_RATIO", 1.0)
                        if attacker_armies / max(1, defender_armies) < min_ratio:
                            return {"type": "PASS", "src": 0, "dest": 0, "qty": 0}
                        action = {
                            "type": "ATTACK",
                            "src": src_id,
                            "dest": dest_id,
                            "qty": qty_percent
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






