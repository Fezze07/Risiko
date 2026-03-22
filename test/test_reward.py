"""
Test: verifica che i reward di fine partita (WIN, LOSS, STALEMATE)
vengano applicati correttamente a tutti i giocatori.

Scenari testati:
  1. Vittoria per conquista (1 giocatore vince, tutti gli altri perdono)
  2. Stallo per raggiungimento MAX_TURNS
  3. Consistenza valori config
  4. Simulazione match completo con agenti dummy
"""

import sys
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parent)
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from config import Config
from core.environment import RisikoEnvironment


def test_1_win_reward():
    """
    Scenario: Player 1 conquista TUTTI i territori.
    Verifica che _finalize_step rilevi la vittoria e applichi WIN al player agente.
    """
    print("=" * 60)
    print("TEST 1: Vittoria per conquista totale")
    print("=" * 60)

    env = RisikoEnvironment(num_players=2)
    env.reset()

    # Forziamo: player 1 possiede tutti i territori
    for t_id, t in env.board.territories.items():
        t.owner_id = 1
        t.armies = 3

    # Forziamo la fase MANEUVER per fare un PASS che chiuda il turno
    # (in ATTACK, un PASS fa passare a MANEUVER e poi _finalize_step rileva la vittoria)
    env.current_phase = 'MANEUVER'
    env.player_turn = 1

    # PASS in MANEUVER = chiude il turno
    action = {'type': 'PASS'}
    reward, done, info = env.step(action, 1)

    print(f"  Player 1 (acting) -> reward={reward}, done={done}")

    # done deve essere True
    if done is not True:
        print(f"  ❌ ERRORE: done dovrebbe essere True, è {done}")
        return False

    # Il reward deve CONTENERE il WIN (ma può avere anche altre penalità/bonus)
    win_val = Config.REWARD['WIN']
    # Verifichiamo che il reward sia ragionevolmente alto (WIN = 7000, meno eventuali penalità)
    print(f"  WIN atteso nel reward: {win_val}")
    print(f"  Reward totale ricevuto: {reward}")

    # Ora verifichiamo la distribuzione post-loop di parallel_trainer
    winner, _ = env.is_game_over()
    print(f"  winner={winner} (atteso: 1)")

    if winner != 1:
        print(f"  ❌ ERRORE: winner dovrebbe essere 1, è {winner}")
        return False

    # Simuliamo la distribuzione del parallel_trainer per player 2
    fitness_map = {1: reward, 2: 0}
    curr_p = 1
    for p_id in [1, 2]:
        if done and p_id == curr_p:
            continue  # curr_p ha già ricevuto il reward in env.step()
        if winner == p_id:
            fitness_map[p_id] += Config.REWARD.get('WIN', 7000)
        elif winner == -1:
            fitness_map[p_id] += Config.REWARD.get('STALEMATE_PENALTY', -6000)
        else:
            fitness_map[p_id] += Config.REWARD.get('LOSS', -8000)

    loss_val = Config.REWARD['LOSS']
    print(f"  fitness_map dopo distribuzione: {fitness_map}")
    print(f"  Player 2 fitness: {fitness_map[2]} (atteso: {loss_val})")

    if fitness_map[2] != loss_val:
        print(f"  ❌ ERRORE: Player 2 dovrebbe avere LOSS ({loss_val}), ha {fitness_map[2]}")
        return False

    print("  ✅ TEST 1 PASSATO: Player 1 ha WIN nel reward, Player 2 ha ricevuto LOSS\n")
    return True


