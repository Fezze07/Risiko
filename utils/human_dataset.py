import json
import os
import random
import numpy as np
from typing import Dict, Any, List, Optional
from core.config import Config


def _index_to_frac(idx: int, count: int) -> float:
    if count <= 1:
        return 0.0
    return idx / float(count - 1)


def encode_action_target(board, player_id: int, phase: str, action: Dict[str, Any]) -> Optional[List[float]]:
    action_type = action.get("type", "PASS")
    if action_type == "PASS":
        return [0.0, 0.0, 0.0, 0.0]

    qty = float(action.get("qty", 0.0))
    if qty < 0:
        qty = 0.0
    if qty > 1:
        qty = 1.0

    decision = 1.0
    src_val = 0.0
    dest_val = 0.0

    if phase == "REINFORCE":
        valid_targets = [
            t_id
            for t_id, t in board.territories.items()
            if t.owner_id == player_id and t.armies < Config.GAME["MAX_ARMIES_PER_TERRITORY"]
        ]
        if not valid_targets:
            return None
        dest = action.get("dest")
        if dest not in valid_targets:
            return None
        idx = valid_targets.index(dest)
        src_val = _index_to_frac(idx, len(valid_targets))
        dest_val = src_val

    elif phase == "ATTACK":
        if action_type != "ATTACK":
            return [0.0, 0.0, 0.0, qty]
        valid_sources = [
            t_id for t_id, t in board.territories.items()
            if t.owner_id == player_id and t.armies > 1
        ]
        if not valid_sources:
            return None
        src = action.get("src")
        if src not in valid_sources:
            return None
        idx_s = valid_sources.index(src)
        src_val = _index_to_frac(idx_s, len(valid_sources))

        enemies = [
            n for n in board.territories[src].neighbors
            if board.territories[n].owner_id != player_id
        ]
        if not enemies:
            return None
        dest = action.get("dest")
        if dest not in enemies:
            return None
        idx_d = enemies.index(dest)
        dest_val = _index_to_frac(idx_d, len(enemies))

    elif phase == "POST_ATTACK_MOVE":
        # Src/Dest non usati nella rete in questa fase
        src_val = 0.0
        dest_val = 0.0

    elif phase == "MANEUVER":
        if action_type != "MANEUVER":
            return [0.0, 0.0, 0.0, qty]
        valid_sources = [
            t_id for t_id, t in board.territories.items()
            if t.owner_id == player_id and t.armies > 1
        ]
        if not valid_sources:
            return None
        src = action.get("src")
        if src not in valid_sources:
            return None
        idx_s = valid_sources.index(src)
        src_val = _index_to_frac(idx_s, len(valid_sources))

        friends = [
            n for n in board.territories[src].neighbors
            if board.territories[n].owner_id == player_id
        ]
        if not friends:
            return None
        dest = action.get("dest")
        if dest not in friends:
            return None
        idx_d = friends.index(dest)
        dest_val = _index_to_frac(idx_d, len(friends))

    return [decision, src_val, dest_val, qty]


def append_sample(sample: Dict[str, Any], filename: str) -> None:
    os.makedirs(os.path.dirname(filename) or ".", exist_ok=True)
    with open(filename, "a", encoding="utf-8") as f:
        json.dump(sample, f, ensure_ascii=False)
        f.write("\n")


def load_samples(filename: str, max_samples: Optional[int] = None) -> List[Dict[str, Any]]:
    if not os.path.exists(filename):
        return []
    samples: List[Dict[str, Any]] = []
    with open(filename, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                samples.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    if max_samples and len(samples) > max_samples:
        samples = random.sample(samples, max_samples)
    return samples


def compute_imitation_bonus(agent, samples: List[Dict[str, Any]], weight: float) -> float:
    if not samples:
        return 0.0
    total_score = 0.0
    for sample in samples:
        state = np.asarray(sample.get("state", []), dtype=np.float32)
        target = np.asarray(sample.get("target", []), dtype=np.float32)
        if state.size == 0 or target.size == 0:
            continue
        output = agent.nn.forward(state)
        loss = np.mean((output - target) ** 2)
        score = max(0.0, 1.0 - float(loss))
        total_score += score
    if total_score <= 0:
        return 0.0
    avg_score = total_score / max(1, len(samples))
    return avg_score * weight
