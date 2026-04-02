from typing import Dict, Any

class Config:
    # =========================================
    # GAME SETTINGS
    # =========================================
    GAME: Dict[str, Any] = {
        "NUM_TERRITORIES": 42,
        "MAX_TURNS": 400,
        "NUM_PLAYERS": 5,
        "INITIAL_PLACEMENT_ARMIES_PER_TERRITORY": 1.5,
        "INITIAL_PLACEMENT_STEP_DIVISOR": 4,
        "RISK_RATIO": 1.9,
        "MAX_TOTAL_ARMIES": 110,
        "STARTING_ARMIES": 1,
        "BONUS_ARMIES_DIVISOR": 3,
        "MIN_BONUS": 1,
        "PHASES": ["INITIAL_PLACEMENT", "REINFORCE", "ATTACK", "POST_ATTACK_MOVE", "MANEUVER"],
    }

    # =========================================
    # CONTINENTS
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
    #  TASK da completare per vincere la partita
    # =========================================
    MISSIONS: Dict[str, Dict[str, Any]] = {
        # --- DOMINATION ---
        "DOMINATION_60": {"type": "territory_count", "target": 0.70},
        "DOMINATION_80": {"type": "territory_count", "target": 0.80},
        "TOTAL_CONTROL": {"type": "territory_count", "target": 1.00},

        # --- EMPIRE  ---
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
    # NEURAL NETWORK
    # =========================================
    NN: Dict[str, Any] = {
        "HIDDEN_LAYERS": [256, 128, 128, 64],  # Architettura: 4 strati nascosti
        # L'input sarà: (Num Territori * 3) -> Stato, Armate, Minaccia
        # L'output sarà: [Azione, Sorgente, Destinazione, Quantità]
        "OUTPUT_SIZE": 4,
        "EPSILON-GREEDY": 0.12,
        "ATTACK_DECISION_THRESHOLD": 0.2,
        "MANEUVER_DECISION_THRESHOLD": 0.45,
        "ATTACK_MIN_RATIO": 1.0,
        "MIN_REINFORCE_QTY": 0.05,
        "MIN_POST_CONQUEST_MOVE": 2,
    }

    # =========================================
    # EVOLUTION SETTINGS
    # =========================================
    EVOLUTION: Dict[str, Any] = {
        "POPULATION_SIZE": 100,       # Quanti agenti per generazione
        "GENERATIONS": 1000000,       # Quante epoche di evoluzione
        "ELITISM_COUNT": 20,          # I top 20 passano alla prossima gen senza modifiche (immortali)
        "TOURNAMENT_SIZE": 12,         # Da quante persone è composto il torneo
        "MUTATION_RATE": 0.03,         # Probabilità che un peso cambi
        "MUTATION_STRENGTH": 0.05,     # Quanto forte è lo "scossone" al peso (deviazione standard)
        "MUTATION_STRENGTH_MIN": 0.02, # Limite inferiore della mutazione dinamica
        "MUTATION_STRENGTH_MAX": 0.12, # Limite superiore della mutazione dinamica
        "MUTATION_STRENGTH_BOOST": 1.5,# Fattore di aumento mutazione in stallo breve
        "CROSSOVER_RATE": 0.7,        # Frequenza di scambio DNA tra genitori
        "STAGNATION_WINDOW": 12,       # Finestra generazioni per rilevare stallo
        "STAGNATION_TRIGGER": 40,     # Generazioni consecutive prima della "catastrofe"
        "CATASTROPHE_MUTATION_RATE": 0.35, # Quota geni mutati nella catastrofe
        "CATASTROPHE_STRENGTH_MULT": 1.5,  # Moltiplicatore forza mutazione in catastrofe
        "EPSILON_MIN": 0.02,          # Limite minimo esplorazione
        "EPSILON_DECAY": 0.990,       # Decadimento epsilon per generazione
    }

    # =========================================
    # HUMAN DATASET (Imitation Learning)
    # =========================================
    HUMAN_DATA: Dict[str, Any] = {
        "ENABLED": True,
        "DATASET_PATH": "dataset/human_dataset.jsonl",
        "MIN_SAMPLES": 100,
        "SAMPLE_SIZE": 512,
        "IMITATION_WEIGHT": 100.0,
    }

    # ---------- CONFIGURAZIONE CARTE ----------
    CARDS: Dict[str, Any] = {
        "ENABLED": True,
        "NUM_JOLLIES": 2,
        "BONUS_3_INFANTRY": 4,      # 3 Fanteria
        "BONUS_3_CAVALRY": 6,       # 3 Cavalleria
        "BONUS_3_ARTILLERY": 8,     # 3 Artiglieria
        "BONUS_MIXED": 10,          # 1 Fanteria + 1 Cavalleria + 1 Artiglieria
        "BONUS_WITH_JOLLY": 10,     # Qualsiasi combinazione con Jolly
        "TERRITORY_BONUS": 2,       # +2 truppe se si possiede il territorio
    }

    # =========================================
    # REWARDS
    # =========================================
    REWARD: Dict[str, float | int] = {
        # --- ESITI PARTITA ---
        "WIN": 10000,
        "LOSS": -8000,
        "STALEMATE_PENALTY": -12000,
        "ELIMINATE_PLAYER": 2000,
        "ELIMINATION_PENALTY": -15000,
        # --- RINFORZI ---
        "REINFORCE_SAFE_PENALTY": -15,          # Penalità base
        "REINFORCE_SAFE_PENALTY_PER_ARMY": -3,  # Penalità aggiuntiva PER OGNI armata piazzata in zona sicura
        "REINFORCE_CHOKEPOINT_BONUS": 15,
        # --- ATTACCO / COMBATTIMENTO ---
        "CONQUER_TERRITORY": 60,
        "CONQUEST_DECAY_FACTOR": 0.65,
        "CONQUER_CHOKEPOINT_BONUS": 30,
        "LOSE_ARMY": -15,
        "ATTACK_RISK_PENALTY": -30,
        # --- CONTINENTI / CONTROLLO MAPPA ---
        "CONQUER_CONTINENT": 50,
        # --- FINE FASE ---
        "END_PHASE_LEAVE_ONE_PENALTY": -30,
        # --- PASSAGGIO TURNO ---
        "PASSIVE_TURN_PENALTY": -100,
        "PASS_PENALTY_CAP": -10000,
        # --- DIFESA / PRESIDIO ---
        "FRONTLINE_GARRISON_BONUS": 20,
        "END_TURN_WITH_2_GARRISON_ARMY": 20,
        # --- MANOVRA ---
        "MANEUVER_TO_FRONT_BASE": 35,
        "MANEUVER_TO_FRONT_PER_ARMY": 8,     # Reward aggiuntivo PER OGNI armata spostata al fronte
        "MANEUVER_PROXIMITY_BONUS": 10,        # Bonus gradiente: ci si avvicina al fronte da interne
        "MANEUVER_TO_CHOKEPOINT": 20,
        "INTERNAL_ARMY_PENALTY": -2,         # Penalità base per armata inattiva nelle retrovie
        "INTERNAL_ARMY_HEAVY_THRESHOLD": 5,   # Oltre questo numero, penalità x2 per armata extra
        # --- ERRORI / STALLO / TEMPO ---
        "INVALID_MOVE": -30,
        "CONSECUTIVE_INVALID_MOVE": -400,
        "GAME_LENGTH_PENALTY": -8,
    }
