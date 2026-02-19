import random
from typing import Dict, List, Optional
from config import Config
from core.territory import Territory

class Board:
    def __init__(self, num_players: Optional[int] = None) -> None:
        self.n: int = Config.GAME["NUM_TERRITORIES"]
        configured_players = int(Config.GAME.get("NUM_PLAYERS", 2))
        resolved_players = num_players if num_players is not None else configured_players
        self.num_players: int = max(2, int(resolved_players))
        self.territories: Dict[int, Territory] = {}
        self._create_map()
        self.reset()

    def _create_map(self) -> None:
        # 1 Crea i territori
        for i in range(self.n):
            self.territories[i] = Territory(i, f"T{i}")

        # 2 Connessione a Griglia
        import math
        cols: int = int(math.sqrt(self.n))
        rows: int = self.n // cols

        for i in range(self.n):
            row: int = i // cols
            col: int = i % cols

            # Vicino a DESTRA
            if col < cols - 1:
                self._add_neighbor(i, i + 1)
            # Vicino in BASSO
            if row < rows - 1:
                self._add_neighbor(i, i + cols)

            # Diagonale Strategica (Top-Left -> Bottom-Right)
            if random.random() < 0.3 and col < cols - 1 and row < rows - 1:
                self._add_neighbor(i, i + cols + 1)

            # Diagonale Strategica (Top-Right -> Bottom-Left)
            if random.random() < 0.3 and col > 0 and row < rows - 1:
                self._add_neighbor(i, i + cols - 1)

    def _add_neighbor(self, id1: int, id2: int) -> None:
        if id2 not in self.territories[id1].neighbors:
            self.territories[id1].neighbors.append(id2)
        if id1 not in self.territories[id2].neighbors:
            self.territories[id2].neighbors.append(id1)

    def reset(self, num_players: Optional[int] = None) -> None:
        # Resetta la mappa per una nuova partita
        if num_players is not None:
            self.num_players = max(2, int(num_players))
        ids: List[int] = list(self.territories.keys())
        random.shuffle(ids)

        # Reset armate e proprietari
        for i, t_id in enumerate(ids):
            owner: int = (i % self.num_players) + 1
            self.territories[t_id].owner_id = owner
            self.territories[t_id].armies = Config.GAME["STARTING_ARMIES"]

    def get_player_territories(self, player_id: int) -> List[Territory]:
        return [t for t in self.territories.values() if t.owner_id == player_id]
