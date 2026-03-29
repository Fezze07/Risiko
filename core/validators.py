from typing import Dict, Any, Tuple
from core.board import Board
from config import Config

class ActionValidator:
    @staticmethod
    def validate_reinforce(board: Board, player_id: int, action: Dict[str, Any], armies_to_place: int) -> Tuple[bool, str]:
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

        qty = float(action.get("qty", 0.0))
        if qty <= 0 or qty < Config.NN.get("MIN_REINFORCE_QTY", 0.0):
            return False, "Quantità rinforzi non valida"

        # Check Max Armies (Global Limit)
        current_total = sum(t.armies for t in board.territories.values() if t.owner_id == player_id)
        if current_total >= Config.GAME.get('MAX_TOTAL_ARMIES', 100):
            return False, "Limite armate superato (Global Max)!"

        # Check simulato sulla quantità
        to_add = max(1, int(armies_to_place * qty))
        effective_add = min(to_add, armies_to_place)
        
        if effective_add <= 0:
            return False, "Nessuna armata da piazzare o quantità nulla"

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
    def validate_maneuver(board: Board, player_id: int, action: Dict[str, Any]) -> Tuple[bool, str]:
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
        movable = t_src.armies - 1
        amount = max(1, int(movable * action.get('qty', 0.0)))
        amount = min(amount, movable)
        
        if amount < 1:
            return False, "Quantità da spostare insufficiente (< 1)"
            

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

        min_move = min(movable, 
            max(1, Config.NN.get("MIN_POST_CONQUEST_MOVE", 1))
        )
        if min_move < 1: # Changed from min_required to min_move
            return False, "Spostamento post conquista non valido"

        return True, ""