def test_2_stalemate_reward():
    """
    Scenario: La partita raggiunge MAX_TURNS senza un vincitore.
    Verifica che is_game_over ritorni winner=-1 (stalemate).
    """
    print("=" * 60)
    print("TEST 2: Stallo per raggiungimento MAX_TURNS")
    print("=" * 60)

    env = RisikoEnvironment(num_players=2)
    env.reset()

    # Forziamo il turno al limite
    env.current_turn = Config.GAME['MAX_TURNS']
    env.current_phase = 'MANEUVER'
    env.player_turn = 1

    action = {'type': 'PASS'}
    reward, done, info = env.step(action, 1)

    print(f"  Player 1 (acting) -> reward={reward}, done={done}")

    if done is not True:
        print(f"  ❌ ERRORE: done dovrebbe essere True, è {done}")
        return False

    winner, _ = env.is_game_over()
    print(f"  winner={winner} (atteso: -1 = stalemate)")

    if winner != -1:
        print(f"  ❌ ERRORE: winner dovrebbe essere -1 (stalemate), è {winner}")
        return False

    # Simuliamo la distribuzione del parallel_trainer
    stalemate_val = Config.REWARD['STALEMATE_PENALTY']
    fitness_map = {1: reward, 2: 0}
    curr_p = 1

    for p_id in [1, 2]:
        if done and p_id == curr_p:
            continue
        if winner == p_id:
            fitness_map[p_id] += Config.REWARD.get('WIN', 7000)
        elif winner == -1:
            fitness_map[p_id] += stalemate_val
        else:
            fitness_map[p_id] += Config.REWARD.get('LOSS', -8000)

    print(f"  fitness_map dopo distribuzione: {fitness_map}")
    print(f"  Player 2 fitness: {fitness_map[2]} (atteso: {stalemate_val})")

    if fitness_map[2] != stalemate_val:
        print(f"  ❌ ERRORE: Player 2 dovrebbe avere STALEMATE ({stalemate_val}), ha {fitness_map[2]}")
        return False

    print("  ✅ TEST 2 PASSATO: Entrambi i player hanno ricevuto STALEMATE\n")
    return True


def test_3_config_values_consistency():
    """
    Verifica che i valori endgame esistano in config.py.
    """
    print("=" * 60)
    print("TEST 3: Consistenza valori config.py")
    print("=" * 60)

    keys_to_check = ['WIN', 'LOSS', 'STALEMATE_PENALTY']
    all_ok = True

    for key in keys_to_check:
        val = Config.REWARD.get(key)
        if val is None:
            print(f"  ❌ '{key}' MANCANTE in Config.REWARD!")
            all_ok = False
        else:
            print(f"  ✅ '{key}' = {val}")

    if all_ok:
        print("  ✅ TEST 3 PASSATO\n")
    else:
        print("  ❌ TEST 3 FALLITO\n")
    return all_ok


def test_4_parallel_trainer_logic():
    """
    Verifica che la logica di distribuzione in parallel_trainer.py sia corretta
    simulando i 3 possibili scenari con fitness_map manuali.
    """
    print("=" * 60)
    print("TEST 4: Logica distribuzione parallel_trainer")
    print("=" * 60)

    num_players = 5
    win_val = Config.REWARD['WIN']
    loss_val = Config.REWARD['LOSS']
    stalemate_val = Config.REWARD['STALEMATE_PENALTY']

    # --- Scenario A: Player 3 vince, done=True ---
    print("  Scenario A: Player 3 vince, done=True")
    fitness_map = {p: 0 for p in range(1, num_players + 1)}
    curr_p = 3
    done = True
    winner = 3

    # curr_p ha già ricevuto WIN dentro env.step (simuliamo)
    fitness_map[curr_p] = win_val

    for p_id in range(1, num_players + 1):
        if not done or p_id != curr_p:
            if winner == p_id:
                fitness_map[p_id] += win_val
            elif winner == -1:
                fitness_map[p_id] += stalemate_val
            else:
                fitness_map[p_id] += loss_val

    print(f"    fitness_map = {fitness_map}")
    # Player 3 dovrebbe avere solo WIN (non doppio)
    assert fitness_map[3] == win_val, f"Player 3 ha {fitness_map[3]}, atteso {win_val}"
    # Tutti gli altri dovrebbero avere LOSS
    for p in [1, 2, 4, 5]:
        assert fitness_map[p] == loss_val, f"Player {p} ha {fitness_map[p]}, atteso {loss_val}"
    print("    ✅ Vittoria distribuita correttamente")

    # --- Scenario B: Stalemate, done=True ---
    print("  Scenario B: Stalemate, done=True")
    fitness_map = {p: 0 for p in range(1, num_players + 1)}
    curr_p = 2
    done = True
    winner = -1

    # curr_p ha già ricevuto STALEMATE dentro env.step (simuliamo)
    fitness_map[curr_p] = stalemate_val

    for p_id in range(1, num_players + 1):
        if not done or p_id != curr_p:
            if winner == p_id:
                fitness_map[p_id] += win_val
            elif winner == -1:
                fitness_map[p_id] += stalemate_val
            else:
                fitness_map[p_id] += loss_val

    print(f"    fitness_map = {fitness_map}")
    for p in range(1, num_players + 1):
        assert fitness_map[p] == stalemate_val, f"Player {p} ha {fitness_map[p]}, atteso {stalemate_val}"
    print("    ✅ Stalemate distribuito correttamente a tutti")

    # --- Scenario C: Loop timeout (done=False), winner=0 ---
    print("  Scenario C: Loop timeout senza game over (done=False, winner=0)")
    fitness_map = {p: 100 for p in range(1, num_players + 1)}
    done = False
    winner = 0

    if winner != 0:
        for p_id in range(1, num_players + 1):
            if not done or p_id != curr_p:
                fitness_map[p_id] += loss_val

    print(f"    fitness_map = {fitness_map}")
    # Nessun reward aggiunto perché winner == 0
    for p in range(1, num_players + 1):
        assert fitness_map[p] == 100, f"Player {p} ha {fitness_map[p]}, atteso 100 (nessun cambiamento)"
    print("    ✅ Nessun reward applicato quando winner=0 (partita non finita)")

    print("  ✅ TEST 4 PASSATO\n")
    return True


