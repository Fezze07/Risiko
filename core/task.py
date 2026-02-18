from config import Config

class MissionManager:
    @staticmethod
    def assign_mission():
        #Assegniamo una missione random
        import random
        mission_name = random.choice(list(Config.MISSIONS.keys()))
        return mission_name, Config.MISSIONS[mission_name]

    @staticmethod
    def check_completion(mission, board, player_id):
        m_type = mission["type"]

        #1 Obiettivo: Percentuale Mappa
        if m_type == "territory_count":
            player_lands = len(board.get_player_territories(player_id))
            needed = int(board.n * mission["target"])
            return player_lands >= needed

        #2 Obiettivo: Continenti Specifici
        elif m_type == "continents":
            targets = mission["target"]
            for zone_name in targets:
                t_ids = Config.CONTINENTS[zone_name]["t_ids"]

                # Se manca anche solo un territorio della zona, missione fallita
                if not all(board.territories[tid].owner_id == player_id for tid in t_ids):
                    return False
            return True  # Se il loop finisce bene, hai vinto

        return False