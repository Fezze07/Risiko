import argparse
import concurrent.futures
import os

from typing import List, Tuple, Optional
from colorama import Fore, Style, init

from ai.agent import Agent
from ai.evolution import EvolutionManager
from config import Config
from core.environment import RisikoEnvironment
from utils.human_dataset import load_samples, compute_imitation_bonus
from utils.parallel_trainer import run_parallel_match
from utils.trainer_utils import TrainerUtils


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

            self.evo_manager.save_best_agent('best_agent.pkl')

            best_color = Fore.GREEN if best_agent.fitness >= 0 else Fore.RED
            avg_color = Fore.GREEN if avg_fitness >= 0 else Fore.RED
            
            print(
                f"GEN {generation + 1} | Best: {best_color}{best_agent.fitness:.0f}{Style.RESET_ALL} "
                f"| Avg: {avg_color}{avg_fitness:.0f}{Style.RESET_ALL} "
                f"| Conq: {total_territories_captured}\n"
                f"  Outcomes: Wins {total_wins} | Loss {total_losses} | Stale {total_stalemates}\n"
                f"  Diagnosis: Invalid {total_invalid_moves} | Avg Turns {avg_turns:.1f} "
                f"| Elims {avg_eliminations:.1f} | ReinEff {reinforce_eff:.2f}\n"
                f"  Phase Avg: Rein {reinforce_avg:.2f} | Att {attack_avg:.2f} | Man {maneuver_avg:.2f}\n"
                f"  Actions: Pass {pass_pct:.1f}% | Rein {reinforce_pct:.1f}% | Att {attack_pct:.1f}% "
                f"| Post {post_attack_pct:.1f}% | Man {maneuver_pct:.1f}%\n"
            )


            self.evo_manager.evolve()
            generation += 1

def main() -> None:
    args = parse_args()
    Main(generations=args.generations, max_workers=args.max_workers)

if __name__ == '__main__':
    main()
