import random

import numpy as np

from ai.processor import Processor
from core.board import Board
from core.config import Config


def test_processor_sets_continent_mission_bits():
    random.seed(0)
    board = Board()
    processor = Processor(board)
    mission = Config.MISSIONS["EMPIRE_NW_SE"]
    state = processor.encode_state(board, 1, 5, "ATTACK", mission)
    cont_keys = sorted(Config.CONTINENTS.keys())
    mission_offset = (3 * board.n) + processor.num_continents

    for zone in mission["target"]:
        idx = cont_keys.index(zone)
        assert state[mission_offset + idx] == 1.0


def test_processor_dominion_mission_bits():
    random.seed(0)
    board = Board()
    processor = Processor(board)
    mission = Config.MISSIONS["DOMINATION_60"]
    state = processor.encode_state(board, 2, 2, "REINFORCE", mission)
    mission_offset = (3 * board.n) + processor.num_continents

    mission_slice = state[mission_offset : mission_offset + processor.num_continents]
    assert np.allclose(mission_slice, np.ones(processor.num_continents))
