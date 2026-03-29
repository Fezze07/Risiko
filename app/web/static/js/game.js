import { gameState } from "./state.js";
import {
    DOM,
    addLog,
    applySelectionHighlights,
    clearSelection,
    handleGameOver,
    handleLog,
    handleReinforceInfo,
    hidePhaseAlert,
    setModeUI,
    showAiOverlay,
    showBattleOverlay,
    showPhaseAlert,
    syncControlState,
    updateQuantityUI,
    updateSendButton,
    updateSpeedLabel,
    updateScoreBar,
    updateUIState,
} from "./ui.js";
import { renderBoard, updateBoardVisuals, flashTerritory } from "./board.js";
import { toggleCardPanel, fetchCards } from "./cards.js";

export function getTerritoryById(id) {
    if (!gameState.boardData || !gameState.boardData.territories) return null;
    return gameState.boardData.territories.find((t) => t.id === id) || null;
}

export function getTerritoryName(id) {
    const t = getTerritoryById(id);
    return t && t.name ? t.name : `#${id}`;
}

function getPlayerMeta(playerId) {
    if (!gameState.playerMap) return null;
    return gameState.playerMap[playerId] || gameState.playerMap[String(playerId)] || null;
}

function isHumanPlayer(playerId) {
    const meta = getPlayerMeta(playerId);
    return !!meta && String(meta.type || "").toUpperCase() === "HUMAN";
}

function isAiPlayer(playerId) {
    const meta = getPlayerMeta(playerId);
    return !!meta && String(meta.type || "").toUpperCase() === "AI";
}

function canHumanAct() {
    return (
        gameState.mode === "PLAY" &&
        isHumanPlayer(gameState.currentPlayer) &&
        !gameState.isAiPlaying &&
        !gameState.isGameOver &&
        !gameState.isBattleModalOpen
    );
}

export function triggerPhaseAlert() {
    if (gameState.mode !== "PLAY") {
        hidePhaseAlert();
        return;
    }
    if (!canHumanAct()) {
        hidePhaseAlert();
        return;
    }

    const phase = gameState.currentPhase;
    let title = "OPERAZIONE ATTIVA";
    let text = "";
    switch (phase) {
        case "INITIAL_PLACEMENT": {
            const n = parseInt(DOM.armiesCount.textContent, 10) || 0;
            title = "FASE: SCHIERAMENTO";
            text = `Posiziona ${n} armate iniziali`;
            break;
        }
        case "REINFORCE": {
            const n = parseInt(DOM.armiesCount.textContent, 10) || 0;
            title = "FASE: RINFORZI";
            text = `Posiziona ${n} armate sui tuoi territori`;
            break;
        }
        case "ATTACK":
            title = "FASE: ATTACCO";
            text = "Seleziona un tuo territorio e un nemico adiacente";
            break;
        case "POST_ATTACK_MOVE":
            title = "FASE: CONQUISTA";
            text = "Scegli quante armate spostare nel nuovo territorio";
            break;
        case "MANEUVER":
            title = "FASE: MANOVRA";
            text = "Sposta armate tra territori alleati adiacenti";
            break;
        case "PLAY_CARDS":
            title = "FASE: TATTICA (CARTE)";
            text = "Controlla le tue carte per bonus rinforzi";
            break;
        default:
            hidePhaseAlert();
            return;
    }
    showPhaseAlert(title, text);
}

