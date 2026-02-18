import numpy as np
from typing import Dict, List, Any

from core.board import Board
from config import Config


class Processor:
    def __init__(self, board: Board):
        self.num_territories: int = board.n
        self.num_continents: int = len(Config.CONTINENTS)
        # Feature: (Territori * 3) + Continenti + Target + Turno + 5 fasi
        self.input_size: int = (
            (self.num_territories * 3) + self.num_continents + self.num_continents + 6
        )

    def encode_state(
        self,
        board: Board,
        player_id: int,
        current_turn: int,
        current_phase: str,
        mission_data: Dict[str, Any],
    ) -> np.ndarray:
        state_vector = np.zeros(self.input_size)
        for i in range(self.num_territories):
            territory = board.territories[i]
            state_vector[i] = 1 if territory.owner_id == player_id else -1
            state_vector[self.num_territories + i] = territory.armies / Config.GAME[
                "MAX_ARMIES_PER_TERRITORY"
            ]
            danger = sum(
                board.territories[n].armies
                for n in territory.neighbors
                if board.territories[n].owner_id != player_id
            )
            state_vector[2 * self.num_territories + i] = min(1.0, danger / 20.0)

        continent_offset = 3 * self.num_territories
        mission_offset = continent_offset + self.num_continents
        cont_keys = sorted(Config.CONTINENTS.keys())
        for idx, key in enumerate(cont_keys):
            data = Config.CONTINENTS[key]
            owned_count = sum(
                1
                for territory_id in data["t_ids"]
                if board.territories[territory_id].owner_id == player_id
            )
            state_vector[continent_offset + idx] = owned_count / len(data["t_ids"])

        mission_bits = np.zeros(self.num_continents)
        if mission_data and mission_data.get("type") == "continents":
            target_zones = mission_data.get("target", [])
            for zone in target_zones:
                if zone in cont_keys:
                    mission_bits[cont_keys.index(zone)] = 1.0
        elif mission_data and mission_data.get("type") == "territory_count":
            mission_bits[:] = 1.0
        state_vector[mission_offset : mission_offset + self.num_continents] = mission_bits

        state_vector[-6] = current_turn / Config.GAME["MAX_TURNS"]
        if current_phase == "INITIAL_PLACEMENT":
            state_vector[-5] = 1.0
        elif current_phase == "REINFORCE":
            state_vector[-4] = 1.0
        elif current_phase == "ATTACK":
            state_vector[-3] = 1.0
        elif current_phase == "POST_ATTACK_MOVE":
            state_vector[-2] = 1.0
        elif current_phase == "MANEUVER":
            state_vector[-1] = 1.0

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
            if raw_decision > 0.4:
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
            if raw_decision > 0.5:
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
