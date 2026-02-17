import os
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.config import Config
import numpy as np

from ai.agent import Agent
from core.environment import RisikoEnvironment
from utils.trainer_utils import TrainerUtils
from utils.watch_match_utils import WatchMatchUtils


def run_single_match_log_check(max_turns: int = Config.GAME["MAX_TURNS"], seed: int = 123) -> str:
    random.seed(seed)
    np.random.seed(seed)

    env = RisikoEnvironment()
    env.reset()

    agent_p1 = Agent(env.board, id=1)
    agent_p2 = Agent(env.board, id=2)

    saved_weights = TrainerUtils.load_weights("best_agent.pkl")
    if saved_weights is not None:
        try:
            agent_p1.nn.set_weights(saved_weights)
            agent_p2.nn.set_weights(saved_weights)
            agent_p1.epsilon = 0.0
            agent_p2.epsilon = 0.0
        except Exception:
            agent_p1.epsilon = 1.0
            agent_p2.epsilon = 1.0
    else:
        agent_p1.epsilon = 1.0
        agent_p2.epsilon = 1.0

    done = False
    action_log = []

    for _ in range(max_turns):
        curr_p = env.player_turn
        phase = env.current_phase
        agent = agent_p1 if curr_p == 1 else agent_p2
        mission = env.p1_mission if curr_p == 1 else env.p2_mission

        action = agent.think(env.board, curr_p, env.current_turn, phase, mission)
        reward, done, info = env.step(action, curr_p)

        reason = WatchMatchUtils.get_reward_reason(action["type"], reward, info)
        log_entry = WatchMatchUtils.format_log_line(curr_p, action, reward, reason)
        action_log.append(log_entry)

        if done:
            break

    os.makedirs("logs", exist_ok=True)
    log_path = os.path.join("logs", "watch_match_log.txt")
    with open(log_path, "w", encoding="utf-8") as f:
        f.write("=== RISIKO AI WATCHER (MANUAL LOG) ===\n")
        f.write(f"Turni simulati: {min(max_turns, len(action_log))}\n")
        f.write("LOG PARTITA COMPLETA:\n")
        for entry in action_log:
            f.write(entry + "\n")

    print(f"[manual_match_log_check] Salvato log in {log_path}")
    for entry in action_log[-10:]:
        print(entry)
    return log_path


if __name__ == "__main__":
    run_single_match_log_check()
