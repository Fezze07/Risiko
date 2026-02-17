import random

from core.config import Config
from core.environment import RisikoEnvironment


def _seeded_environment() -> RisikoEnvironment:
    random.seed(0)
    env = RisikoEnvironment()
    env.reset()
    return env


def _find_frontline_territory(env: RisikoEnvironment, player_id: int):
    for territory in env.board.get_player_territories(player_id):
        if any(
            env.board.territories[n].owner_id != player_id
            for n in territory.neighbors
        ):
            return territory
    return None


def test_reinforce_frontline_reward():
    env = _seeded_environment()
    env.current_phase = "REINFORCE"
    env.player_turn = 1
    env.armies_to_place = 5

    frontline = _find_frontline_territory(env, 1)
    assert frontline is not None, "Serve un territorio di fronte per il test"

    action = {"type": "REINFORCE", "dest": frontline.id, "qty": 1.0}
    reward, _, _ = env.step(action, 1)

    assert reward >= Config.REWARD["REINFORCE_STRATEGIC_MULT"]


def test_attack_step_produces_valid_reward():
    env = _seeded_environment()
    env.current_phase = "ATTACK"
    env.player_turn = 1
    env.armies_to_place = 0

    attacker = _find_frontline_territory(env, 1)
    assert attacker is not None
    enemies = [
        env.board.territories[n_id]
        for n_id in attacker.neighbors
        if env.board.territories[n_id].owner_id != 1
    ]
    assert enemies, "Serve almeno un nemico confinante"
    target = enemies[0]

    attacker.armies = 5
    target.armies = 3

    action = {"type": "ATTACK", "src": attacker.id, "dest": target.id, "qty": 1.0}
    reward, _, _ = env.step(action, 1)
    assert reward != Config.REWARD["INVALID_MOVE"]


def test_maneuver_strategic_reward():
    env = _seeded_environment()
    env.current_phase = "MANEUVER"
    env.player_turn = 1

    src = env.board.territories[0]
    dest = env.board.territories[1]
    enemy = env.board.territories[2]

    src.owner_id = dest.owner_id = 1
    enemy.owner_id = 2
    src.neighbors = [dest.id]
    dest.neighbors = [src.id, enemy.id]
    enemy.neighbors = [dest.id]

    src.armies = 5
    dest.armies = 1

    prev_progress = env.progress_cache.get(1, 0)
    action = {"type": "MANEUVER", "src": src.id, "dest": dest.id, "qty": 0.5}
    reward, _, _ = env.step(action, 1)

    delta_progress = env.progress_cache.get(1, 0) - prev_progress
    expected = (
        Config.REWARD["MANEUVER_STRATEGIC"]
        + Config.REWARD["VALID_SAFE_ACTION_BONUS"]
        + delta_progress
    )
    assert reward == expected
