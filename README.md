# 🎲 Risiko AI - Progetto di Reinforcement Learning

Questo progetto implementa un ambiente di **Reinforcement Learning** per addestrare agenti AI a giocare al gioco da tavolo **Risk** (Risiko). Utilizza un **Algoritmo Genetico** (Strategia Evolutiva) per far evolvere una popolazione di Reti Neurali che imparano a giocare attraverso il self-play.

## 🧠 Concetti Chiave

- **Algoritmo Genetico**: Gli agenti evolvono nel corso delle generazioni. I più performanti (quelli che vincono o ottengono risultati migliori) si riproducono e subiscono mutazioni.
- **Rete Neurale**: Ogni agente prende decisioni tramite una Rete Neurale che valuta lo stato della board.
- **Addestramento Parallelo**: Le partite vengono simulate in parallelo usando `concurrent.futures` per massimizzare l’utilizzo della CPU.
- **Ambiente Risiko**: Implementazione personalizzata delle regole di Risk, incluse le fasi (Rinforzo, Attacco, Manovra), i Continenti e il lancio dei dadi.

## 🚀 Installazione

1. **Clona la repository**:
    ```bash
    git clone https://github.com/Fezze07/RisikoReinforcementLearning.git
    cd Risiko
    ```

2. **Crea un ambiente virtuale** (opzionale ma consigliato):
    ```bash
    python -m venv .venv
    # Windows
    .venv\Scripts\activate
    # Linux/Mac
    source .venv/bin/activate
    ```

3. **Installa le dipendenze**:
    ```bash
    pip install -r requirements.txt
    ```

## 🎮 Utilizzo

Per avviare il ciclo di addestramento:

```bash
python main.py
```

Lo script eseguirà:

1. Inizializzazione di una popolazione di agenti.
2. Avvio di un torneo in cui gli agenti giocano tra loro.
3. Calcolo della fitness in base alle prestazioni di gioco (vittorie, conquiste, ecc.).
4. Evoluzione della popolazione (Selezione, Crossover, Mutazione).
5. Salvataggio del miglior agente in `best_agent.pkl`.
6. (Opzionale) Visualizzazione di una partita del miglior agente.

## 📂 Struttura del Progetto

- **`main.py`**: Punto di ingresso. Gestisce il ciclo di addestramento e l’esecuzione parallela.
- **`core/`**: Contiene la logica del gioco.
    - `environment.py`: Motore del gioco (regole, turni, fasi).
    - `board.py`: Gestione dei territori e della mappa.
    - `config.py`: Parametri di configurazione (Ricompense, Iperparametri, Regole).
- **`ai/`**: Contiene la logica dell’AI.
    - `agent.py`: Wrapper dell’agente AI.
    - `network.py`: Implementazione della Rete Neurale.
    - `evolution.py`: Logica dell’Algoritmo Genetico (Selezione, Mutazione).
    - `processor.py`: Codifica lo stato della board per la NN e decodifica l’output della NN in azioni.
- **`utils/`**: Funzioni di supporto per training e logging.
- **`visual/`**: Visualizzatore in console per osservare le partite.

## 🔧 Configurazione

Puoi modificare i parametri di training e di gioco in `core/config.py`:

- **Architettura NN**: Layer nascosti, dimensione input/output.
- **Evoluzione**: Dimensione della popolazione, tasso di mutazione, dimensione del torneo.
- **Ricompense**: Punti per vittoria, conquista territori, ecc.

## 🛠️ Tecnologie

- **Python 3.x**
- **NumPy**: Operazioni matriciali per la Rete Neurale.
- **Colorama**: Output colorato in console.

---

*Creato da Federico Cisera*