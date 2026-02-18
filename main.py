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
        '--long-session',
        action='store_true',
        help='Forza la sessione lunga (10^6 generazioni).',
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
        long_session: bool,
        max_workers: Optional[int],
    ) -> None:
        init(autoreset=True)
        print('=== AVVIO TRAINING PARALLELO ===')
        self.env: RisikoEnvironment = RisikoEnvironment()
        self.evo_manager: EvolutionManager = EvolutionManager(self.env.board)
        self.max_generations = generations
        self.use_long_session = long_session
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
        if self.use_long_session or Config.DEBUG['LONG_SESSION']:
            return None
        return Config.EVOLUTION['GENERATIONS']

    def _build_match_tasks(
        self, population: List[Agent]
    ) -> List[Tuple[Agent, Agent, int, int]]:
        tasks: List[Tuple[Agent, Agent, int, int]] = []
        for i, agent in enumerate(population):
            for j in range(1, Config.EVOLUTION['TOURNAMENT_SIZE'] + 1):
                opponent_idx = (i + j) % len(population)
                opponent = population[opponent_idx]
                tasks.append((agent, opponent, i, opponent_idx))
        return tasks

    def run_training_loop(self) -> None:
        max_gens = self._determine_generations()
        generation = 0
        while True:
            if max_gens is not None and generation >= max_gens:
                break

            for agent in self.evo_manager.population:
                agent.reset_fitness()
                agent.match_count = 0

            population = self.evo_manager.population
            match_tasks = self._build_match_tasks(population)

            batch_input = [(match[0], match[1]) for match in match_tasks]
            results = list(
                self.executor.map(run_parallel_match, batch_input, chunksize=10)
            )

            post_move_count = 0
            post_move_qty_sum = 0
            post_move_risky = 0

            reinforce_count = 0
            reinforce_reward_sum = 0
            attack_count = 0
            attack_reward_sum = 0
            post_attack_count = 0
            post_attack_reward_sum = 0
            maneuver_count = 0
            maneuver_reward_sum = 0
            pass_count = 0
            total_actions = 0

            for idx, (res_fit1, res_fit2, stats) in enumerate(results):
                p1_idx = match_tasks[idx][2]
                p2_idx = match_tasks[idx][3]

                population[p1_idx].fitness += res_fit1
                population[p1_idx].match_count += 1
                population[p2_idx].fitness += res_fit2
                population[p2_idx].match_count += 1

                post_move_count += stats.get('post_move_count', 0)
                post_move_qty_sum += stats.get('post_move_qty_sum', 0)
                post_move_risky += stats.get('post_move_risky', 0)

                reinforce_count += stats.get('reinforce_count', 0)
                reinforce_reward_sum += stats.get('reinforce_reward_sum', 0)
                attack_count += stats.get('attack_count', 0)
                attack_reward_sum += stats.get('attack_reward_sum', 0)
                post_attack_count += stats.get('post_attack_move_count', 0)
                post_attack_reward_sum += stats.get('post_attack_move_reward_sum', 0)
                maneuver_count += stats.get('maneuver_count', 0)
                maneuver_reward_sum += stats.get('maneuver_reward_sum', 0)
                pass_count += stats.get('pass_count', 0)
                total_actions += stats.get('total_actions', 0)

            for agent in self.evo_manager.population:
                if agent.match_count > 0:
                    agent.fitness /= agent.match_count

            if Config.HUMAN_DATA.get("ENABLED", False):
                samples = load_samples(
                    Config.HUMAN_DATA["DATASET_PATH"],
                    Config.HUMAN_DATA.get("SAMPLE_SIZE"),
                )
                if len(samples) >= Config.HUMAN_DATA.get("MIN_SAMPLES", 0):
                    weight = float(Config.HUMAN_DATA.get("IMITATION_WEIGHT", 0.0))
                    if weight > 0:
                        for agent in population:
                            agent.fitness += compute_imitation_bonus(agent, samples, weight)

            best_agent = max(population, key=lambda x: x.fitness)
            avg_fitness = sum(a.fitness for a in population) / len(population)

            post_move_avg = 0.0
            post_move_risky_pct = 0.0
            if post_move_count > 0:
                post_move_avg = post_move_qty_sum / post_move_count
                post_move_risky_pct = (post_move_risky / post_move_count) * 100

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

            pass_pct = 0.0
            reinforce_pct = 0.0
            attack_pct = 0.0
            post_attack_pct = 0.0
            maneuver_pct = 0.0
            if total_actions > 0:
                pass_pct = (pass_count / total_actions) * 100
                reinforce_pct = (reinforce_count / total_actions) * 100
                attack_pct = (attack_count / total_actions) * 100
                post_attack_pct = (post_attack_count / total_actions) * 100
                maneuver_pct = (maneuver_count / total_actions) * 100

            metrics = {
                "reinforce_avg": reinforce_avg,
                "attack_avg": attack_avg,
                "post_move_avg": post_move_avg,
                "maneuver_avg": maneuver_avg,
                "risky_pct": post_move_risky_pct,
                "pass_pct": pass_pct,
                "reinforce_pct": reinforce_pct,
                "attack_pct": attack_pct,
                "post_pct": post_attack_pct,
                "maneuver_pct": maneuver_pct,
            }
            is_new_record = TrainerUtils.update_records(
                best_agent.fitness, avg_fitness, metrics
            )
            if is_new_record:
                print('NUOVO RECORD STORICO REGISTRATO!')

            self.evo_manager.save_best_agent('best_agent.pkl')

            best_color = Fore.GREEN if best_agent.fitness >= 0 else Fore.RED
            avg_color = Fore.GREEN if avg_fitness >= 0 else Fore.RED
            if post_move_risky_pct >= 50:
                risky_color = Fore.RED
            elif post_move_risky_pct >= 30:
                risky_color = Fore.YELLOW
            else:
                risky_color = Fore.GREEN

            print(
                f"GEN {generation + 1} | Best: {best_color}{best_agent.fitness:.2f}{Style.RESET_ALL} "
                f"| Avg: {avg_color}{avg_fitness:.2f}{Style.RESET_ALL}"
                f"| Risky: {risky_color}{post_move_risky_pct:.1f}%{Style.RESET_ALL} \n"
                f"| Reinforce avg: {reinforce_avg:.2f} | Attack avg: {attack_avg:.2f} "
                f"| PostMove avg: {post_move_avg:.2f} | Maneuver avg: {maneuver_avg:.2f} \n"
                f"| Pass: {pass_pct:.1f}% | Rein: {reinforce_pct:.1f}% | Att: {attack_pct:.1f}% "
                f"| Post: {post_attack_pct:.1f}% | Man: {maneuver_pct:.1f}%\n"
            )

            self.evo_manager.evolve()
            generation += 1

def main() -> None:
    args = parse_args()
    Main(
        generations=args.generations,
        long_session=args.long_session,
        max_workers=args.max_workers,
    )

if __name__ == '__main__':
    main()
