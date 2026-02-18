from typing import Dict, Any

class Config:
    
    # =========================================
    # ⚙️ UTILS & DEBUG
    # =========================================
    DEBUG: Dict[str, Any] = {
        "LONG_SESSION": True
    }
    # =========================================
    # 🌍 GAME SETTINGS (Il Mondo Fisico)
    # =========================================
    GAME: Dict[str, Any] = {
        "NUM_PLAYERS": 2,
        "NUM_TERRITORIES": 25,
        "MAX_TURNS": 130,
        "MAX_ARMIES_PER_TERRITORY": 30,
        "MAX_TOTAL_ARMIES": 100,
        "STARTING_ARMIES": 1,
        "BONUS_ARMIES_DIVISOR": 3,
        "MIN_BONUS": 1,
        "MIN_REINFORCE_QTY": 0.05,
        "MIN_POST_CONQUEST_MOVE": 2,
        "INITIAL_PLACEMENT_TOTAL": 10,
        "INITIAL_PLACEMENT_STEP": 3,
        "PHASES": ["INITIAL_PLACEMENT", "REINFORCE", "ATTACK", "POST_ATTACK_MOVE", "MANEUVER"]
    }

    # =========================================
    # 🗺️ CONTINENTS (5x5 grid, 25 territories)
    # =========================================
    CONTINENTS: Dict[str, Dict[str, Any]] = {
        "NORTH_WEST": {"t_ids": [0, 1, 5, 6, 10, 11], "bonus": 3},
        "NORTH_EAST": {"t_ids": [3, 4, 8, 9, 13, 14], "bonus": 3},
        "SOUTH_WEST": {"t_ids": [10, 11, 15, 16, 20, 21], "bonus": 3},
        "SOUTH_EAST": {"t_ids": [13, 14, 18, 19, 23, 24], "bonus": 3},
        "CENTER":     {"t_ids": [7, 12, 17], "bonus": 2}
    }

    # =========================================
    # 📝 TASK da completare per vincere la partita
    # =========================================
    MISSIONS: Dict[str, Dict[str, Any]] = {
        # --- DOMINATION (Hard & Insane) ---
        "DOMINATION_60": {"type": "territory_count", "target": 0.70},
        "DOMINATION_80": {"type": "territory_count", "target": 0.80},
        "TOTAL_CONTROL": {"type": "territory_count", "target": 1.00},

        # --- EMPIRE  ---
        "EMPIRE_NW_SE": {"type": "continents", "target": ["NORTH_WEST", "SOUTH_EAST"]},
        "EMPIRE_NE_SW": {"type": "continents", "target": ["NORTH_EAST", "SOUTH_WEST"]},
        "TRIAD": {"type": "continents", "target": ["NORTH_WEST", "NORTH_EAST", "CENTER"]},
        "MAP_CONTROL": {"type": "continents", "target": ["NORTH_WEST", "NORTH_EAST", "SOUTH_WEST", "SOUTH_EAST"]}
    }

    # =========================================
    # 🧠 NEURAL NETWORK SETTINGS (Il Cervello)
    # =========================================
    NN: Dict[str, Any] = {
        "HIDDEN_LAYERS": [128, 64, 32],  # Architettura: 2 strati nascosti
        # L'input sarà: (Num Territori * 3) -> Stato, Armate, Minaccia
        # L'output sarà: [Azione, Sorgente, Destinazione, Quantità]
        "OUTPUT_SIZE": 4,
        "EPSILON-GREEDY": 0.05,
        "ATTACK_DECISION_THRESHOLD": 0.6,
        "MANEUVER_DECISION_THRESHOLD": 0.6,
        "ATTACK_MIN_RATIO": 1.15
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
        "IMITATION_WEIGHT": 500.0,
    }

    # =========================================
    # 💎 REWARDS (La Motivazione)
    # =================================s========
    REWARD: Dict[str, int] = {
        # --- ESITI PARTITA ---
        "WIN": 10000,
        "LOSS": -7000,
        # --- RINFORZI ---
        "REINFORCE_ARMY": 0,
        "REINFORCE_STRATEGIC_MULT": 4,
        "REINFORCE_SAFE_MULT": 0,
        "REINFORCE_SAFE_PENALTY": -15,
        "REINFORCE_STACK_PENALTY": -25,
        "REINFORCE_STACK_THRESHOLD": 8,
        "REINFORCE_REPEAT_PENALTY": -30,
        "PASS_REPEAT_PENALTY": -13,
        "ARMY_LIMIT_PENALTY": -80,
        # --- ATTACCO / COMBATTIMENTO ---
        "CONQUER_TERRITORY": 30,
        "LOSE_TERRITORY": -300,
        "KILL_ENEMY_ARMY": 10,
        "LOSE_ARMY": -8,
        "ATTACK_RISK_PENALTY": -150,
        "AVOID_RISK_BONUS": 15,
        "LEAVE_ONE_ARMY_PENALTY": -300,
        "CONQUEST_STREAK_CAP": 3,
        # --- DIFESA / PRESIDIO ---
        "DEFEND_BONUS": 25,
        "DEFEND_HOLD_TERRITORY": 70,
        "FRONTLINE_STABLE_BONUS": 100,
        "FRONTLINE_FORTIFIED_BONUS": 150,
        "VALID_SAFE_ACTION_BONUS": 8,
        # --- MANOVRA ---
        "MANEUVER_CORRECTLY": 10,
        "MANEUVER_PENALTY": -40,
        "MANEUVER_STRATEGIC": 60,
        # --- CONTINENTI / CONTROLLO MAPPA ---
        "HOLD_CONTINENT": 80,
        "CONQUER_CONTINENT": 150,
        "LOSE_CONTINENT": -2000,
        # --- PROGRESSO VERSO LA VITTORIA ---
        "PROGRESS_TERRITORY_SCALE": 40,
        "PROGRESS_CONTINENT_SCALE": 30,
        # --- ERRORI / STALLO / TEMPO ---
        "INVALID_MOVE": -100,
        "INVALID_MOVE_ATTACK": -200,
        "CONSECUTIVE_INVALID_MOVE": -500,
        "STALEMATE_PENALTY": -30,
        "GAME_LENGTH_PENALTY": -2,
    }

