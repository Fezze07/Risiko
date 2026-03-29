from ai.network import NeuralNetwork
from ai.processor import Processor
from config import Config
from core.board import Board
import random
from typing import Dict, Any, Optional

class Agent:
    def __init__(self, board_ref: Board, id: Optional[int] = None):
        self.id: Optional[int] = id
        self.processor: Processor = Processor(board_ref)
        self.epsilon: float = Config.NN["EPSILON-GREEDY"]

        # Architettura della Neural Network
        self.nn: NeuralNetwork = NeuralNetwork(
            input_size=self.processor.input_size,
            hidden_sizes=Config.NN["HIDDEN_LAYERS"],
            output_size=Config.NN["OUTPUT_SIZE"]
        )

        self.fitness: float = 0
        self.last_action_valid: bool = True
        self.match_count: int = 0

    def think(self, board: Board, player_id: int, current_turn: int, phase: str, mission_data: Dict[str, Any]) -> Dict[str, Any]:
        # L'agente osserva la board e sputa fuori una mossa decodificata

        # EPSILON-GREEDY: Mossa random ma sensata per la fase
        if random.random() < self.epsilon:
            return self._get_random_action(phase, board, player_id)

        # 1. Encoding (Board -> Vettore)
        state = self.processor.encode_state(
            board,
            current_player_id=player_id,
            current_turn=current_turn,
            current_phase=phase,
            mission_data=mission_data,
        )

        # 2. Forward Pass (Vettore -> Output NN)
        output = self.nn.forward(state)

        # 3. Decoding (Output NN -> Action Dict)
        return self.processor.decode_output(output, phase, board, player_id)

    def _get_random_action(self, phase: str, board: Board, player_id: int) -> Dict[str, Any]:
        # Genera un'azione LEGALMENTE VALIDA in base alla fase per un'esplorazione utile
        my_territories = [t_id for t_id, t in board.territories.items() if t.owner_id == player_id]
        
        if not my_territories:
            return {"type": "PASS", "src": 0, "dest": 0, "qty": 0}

        if phase == "REINFORCE" or phase == "INITIAL_PLACEMENT":
            valid_targets = [
                t_id for t_id in my_territories 
            ]
            if not valid_targets:
                return {"type": "PASS", "src": 0, "dest": 0, "qty": 0}
            target_id = random.choice(valid_targets)
            return {"type": "REINFORCE", "src": target_id, "dest": target_id, "qty": random.random()}

        if phase == "PLAY_CARDS":
            if random.random() < 0.5:
                return {"type": "PLAY_CARDS", "src": 0, "dest": 0, "qty": 0}
            else:
                return {"type": "PASS", "src": 0, "dest": 0, "qty": 0}

        if phase == "ATTACK":
            # 20% di probabilità di passare
            if random.random() < 0.2:
                return {"type": "PASS", "src": 0, "dest": 0, "qty": 0}
            
            valid_sources = [t_id for t_id in my_territories if board.territories[t_id].armies > 1]
            if not valid_sources:
                return {"type": "PASS", "src": 0, "dest": 0, "qty": 0}
            
            src_id = random.choice(valid_sources)
            enemies = [n for n in board.territories[src_id].neighbors if board.territories[n].owner_id != player_id]
            
            if not enemies:
                # Se la sorgente scelta non ha nemici, riprova una volta con una sorgente a caso che ne abbia
                potential_sources = [s for s in valid_sources if any(board.territories[n].owner_id != player_id for n in board.territories[s].neighbors)]
                if not potential_sources:
                    return {"type": "PASS", "src": 0, "dest": 0, "qty": 0}
                src_id = random.choice(potential_sources)
                enemies = [n for n in board.territories[src_id].neighbors if board.territories[n].owner_id != player_id]
            
            dest_id = random.choice(enemies)
            return {"type": "ATTACK", "src": src_id, "dest": dest_id, "qty": random.random()}

        if phase == "POST_ATTACK_MOVE":
            return {"type": "POST_ATTACK_MOVE", "src": 0, "dest": 0, "qty": random.random()}

        if phase == "MANEUVER":
            if random.random() < 0.2:
                return {"type": "PASS", "src": 0, "dest": 0, "qty": 0}
                
            valid_sources = [t_id for t_id in my_territories if board.territories[t_id].armies > 1]
            if not valid_sources:
                return {"type": "PASS", "src": 0, "dest": 0, "qty": 0}
                
            # Scegli una sorgente che abbia vicini amici
            potential_sources = [s for s in valid_sources if any(board.territories[n].owner_id == player_id for n in board.territories[s].neighbors)]
            if not potential_sources:
                return {"type": "PASS", "src": 0, "dest": 0, "qty": 0}
                
            src_id = random.choice(potential_sources)
            friends = [n for n in board.territories[src_id].neighbors if board.territories[n].owner_id == player_id]
            
            dest_id = random.choice(friends)
            return {"type": "MANEUVER", "src": src_id, "dest": dest_id, "qty": random.random()}

        return {"type": "PASS", "src": 0, "dest": 0, "qty": 0}

    def reset_fitness(self) -> None:
        self.fitness = 0

    def reset_memory(self) -> None:
        """Resetta la memoria temporale all'inizio di ogni match."""
        self.processor._prev_army_count = -1
        self.processor._prev_territory_count = -1
        self.processor._current_turn_id = -1
        self.processor._turn_start_territories = -1
        self.processor._consecutive_attacks = 0
        self.processor._territories_lost_last_turn = 0
        self.processor._last_game_territory_count = -1
