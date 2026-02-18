import { gameState } from "./state.js";
import { getTerritoryById, triggerPhaseAlert } from "./game.js";

export const DOM = {
    boardSvg: document.getElementById("board-svg"),
    selSrc: document.getElementById("sel-src"),
    selDest: document.getElementById("sel-dest"),
    btnQtyMinus: document.getElementById("btn-qty-minus"),
    btnQtyPlus: document.getElementById("btn-qty-plus"),
    qtyDisplay: document.getElementById("qty-display"),
    btnSend: document.getElementById("btn-send"),
    btnPass: document.getElementById("btn-pass"),
    btnClear: document.getElementById("btn-clear"),
    logContainer: document.getElementById("log-container"),
    phaseValue: document.getElementById("phase-value"),
    scoreP1: document.getElementById("score-p1"),
    scoreP2: document.getElementById("score-p2"),
    turnInfo: document.getElementById("turn-info"),
    missionInfo: document.getElementById("mission-info"),
    aiOverlay: document.getElementById("ai-thinking-overlay"),
    armiesInfo: document.getElementById("armies-info"),
    armiesCount: document.getElementById("armies-count"),
    connStatus: document.getElementById("connection-status"),
    gameOverModal: document.getElementById("game-over-modal"),
    gameOverTitle: document.getElementById("game-over-title"),
    gameOverMsg: document.getElementById("game-over-msg"),
    btnZoomIn: document.getElementById("btn-zoom-in"),
    btnZoomOut: document.getElementById("btn-zoom-out"),
    btnZoomReset: document.getElementById("btn-zoom-reset"),
    battleModal: document.getElementById("battle-modal"),
    battleClose: document.getElementById("btn-battle-close"),
    battleAttackerLabel: document.getElementById("battle-attacker-label"),
    battleDefenderLabel: document.getElementById("battle-defender-label"),
    battleRoute: document.getElementById("battle-route"),
    diceAtt: document.getElementById("dice-attacker"),
    diceDef: document.getElementById("dice-defender"),
    phasePrompt: document.getElementById("phase-prompt"),
    promptTitle: document.getElementById("prompt-title"),
    promptText: document.getElementById("prompt-text"),
    p1FinalReward: document.getElementById("p1-final-reward"),
    p2FinalReward: document.getElementById("p2-final-reward"),
    landingOverlay: document.getElementById("landing-overlay"),
    btnModePlay: document.getElementById("btn-mode-play"),
    btnModeWatch: document.getElementById("btn-mode-watch"),
    controlBar: document.getElementById("control-bar"),
    btnCtrlPlay: document.getElementById("btn-ctrl-play"),
    btnCtrlPause: document.getElementById("btn-ctrl-pause"),
    btnCtrlReset: document.getElementById("btn-ctrl-reset"),
    speedSlider: document.getElementById("speed-slider"),
    speedValue: document.getElementById("speed-value"),
    scoreP1Label: document.getElementById("score-p1-label"),
    scoreP2Label: document.getElementById("score-p2-label"),
};

export function setModeUI(mode) {
    if (!mode) {
        return;
    }
    if (DOM.landingOverlay) {
        DOM.landingOverlay.classList.add("hidden");
    }
    if (DOM.controlBar) {
        DOM.controlBar.classList.remove("hidden");
    }
    if (mode === "WATCH") {
        if (DOM.scoreP1Label) DOM.scoreP1Label.textContent = "AI 1";
        if (DOM.scoreP2Label) DOM.scoreP2Label.textContent = "AI 2";
        if (DOM.missionInfo) DOM.missionInfo.textContent = "Spectator mode: AI vs AI";
    } else {
        if (DOM.scoreP1Label) DOM.scoreP1Label.textContent = "PLAYER 1";
        if (DOM.scoreP2Label) DOM.scoreP2Label.textContent = "AI AGENT";
    }
    syncControlState();
}

export function syncControlState() {
    if (!DOM.btnCtrlPlay || !DOM.btnCtrlPause) return;
    DOM.btnCtrlPlay.disabled = gameState.isRunning;
    DOM.btnCtrlPause.disabled = !gameState.isRunning;
}

export function updateSpeedLabel(ms) {
    if (DOM.speedValue) {
        DOM.speedValue.textContent = `${ms} ms`;
    }
}

