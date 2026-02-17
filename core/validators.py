from typing import Dict, Any, Tuple
from core.board import Board
from core.config import Config

class ActionValidator:
    @staticmethod
    def validate_reinforce(board: Board, player_id: int, action: Dict[str, Any], armies_to_place: int, max_armies: int) -> Tuple[bool, str]:
        if 'dest' not in action:
            return False, "Destinazione mancante"
        
        t_id = action['dest']
        if not (0 <= t_id < board.n):
            return False, "ID territorio non valido"

        t_dest = board.territories[t_id]

        if t_dest.owner_id != player_id:
            return False, "Territorio non di tua proprietà"
        
        if armies_to_place <= 0:
            return False, "Nessuna armata disponibile"

        qty = action.get('qty', 0.0)
        if qty <= 0 or qty < Config.GAME.get("MIN_REINFORCE_QTY", 0.0):
            return False, "Quantita' rinforzo troppo bassa"

        # Check simulato sulla quantità
        to_add = max(1, int(armies_to_place * qty))
        space_in_territory = max_armies - t_dest.armies
        effective_add = min(to_add, armies_to_place, space_in_territory)
        
        if effective_add <= 0:
            return False, "Nessuno spazio disponibile o quantità nulla"

        return True, ""

    @staticmethod
    def validate_attack(board: Board, player_id: int, action: Dict[str, Any]) -> Tuple[bool, str]:
        if 'src' not in action or 'dest' not in action:
             return False, "Sorgente o destinazione mancante"

        src_id, dest_id = action['src'], action['dest']
        if not (0 <= src_id < board.n) or not (0 <= dest_id < board.n):
             return False, "ID territori non validi"

        t_att = board.territories[src_id]
        t_def = board.territories[dest_id]

        if t_att.owner_id != player_id:
            return False, "Territorio sorgente non tuo"
        
        if t_def.owner_id == player_id:
            return False, "Non puoi attaccare te stesso"
        
        if dest_id not in t_att.neighbors:
            return False, "I territori non sono confinanti"
        
        if t_att.armies <= 1:
            return False, "Armate insufficienti per attaccare (serve > 1)"

        return True, ""

    @staticmethod
    def validate_maneuver(board: Board, player_id: int, action: Dict[str, Any], max_armies: int) -> Tuple[bool, str]:
        if 'src' not in action or 'dest' not in action:
             return False, "Sorgente o destinazione mancante"

        src_id, dest_id = action['src'], action['dest']
        if not (0 <= src_id < board.n) or not (0 <= dest_id < board.n):
             return False, "ID territori non validi"

        t_src = board.territories[src_id]
        t_dest = board.territories[dest_id]

        if t_src.owner_id != player_id:
            return False, "Territorio sorgente non tuo"
        
        if t_dest.owner_id != player_id:
            return False, "Territorio destinazione non tuo"
        
        if dest_id not in t_src.neighbors:
            return False, "I territori non sono confinanti"
        
        if t_src.armies <= 1:
            return False, "Armate insufficienti per spostare (serve > 1)"
        
        # Check quantità
        amount = int((t_src.armies - 1) * action.get('qty', 0.0))
        if amount < 1:
            return False, "Quantità da spostare insufficiente (< 1)"
            
        # Check Max Armies (Anti-Farming)
        if t_dest.armies + amount > max_armies:
             return False, f"Limite armate superato ({t_dest.armies} + {amount} > {max_armies})"

        return True, ""

    @staticmethod
    def validate_post_attack_move( board: Board, player_id: int, src_id: int, dest_id: int) -> Tuple[bool, str]:
        if not (0 <= src_id < board.n) or not (0 <= dest_id < board.n):
            return False, "ID territori non validi (post conquista)"

        t_src = board.territories[src_id]
        t_dest = board.territories[dest_id]

        if t_src.owner_id != player_id or t_dest.owner_id != player_id:
            return False, "Post conquista incoerente: territori non tuoi"

        movable = t_src.armies - 1
        if movable < 1:
            return False, "Armate insufficienti per lo spostamento post conquista"

        min_required = min(
            movable,
            max(1, Config.GAME.get("MIN_POST_CONQUEST_MOVE", 1))
        )
        if min_required < 1:
            return False, "Spostamento post conquista non valido"

        return True, ""
