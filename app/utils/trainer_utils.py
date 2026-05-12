import pickle
import os
from typing import Any, Optional, Dict


class TrainerUtils:
    @staticmethod
    def load_weights(filename: str = 'best_agent.pkl') -> Optional[Any]:
        # Try dataset folder if it exists there
        path = filename
        if not os.path.exists(path):
            path = os.path.join('dataset', filename)
            
        if os.path.exists(path):
            if os.path.getsize(path) == 0:
                print(f"[TrainerUtils] Salto caricamento: {path} è vuoto.")
                return None
            try:
                with open(path, 'rb') as f:
                    data = pickle.load(f)
                    # Support both old format (array) and new format (dict)
                    if isinstance(data, dict) and 'weights' in data:
                        return data['weights']
                    return data
            except (EOFError, pickle.UnpicklingError, Exception) as e:
                print(f"[TrainerUtils] Errore nel caricamento di {path}: {e}")
                return None
        return None
