import { gameState } from "./state.js";
import { CONSTANTS } from "./constants.js";
import { DOM, addLog, updateQuantityUI, clearSelection, updateUIState } from "./ui.js";
import { updateZoom } from "./board.js";
import { handleMessage, sendAction, sendPass } from "./game.js";

function connect() {
    const protocol = location.protocol === "https:" ? "wss" : "ws";
    gameState.ws = new WebSocket(`${protocol}://${location.host}/ws/game`);

    gameState.ws.onopen = () => {
        DOM.connStatus.className = "status-connected";
        DOM.connStatus.textContent = "● Connesso";
        addLog("[INFO] Connesso al server", "log-info");
    };

    gameState.ws.onclose = () => {
        DOM.connStatus.className = "status-disconnected";
        DOM.connStatus.textContent = "● Disconnesso";
        if (!gameState.isGameOver) {
            addLog("[INFO] Connessione persa", "log-error");
        }
    };

    gameState.ws.onerror = () => {
        DOM.connStatus.className = "status-disconnected";
        DOM.connStatus.textContent = "● Errore";
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

// ---- Event Listeners ----
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

DOM.btnSend.addEventListener("click", sendAction);
DOM.btnPass.addEventListener("click", () => sendPass());
DOM.btnClear.addEventListener("click", clearSelection);

// Zoom
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

// Pan/Drag
DOM.boardSvg.addEventListener("mousedown", (e) => {
    if (e.target.classList.contains("territory-cell") ||
        e.target.closest(".territory-group")) {
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

// Start
connect();