function handleInit(msg) {
    gameState.mode = msg.mode || gameState.mode;
    gameState.isRunning = !!msg.running;
    gameState.delayMs = msg.delay_ms || gameState.delayMs;
    gameState.numPlayers = msg.num_players || gameState.numPlayers;
    gameState.playerMap = msg.player_map || gameState.playerMap || {};
    gameState.boardData = msg.board;
    gameState.continents = msg.continents || [];
    if (msg.max_armies) gameState.maxArmies = msg.max_armies;
    gameState.currentPlayer = msg.current_player;
    gameState.currentPhase = msg.phase;
    gameState.isGameOver = false;

    const humanIds = Object.keys(gameState.playerMap || {})
        .map((id) => Number(id))
        .filter((id) => Number.isFinite(id) && isHumanPlayer(id))
        .sort((a, b) => a - b);
    gameState.localHumanId = humanIds.length ? humanIds[0] : 1;

    setModeUI(gameState.mode);
    updateSpeedLabel(gameState.delayMs);
    if (DOM.speedSlider) DOM.speedSlider.value = gameState.delayMs;

    updateUIState(msg);
    if (msg.player_stats) updateScoreBar(msg.player_stats);
    renderBoard();
    const initMessage = gameState.mode === "WATCH" ? "Modalita WATCH avviata" : "Modalita PLAY avviata";
    addLog(`[INFO] ${initMessage}`, "log-info");

    if (gameState.mode === "PLAY") {
        const mission =
            (msg.player_missions && msg.player_missions[String(gameState.localHumanId)]) ||
            msg.p1_mission ||
            "Missione non disponibile";
        if (mission) {
            DOM.missionInfo.textContent = mission;
            DOM.missionInfo.title = mission;
        }
        triggerPhaseAlert();
    } else {
        hidePhaseAlert();
    }
    syncControlState();
}

function handleStateUpdate(msg) {
    if (msg.board && msg.board.territories) {
        if (!gameState.boardData) gameState.boardData = msg.board;
        else gameState.boardData.territories = msg.board.territories;
    }
    if (msg.player_map) gameState.playerMap = msg.player_map;
    if (msg.num_players) gameState.numPlayers = msg.num_players;
    if (msg.max_armies) gameState.maxArmies = msg.max_armies;
    gameState.currentPlayer = msg.current_player;
    gameState.currentPhase = msg.phase;
    if (msg.mode) gameState.mode = msg.mode;
    if (msg.delay_ms !== undefined) {
        gameState.delayMs = msg.delay_ms;
        updateSpeedLabel(gameState.delayMs);
        if (DOM.speedSlider) DOM.speedSlider.value = gameState.delayMs;
    }
    if (msg.running !== undefined) {
        gameState.isRunning = !!msg.running;
    }

    updateUIState(msg);
    updateBoardVisuals();

    if (gameState.mode === "PLAY" && isAiPlayer(msg.current_player) && msg.running) {
        showAiOverlay(true);
    } else {
        showAiOverlay(false);
        gameState.isAiPlaying = false;
    }

    if (gameState.mode === "PLAY") {
        triggerPhaseAlert();
        if (gameState.currentPhase === "PLAY_CARDS" && isHumanPlayer(gameState.currentPlayer) && !gameState.isAiPlaying) {
            toggleCardPanel(true);
        }
    } else {
        hidePhaseAlert();
    }

    if (msg.extra && msg.extra.rolls_att && msg.extra.rolls_def) {
        applySelectionHighlights();
        showBattleOverlay(msg.extra.rolls_att, msg.extra.rolls_def, msg.extra.last_action);
    }
    if (msg.extra && msg.extra.last_action) {
        const last = msg.extra.last_action;
        if (last.type === "REINFORCE") {
            flashTerritory(last.dest, "flash-reinforce");
        } else if (last.type === "MANEUVER") {
            flashTerritory(last.src, "flash-move");
            flashTerritory(last.dest, "flash-move");
        } else if (last.type === "POST_ATTACK_MOVE") {
            flashTerritory(last.src, "flash-post");
            flashTerritory(last.dest, "flash-post");
        }
    }
    syncControlState();
}

