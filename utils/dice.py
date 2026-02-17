import random
from typing import List

def get_random_dice(n_dice: int) -> List[int]:
    # Lancia n dadi e li restituisce ordinati in modo decrescente
    rolls = [random.randint(1, 6) for _ in range(n_dice)]
    rolls.sort(reverse=True)
    return rolls