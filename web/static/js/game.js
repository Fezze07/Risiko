import { gameState } from "./state.js";
import { CONSTANTS } from "./constants.js";
import { DOM, addLog, updateUIState, handleLog, handleReinforceInfo, handleGameOver, updateQuantityUI, showAiOverlay, applySelectionHighlights, updateSendButton, clearSelection, showBattleOverlay, showPhaseAlert, hidePhaseAlert } from "./ui.js";
import { renderBoard, updateBoardVisuals } from "./board.js";

// ---- Helpers ----
export function getTerritoryById(id) {
    if (!gameState.boardData || !gameState.boardData.territories) return null;
    return gameState.boardData.territories.find(t => t.id === id) || null;
}

export function triggerPhaseAlert() {
    if (gameState.currentPlayer !== 1 || gameState.isAiPlaying || gameState.isGameOver) {
        hidePhaseAlert();
        return;
    }

    const phase = gameState.currentPhase;
    let title = "OPERAZIONE ATTIVA";
    let text = "";

    switch (phase) {
        case "INITIAL_PLACEMENT":
            const atpInit = parseInt(DOM.armiesCount.textContent, 10) || 0;
            title = "FASE: SCHIERAMENTO";
            text = `Posiziona ${atpInit} armate iniziali`;
            break;
        case "REINFORCE":
            const atp = parseInt(DOM.armiesCount.textContent, 10) || 0;
            title = "FASE: RINFORZI";
            text = `Posiziona ${atp} armate sui tuoi territori`;
            break;
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
            text = "Sposta le armate tra due tuoi territori collegati";
            break;
        default:
            hidePhaseAlert();
            return;
    }

    showPhaseAlert(title, text);
}

// ---- Message Handler ----
export function handleMessage(msg) {
    switch (msg.type) {
        case "init":
            handleInit(msg);
            break;
        case "state_update":
            handleStateUpdate(msg);
            break;
        case "reinforce_info":
            // This call is now handled by the ui.js handleReinforceInfo, which also calls triggerPhaseAlert
            handleReinforceInfo(msg);
            break;
        case "error":
            addLog(`[ERRORE] ${msg.message}`, "log-error");
            break;
        case "log":
            handleLog(msg);
            break;
        case "ai_thinking":
            showAiOverlay(true);
            break;
        case "ai_done":
            showAiOverlay(false);
            gameState.isAiPlaying = false;
            break;
        case "post_attack_move_required":
            handlePostAttackRequired(msg);
            break;
        case "game_over":
            handleGameOver(msg);
            break;
    }
}

// ---- Init ----
function handleInit(msg) {
    gameState.boardData = msg.board;
    gameState.continents = msg.continents || [];
    gameState.currentPlayer = msg.current_player;
    gameState.currentPhase = msg.phase;
    updateUIState(msg);
    if (msg.p1_mission) {
        DOM.missionInfo.textContent = "🎯 " + msg.p1_mission;
        DOM.missionInfo.title = msg.p1_mission;
    }
    renderBoard();
    addLog("[INFO] Partita inizializzata — Buona fortuna!", "log-info");
    triggerPhaseAlert();
}

// ---- State Update ----
function handleStateUpdate(msg) {
    if (msg.board && msg.board.territories) {
        gameState.boardData.territories = msg.board.territories;
    }
    gameState.currentPlayer = msg.current_player;
    gameState.currentPhase = msg.phase;
    updateUIState(msg);
    updateBoardVisuals();

    if (!msg.ai_playing) {
        showAiOverlay(false);
        gameState.isAiPlaying = false;
        triggerPhaseAlert();
    } else {
        hidePhaseAlert();
    }

    if (msg.extra && msg.extra.rolls_att && msg.extra.rolls_def) {
        // Trigger battle overlay if dice info is present
        applySelectionHighlights();
        showBattleOverlay(msg.extra.rolls_att, msg.extra.rolls_def);
    }
}

// ---- Post Attack Move ----
function handlePostAttackRequired(msg) {
    addLog(`[INFO] Conquista! Scegli quante truppe spostare (#${msg.src} → #${msg.dest})`, "log-info");
    gameState.currentPhase = "POST_ATTACK_MOVE";
    DOM.phaseValue.textContent = "POST_ATTACK_MOVE";

    gameState.selectedSrc = msg.src;
    gameState.selectedDest = msg.dest;

    const tSrc = getTerritoryById(gameState.selectedSrc);
    const tDest = getTerritoryById(gameState.selectedDest);

    DOM.selSrc.textContent = `#${gameState.selectedSrc} (${tSrc ? tSrc.armies : "?"} 🪖)`;
    DOM.selDest.textContent = `#${gameState.selectedDest} (${tDest ? tDest.armies : "?"} 🪖)`;

    applySelectionHighlights();

    // Update UI and sync Quantity
    updateQuantityUI();
    gameState.currentQty = gameState.maxQty;
    updateQuantityUI();
    triggerPhaseAlert();
}

