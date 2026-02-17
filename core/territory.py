from typing import List, Optional

class Territory:
    def __init__(self, territory_id: int, name: str):
        self.id: int = territory_id
        self.name: str = name
        self.owner_id: Optional[int] = None
        self.armies: int = 0
        self.neighbors: List[int] = []

    def __repr__(self) -> str:
        return f"[{self.name} (P{self.owner_id}): {self.armies} armate]"