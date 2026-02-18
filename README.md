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
    git clone https://github.com/Fezze07/RisikoReinforcementLearning.git
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
Per avviare l'evoluzione della popolazione:
```bash
python main.py
```

### Osservazione Match
Per vedere i migliori agenti sfidarsi in console (modalità debug):
```bash
python main.py --watch
```

### Web Interface
Per avviare il server web e accedere alla dashboard (stats e visualizzazione grafica):
```bash
python -m web.server
```
Poi apri `http://localhost:8000` nel browser.

## 📂 Struttura del Progetto

- **`main.py`**: Entry point principale per il training e la gestione dei processi paralleli.
- **`config.py`**: Configurazione centralizzata (Iperparametri, Reward, Regole di gioco).
- **`core/`**: Logica del gioco e regole.
    - `environment.py`: Motore del gioco e calcolo dei premi.
    - `actions.py`: Esecuzione fisica delle azioni (Attacchi, Rinforzi).
    - `board.py` & `territory.py`: Modello dati della mappa.
    - `validators.py`: Controllo della validità delle mosse.
    - `task.py`: Gestione degli obiettivi e delle missioni.
- **`ai/`**: Cervello degli agenti.
    - `network.py`: Architettura della Rete Neurale (NumPy focus).
    - `evolution.py`: Operatori genetici (Mutazione, Crossover).
    - `processor.py`: Encoding/Decoding dello stato tra board e rete.
- **`web/`**: Server FastAPI e interfaccia frontend (Socket communication).
- **`dataset/`**: Raccolta di dati per l'Imitation Learning.
- **`utils/`**: Utility per il logging, training parallelo e gestione dei match.
- **`visual/`**: Renderer ANSI per la console.
- **`tests/`**: Suite di test unitari per l'ambiente e le ricompense.

## 🛠️ Stack Tecnologico

- **Python 3.x**
- **NumPy**: Motore di calcolo per le reti neurali.
- **FastAPI**: Backend per la dashboard web.
- **Colorama**: Visualizzazione raffinata in terminale.

---

*Creato da Federico Cisera*
