from typing import Dict, List

# ================================
# 🌎 TERRITORIES (Risiko Classic)
# ================================

TERRITORIES: Dict[int, Dict] = {
    # ------------------------------
    # NORTH AMERICA (0 - 8)
    # ------------------------------
    0:  {"name": "Alaska", "continent": "NORTH_AMERICA", "neighbors": [1, 3, 29]},
    1:  {"name": "Northwest Territory", "continent": "NORTH_AMERICA", "neighbors": [0, 3, 4, 2]},
    2:  {"name": "Greenland", "continent": "NORTH_AMERICA", "neighbors": [1, 4, 5, 14]},
    3:  {"name": "Alberta", "continent": "NORTH_AMERICA", "neighbors": [0, 1, 4, 6]},
    4:  {"name": "Ontario", "continent": "NORTH_AMERICA", "neighbors": [1, 3, 6, 7, 5, 2]},
    5:  {"name": "Quebec", "continent": "NORTH_AMERICA", "neighbors": [4, 7, 2]},
    6:  {"name": "Western US", "continent": "NORTH_AMERICA", "neighbors": [3, 4, 7, 8]},
    7:  {"name": "Eastern US", "continent": "NORTH_AMERICA", "neighbors": [4, 5, 6, 8]},
    8:  {"name": "Central America", "continent": "NORTH_AMERICA", "neighbors": [6, 7, 9]},

    # ------------------------------
    # SOUTH AMERICA (9 - 12)
    # ------------------------------
    9:  {"name": "Venezuela", "continent": "SOUTH_AMERICA", "neighbors": [8, 10, 11]},
    10: {"name": "Peru", "continent": "SOUTH_AMERICA", "neighbors": [9, 11, 12]},
    11: {"name": "Brazil", "continent": "SOUTH_AMERICA", "neighbors": [9, 10, 12, 21]},
    12: {"name": "Argentina", "continent": "SOUTH_AMERICA", "neighbors": [10, 11]},

    # ------------------------------
    # EUROPE (13 - 19)
    # ------------------------------
    13: {"name": "Iceland", "continent": "EUROPE", "neighbors": [2, 14, 15]},
    14: {"name": "Great Britain", "continent": "EUROPE", "neighbors": [13, 15, 16, 17]},
    15: {"name": "Scandinavia", "continent": "EUROPE", "neighbors": [13, 14, 16, 19]},
    16: {"name": "Northern Europe", "continent": "EUROPE", "neighbors": [14, 15, 19, 18, 17]},
    17: {"name": "Western Europe", "continent": "EUROPE", "neighbors": [14, 16, 18, 21]},
    18: {"name": "Southern Europe", "continent": "EUROPE", "neighbors": [16, 19, 35, 22, 21, 17]},
    19: {"name": "Ukraine", "continent": "EUROPE", "neighbors": [15, 16, 18, 35, 34, 27]},

    # ------------------------------
    # AFRICA (20 - 25)
    # ------------------------------
    20: {"name": "North Africa", "continent": "AFRICA", "neighbors": [11, 17, 18, 22, 23, 21]},
    21: {"name": "Egypt", "continent": "AFRICA", "neighbors": [20, 18, 35, 23]},
    22: {"name": "East Africa", "continent": "AFRICA", "neighbors": [21, 20, 23, 24, 25, 35]},
    23: {"name": "Congo", "continent": "AFRICA", "neighbors": [20, 22, 24]},
    24: {"name": "South Africa", "continent": "AFRICA", "neighbors": [23, 22, 25]},
    25: {"name": "Madagascar", "continent": "AFRICA", "neighbors": [24, 22]},

    # ------------------------------
    # ASIA (26 - 37)
    # ------------------------------
    26: {"name": "Ural", "continent": "ASIA", "neighbors": [19, 27, 32, 34]},
    27: {"name": "Siberia", "continent": "ASIA", "neighbors": [26, 28, 30, 31, 32]},
    28: {"name": "Yakutsk", "continent": "ASIA", "neighbors": [27, 29, 30]},
    29: {"name": "Kamchatka", "continent": "ASIA", "neighbors": [28, 30, 31, 0]},
    30: {"name": "Irkutsk", "continent": "ASIA", "neighbors": [27, 28, 29, 31]},
    31: {"name": "Mongolia", "continent": "ASIA", "neighbors": [27, 30, 29, 33, 32]},
    32: {"name": "China", "continent": "ASIA", "neighbors": [26, 27, 31, 33, 36, 34]},
    33: {"name": "Japan", "continent": "ASIA", "neighbors": [29, 31]},
    34: {"name": "Afghanistan", "continent": "ASIA", "neighbors": [19, 26, 32, 35, 36]},
    35: {"name": "Middle East", "continent": "ASIA", "neighbors": [18, 19, 34, 36, 21, 22]},
    36: {"name": "India", "continent": "ASIA", "neighbors": [35, 34, 32, 37]},
    37: {"name": "Siam", "continent": "ASIA", "neighbors": [36, 32, 38]},

    # ------------------------------
    # OCEANIA (38 - 41)
    # ------------------------------
    38: {"name": "Indonesia", "continent": "OCEANIA", "neighbors": [37, 39, 40]},
    39: {"name": "New Guinea", "continent": "OCEANIA", "neighbors": [38, 40, 41]},
    40: {"name": "Western Australia", "continent": "OCEANIA", "neighbors": [38, 39, 41]},
    41: {"name": "Eastern Australia", "continent": "OCEANIA", "neighbors": [39, 40]},
}