export function showBattleOverlay(rollsAtt, rollsDef, meta) {
    if (!rollsAtt || !rollsDef) return;
    if (gameState.isBattleModalOpen) return;
    gameState.isBattleModalOpen = true;
    if (gameState.ws && gameState.ws.readyState === WebSocket.OPEN) {
        gameState.pauseForModal = true;
        gameState.ws.send(JSON.stringify({ command: "CONTROL", action: "PAUSE" }));
    }
    DOM.diceAtt.innerHTML = "";
    DOM.diceDef.innerHTML = "";
    rollsAtt.forEach((val, i) => {
        const die = document.createElement("div");
        die.className = "die att";
        die.style.animationDelay = `${i * 0.1}s`;
        die.textContent = val;
        DOM.diceAtt.appendChild(die);
    });
    rollsDef.forEach((val, i) => {
        const die = document.createElement("div");
        die.className = "die def";
        die.style.animationDelay = `${(rollsAtt.length + i) * 0.1}s`;
        die.textContent = val;
        DOM.diceDef.appendChild(die);
    });
    if (meta && DOM.battleAttackerLabel && DOM.battleDefenderLabel && DOM.battleRoute) {
        const att = meta.player === 1 ? "P1" : "P2";
        const def = meta.player === 1 ? "P2" : "P1";
        DOM.battleAttackerLabel.textContent = `Attacker ${att}`;
        DOM.battleDefenderLabel.textContent = `Defender ${def}`;
        const src = meta.src !== undefined ? `#${meta.src}` : "?";
        const dest = meta.dest !== undefined ? `#${meta.dest}` : "?";
        DOM.battleRoute.textContent = `${src} -> ${dest}`;
    }
    DOM.battleModal.classList.remove("hidden");
}

export function closeBattleOverlay() {
    if (!gameState.isBattleModalOpen) return;
    gameState.isBattleModalOpen = false;
    DOM.battleModal.classList.add("hidden");
    if (gameState.pauseForModal && gameState.ws && gameState.ws.readyState === WebSocket.OPEN) {
        gameState.pauseForModal = false;
        gameState.ws.send(JSON.stringify({ command: "CONTROL", action: "PLAY" }));
    }
}

export function showPhaseAlert(title, text) {
    if (!DOM.phasePrompt) return;
    DOM.promptTitle.textContent = title;
    DOM.promptText.textContent = text;
    DOM.phasePrompt.classList.remove("hidden");
}

export function hidePhaseAlert() {
    if (DOM.phasePrompt) DOM.phasePrompt.classList.add("hidden");
}

export function addLog(text, className) {
    const el = document.createElement("div");
    el.className = "log-entry " + (className || "");
    el.textContent = text;
    DOM.logContainer.appendChild(el);
    DOM.logContainer.scrollTop = DOM.logContainer.scrollHeight;
    while (DOM.logContainer.children.length > 200) {
        DOM.logContainer.removeChild(DOM.logContainer.firstChild);
    }
}

export function handleLog(msg) {
    const entry = msg.entry || "";
    const player = msg.player || (entry.startsWith("P1") ? 1 : entry.startsWith("P2") ? 2 : 0);
    let cls = player === 1 ? "log-p1" : player === 2 ? "log-p2" : "";
    if (msg.reward !== undefined) {
        if (msg.reward > 0) cls += " log-reward-pos";
        else if (msg.reward < 0) cls += " log-reward-neg";
    }
    addLog(entry, cls);
}

export function showAiOverlay(show) {
    if (show) {
        DOM.aiOverlay.classList.remove("hidden");
        gameState.isAiPlaying = true;
    } else {
        DOM.aiOverlay.classList.add("hidden");
    }
}

export function updateUIState(msg) {
    DOM.phaseValue.textContent = msg.phase || gameState.currentPhase;
    DOM.turnInfo.textContent = `Turno: ${msg.turn || 0}`;
    if (msg.p1_score !== undefined) DOM.scoreP1.textContent = msg.p1_score;
    if (msg.p2_score !== undefined) DOM.scoreP2.textContent = msg.p2_score;

    const atp = msg.armies_to_place || 0;
    const canShowReinforce = gameState.mode === "PLAY" && gameState.currentPlayer === 1;
    if (atp > 0 && canShowReinforce && (gameState.currentPhase === "REINFORCE" || gameState.currentPhase === "INITIAL_PLACEMENT")) {
        DOM.armiesInfo.classList.remove("hidden");
        DOM.armiesCount.textContent = atp;
    } else {
        DOM.armiesInfo.classList.add("hidden");
    }

    const myTurn = gameState.mode === "PLAY" && gameState.currentPlayer === 1 && !gameState.isAiPlaying && !gameState.isGameOver && !gameState.isBattleModalOpen;
    const allowTactical = gameState.mode === "PLAY";
    DOM.btnPass.disabled = !myTurn;
    DOM.btnSend.disabled = !allowTactical;
    DOM.btnClear.disabled = !allowTactical;
    if (DOM.btnQtyMinus) DOM.btnQtyMinus.disabled = !allowTactical;
    if (DOM.btnQtyPlus) DOM.btnQtyPlus.disabled = !allowTactical;
    updateSendButton();
    updateQuantityUI();
    syncControlState();
}

export function handleReinforceInfo(msg) {
    const n = msg.armies_to_place || 0;
    if (gameState.mode !== "PLAY") {
        DOM.armiesInfo.classList.add("hidden");
        return;
    }
    if (n > 0) {
        DOM.armiesInfo.classList.remove("hidden");
        DOM.armiesCount.textContent = n;
        addLog(`[INFO] Hai ${n} truppe da piazzare`, "log-info");
        triggerPhaseAlert();
    } else {
        DOM.armiesInfo.classList.add("hidden");
    }
}