function handlePostAttackRequired(msg) {
    const srcName = getTerritoryName(msg.src);
    const destName = getTerritoryName(msg.dest);
    addLog(`[INFO] Conquista: scegli spostamento (${srcName} -> ${destName})`, "log-info");
    gameState.currentPhase = "POST_ATTACK_MOVE";
    DOM.phaseValue.textContent = "POST_ATTACK_MOVE";
    gameState.selectedSrc = msg.src;
    gameState.selectedDest = msg.dest;

    const tSrc = getTerritoryById(gameState.selectedSrc);
    const tDest = getTerritoryById(gameState.selectedDest);
    DOM.selSrc.textContent = `${srcName} (${tSrc ? tSrc.armies : "?"} armies)`;
    DOM.selDest.textContent = `${destName} (${tDest ? tDest.armies : "?"} armies)`;
    applySelectionHighlights();
    updateQuantityUI();
    gameState.currentQty = gameState.maxQty;
    updateQuantityUI();
    triggerPhaseAlert();
}

export function handleMessage(msg) {
    switch (msg.type) {
        case "ready":
            if (msg.num_players) gameState.numPlayers = msg.num_players;
            if (msg.player_map) gameState.playerMap = msg.player_map;
            if (msg.max_armies) gameState.maxArmies = msg.max_armies;
            addLog("[INFO] Server pronto. Scegli una modalita.", "log-info");
            break;
        case "init":
            handleInit(msg);
            break;
        case "state_update":
            handleStateUpdate(msg);
            break;
        case "reinforce_info":
            handleReinforceInfo(msg);
            break;
        case "speed_updated":
            gameState.delayMs = msg.delay_ms;
            updateSpeedLabel(gameState.delayMs);
            if (DOM.speedSlider) DOM.speedSlider.value = gameState.delayMs;
            break;
        case "mode_status":
            gameState.isRunning = !!msg.running;
            syncControlState();
            break;
        case "error":
            addLog(`[ERRORE] ${msg.message}`, "log-error");
            break;
        case "log":
            handleLog(msg);
            break;
        case "ai_thinking":
            if (gameState.mode === "PLAY") showAiOverlay(true);
            break;
        case "ai_done":
            showAiOverlay(false);
            gameState.isAiPlaying = false;
            break;
        case "runner_stopped":
            showAiOverlay(false);
            gameState.isAiPlaying = false;
            break;
        case "post_attack_move_required":
            handlePostAttackRequired(msg);
            break;
        case "game_over":
            handleGameOver(msg);
            break;
        case "PLAYER_RECEIVED_CARD": {
            addLog(`[CARTE] Hai ricevuto una nuova carta territorio!`, "log-success");
            fetchCards();
            break;
        }
        case "PLAYER_ELIMINATED_TRANSFER_CARDS": {
            addLog(`[CARTE] Ereditate ${msg.amount} carte dal giocatore eliminato!`, "log-success");
            fetchCards();
            break;
        }
        default:
            break;
    }
}

export function startMode(mode, options = {}) {
    if (!gameState.ws || gameState.ws.readyState !== WebSocket.OPEN) return;
    const payload = { command: "START_MODE", mode };
    if (options.numPlayers) payload.num_players = Number(options.numPlayers);
    if (options.playerTypes) payload.player_types = options.playerTypes;
    gameState.ws.send(JSON.stringify(payload));
}

export function sendControl(action) {
    if (!gameState.ws || gameState.ws.readyState !== WebSocket.OPEN) return;
    gameState.ws.send(JSON.stringify({ command: "CONTROL", action }));
}

export function setSpeed(delayMs) {
    if (!gameState.ws || gameState.ws.readyState !== WebSocket.OPEN) return;
    const clamped = Math.max(100, Math.min(2000, Number(delayMs)));
    gameState.ws.send(JSON.stringify({ command: "SET_SPEED", delay_ms: clamped }));
}

