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
    turnInfo: document.getElementById("turn-info"),
    currentPlayerLabel: document.getElementById("current-player-label"),
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
    statsBar: document.getElementById("stats-bar"),
    leaderboardCurrent: document.getElementById("leaderboard-current"),
    playerLegend: document.getElementById("player-legend"),
    encodingDebug: document.getElementById("encoding-debug"),
    territoryTooltip: document.getElementById("territory-tooltip"),
};

function getPlayerMeta(playerId) {
    if (!gameState.playerMap) return null;
    return gameState.playerMap[playerId] || gameState.playerMap[String(playerId)] || null;
}

function isHumanPlayer(playerId) {
    const meta = getPlayerMeta(playerId);
    return !!meta && String(meta.type || "").toUpperCase() === "HUMAN";
}

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
    if (mode === "WATCH" && DOM.missionInfo) {
        DOM.missionInfo.textContent = "Spectator mode: AI vs AI";
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

export function updateLeaderboard(playerStats = [], currentPlayer = 1) {
    if (DOM.currentPlayerLabel) {
        DOM.currentPlayerLabel.textContent = `P${currentPlayer}`;
    }
    if (DOM.leaderboardCurrent) {
        const meta = getPlayerMeta(currentPlayer);
        const role = meta ? String(meta.type || "AI").toUpperCase() : "AI";
        DOM.leaderboardCurrent.textContent = `Current: P${currentPlayer} (${role})`;
    }
    if (!DOM.playerLegend) return;
    DOM.playerLegend.innerHTML = "";

    const sorted = [...playerStats].sort((a, b) => {
        if (b.territories !== a.territories) return b.territories - a.territories;
        return b.armies - a.armies;
    });

    sorted.forEach((entry, idx) => {
        const row = document.createElement("div");
        row.className = "legend-row";
        if (entry.id === currentPlayer) {
            row.classList.add("current-turn");
        }

        const rank = document.createElement("div");
        rank.className = "legend-rank";
        rank.textContent = String(idx + 1);

        const swatch = document.createElement("span");
        swatch.className = "legend-swatch";
        swatch.style.background = entry.color || "#666";

        const main = document.createElement("div");
        main.className = "legend-main";

        const name = document.createElement("span");
        name.className = "legend-name";
        name.textContent = `P${entry.id}`;

        const badges = document.createElement("div");
        badges.className = "legend-badges";
        const role = document.createElement("span");
        role.className = "legend-role";
        role.textContent = String(entry.type || "AI").toUpperCase();
        badges.appendChild(role);

        main.appendChild(swatch);
        main.appendChild(name);
        main.appendChild(badges);

        const stats = document.createElement("div");
        stats.className = "legend-stats";
        const tChip = document.createElement("span");
        tChip.className = "legend-chip";
        tChip.textContent = `${entry.territories} T`;
        const aChip = document.createElement("span");
        aChip.className = "legend-chip";
        aChip.textContent = `${entry.armies} A`;
        const score = document.createElement("span");
        score.className = "legend-score";
        score.textContent = String(entry.score ?? 0);
        stats.appendChild(tChip);
        stats.appendChild(aChip);
        stats.appendChild(score);

        row.appendChild(rank);
        row.appendChild(main);
        row.appendChild(stats);
        DOM.playerLegend.appendChild(row);
    });
}

export function updateScoreBar(playerStats = []) {
    if (!DOM.statsBar) return;
    DOM.statsBar.innerHTML = "";
    if (!Array.isArray(playerStats) || playerStats.length === 0) return;

    playerStats.forEach((entry) => {
        const card = document.createElement("div");
        card.className = "score-card player-score";
        if (entry.color) {
            card.style.borderLeftColor = entry.color;
        }

        const label = document.createElement("span");
        label.textContent = `P${entry.id}`;
        if (entry.type) {
            const role = document.createElement("span");
            role.className = "legend-role";
            role.textContent = String(entry.type || "AI").toUpperCase();
            label.appendChild(role);
        }

        const value = document.createElement("span");
        value.className = "score-value";
        value.textContent = String(entry.score ?? 0);

        card.appendChild(label);
        card.appendChild(value);
        DOM.statsBar.appendChild(card);
    });
}
export function showEncodingDebug(territoryId, data, pointer = null) {
    const text =
        `Territory #${territoryId}\n` +
        `Is Mine: ${data.isMine.toFixed(1)}\n` +
        `Normalized Armies: ${data.armiesNormalized.toFixed(3)}\n` +
        `Relative Enemy ID: ${data.enemyRelative.toFixed(3)}\n` +
        `Threat Level: ${data.threatLevel.toFixed(3)}`;

    if (DOM.encodingDebug) {
        DOM.encodingDebug.textContent = text;
    }
    if (DOM.territoryTooltip && pointer) {
        DOM.territoryTooltip.textContent = text;
        DOM.territoryTooltip.style.left = `${pointer.x + 14}px`;
        DOM.territoryTooltip.style.top = `${pointer.y + 14}px`;
        DOM.territoryTooltip.classList.remove("hidden");
    }
}

export function clearEncodingDebug() {
    if (DOM.encodingDebug) {
        DOM.encodingDebug.textContent = "Hover su un territorio per vedere le feature NN.";
    }
    if (DOM.territoryTooltip) {
        DOM.territoryTooltip.classList.add("hidden");
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
        const attackerId = meta.player !== undefined ? meta.player : "?";
        const defenderId = meta.defender_id !== undefined ? meta.defender_id : "?";
        DOM.battleAttackerLabel.textContent = `Attacker P${attackerId}`;
        DOM.battleDefenderLabel.textContent = `Defender P${defenderId}`;
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
    return el;
}

export function handleLog(msg) {
    const entry = msg.entry || "";
    const player = Number(msg.player || 0);
    let cls = "";
    if (msg.reward !== undefined) {
        if (msg.reward > 0) cls += " log-reward-pos";
        else if (msg.reward < 0) cls += " log-reward-neg";
    }
    const line = addLog(entry, cls.trim());
    const meta = getPlayerMeta(player);
    if (line && meta && meta.color) {
        line.style.borderLeftColor = meta.color;
        const rawColor = String(meta.color);
        const alphaBg = rawColor.startsWith("hsl(")
            ? rawColor.replace("hsl(", "hsla(").replace(")", ", 0.16)")
            : rawColor;
        line.style.background = alphaBg;
    }
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
    DOM.turnInfo.textContent = `${msg.turn || 0}`;
    if (DOM.currentPlayerLabel) DOM.currentPlayerLabel.textContent = `P${gameState.currentPlayer}`;
    if (msg.player_stats) {
        updateLeaderboard(msg.player_stats, gameState.currentPlayer);
        updateScoreBar(msg.player_stats);
    }

    const atp = msg.armies_to_place || 0;
    const canShowReinforce = gameState.mode === "PLAY" && isHumanPlayer(gameState.currentPlayer);
    if (atp > 0 && canShowReinforce && (gameState.currentPhase === "REINFORCE" || gameState.currentPhase === "INITIAL_PLACEMENT")) {
        DOM.armiesInfo.classList.remove("hidden");
        DOM.armiesCount.textContent = atp;
    } else {
        DOM.armiesInfo.classList.add("hidden");
    }

    const humanTurn =
        gameState.mode === "PLAY" &&
        isHumanPlayer(gameState.currentPlayer) &&
        !gameState.isAiPlaying &&
        !gameState.isGameOver &&
        !gameState.isBattleModalOpen;
    const passAllowed = humanTurn && gameState.currentPlayer === 1 && isHumanPlayer(1);
    DOM.btnPass.disabled = !passAllowed;
    DOM.btnSend.disabled = !humanTurn;
    DOM.btnClear.disabled = !humanTurn;
    if (DOM.btnQtyMinus) DOM.btnQtyMinus.disabled = !humanTurn;
    if (DOM.btnQtyPlus) DOM.btnQtyPlus.disabled = !humanTurn;
    updateSendButton();
    updateQuantityUI();
    syncControlState();
}

export function handleReinforceInfo(msg) {
    const n = msg.armies_to_place || 0;
    if (gameState.mode !== "PLAY" || !isHumanPlayer(gameState.currentPlayer)) {
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
    if (msg.winner > 0) {
        const winnerMeta = getPlayerMeta(msg.winner);
        const role = winnerMeta ? String(winnerMeta.type || "AI").toUpperCase() : "AI";
        winnerDisplay = `${role} P${msg.winner} VINCE`;
    } else {
        winnerDisplay = "PAREGGIO";
    }
    DOM.gameOverTitle.textContent = winnerDisplay;
    DOM.gameOverMsg.textContent = `Risultato missione: ${msg.message}`;
    if (msg.player_stats) {
        updateLeaderboard(msg.player_stats, gameState.currentPlayer);
        updateScoreBar(msg.player_stats);
    }
    addLog(`[GAME OVER] Vincitore: Player ${msg.winner}`, "log-info");
    syncControlState();
}

export function updateQuantityUI() {
    const stepperDiv = document.querySelector(".army-stepper");
    const humanTurn = gameState.mode === "PLAY" && isHumanPlayer(gameState.currentPlayer);
    if (!humanTurn) {
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
    const humanTurn =
        gameState.mode === "PLAY" &&
        isHumanPlayer(gameState.currentPlayer) &&
        !gameState.isAiPlaying &&
        !gameState.isGameOver &&
        !gameState.isBattleModalOpen;
    if (!humanTurn) {
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
