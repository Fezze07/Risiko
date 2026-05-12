import pickle
import os
import time
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

            # Try a few times in case file is being written (avoid partial-read race)
            attempts = 3
            for attempt in range(attempts):
                try:
                    with open(path, 'rb') as f:
                        data = pickle.load(f)
                        # Support both old format (array) and new format (dict)
                        if isinstance(data, dict) and 'weights' in data:
                            return data['weights']
                        return data
                except (EOFError, pickle.UnpicklingError) as e:
                    # Possibly writer in progress; wait and retry a bit
                    if attempt < attempts - 1:
                        time.sleep(0.2 * (attempt + 1))
                        continue
                    print(f"[TrainerUtils] Errore nel caricamento di {path}: {e}")
                    return None
                except Exception as e:
                    print(f"[TrainerUtils] Errore nel caricamento di {path}: {e}")
                    return None
        return None
