from typing import Dict, Any

class Config:
    # =========================================
    # 🌍 GAME SETTINGS (Il Mondo Fisico)
    # =========================================
    GAME: Dict[str, Any] = {
        "NUM_TERRITORIES": 42,
        "MAX_TURNS": 250,
        "NUM_PLAYERS": 6,
        "INITIAL_PLACEMENT_ARMIES_PER_TERRITORY": 1.5,
        "INITIAL_PLACEMENT_STEP_DIVISOR": 4,
        "MAX_ARMIES_PER_TERRITORY": 30,
        "RISK_RATIO": 1.7,
        "MAX_TOTAL_ARMIES": 100,
        "STARTING_ARMIES": 1,
        "BONUS_ARMIES_DIVISOR": 3,
        "MIN_BONUS": 1,
        "MIN_REINFORCE_QTY": 0.05,
        "MIN_POST_CONQUEST_MOVE": 2,
        "PHASES": ["INITIAL_PLACEMENT", "REINFORCE", "ATTACK", "POST_ATTACK_MOVE", "MANEUVER"]
    }

    # =========================================
    # 🗺️ CONTINENTS
    # =========================================
    CONTINENTS = {
        "NORTH_AMERICA": {"t_ids": list(range(0, 9)), "bonus": 5},
        "SOUTH_AMERICA": {"t_ids": list(range(9, 13)), "bonus": 2},
        "EUROPE": {"t_ids": list(range(13, 20)), "bonus": 5},
        "AFRICA": {"t_ids": list(range(20, 26)), "bonus": 3},
        "ASIA": {"t_ids": list(range(26, 38)), "bonus": 7},
        "OCEANIA": {"t_ids": list(range(38, 42)), "bonus": 2},
    }

    # =========================================
    # 📝 TASK da completare per vincere la partita
    # =========================================
    MISSIONS: Dict[str, Dict[str, Any]] = {
        # --- DOMINATION (Hard & Insane) ---
        "DOMINATION_60": {"type": "territory_count", "target": 0.70},
        "DOMINATION_80": {"type": "territory_count", "target": 0.80},
        "TOTAL_CONTROL": {"type": "territory_count", "target": 1.00},

        # --- EMPIRE (Realistiche stile Risiko) ---
        "CONTROL_NA_AU": { "type": "continents", "target": ["NORTH_AMERICA", "OCEANIA"]},
        "CONTROL_EU_SA": { "type": "continents","target": ["EUROPE", "SOUTH_AMERICA"]},
        "CONTROL_AS_SA": { "type": "continents", "target": ["ASIA", "SOUTH_AMERICA"]},
        "CONTROL_EU_AU": { "type": "continents", "target": ["EUROPE", "OCEANIA"]},
        "CONTROL_NA_AF": { "type": "continents","target": ["NORTH_AMERICA", "AFRICA"]},
        "CONTROL_AS_AF": { "type": "continents","target": ["ASIA", "AFRICA"]},
        "CONTROL_3_ANY": { "type": "continent_count","target": 3},
        "CONTROL_4_ANY": { "type": "continent_count", "target": 4}
    }

    # =========================================
    # 🧠 NEURAL NETWORK SETTINGS (Il Cervello)
    # =========================================
    NN: Dict[str, Any] = {
        "HIDDEN_LAYERS": [128, 64, 32],  # Architettura: 2 strati nascosti
        # L'input sarà: (Num Territori * 3) -> Stato, Armate, Minaccia
        # L'output sarà: [Azione, Sorgente, Destinazione, Quantità]
        "OUTPUT_SIZE": 4,
        "EPSILON-GREEDY": 0.12,
        "ATTACK_DECISION_THRESHOLD": 0.2,
        "MANEUVER_DECISION_THRESHOLD": 0.45,
        "ATTACK_MIN_RATIO": 1.0,
    }

    # =========================================
    # 🧬 EVOLUTION SETTINGS (Motore Genetico)
    # =========================================
    EVOLUTION: Dict[str, Any] = {
        "POPULATION_SIZE": 100,       # Quanti agenti per generazione
        "GENERATIONS": 500,          # Quante epoche di evoluzione
        "ELITISM_COUNT": 20,          # I top 20 passano alla prossima gen senza modifiche (immortali)
        "TOURNAMENT_SIZE": 8,         # Da quante persone è composto il torneo
        "MUTATION_RATE": 0.25,         # Probabilità che un peso cambi
        "MUTATION_STRENGTH": 0.05,     # Quanto forte è lo "scossone" al peso (deviazione standard)
        "MUTATION_STRENGTH_MIN": 0.02, # Limite inferiore della mutazione dinamica
        "MUTATION_STRENGTH_MAX": 0.12, # Limite superiore della mutazione dinamica
        "MUTATION_STRENGTH_BOOST": 1.5,# Fattore di aumento mutazione in stallo breve
        "CROSSOVER_RATE": 0.7,        # Frequenza di scambio DNA tra genitori
        "STAGNATION_WINDOW": 8,       # Finestra generazioni per rilevare stallo
        "STAGNATION_TRIGGER": 40,     # Generazioni consecutive prima della "catastrofe"
        "CATASTROPHE_MUTATION_RATE": 0.35, # Quota geni mutati nella catastrofe
        "CATASTROPHE_STRENGTH_MULT": 1.5,  # Moltiplicatore forza mutazione in catastrofe
        "EPSILON_MIN": 0.02,          # Limite minimo esplorazione
        "EPSILON_DECAY": 0.990,       # Decadimento epsilon per generazione
    }

    # =========================================
    # 👤 HUMAN DATASET (Imitation Learning)
    # =========================================
    HUMAN_DATA: Dict[str, Any] = {
        "ENABLED": True,
        "DATASET_PATH": "dataset/human_dataset.jsonl",
        "MIN_SAMPLES": 100,
        "SAMPLE_SIZE": 512,
        "IMITATION_WEIGHT": 100.0,
    }

    # =========================================
    # 💎 REWARDS (La Motivazione)
    # =========================================
    REWARD: Dict[str, int] = {
        # --- ESITI PARTITA ---
        "WIN": 7000,
        "LOSS": -8000,
        "STALEMATE_PENALTY": -4000,
        # --- RINFORZI ---
        "REINFORCE_ARMY": 0,
        "REINFORCE_STRATEGIC_MULT": 2,
        "REINFORCE_SAFE_MULT": 0,
        "REINFORCE_SAFE_PENALTY": -25,
        "REINFORCE_STACK_PENALTY": -25,
        "REINFORCE_STACK_THRESHOLD": 12,
        "REINFORCE_REPEAT_PENALTY": -30,
        # --- ATTACCO / COMBATTIMENTO ---
        "CONQUER_TERRITORY": 250,
        "LOSE_TERRITORY": -300,
        "KILL_ENEMY_ARMY": 30,
        "LOSE_ARMY": -8,
        "ATTACK_RISK_PENALTY": -140,
        "AVOID_RISK_BONUS": 35,
        "LEAVE_ONE_ARMY_PENALTY": -280,
        "POST_ATTACK_RISK_PENALTY": -200,
        "POST_ATTACK_LEAVE_ONE_PENALTY": -300,
        "CONQUEST_STREAK_CAP": 3,
        "PASS_ATTACK_PENALTY": -40,
        "PASS_REPEAT_PENALTY": -10,
        "PASSIVE_TURN_PENALTY": -10,
        # --- DIFESA / PRESIDIO ---
        "DEFEND_BONUS": 25,
        "DEFEND_HOLD_TERRITORY": 70,
        "FRONTLINE_STABLE_BONUS": 250,
        "FRONTLINE_FORTIFIED_BONUS": 400,
        "VALID_SAFE_ACTION_BONUS": 8,
        # --- MANOVRA ---
        "MANEUVER_CORRECTLY": 10,
        "MANEUVER_PENALTY": -80,
        "MANEUVER_STRATEGIC": 60,
        # --- CONTINENTI / CONTROLLO MAPPA ---
        "HOLD_CONTINENT": 70,
        "CONQUER_CONTINENT": 150,
        "LOSE_CONTINENT": -2000,
        # --- PROGRESSO VERSO LA VITTORIA ---
        "PROGRESS_TERRITORY_SCALE": 40,
        "PROGRESS_CONTINENT_SCALE": 30,
        # --- ERRORI / STALLO / TEMPO ---
        "INVALID_MOVE": -100,
        "INVALID_MOVE_ATTACK": -200,
        "CONSECUTIVE_INVALID_MOVE": -500,
        "GAME_LENGTH_PENALTY": -10,
    }
