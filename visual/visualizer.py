import os
from colorama import init, Fore, Style
from core.config import Config
import math

init(autoreset=True)


class Visualizer:
    BLUE = Fore.BLUE + Style.BRIGHT
    RED = Fore.RED + Style.BRIGHT
    YELLOW = Fore.YELLOW + Style.BRIGHT
    RESET = Style.RESET_ALL
    BOLD = Style.BRIGHT

    @staticmethod
    def render_board(board, turn, phase, player_id, mission, p1_score, p2_score, logs):
        os.system('cls' if os.name == 'nt' else 'clear')

        print(f"{Visualizer.BOLD}=== RISIKO AI WATCHER ==={Visualizer.RESET}")
        p_color = Visualizer.BLUE if player_id == 1 else Visualizer.RED

        print(
            f"Turno: {turn:03d} | Fase: {p_color}{phase:<16}{Visualizer.RESET} "
            f"| Muove: {p_color}Player {player_id}{Visualizer.RESET}"
        )
        mission_label, mission_details = Visualizer._format_mission(mission)
        if mission_details:
            print(f"Missione: {Visualizer.YELLOW}{mission_label} ({mission_details}){Visualizer.RESET}")
        else:
            print(f"Missione: {Visualizer.YELLOW}{mission_label}{Visualizer.RESET}")
        print(
            f"{Visualizer.BLUE}P1 Score: {p1_score:<10.2f}{Visualizer.RESET} | "
            f"{Visualizer.RED}P2 Score: {p2_score:<10.2f}{Visualizer.RESET}"
        )
        print('=' * 60 + '\n')

        n = board.n
        cols = int(math.sqrt(n))
        rows = n // cols

        print('     ' + ' '.join([f'   {i:02d}    ' for i in range(cols)]))

        for row in range(rows):
            row_str = f'{row:02d} '
            for col in range(cols):
                t_id = row * cols + col
                t = board.territories[t_id]

                if t.owner_id == 1:
                    color = Visualizer.BLUE
                    symbol = 'P1'
                elif t.owner_id == 2:
                    color = Visualizer.RED
                    symbol = 'P2'
                else:
                    color = Fore.WHITE
                    symbol = '--'

                cell_content = f'{t_id:02d}|{symbol}:{t.armies:03d}'
                row_str += f'{color}[{cell_content}]{Visualizer.RESET} '

            print(row_str)

        print('\n' + '=' * 60)
        print(
            f"{Visualizer.BOLD}LOG ULTIME AZIONI (Player | Azione | Da->A | Q.ta | Rew):{Visualizer.RESET}"
        )

        for entry in logs[-20:]:
            if 'ERROR:' in entry:
                print(f'{Fore.YELLOW}{entry}{Visualizer.RESET}')
            elif 'VITTORIA' in entry or 'Conquista' in entry or 'Continente preso' in entry:
                print(f'{Fore.GREEN}{Style.BRIGHT}{entry}{Visualizer.RESET}')
            elif entry.startswith('P1'):
                print(f'{Fore.CYAN}{entry}{Visualizer.RESET}')
            elif entry.startswith('P2'):
                print(f'{Fore.LIGHTRED_EX}{entry}{Visualizer.RESET}')
            else:
                print(f'  {entry}')

    @staticmethod
    def _format_mission(mission) -> tuple[str, str]:
        if not mission:
            return "unknown", ""

        # Supporta sia mission name (str) che mission dict
        if isinstance(mission, str):
            data = Config.MISSIONS.get(mission)
            if not data:
                return mission, ""
            return Visualizer._format_mission_from_data(mission, data)

        if isinstance(mission, dict):
            mission_type = mission.get("type", "unknown")
            return Visualizer._format_mission_from_data(mission_type, mission)

        return str(mission), ""

    @staticmethod
    def _format_mission_from_data(label: str, data: dict) -> tuple[str, str]:
        mission_type = data.get('type')
        target = data.get('target')
        if mission_type == 'territory_count':
            try:
                return label, f"target {int(float(target) * 100)}%"
            except Exception:
                return label, f"target {target}"
        if mission_type == 'continents' and isinstance(target, list):
            return label, " + ".join(str(t) for t in target)
        return label, ""
