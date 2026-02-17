import numpy as np
from typing import List, Dict, Any

class NeuralNetwork:
    def __init__(self, input_size: int, hidden_sizes: List[int], output_size: int):
        self.input_size: int = input_size
        self.output_size: int = output_size
        self.layers: List[Dict[str, np.ndarray]] = []

        # Architettura: [Input] -> [Hidden1] -> [Hidden2] -> [Output]
        all_layers: List[int] = [input_size] + hidden_sizes + [output_size]

        # Inizializzazione pesi (Weights) e bias
        for i in range(len(all_layers) - 1):
            w = np.random.randn(all_layers[i], all_layers[i + 1]) * np.sqrt(2.0 / all_layers[i])
            b = np.zeros((1, all_layers[i + 1]))
            self.layers.append({'w': w, 'b': b})

    def forward(self, x: np.ndarray) -> np.ndarray:
        # Passaggio dei dati attraverso la rete (Inference)
        current_input = x.reshape(1, -1)

        for i, layer in enumerate(self.layers):
            # Operazione core: z = xW + b
            z = np.dot(current_input, layer['w']) + layer['b']

            # Attivazione: ReLU per i livelli nascosti, Sigmoide per l'output
            if i < len(self.layers) - 1:
                # ReLU
                current_input = np.maximum(0, z)
            else:
                # Sigmoid (output tra 0 e 1)
                z = np.clip(z, -500, 500)
                current_input = 1 / (1 + np.exp(-z))
        return current_input.flatten()

    def get_weights(self) -> np.ndarray:
        # Estrae tutti i pesi come un unico vettore (per crossover/mutazione)
        flat_weights: List[np.ndarray] = []
        for layer in self.layers:
            flat_weights.append(layer['w'].flatten())
            flat_weights.append(layer['b'].flatten())
        return np.concatenate(flat_weights)

    def set_weights(self, flat_weights: np.ndarray) -> None:
        # Ricarica i pesi nella rete da un vettore flat
        start: int = 0
        for layer in self.layers:
            # Ricostruisci W
            w_size = layer['w'].size
            layer['w'] = flat_weights[start:start + w_size].reshape(layer['w'].shape)
            start += w_size

            # Ricostruisci b
            b_size = layer['b'].size
            layer['b'] = flat_weights[start:start + b_size].reshape(layer['b'].shape)
            start += b_size
