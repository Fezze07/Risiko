import pickle
import os
import json
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
                    return pickle.load(f)
            except (EOFError, pickle.UnpicklingError, Exception) as e:
                print(f"[TrainerUtils] Errore nel caricamento di {path}: {e}")
                return None
        return None

    @staticmethod
    def update_records(
        best_fit: float,
        avg_fit: float,
        metrics: Dict[str, float],
        filename: str = 'records.json',
    ) -> bool:
        records: Dict[str, Any] = {
            'all_time_best': None,
            'all_time_avg': None,
            'metrics': {},
        }

        path = filename
        if not os.path.exists(path):
            path = os.path.join('dataset', filename)

        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    records = json.load(f)
            except (json.JSONDecodeError, OSError) as exc:
                print(f"[TrainerUtils] Impossibile leggere {path}: {exc}")

        updated = False

        if records.get('all_time_best') is None or best_fit > records['all_time_best']:
            records['all_time_best'] = round(best_fit, 2)
            updated = True

        if records.get('all_time_avg') is None or avg_fit > records['all_time_avg']:
            records['all_time_avg'] = round(avg_fit, 2)
            updated = True

        metrics_record = records.get('metrics', {})
        for key, value in metrics.items():
            prev = metrics_record.get(key)
            if prev is None or value > prev:
                metrics_record[key] = round(value, 2)
                updated = True
        records['metrics'] = metrics_record

        if updated:
            dataset_path = os.path.join('dataset', filename)
            with open(dataset_path, 'w') as f:
                json.dump(records, f, indent=4)
            return True
        return False