export function handleGameOver(msg) {
    gameState.isGameOver = true;
    gameState.isRunning = false;
    DOM.gameOverModal.classList.remove("hidden");
    let winnerDisplay = "GAME OVER";
    if (gameState.mode === "WATCH") {
        winnerDisplay = msg.winner === 1 ? "AI 1 VINCE" : msg.winner === 2 ? "AI 2 VINCE" : "PAREGGIO";
    } else {
        winnerDisplay = msg.winner === 1 ? "HAI VINTO!" : msg.winner === 2 ? "AI AGENT VINCE" : "PAREGGIO";
    }
    DOM.gameOverTitle.textContent = winnerDisplay;
    DOM.gameOverMsg.textContent = `Risultato missione: ${msg.message}`;
    if (msg.p1_score !== undefined) DOM.p1FinalReward.textContent = Math.round(msg.p1_score);
    if (msg.p2_score !== undefined) DOM.p2FinalReward.textContent = Math.round(msg.p2_score);
    addLog(`[GAME OVER] Vincitore: Player ${msg.winner}`, "log-info");
    syncControlState();
}

export function updateQuantityUI() {
    const stepperDiv = document.querySelector(".army-stepper");
    if (gameState.mode !== "PLAY") {
        if (stepperDiv) stepperDiv.style.display = "none";
        return;
    }
    if (gameState.currentPhase === "ATTACK") {
        if (stepperDiv) stepperDiv.style.display = "none";
        return;
    }
    if (stepperDiv) stepperDiv.style.display = "flex";

    let newMax = 1;
    if (gameState.currentPhase === "REINFORCE" || gameState.currentPhase === "INITIAL_PLACEMENT") {
        newMax = parseInt(DOM.armiesCount.textContent, 10) || 0;
    } else if (gameState.currentPhase === "MANEUVER" || gameState.currentPhase === "POST_ATTACK_MOVE") {
        if (gameState.selectedSrc !== null) {
            const t = getTerritoryById(gameState.selectedSrc);
            if (t && t.armies > 1) {
                newMax = t.armies - 1;
            }
        }
    }

    gameState.maxQty = Math.max(0, newMax);
    if (gameState.currentQty > gameState.maxQty) gameState.currentQty = gameState.maxQty;
    if (gameState.currentQty < 1 && gameState.maxQty >= 1) gameState.currentQty = 1;
    if (gameState.maxQty < 1) gameState.currentQty = 0;

    if (DOM.qtyDisplay) {
        DOM.qtyDisplay.textContent = `${gameState.currentQty} armies`;
    }
    if (DOM.btnQtyMinus) DOM.btnQtyMinus.disabled = gameState.currentQty <= 1;
    if (DOM.btnQtyPlus) DOM.btnQtyPlus.disabled = gameState.currentQty >= gameState.maxQty;
}

export function updateSendButton() {
    const myTurn = gameState.mode === "PLAY" && gameState.currentPlayer === 1 && !gameState.isAiPlaying && !gameState.isGameOver;
    if (!myTurn) {
        DOM.btnSend.disabled = true;
        return;
    }

    if (gameState.currentPhase === "REINFORCE" || gameState.currentPhase === "INITIAL_PLACEMENT") {
        DOM.btnSend.disabled = gameState.selectedDest === null;
    } else if (gameState.currentPhase === "POST_ATTACK_MOVE") {
        DOM.btnSend.disabled = false;
    } else {
        DOM.btnSend.disabled = gameState.selectedSrc === null || gameState.selectedDest === null;
    }
}

export function applySelectionHighlights() {
    document.querySelectorAll(".territory-cell").forEach((rect) => {
        rect.classList.remove("selected-src", "selected-dest");
    });
    document.querySelectorAll(".territory-group").forEach((g) => {
        g.classList.remove("selected");
    });

    if (gameState.selectedSrc !== null) {
        const rect = document.querySelector(`.territory-cell[data-id="${gameState.selectedSrc}"]`);
        if (rect) rect.classList.add("selected-src");
        const group = document.querySelector(`.territory-group[data-id="${gameState.selectedSrc}"]`);
        if (group) group.classList.add("selected");
    }

    if (gameState.selectedDest !== null) {
        const rect = document.querySelector(`.territory-cell[data-id="${gameState.selectedDest}"]`);
        if (rect) rect.classList.add("selected-dest");
        const group = document.querySelector(`.territory-group[data-id="${gameState.selectedDest}"]`);
        if (group) group.classList.add("selected");
    }

    if (gameState.currentPhase === "ATTACK") {
        highlightConnections(gameState.selectedSrc);
    } else {
        highlightConnections(null);
    }
}

export function highlightConnections(srcId) {
    document.querySelectorAll(".connection-line").forEach((line) => {
        const u = line.getAttribute("data-u");
        const v = line.getAttribute("data-v");
        if (srcId !== null && (u === srcId.toString() || v === srcId.toString())) {
            line.classList.add("highlight");
        } else {
            line.classList.remove("highlight");
        }
    });
}

export function clearSelection() {
    gameState.selectedSrc = null;
    gameState.selectedDest = null;
    DOM.selSrc.textContent = "-";
    DOM.selDest.textContent = "-";
    applySelectionHighlights();
    updateSendButton();
    updateQuantityUI();
}
