import argparse
import concurrent.futures
import os

from typing import List, Tuple, Optional
from colorama import Fore, Style, init

from app.ai.agent import Agent
from app.ai.evolution import EvolutionManager
from config import Config
from app.core.environment import RisikoEnvironment
from app.utils.human_dataset import load_samples, compute_imitation_bonus
from app.utils.parallel_trainer import run_parallel_match
from app.utils.trainer_utils import TrainerUtils


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='Allenamento AI per Risiko.')
    parser.add_argument(
        '--generations',
        '-g',
        type=int,
        help="Sovrascrive il numero di generazioni dell'evoluzione.",
    )
    parser.add_argument(
        '--max-workers',
        '-w',
        type=int,
        help='Numero massimo di processi paralleli da usare.',
    )
    return parser.parse_args()


class Main:
    def __init__(
        self,
        *,
        generations: Optional[int],
        max_workers: Optional[int],
    ) -> None:
        init(autoreset=True)
        print('=== AVVIO TRAINING PARALLELO ===')
        self.env: RisikoEnvironment = RisikoEnvironment()
        self.evo_manager: EvolutionManager = EvolutionManager(self.env.board)
        self.max_generations = generations
        worker_count = max_workers or os.cpu_count() or 2
        self.executor = concurrent.futures.ProcessPoolExecutor(max_workers=worker_count)

        saved_weights = TrainerUtils.load_weights('best_agent.pkl')
        if saved_weights is not None:
            loaded = self.evo_manager.load_population('best_agent.pkl')
            if loaded:
                print('[Main] Brain caricato')

        try:
            self.run_training_loop()
        finally:
            self.executor.shutdown(wait=True)

    def _determine_generations(self) -> Optional[int]:
        if self.max_generations is not None:
            return self.max_generations
        return Config.EVOLUTION['GENERATIONS']

    def _build_match_tasks(
        self, population: List[Agent]
    ) -> List[Tuple[Tuple[Agent, ...], Tuple[int, ...]]]:
        tasks: List[Tuple[Tuple[Agent, ...], Tuple[int, ...]]] = []
        num_players = self.env.num_players
        
        # Per ogni agente nella popolazione, facciamo in modo che partecipi a circa TOURNAMENT_SIZE match
        for i in range(len(population)):
            for j in range(Config.EVOLUTION.get('TOURNAMENT_SIZE', 1)):
                match_agents_indices = [i]
                for k in range(1, num_players):
                    # Seleziona altri agenti casuali o sequenziali per completare il tavolo
                    opponent_idx = (i + j + k) % len(population)
                    match_agents_indices.append(opponent_idx)
                
                match_agents = tuple(population[idx] for idx in match_agents_indices)
                # Decoriamo il compito con gli indici reali per poter riassegnare il fitness dopo
                tasks.append((match_agents, tuple(match_agents_indices)))
        return tasks

    def run_training_loop(self) -> None:
        max_gens = self._determine_generations()
        generation = 0
        while True:
            # Se max_gens è <= 0, consideriamo il training infinito
            if max_gens is not None and max_gens > 0 and generation >= max_gens:
                break

            for agent in self.evo_manager.population:
                agent.reset_fitness()
                agent.match_count = 0

            population = self.evo_manager.population
            match_tasks_data = self._build_match_tasks(population)
            
            # match_tasks_data contiene ((agente1, agente2, ...), (idx1, idx2, ...))
            batch_input = [task[0] for task in match_tasks_data]
            
            # Esecuzione parallela
            results = list(self.executor.map(run_parallel_match, batch_input))
            
            # Accumulo risultati
            total_actions = 0
            pass_count = 0
            reinforce_count = 0
            attack_count = 0
            post_attack_count = 0
            maneuver_count = 0
            
            reinforce_reward_sum = 0.0
            attack_reward_sum = 0.0
            post_attack_reward_sum = 0.0
            maneuver_reward_sum = 0.0
            
            post_move_count = 0
            total_territories_captured = 0
            
            # Generation outcomes
            total_wins = 0
            total_losses = 0
            total_stalemates = 0
            
            # New Diagnostics counters
            total_invalid_moves = 0
            total_turns_sum = 0
            total_armies_placed_sum = 0
            total_eliminations_sum = 0

            # Deep Maneuver Diagnosis counters
            man_inactive_pen_sum = 0.0
            man_leave_one_pen_sum = 0.0
            man_strategic_count = 0
            man_away_count = 0
            man_pass_count = 0
            garrison_bonus_sum_all = 0.0
            
            setup_overstack_pen_sum = 0.0
            post_attack_abandon_pen_sum = 0.0

            for res_idx, (fitness_scores, stats) in enumerate(results):
                player_indices = match_tasks_data[res_idx][1]
                for i, player_idx in enumerate(player_indices):
                    player_id = i + 1
                    population[player_idx].fitness += fitness_scores.get(player_id, 0)
                    population[player_idx].match_count += 1
                
                # Somma statistiche globali della generazione
                total_actions += stats.get('total_actions', 0)
                pass_count += stats.get('pass_count', 0)
                reinforce_count += stats.get('reinforce_count', 0)
                attack_count += stats.get('attack_count', 0)
                post_attack_count += stats.get('post_attack_move_count', 0)
                maneuver_count += stats.get('maneuver_count', 0)
                
                reinforce_reward_sum += stats.get('reinforce_reward_sum', 0.0)
                attack_reward_sum += stats.get('attack_reward_sum', 0.0)
                post_attack_reward_sum += stats.get('post_attack_move_reward_sum', 0.0)
                maneuver_reward_sum += stats.get('maneuver_reward_sum', 0.0)
                
                post_move_count += stats.get('post_move_count', 0)
                total_territories_captured += stats.get('territories_captured', 0)
                
                total_wins += stats.get('wins', 0)
                total_losses += stats.get('losses', 0)
                total_stalemates += stats.get('stalemates', 0)
                
                # New Diagnostics
                total_invalid_moves += stats.get('invalid_moves', 0)
                total_turns_sum += stats.get('total_turns', 0)
                total_armies_placed_sum += stats.get('armies_placed', 0)
                total_eliminations_sum += stats.get('players_eliminated', 0)

                # Deep Maneuver Diagnosis accumulation
                man_inactive_pen_sum += stats.get('maneuver_inactive_pen_sum', 0.0)
                man_leave_one_pen_sum += stats.get('maneuver_leave_one_pen_sum', 0.0)
                man_strategic_count += stats.get('maneuver_strategic_count', 0)
                man_away_count += stats.get('maneuver_away_count', 0)
                man_pass_count += stats.get('maneuver_pass_count', 0)
                garrison_bonus_sum_all += stats.get('garrison_bonus_sum', 0.0)
                
                setup_overstack_pen_sum += stats.get('setup_overstack_pen_sum', 0.0)
                post_attack_abandon_pen_sum += stats.get('post_attack_abandon_pen_sum', 0.0)

            # Normalizzazione fitness per il numero di match giocati
            for agent in population:
                if agent.match_count > 0:
                    agent.fitness /= agent.match_count

            # Imitation Learning: carica campioni umani e applica bonus
            if Config.HUMAN_DATA.get("ENABLED", False):
                samples = load_samples(Config.HUMAN_DATA.get("DATASET_PATH", "dataset/human_dataset.jsonl"))
                if len(samples) >= Config.HUMAN_DATA.get("MIN_SAMPLES", 0):
                    weight = float(Config.HUMAN_DATA.get("IMITATION_WEIGHT", 0.0))
                    if weight > 0:
                        for agent in population:
                            agent.fitness += compute_imitation_bonus(agent, samples, weight)

            best_agent = max(population, key=lambda x: x.fitness)
            avg_fitness = sum(a.fitness for a in population) / len(population)


            reinforce_avg = 0.0
            attack_avg = 0.0
            post_attack_avg = 0.0
            maneuver_avg = 0.0
            if reinforce_count > 0:
                reinforce_avg = reinforce_reward_sum / reinforce_count
            if attack_count > 0:
                attack_avg = attack_reward_sum / attack_count
            if post_attack_count > 0:
                post_attack_avg = post_attack_reward_sum / post_attack_count
            if maneuver_count > 0:
                maneuver_avg = maneuver_reward_sum / maneuver_count

            pass_pct = (pass_count / total_actions * 100) if total_actions > 0 else 0
            reinforce_pct = (reinforce_count / total_actions * 100) if total_actions > 0 else 0
            attack_pct = (attack_count / total_actions * 100) if total_actions > 0 else 0
            post_attack_pct = (post_attack_count / total_actions * 100) if total_actions > 0 else 0
            maneuver_pct = (maneuver_count / total_actions * 100) if total_actions > 0 else 0

            # New Diagnostic Averages
            num_matches = len(results)
            avg_turns = total_turns_sum / num_matches if num_matches > 0 else 0
            avg_eliminations = total_eliminations_sum / num_matches if num_matches > 0 else 0
            reinforce_eff = total_armies_placed_sum / reinforce_count if reinforce_count > 0 else 0

            # Deep Maneuver Averages (per match)
            avg_man_inactive = man_inactive_pen_sum / num_matches if num_matches > 0 else 0
            avg_man_leave_one = man_leave_one_pen_sum / num_matches if num_matches > 0 else 0
            man_strategic_pct = (man_strategic_count / maneuver_count * 100) if maneuver_count > 0 else 0
            man_away_pct = (man_away_count / maneuver_count * 100) if maneuver_count > 0 else 0
            avg_garrison_bonus = garrison_bonus_sum_all / num_matches if num_matches > 0 else 0
            
            avg_setup_overstack = setup_overstack_pen_sum / num_matches if num_matches > 0 else 0
            avg_post_attack_abandon = post_attack_abandon_pen_sum / num_matches if num_matches > 0 else 0

            self.evo_manager.save_best_agent('best_agent.pkl')

            best_color = Fore.GREEN if best_agent.fitness >= 0 else Fore.RED
            avg_color = Fore.GREEN if avg_fitness >= 0 else Fore.RED

            inactive_color = Fore.RED if avg_man_inactive < -100 else Fore.YELLOW
            leave_color = Fore.RED if avg_man_leave_one < -50 else Fore.YELLOW

            print(f"\n{Fore.CYAN}{'='*80}{Style.RESET_ALL}")
            print(f"{Fore.CYAN}| {Style.BRIGHT}GENERAZIONE {generation + 1:<64}{Style.RESET_ALL}{Fore.CYAN} |")
            print(f"{Fore.CYAN}{'='*80}{Style.RESET_ALL}")
            
            print(f"  {Style.BRIGHT}PERFORMANCE:{Style.RESET_ALL}")
            print(f"    Best Fitness: {best_color}{best_agent.fitness:>8.0f}{Style.RESET_ALL} | "
                  f"Avg Fitness: {avg_color}{avg_fitness:>8.0f}{Style.RESET_ALL} | "
                  f"Total Conq: {Fore.YELLOW}{total_territories_captured:>6}{Style.RESET_ALL}")
            print(f"    Outcomes:     Wins: {Fore.GREEN}{total_wins:>4}{Style.RESET_ALL} | "
                  f"Loss: {Fore.RED}{total_losses:>4}{Style.RESET_ALL} | "
                  f"Stale: {Fore.YELLOW}{total_stalemates:>4}{Style.RESET_ALL}")
            
            print(f"\n  {Style.BRIGHT}DIAGNOSTICS:{Style.RESET_ALL}")
            print(f"    Errors:       {Fore.RED}{total_invalid_moves:>5}{Style.RESET_ALL} | "
                  f"Avg Turns: {Fore.CYAN}{avg_turns:>5.1f}{Style.RESET_ALL} | "
                  f"Eliminations: {Fore.YELLOW}{avg_eliminations:>4.1f}{Style.RESET_ALL} | "
                  f"Rein.Eff: {Fore.MAGENTA}{reinforce_eff:>4.2f}{Style.RESET_ALL}")
            print(f"    Overstack:    {Fore.YELLOW}{avg_setup_overstack:>5.1f}/match{Style.RESET_ALL} | "
                  f"Post-Att Abandon: {Fore.YELLOW}{avg_post_attack_abandon:>5.1f}/match{Style.RESET_ALL}")
            
            print(f"\n  {Style.BRIGHT}PHASE ANALYSIS (Rewards & Actions):{Style.RESET_ALL}")
            print(f"    Reinforce:    Rew: {reinforce_avg:>6.2f} | Act: {reinforce_pct:>5.1f}%")
            print(f"    Attack:       Rew: {attack_avg:>6.2f} | Act: {attack_pct:>5.1f}%")
            print(f"    Maneuver:     Rew: {maneuver_avg:>6.2f} | Act: {maneuver_pct:>5.1f}%")
            print(f"    Post-Attack:  Act: {post_attack_pct:>5.1f}% | Pass: {pass_pct:>5.1f}%")

            print(f"\n  {Style.BRIGHT}MANEUVER DETAILS:{Style.RESET_ALL}")
            print(f"    Inactive:     {inactive_color}{avg_man_inactive:>6.0f}/match{Style.RESET_ALL} | "
                  f"Exposed Front: {leave_color}{avg_man_leave_one:>6.0f}/match{Style.RESET_ALL}")
            print(f"    Strategic:    {man_strategic_pct:>5.1f}% | Retreats: {man_away_pct:>5.1f}% | "
                  f"Pass: {man_pass_count:>5} | Garrison: {Fore.CYAN}{avg_garrison_bonus:>4.0f}/match{Style.RESET_ALL}")
            print(f"{Fore.CYAN}{'='*80}{Style.RESET_ALL}\n")


            self.evo_manager.evolve()
            generation += 1

def main() -> None:
    args = parse_args()
    Main(generations=args.generations, max_workers=args.max_workers)

if __name__ == '__main__':
    main()