// ---- Territory Click ----
export function onTerritoryClick(id) {
    if (gameState.isAiPlaying || gameState.isGameOver || gameState.currentPlayer !== 1) return;

    const t = getTerritoryById(id);
    if (!t) return;

    if (gameState.currentPhase === "REINFORCE" || gameState.currentPhase === "INITIAL_PLACEMENT") {
        if (t.owner !== 1) {
            addLog("[ERRORE] Seleziona un tuo territorio per il rinforzo", "log-error");
            return;
        }
        gameState.selectedSrc = null;
        gameState.selectedDest = id;
        DOM.selSrc.textContent = "—";
        DOM.selDest.textContent = `#${id} (${t.armies} 🪖)`;
    } else if (gameState.currentPhase === "POST_ATTACK_MOVE") {
        return;
    } else {
        if (gameState.selectedSrc === null) {
            if (t.owner !== 1) {
                addLog("[ERRORE] Seleziona un tuo territorio come sorgente", "log-error");
                return;
            }
            gameState.selectedSrc = id;
            gameState.selectedDest = null;
            DOM.selSrc.textContent = `#${id} (${t.armies} 🪖)`;
            DOM.selDest.textContent = "—";
        } else if (gameState.selectedDest === null) {
            if (gameState.currentPhase === "ATTACK" && t.owner === 1) {
                addLog("[ERRORE] Non puoi attaccare un tuo territorio", "log-error");
                return;
            }
            if (gameState.currentPhase === "MANEUVER" && t.owner !== 1) {
                addLog("[ERRORE] La destinazione della manovra deve essere tua", "log-error");
                return;
            }
            gameState.selectedDest = id;
            DOM.selDest.textContent = `#${id} (${t.armies} 🪖)`;
        } else {
            // Stricter check: only allow selecting our territory as source
            if (t.owner !== 1) {
                // Do nothing if it's not our territory
                return;
            }

            gameState.selectedSrc = id;
            gameState.selectedDest = null;
            DOM.selSrc.textContent = `#${id} (${t.armies} 🪖)`;
            DOM.selDest.textContent = "—";
        }
    }

    applySelectionHighlights();
    updateSendButton();
    updateQuantityUI();
    gameState.currentQty = gameState.maxQty;
    updateQuantityUI();

    if (gameState.currentPhase === "REINFORCE" || gameState.currentPhase === "INITIAL_PLACEMENT") triggerPhaseAlert();
}

// ---- Send Action ----
export function sendAction() {
    if (!gameState.ws || gameState.ws.readyState !== WebSocket.OPEN) return;

    let qty = 1.0;
    let msg = {};

    if (gameState.currentPhase === "REINFORCE" || gameState.currentPhase === "INITIAL_PLACEMENT") {
        const atp = parseInt(DOM.armiesCount.textContent, 10) || 1;
        qty = gameState.currentQty / atp;
        msg = { action_type: "REINFORCE", dest: gameState.selectedDest, qty: qty };
    } else if (gameState.currentPhase === "POST_ATTACK_MOVE") {
        const t = getTerritoryById(gameState.selectedSrc);
        const totalMovable = (t && t.armies > 1) ? (t.armies - 1) : 1;
        qty = gameState.currentQty / totalMovable;
        msg = { action_type: "POST_ATTACK_MOVE", qty: qty };
    } else if (gameState.currentPhase === "ATTACK") {
        if (gameState.selectedSrc === null || gameState.selectedDest === null) return;
        msg = { action_type: "ATTACK", src: gameState.selectedSrc, dest: gameState.selectedDest };
    } else if (gameState.currentPhase === "MANEUVER") {
        const t = getTerritoryById(gameState.selectedSrc);
        if (t && t.armies > 1) {
            qty = gameState.currentQty / (t.armies - 1);
        }
        msg = { action_type: "MANEUVER", src: gameState.selectedSrc, dest: gameState.selectedDest, qty: qty };
    }

    gameState.ws.send(JSON.stringify(msg));
    clearSelection();
}

export function sendPass() {
    if (!gameState.ws || gameState.ws.readyState !== WebSocket.OPEN) return;
    if (gameState.isAiPlaying || gameState.isGameOver || gameState.currentPlayer !== 1) return;
    gameState.ws.send(JSON.stringify({ action_type: "PASS" }));
    clearSelection();
}