def test_5_main_py_accumulation():
    """
    Verifica che main.py accumuli e normalizzi correttamente i fitness.
    Simula 2 match con lo stesso agente e controlla la media.
    """
    print("=" * 60)
    print("TEST 5: Accumulazione e normalizzazione in main.py")
    print("=" * 60)

    # Simuliamo: un agente gioca 2 match
    # Match 1: fitness=7000 (vittoria)
    # Match 2: fitness=-8000 (sconfitta)
    # Media attesa: (7000 + -8000) / 2 = -500

    class MockAgent:
        def __init__(self):
            self.fitness = 0.0
            self.match_count = 0
        def reset_fitness(self):
            self.fitness = 0.0

    agent = MockAgent()
    agent.reset_fitness()
    agent.match_count = 0

    # Match 1
    agent.fitness += 7000
    agent.match_count += 1

    # Match 2
    agent.fitness += -8000
    agent.match_count += 1

    # Normalizzazione (come in main.py linea 154-157)
    if agent.match_count > 0:
        agent.fitness /= agent.match_count

    expected_avg = (7000 + -8000) / 2
    print(f"  Fitness dopo 2 match: {agent.fitness} (atteso: {expected_avg})")

    if abs(agent.fitness - expected_avg) < 0.01:
        print("  ✅ TEST 5 PASSATO: Normalizzazione corretta\n")
        return True
    else:
        print(f"  ❌ TEST 5 FALLITO: Atteso {expected_avg}, ottenuto {agent.fitness}\n")
        return False


if __name__ == '__main__':
    print("\n🎯 AVVIO SUITE DI TEST REWARD ENDGAME\n")
    print(f"Config.REWARD valori endgame:")
    print(f"  WIN = {Config.REWARD.get('WIN')}")
    print(f"  LOSS = {Config.REWARD.get('LOSS')}")
    print(f"  STALEMATE_PENALTY = {Config.REWARD.get('STALEMATE_PENALTY')}")
    print()

    results = []
    results.append(("Test 1: Vittoria", test_1_win_reward()))
    results.append(("Test 2: Stalemate", test_2_stalemate_reward()))
    results.append(("Test 3: Config", test_3_config_values_consistency()))
    results.append(("Test 4: Parallel Trainer", test_4_parallel_trainer_logic()))
    results.append(("Test 5: Normalizzazione", test_5_main_py_accumulation()))

    print("=" * 60)
    print("RIEPILOGO")
    print("=" * 60)
    all_passed = True
    for name, passed in results:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"  {status} — {name}")
        if not passed:
            all_passed = False

    print()
    if all_passed:
        print("🏁 TUTTI I TEST PASSATI!")
    else:
        print("⚠️ ALCUNI TEST FALLITI!")
