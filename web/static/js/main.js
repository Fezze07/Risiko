import { gameState } from "./state.js";
import { CONSTANTS } from "./constants.js";
import { DOM, addLog, clearSelection, closeBattleOverlay, syncControlState, updateQuantityUI, updateSpeedLabel } from "./ui.js";
import { updateZoom } from "./board.js";
import { handleMessage, sendAction, sendControl, sendPass, setSpeed, startMode } from "./game.js";

let pendingMode = null;

function clampPlayers(value) {
    const parsed = Number(value);
    if (!Number.isFinite(parsed)) return 2;
    return Math.max(2, Math.min(8, Math.round(parsed)));
}

function parseLobbyConfig() {
    const params = new URLSearchParams(window.location.search);
    const modeParam = (params.get("mode") || "").toUpperCase();
    const requestedPlayers = clampPlayers(params.get("players") || 2);
    const typesRaw = (params.get("types") || "").split(",").map((v) => String(v || "").trim().toUpperCase());
    const playerTypes = {};
    for (let i = 1; i <= requestedPlayers; i += 1) {
        const role = typesRaw[i - 1];
        playerTypes[String(i)] = role === "HUMAN" || role === "H" ? "HUMAN" : "AI";
    }
    if (modeParam !== "WATCH" && !Object.values(playerTypes).includes("HUMAN")) {
        playerTypes["1"] = "HUMAN";
    }
    gameState.lobbyConfig = {
        numPlayers: requestedPlayers,
        playerTypes,
    };
}

function connect() {
    const protocol = location.protocol === "https:" ? "wss" : "ws";
    const wsUrl = new URL(`${protocol}://${location.host}/ws/game`);
    wsUrl.searchParams.set("num_players", String(gameState.lobbyConfig.numPlayers || 2));
    gameState.ws = new WebSocket(wsUrl.toString());

    gameState.ws.onopen = () => {
        DOM.connStatus.className = "status-connected";
        DOM.connStatus.textContent = "Connected";
        addLog("[INFO] Connesso al server", "log-info");
        syncControlState();
        if (pendingMode) {
            startMode(pendingMode, gameState.lobbyConfig);
            pendingMode = null;
        }
    };

    gameState.ws.onclose = () => {
        DOM.connStatus.className = "status-disconnected";
        DOM.connStatus.textContent = "Disconnected";
        if (!gameState.isGameOver) addLog("[INFO] Connessione persa", "log-error");
    };

    gameState.ws.onerror = () => {
        DOM.connStatus.className = "status-disconnected";
        DOM.connStatus.textContent = "Error";
    };

    gameState.ws.onmessage = (event) => {
        try {
            const msg = JSON.parse(event.data);
            handleMessage(msg);
        } catch (e) {
            console.error("Parse error:", e);
        }
    };
}

if (DOM.btnQtyMinus) {
    DOM.btnQtyMinus.addEventListener("click", () => {
        if (gameState.currentQty > 1) {
            gameState.currentQty--;
            updateQuantityUI();
        }
    });
}

if (DOM.btnQtyPlus) {
    DOM.btnQtyPlus.addEventListener("click", () => {
        if (gameState.currentQty < gameState.maxQty) {
            gameState.currentQty++;
            updateQuantityUI();
        }
    });
}

if (DOM.btnCtrlPlay) {
    DOM.btnCtrlPlay.addEventListener("click", () => sendControl("PLAY"));
}
if (DOM.btnCtrlPause) {
    DOM.btnCtrlPause.addEventListener("click", () => sendControl("PAUSE"));
}
if (DOM.btnCtrlReset) {
    DOM.btnCtrlReset.addEventListener("click", () => sendControl("RESET"));
}
if (DOM.speedSlider) {
    DOM.speedSlider.addEventListener("input", (e) => {
        const value = Number(e.target.value || 500);
        updateSpeedLabel(value);
        setSpeed(value);
    });
}
if (DOM.toggleAutoSkipBattle) {
    DOM.toggleAutoSkipBattle.checked = gameState.autoSkipBattle;
    DOM.toggleAutoSkipBattle.addEventListener("change", (e) => {
        gameState.autoSkipBattle = !!e.target.checked;
    });
}

if (DOM.btnSend) DOM.btnSend.addEventListener("click", sendAction);
if (DOM.btnPass) DOM.btnPass.addEventListener("click", () => sendPass());
if (DOM.btnClear) DOM.btnClear.addEventListener("click", clearSelection);

if (DOM.btnZoomIn) {
    DOM.btnZoomIn.addEventListener("click", () => {
        if (gameState.currentZoom < CONSTANTS.MAX_ZOOM) {
            gameState.currentZoom = parseFloat((gameState.currentZoom + CONSTANTS.ZOOM_STEP).toFixed(1));
            updateZoom();
        }
    });
}
if (DOM.btnZoomOut) {
    DOM.btnZoomOut.addEventListener("click", () => {
        if (gameState.currentZoom > CONSTANTS.MIN_ZOOM) {
            gameState.currentZoom = parseFloat((gameState.currentZoom - CONSTANTS.ZOOM_STEP).toFixed(1));
            updateZoom();
        }
    });
}
if (DOM.btnZoomReset) {
    DOM.btnZoomReset.addEventListener("click", () => {
        gameState.currentZoom = 1.0;
        gameState.panX = 0;
        gameState.panY = 0;
        updateZoom();
    });
}

DOM.boardSvg.addEventListener("mousedown", (e) => {
    if (e.target.classList.contains("territory-circle") || e.target.closest(".territory-group")) {
        return;
    }
    gameState.isPanning = true;
    gameState.startPanX = e.clientX - gameState.panX;
    gameState.startPanY = e.clientY - gameState.panY;
    DOM.boardSvg.style.cursor = "grabbing";
    e.preventDefault();
});

DOM.boardSvg.addEventListener("mousemove", (e) => {
    if (!gameState.isPanning) return;
    gameState.panX = e.clientX - gameState.startPanX;
    gameState.panY = e.clientY - gameState.startPanY;
    updateZoom();
    e.preventDefault();
});

DOM.boardSvg.addEventListener("mouseup", () => {
    gameState.isPanning = false;
    DOM.boardSvg.style.cursor = "grab";
});

DOM.boardSvg.addEventListener("mouseleave", () => {
    gameState.isPanning = false;
    DOM.boardSvg.style.cursor = "grab";
});

DOM.boardSvg.style.cursor = "grab";
if (DOM.speedSlider) {
    DOM.speedSlider.value = String(gameState.delayMs);
    updateSpeedLabel(gameState.delayMs);
}
if (DOM.battleClose) {
    DOM.battleClose.addEventListener("click", closeBattleOverlay);
}
const params = new URLSearchParams(window.location.search);
const modeParam = (params.get("mode") || "").toUpperCase();
parseLobbyConfig();
if (modeParam === "PLAY" || modeParam === "WATCH") {
    pendingMode = modeParam;
}
connect();
