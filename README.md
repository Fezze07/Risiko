# 🎲 Risiko AI - Reinforcement Learning & Evolutionary Strategies

Questo progetto implementa un ambiente avanzato di **Reinforcement Learning** per addestrare agenti AI a giocare a **Risiko**. Il sistema utilizza un motore evolutivo (Algoritmo Genetico) combinato con tecniche di **Imitation Learning** per sviluppare strategie di gioco sofisticate e realistiche.

## 🧠 Caratteristiche Principali

- **🧬 Motore Evolutivo**: Evoluzione di reti neurali tramite selezione naturale, crossover e mutazioni dinamiche. Include meccanismi di **Elitismo** e gestione dello **Stagnamento** (Catastrofi).
- **🤖 Imitation Learning**: Possibilità di pre-addestrare gli agenti utilizzando dataset di partite umane per accelerare l'apprendimento di tattiche base.
- **⚖️ Reward System Bilanciato**: Sistema di ricompense raffinato per incoraggiare il gioco difensivo, prevenire lo stacking eccessivo e scoraggiare comportamenti ripetitivi o suicidi.
- **🗺️ Ambiente Completo**: Mappa dinamica con territori, continenti, bonus armate, obiettivi (Missioni) e gestione delle fasi di gioco (Rinforzo, Attacco, Spostamento, Manovra).
- **🌐 Web Dashboard**: Interfaccia web integrata per monitorare l'addestramento, visualizzare le partite in tempo reale e analizzare le performance degli agenti.

## 🚀 Installazione

1. **Clona la repository**:
    ```bash
    git clone https://github.com/Fezze07/Risiko.git
    cd Risiko
    ```

2. **Crea un ambiente virtuale**:
    ```bash
    python -m venv .venv
    # Windows
    .venv\Scripts\activate
    ```

3. **Installa le dipendenze**:
    ```bash
    pip install -r requirements.txt
    ```

## 🎮 Utilizzo

### Addestramento
Per avviare l'evoluzione della popolazione in parallelo:
```bash
python main.py
```
Puoi specificare il numero di generazioni con `--generations <N>` e i processi con `--max-workers <W>`.

### Web Dashboard
Per avviare la dashboard grafica (stats e visualizzazione partita):
```bash
uvicorn app.web.server:app --reload --port 8000
```
Poi apri `http://localhost:8000` nel browser.

## 📂 Struttura del Progetto

Il progetto è organizzato per separare la logica del gioco (Core), l'intelligenza degli agenti (AI) e l'interfaccia di monitoraggio (Web).

- **`main.py`**: Entry point per avviare il training evolutivo parallelo.
- **`config.py`**: Configurazione centralizzata degli iperparametri, reward e regole.
- **`app/`**: Core del software.
    - **`core/`**: Motore del gioco e regole di Risiko.
        - `environment.py`: Gestione turni, fasi di gioco e calcolo reward.
        - `board.py` & `world.py`: Rappresentazione della mappa e dei territori.
        - `actions.py`: Implementazione fisica delle mosse.
        - `cards.py`: Gestione del mazzo carte e bonus tris.
    - **`ai/`**: Logica degli agenti.
        - `network.py`: Architettura della rete neurale (NumPy).
        - `evolution.py`: Algoritmi genetici (Crossover, Mutazione).
        - `processor.py`: Encoding dello stato mappa per gli ingressi dell'AI.
        - `agent.py`: Classe base dell'agente intelligente.
    - **`web/`**: API FastAPI e dashboard frontend.
    - **`utils/`**: Utility per logging, parallelismo e gestione dataset.
- **`dataset/`**: File `.jsonl` per l'Imitation Learning.

## 🛠️ Stack Tecnologico

- **Python 3.11+**
- **NumPy**: Calcolo matriciale per le reti neurali.
- **FastAPI & Uvicorn**: Backend asincrono per la dashboard.
- **Colorama**: Formattazione output terminale.

---

*Creato da Federico Cisera*
