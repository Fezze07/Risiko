import { gameState } from "./state.js";
import { CONSTANTS } from "./constants.js";
import { getTerritoryById } from "./game.js";

// DOM Elements
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
    diceAtt: document.getElementById("dice-attacker"),
    diceDef: document.getElementById("dice-defender"),
    phasePrompt: document.getElementById("phase-prompt"),
    promptTitle: document.getElementById("prompt-title"),
    promptText: document.getElementById("prompt-text"),
    p1FinalReward: document.getElementById("p1-final-reward"),
    p2FinalReward: document.getElementById("p2-final-reward")
};

// ... existing code ...

export function showBattleOverlay(rollsAtt, rollsDef) {
    if (!rollsAtt || !rollsDef) return;

    // Clear previous dice
    DOM.diceAtt.innerHTML = "";
    DOM.diceDef.innerHTML = "";

    // Add attacker dice
    rollsAtt.forEach((val, i) => {
        const die = document.createElement("div");
        die.className = "die att";
        die.style.animationDelay = `${i * 0.1}s`;
        die.textContent = val;
        DOM.diceAtt.appendChild(die);
    });

    // Add defender dice
    rollsDef.forEach((val, i) => {
        const die = document.createElement("div");
        die.className = "die def";
        die.style.animationDelay = `${(rollsAtt.length + i) * 0.1}s`;
        die.textContent = val;
        DOM.diceDef.appendChild(die);
    });

    DOM.battleModal.classList.remove("hidden");
}

export function showPhaseAlert(title, text) {
    if (!DOM.phasePrompt) return;

    DOM.promptTitle.textContent = title;
    DOM.promptText.textContent = text;
    DOM.phasePrompt.classList.remove("hidden");

    // Auto-hide after some time if it's just a transition
    // But for now, we might want it persistent until the phase changes
}

export function hidePhaseAlert() {
    if (DOM.phasePrompt) DOM.phasePrompt.classList.add("hidden");
}

// ---- Log ----
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

// ---- AI Overlay ----
export function showAiOverlay(show) {
    if (show) {
        DOM.aiOverlay.classList.remove("hidden");
        gameState.isAiPlaying = true;
    } else {
        DOM.aiOverlay.classList.add("hidden");
    }
}

// ---- UI State ----
export function updateUIState(msg) {
    DOM.phaseValue.textContent = msg.phase || gameState.currentPhase;
    DOM.turnInfo.textContent = `Turno: ${msg.turn || 0}`;
    if (msg.p1_score !== undefined) DOM.scoreP1.textContent = msg.p1_score;
    if (msg.p2_score !== undefined) DOM.scoreP2.textContent = msg.p2_score;

    const atp = msg.armies_to_place || 0;
    if (atp > 0 && gameState.currentPlayer === 1 && (gameState.currentPhase === "REINFORCE" || gameState.currentPhase === "INITIAL_PLACEMENT")) {
        DOM.armiesInfo.classList.remove("hidden");
        DOM.armiesCount.textContent = atp;
    } else {
        DOM.armiesInfo.classList.add("hidden");
    }

    const myTurn = gameState.currentPlayer === 1 && !gameState.isAiPlaying && !gameState.isGameOver;
    DOM.btnPass.disabled = !myTurn;
    updateSendButton();
    updateQuantityUI();
}

// ---- Reinforce Info ----
export function handleReinforceInfo(msg) {
    const n = msg.armies_to_place || 0;
    if (n > 0) {
        DOM.armiesInfo.classList.remove("hidden");
        DOM.armiesCount.textContent = n;
        addLog(`[INFO] Hai ${n} truppe da piazzare`, "log-info");

        // Import triggerPhaseAlert from game.js and call it
        import("./game.js").then(module => {
            module.triggerPhaseAlert();
        });
    } else {
        DOM.armiesInfo.classList.add("hidden");
    }
}

export function handleGameOver(msg) {
    gameState.isGameOver = true;
    DOM.gameOverModal.classList.remove("hidden");
    const winnerDisplay = msg.winner === 1 ? "HAI VINTO!" : "AI AGENT VINCE";
    DOM.gameOverTitle.textContent = winnerDisplay;
    DOM.gameOverMsg.textContent = `Risultato missione: ${msg.message}`;

    if (msg.p1_reward !== undefined) DOM.p1FinalReward.textContent = Math.round(msg.p1_reward);
    if (msg.p2_reward !== undefined) DOM.p2FinalReward.textContent = Math.round(msg.p2_reward);

    addLog(`[GAME OVER] Vincitore: Player ${msg.winner}`, "log-info");
}

// ---- Update Quantity UI ----
export function updateQuantityUI() {
    const stepperDiv = document.querySelector(".army-stepper");

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
            } else {
                newMax = 1;
            }
        } else {
            newMax = 1;
        }
    }

    gameState.maxQty = newMax;
    if (gameState.maxQty < 0) gameState.maxQty = 0;

    if (gameState.currentQty > gameState.maxQty) gameState.currentQty = gameState.maxQty;
    if (gameState.currentQty < 1 && gameState.maxQty >= 1) gameState.currentQty = 1;
    if (gameState.maxQty < 1) gameState.currentQty = 0;

    if (DOM.qtyDisplay) {
        DOM.qtyDisplay.textContent = gameState.currentQty + " 🪖";
    }

    if (DOM.btnQtyMinus) DOM.btnQtyMinus.disabled = gameState.currentQty <= 1;
    if (DOM.btnQtyPlus) DOM.btnQtyPlus.disabled = gameState.currentQty >= gameState.maxQty;
}

// ---- Update Send Button ----
export function updateSendButton() {
    const myTurn = gameState.currentPlayer === 1 && !gameState.isAiPlaying && !gameState.isGameOver;
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

// ---- Selection Highlights ----
export function applySelectionHighlights() {
    // 1. Reset everything
    document.querySelectorAll(".territory-cell").forEach(rect => {
        rect.classList.remove("selected-src", "selected-dest");
    });
    document.querySelectorAll(".territory-group").forEach(g => {
        g.classList.remove("selected");
    });

    // 2. Apply Source highlight & scaling
    if (gameState.selectedSrc !== null) {
        const rect = document.querySelector(`.territory-cell[data-id="${gameState.selectedSrc}"]`);
        if (rect) rect.classList.add("selected-src");
        const group = document.querySelector(`.territory-group[data-id="${gameState.selectedSrc}"]`);
        if (group) group.classList.add("selected");
    }

    // 3. Apply Destination highlight & scaling
    if (gameState.selectedDest !== null) {
        const rect = document.querySelector(`.territory-cell[data-id="${gameState.selectedDest}"]`);
        if (rect) rect.classList.add("selected-dest");
        const group = document.querySelector(`.territory-group[data-id="${gameState.selectedDest}"]`);
        if (group) group.classList.add("selected");
    }

    // 4. Highlight connections for Attack Phase
    if (gameState.currentPhase === "ATTACK") {
        highlightConnections(gameState.selectedSrc);
    } else {
        highlightConnections(null);
    }
}

export function highlightConnections(srcId) {
    document.querySelectorAll(".connection-line").forEach(line => {
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
    DOM.selSrc.textContent = "—";
    DOM.selDest.textContent = "—";
    applySelectionHighlights();
    updateSendButton();
    updateQuantityUI();
}