export function onTerritoryClick(id) {
    if (gameState.mode !== "PLAY") return;
    if (gameState.isBattleModalOpen) return;
    if (!canHumanAct()) return;

    const t = getTerritoryById(id);
    if (!t) return;
    const actingPlayer = gameState.currentPlayer;

    if (gameState.currentPhase === "REINFORCE" || gameState.currentPhase === "INITIAL_PLACEMENT") {
        if (t.owner !== actingPlayer) {
            addLog("[ERRORE] Seleziona un tuo territorio per il rinforzo", "log-error");
            return;
        }
        gameState.selectedSrc = null;
        gameState.selectedDest = id;
        DOM.selSrc.textContent = "-";
        DOM.selDest.textContent = `#${id} (${t.armies} armies)`;
    } else if (gameState.currentPhase === "POST_ATTACK_MOVE") {
        return;
    } else {
        if (gameState.selectedSrc === null) {
            if (t.owner !== actingPlayer) {
                addLog("[ERRORE] Seleziona un tuo territorio come sorgente", "log-error");
                return;
            }
            gameState.selectedSrc = id;
            gameState.selectedDest = null;
            DOM.selSrc.textContent = `#${id} (${t.armies} armies)`;
            DOM.selDest.textContent = "-";
        } else if (gameState.selectedDest === null) {
            if (gameState.currentPhase === "ATTACK" && t.owner === actingPlayer) {
                addLog("[ERRORE] Non puoi attaccare un tuo territorio", "log-error");
                return;
            }
            if (gameState.currentPhase === "MANEUVER" && t.owner !== actingPlayer) {
                addLog("[ERRORE] La destinazione della manovra deve essere tua", "log-error");
                return;
            }
            gameState.selectedDest = id;
            DOM.selDest.textContent = `#${id} (${t.armies} armies)`;
        } else {
            if (t.owner !== actingPlayer) return;
            gameState.selectedSrc = id;
            gameState.selectedDest = null;
            DOM.selSrc.textContent = `#${id} (${t.armies} armies)`;
            DOM.selDest.textContent = "-";
        }
    }

    applySelectionHighlights();
    updateSendButton();
    updateQuantityUI();
    gameState.currentQty = gameState.maxQty;
    updateQuantityUI();
    if (gameState.currentPhase === "REINFORCE" || gameState.currentPhase === "INITIAL_PLACEMENT") triggerPhaseAlert();
}

export function sendAction() {
    if (!gameState.ws || gameState.ws.readyState !== WebSocket.OPEN) return;
    if (gameState.mode !== "PLAY") return;
    if (gameState.isBattleModalOpen) return;
    if (!canHumanAct()) return;

    let qty = 1.0;
    let msg = {};
    if (gameState.currentPhase === "REINFORCE" || gameState.currentPhase === "INITIAL_PLACEMENT") {
        const atp = parseInt(DOM.armiesCount.textContent, 10) || 1;
        qty = gameState.currentQty / atp;
        msg = { action_type: "REINFORCE", dest: gameState.selectedDest, qty };
    } else if (gameState.currentPhase === "POST_ATTACK_MOVE") {
        const t = getTerritoryById(gameState.selectedSrc);
        const totalMovable = t && t.armies > 1 ? t.armies - 1 : 1;
        qty = gameState.currentQty / totalMovable;
        msg = { action_type: "POST_ATTACK_MOVE", qty };
    } else if (gameState.currentPhase === "ATTACK") {
        if (gameState.selectedSrc === null || gameState.selectedDest === null) return;
        msg = { action_type: "ATTACK", src: gameState.selectedSrc, dest: gameState.selectedDest };
    } else if (gameState.currentPhase === "MANEUVER") {
        const t = getTerritoryById(gameState.selectedSrc);
        if (t && t.armies > 1) qty = gameState.currentQty / (t.armies - 1);
        msg = { action_type: "MANEUVER", src: gameState.selectedSrc, dest: gameState.selectedDest, qty };
    }

    gameState.ws.send(JSON.stringify(msg));
    clearSelection();
}

export function sendPass() {
    if (!gameState.ws || gameState.ws.readyState !== WebSocket.OPEN) return;
    if (gameState.mode !== "PLAY") return;
    if (gameState.isBattleModalOpen) return;
    if (!canHumanAct()) return;
    if (!(gameState.currentPlayer === 1 && isHumanPlayer(1))) return;
    gameState.ws.send(JSON.stringify({ action_type: "PASS" }));
    clearSelection();
}
