import numpy as np
import random
import copy
import pickle
import os
from typing import List
from app.ai.agent import Agent
from config import Config
from app.utils.trainer_utils import TrainerUtils
from app.core.board import Board


class EvolutionManager:
    def __init__(self, board_ref: Board):
        self.board_ref: Board = board_ref
        self.population_size: int = Config.EVOLUTION['POPULATION_SIZE']
        self.population: List[Agent] = [Agent(board_ref, id=i) for i in range(self.population_size)]

        self.best_fitness_ever: float = -float('inf')
        self.stagnation_counter: int = 0
        self.best_fitness_history: List[float] = []
        self.current_mutation_strength: float = Config.EVOLUTION['MUTATION_STRENGTH']
        self.current_epsilon: float = Config.NN['EPSILON-GREEDY']

    def _weights_compatible(self, flat_weights: np.ndarray) -> bool:
        expected_size = self.population[0].nn.get_weights().size
        return flat_weights.size == expected_size

    def evolve(self) -> None:
        self.population.sort(key=lambda x: x.fitness, reverse=True)
        current_best_fitness = self.population[0].fitness

        self._update_logic(current_best_fitness)

        new_population: List[Agent] = []
        elites = self.population[:Config.EVOLUTION['ELITISM_COUNT']]

        if current_best_fitness < self.best_fitness_ever:
            best_ever_weights = TrainerUtils.load_weights('hall_of_fame.pkl')
            if (
                best_ever_weights is not None
                and isinstance(best_ever_weights, np.ndarray)
                and self._weights_compatible(best_ever_weights)
            ):
                ghost = Agent(self.board_ref)
                ghost.nn.set_weights(best_ever_weights)
                new_population.append(ghost)

        while len(new_population) < Config.EVOLUTION['ELITISM_COUNT']:
            idx = len(new_population)
            elite_clone = copy.deepcopy(elites[idx])
            elite_clone.reset_fitness()
            new_population.append(elite_clone)

        if self.stagnation_counter >= Config.EVOLUTION['STAGNATION_TRIGGER']:
            print(f"[Evolution] CATASTROFE: reset basato sui top {len(elites)} agenti.")
            while len(new_population) < self.population_size:
                base_elite = random.choice(elites)
                new_dna = self._heavy_mutation(copy.deepcopy(base_elite.nn.get_weights()))
                child = Agent(self.board_ref)
                child.nn.set_weights(new_dna)
                new_population.append(child)
            self.stagnation_counter = 0

        else:
            while len(new_population) < self.population_size:
                parent1 = self._tournament_selection()
                parent2 = self._tournament_selection()

                if random.random() < Config.EVOLUTION['CROSSOVER_RATE']:
                    child_dna = self._crossover(parent1, parent2)
                else:
                    child_dna = copy.deepcopy(parent1.nn.get_weights())

                child_dna = self._mutate(child_dna)
                child = Agent(self.board_ref)
                child.nn.set_weights(child_dna)
                new_population.append(child)

        for agent in new_population:
            agent.epsilon = self.current_epsilon

        self.population = new_population

    def _tournament_selection(self) -> Agent:
        contestants = random.sample(self.population, Config.EVOLUTION['TOURNAMENT_SIZE'])
        return max(contestants, key=lambda x: x.fitness)

    def _crossover(self, p1: Agent, p2: Agent) -> np.ndarray:
        dna1 = p1.nn.get_weights()
        dna2 = p2.nn.get_weights()
        mask = np.random.randint(0, 2, size=dna1.shape).astype(bool)
        child_dna = np.where(mask, dna1, dna2)
        return child_dna

    def _update_logic(self, current_best: float) -> None:
        if current_best > self.best_fitness_ever:
            self.best_fitness_ever = current_best
            self.stagnation_counter = 0
            self.save_best_agent('hall_of_fame.pkl')
        else:
            self.stagnation_counter += 1

        self.best_fitness_history.append(current_best)
        if len(self.best_fitness_history) > Config.EVOLUTION['STAGNATION_WINDOW']:
            self.best_fitness_history.pop(0)

        if len(self.best_fitness_history) == Config.EVOLUTION['STAGNATION_WINDOW']:
            if current_best <= self.best_fitness_history[0]:
                self.current_mutation_strength = (
                    Config.EVOLUTION['MUTATION_STRENGTH'] * Config.EVOLUTION['MUTATION_STRENGTH_BOOST']
                )
            else:
                self.current_mutation_strength = Config.EVOLUTION['MUTATION_STRENGTH']

        self.current_mutation_strength = min(
            Config.EVOLUTION['MUTATION_STRENGTH_MAX'],
            max(Config.EVOLUTION['MUTATION_STRENGTH_MIN'], self.current_mutation_strength),
        )
        if self.current_epsilon > Config.EVOLUTION['EPSILON_MIN']:
            self.current_epsilon *= Config.EVOLUTION['EPSILON_DECAY']

    def _mutate(self, dna: np.ndarray) -> np.ndarray:
        mutation_mask = np.random.random(dna.shape) < Config.EVOLUTION['MUTATION_RATE']
        noise = np.random.normal(0, self.current_mutation_strength, dna.shape)
        dna[mutation_mask] += noise[mutation_mask]
        return dna

    def _heavy_mutation(self, dna: np.ndarray) -> np.ndarray:
        mutation_mask = np.random.random(dna.shape) < Config.EVOLUTION['CATASTROPHE_MUTATION_RATE']
        noise = np.random.normal(
            0,
            Config.EVOLUTION['MUTATION_STRENGTH'] * Config.EVOLUTION['CATASTROPHE_STRENGTH_MULT'],
            dna.shape,
        )
        dna[mutation_mask] += noise[mutation_mask]
        return dna

    def save_best_agent(self, filename: str = 'best_agent.pkl') -> None:
        best_agent = max(self.population, key=lambda x: x.fitness)
        path = os.path.join('dataset', filename)
        weights = best_agent.nn.get_weights()
        # dump weights
        with open(path, 'wb') as f:
            pickle.dump(weights, f)

        # compute and log a checksum to help debugging (detect unchanged/same saves)
        try:
            import hashlib
            md5 = hashlib.md5(weights.tobytes()).hexdigest()
            print(f"[Evolution] Saved {path} (md5={md5}, fitness={best_agent.fitness})")
        except Exception:
            print(f"[Evolution] Saved {path} (fitness={best_agent.fitness})")

    def load_population(self, filename: str = 'best_agent.pkl') -> bool:
        path = filename
        if not os.path.exists(path):
            path = os.path.join('dataset', filename)

        if not os.path.exists(path):
            return False

        with open(path, 'rb') as f:
            best_weights = pickle.load(f)

        if not isinstance(best_weights, np.ndarray):
            print(f"[Evolution] Pesi in {filename} non validi, skip caricamento.")
            return False

        # NeuralNetwork.set_weights gestisca l'auto-resize
        for agent in self.population:
            dna = self._mutate(copy.deepcopy(best_weights))
            agent.nn.set_weights(dna)

        print(f"[Evolution] Popolazione caricata dal file {filename}")
        return True
