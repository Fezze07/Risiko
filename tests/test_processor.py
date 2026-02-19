import random

import numpy as np

from ai.processor import Processor
from core.board import Board
from config import Config


def test_processor_input_size_is_fixed_per_territory():
    random.seed(0)
    board = Board()
    processor = Processor(board)
    assert processor.features_per_territory == 4
    assert processor.input_size == board.n * 4

    original_players = Config.GAME["NUM_PLAYERS"]
    try:
        Config.GAME["NUM_PLAYERS"] = 6
        processor_six_players = Processor(board)
        assert processor_six_players.input_size == board.n * 4
    finally:
        Config.GAME["NUM_PLAYERS"] = original_players


def test_processor_encodes_relative_features_for_current_player():
    random.seed(0)
    board = Board()
    processor = Processor(board)
    max_armies = Config.GAME["MAX_ARMIES_PER_TERRITORY"]

    original_players = Config.GAME["NUM_PLAYERS"]
    try:
        Config.GAME["NUM_PLAYERS"] = 3

        board.territories[0].owner_id = 1
        board.territories[0].armies = 10
        board.territories[0].neighbors = [1, 2]

        board.territories[1].owner_id = 2
        board.territories[1].armies = 7
        board.territories[1].neighbors = [0]

        board.territories[2].owner_id = 3
        board.territories[2].armies = 5
        board.territories[2].neighbors = [0]

        state_p1 = processor.encode_state(board, current_player_id=1)
        assert state_p1[0] == 1.0
        assert np.isclose(state_p1[1], 10 / max_armies)
        assert state_p1[2] == 0.0
        assert np.isclose(state_p1[3], (7 + 5) / (max_armies * 2))

        t1_offset = 4
        t2_offset = 8
        assert state_p1[t1_offset] == 0.0
        assert np.isclose(state_p1[t1_offset + 2], 0.1)
        assert np.isclose(state_p1[t2_offset + 2], 1.0)

        state_p2 = processor.encode_state(board, current_player_id=2)
        assert state_p2[t1_offset] == 1.0
        assert state_p2[t1_offset + 2] == 0.0
        assert np.isclose(state_p2[2], 1.0)
        assert np.isclose(state_p2[t2_offset + 2], 0.1)
    finally:
        Config.GAME["NUM_PLAYERS"] = original_players
