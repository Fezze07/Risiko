import random
from dataclasses import dataclass
from enum import Enum, auto
from typing import List, Dict, Tuple, Optional
from config import Config
from app.core.board import Board

class CardType(Enum):
    INFANTRY = auto()
    CAVALRY = auto()
    ARTILLERY = auto()
    JOLLY = auto()

@dataclass
class Card:
    territory_id: Optional[int]
    territory_name: Optional[str]
    card_type: CardType

    def __repr__(self) -> str:
        return f"Card({self.card_type.name}, {self.territory_name})"

class DeckManager:
    def __init__(self, territories: dict):
        self.deck: List[Card] = []
        self.discard_pile: List[Card] = []
        self._initialize_deck(territories)

    def _initialize_deck(self, territories: dict):
        base_types = [CardType.INFANTRY, CardType.CAVALRY, CardType.ARTILLERY]
        t_ids = list(territories.keys())
        
        for i, t_id in enumerate(t_ids):
            c_type = base_types[i % 3]
            self.deck.append(Card(t_id, territories[t_id].name, c_type))
            
        for _ in range(Config.CARDS['NUM_JOLLIES']):
            self.deck.append(Card(None, None, CardType.JOLLY))
            
        random.shuffle(self.deck)

    def draw(self) -> Optional[Card]:
        if not self.deck:
            if not self.discard_pile:
                return None
            self.reshuffle()
        return self.deck.pop()

    def discard(self, cards: List[Card]):
        self.discard_pile.extend(cards)

    def reshuffle(self):
        self.deck.extend(self.discard_pile)
        self.discard_pile.clear()
        random.shuffle(self.deck)

class CardManager:
    def __init__(self, num_players: int, deck_manager: DeckManager):
        self.deck_manager = deck_manager
        self.player_hands: Dict[int, List[Card]] = {p: [] for p in range(1, num_players + 1)}
        self.conquered_this_turn: Dict[int, bool] = {p: False for p in range(1, num_players + 1)}

    def mark_conquest(self, player_id: int):
        self.conquered_this_turn[player_id] = True

    def give_card_if_eligible(self, player_id: int) -> bool:
        if self.conquered_this_turn.get(player_id, False):
            card = self.deck_manager.draw()
            if card:
                self.player_hands[player_id].append(card)
                self.conquered_this_turn[player_id] = False
                return True
        self.conquered_this_turn[player_id] = False
        return False

    def transfer_cards(self, from_player: int, to_player: int):
        self.player_hands[to_player].extend(self.player_hands.get(from_player, []))
        self.player_hands[from_player] = []

    def has_valid_combination(self, player_id: int) -> bool:
        hand = self.player_hands[player_id]
        if len(hand) < 3:
            return False
            
        inf = sum(1 for c in hand if c.card_type == CardType.INFANTRY)
        cav = sum(1 for c in hand if c.card_type == CardType.CAVALRY)
        art = sum(1 for c in hand if c.card_type == CardType.ARTILLERY)
        jol = sum(1 for c in hand if c.card_type == CardType.JOLLY)
        
        # Combinazioni valide per Risiko:
        # 1. Tris di un tipo (FFF, CCC, AAA)
        # 2. Una per tipo (FCA)
        # 3. 2 uguali + 1 Jolly
        # 4. 2 diversi + 1 Jolly
        # 5. 1 o 2 uguali + 2 Jolly

        if inf >= 3 or cav >= 3 or art >= 3: return True
        if inf >= 1 and cav >= 1 and art >= 1: return True
        if jol >= 1 and (inf >= 2 or cav >= 2 or art >= 2): return True
        if jol >= 1 and ((inf>=1 and cav>=1) or (inf>=1 and art>=1) or (cav>=1 and art>=1)): return True
        if jol >= 2 and (inf >= 1 or cav >= 1 or art >= 1): return True
        
        return False

    def validate_combination(self, cards: List[Card]) -> bool:
        if len(cards) != 3: return False
        
        types = [c.card_type for c in cards]
        fc = types.count(CardType.INFANTRY)
        cc = types.count(CardType.CAVALRY)
        ac = types.count(CardType.ARTILLERY)
        jc = types.count(CardType.JOLLY)
        
        if fc == 3 or cc == 3 or ac == 3: return True
        if fc == 1 and cc == 1 and ac == 1: return True
        if jc >= 1 and (fc == 2 or cc == 2 or ac == 2): return True
        if jc >= 1 and ((fc==1 and cc==1) or (fc==1 and ac==1) or (cc==1 and ac==1)): return True
        if jc >= 2 and (fc == 1 or cc == 1 or ac == 1): return True
        
        return False

    def calculate_bonus(self, cards: List[Card], board: Board, player_id: int) -> Tuple[int, Dict[int, int]]:
        types = [c.card_type for c in cards]
        fc = types.count(CardType.INFANTRY)
        cc = types.count(CardType.CAVALRY)
        ac = types.count(CardType.ARTILLERY)
        jc = types.count(CardType.JOLLY)

        base_bonus = 0
        if fc == 3: base_bonus = Config.CARDS['BONUS_3_INFANTRY']
        elif cc == 3: base_bonus = Config.CARDS['BONUS_3_CAVALRY']
        elif ac == 3: base_bonus = Config.CARDS['BONUS_3_ARTILLERY']
        elif fc == 1 and cc == 1 and ac == 1: base_bonus = Config.CARDS['BONUS_MIXED']
        elif jc > 0: base_bonus = Config.CARDS['BONUS_WITH_JOLLY']

        territory_bonuses = {}
        t_bonus_val = Config.CARDS['TERRITORY_BONUS']
        
        for card in cards:
            if card.territory_id is not None:
                t = board.territories.get(card.territory_id)
                if t and t.owner_id == player_id:
                    territory_bonuses[card.territory_id] = territory_bonuses.get(card.territory_id, 0) + t_bonus_val

        return base_bonus, territory_bonuses

    def get_best_combination(self, player_id: int, board: Board) -> List[int]:
        hand = self.player_hands[player_id]
        if len(hand) < 3:
            return []
            
        import itertools
        best_indices = []
        best_total = -1
        
        # Testiamo tutte le combinazioni possibili di 3 carte nella mano
        for indices in itertools.combinations(range(len(hand)), 3):
            cards = [hand[i] for i in indices]
            if self.validate_combination(cards):
                b_base, t_bon = self.calculate_bonus(cards, board, player_id)
                # Calcoliamo il totale che si otterrebbe
                total = b_base + sum(t_bon.values())
                if total > best_total:
                    best_total = total
                    best_indices = list(indices)
                    
        return best_indices

    def play_combination(self, player_id: int, card_indices: List[int], board: Board) -> Tuple[int, Dict[int, int]]:
        hand = self.player_hands[player_id]
        
        try:
            selected_cards = [hand[i] for i in card_indices]
        except IndexError:
            return 0, {}

        if not self.validate_combination(selected_cards):
            return 0, {}

        bonus, t_bonuses = self.calculate_bonus(selected_cards, board, player_id)
        
        # Rimuovi le carte e aggiorna la mano nel dizionario in modo esplicito
        indices_set = set(card_indices)
        self.player_hands[player_id] = [c for i, c in enumerate(hand) if i not in indices_set]
        
        self.deck_manager.discard(selected_cards)
        return bonus, t_bonuses
