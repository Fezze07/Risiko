import { gameState } from "./state.js";
import { CONSTANTS } from "./constants.js";
import { DOM, applySelectionHighlights, clearEncodingDebug, showEncodingDebug } from "./ui.js";
import { onTerritoryClick } from "./game.js";

function getPlayerMeta(playerId) {
    if (!gameState.playerMap) return null;
    return gameState.playerMap[playerId] || gameState.playerMap[String(playerId)] || null;
}

// Genera colori dinamici basati sull'ID del player
export function getPlayerColor(playerID, totalPlayers) {
    const hue = (playerID * (360 / totalPlayers));
    return `hsl(${hue}, 70%, 50%)`;
}

function getOwnerColor(ownerId, totalPlayers) {
    if (!ownerId) return "rgba(255, 255, 255, 0.10)";
    const meta = getPlayerMeta(ownerId);
    if (meta && meta.color) return meta.color;
    return getPlayerColor(ownerId, totalPlayers);
}

function getTerritoryMap() {
    const map = {};
    if (!gameState.boardData || !gameState.boardData.territories) return map;
    gameState.boardData.territories.forEach((t) => {
        map[t.id] = t;
    });
    return map;
}

function normalizeEnemyRelative(ownerId, currentPlayerId, totalPlayers) {
    if (!ownerId || ownerId === currentPlayerId) return 0.0;
    let relative = (ownerId - currentPlayerId) % totalPlayers;
    if (relative < 0) relative += totalPlayers;
    if (relative === 0) relative = totalPlayers - 1;
    if (totalPlayers <= 2) return 1.0;
    const normalized = 0.1 + ((relative - 1) / (totalPlayers - 2)) * 0.9;
    return Math.max(0.1, Math.min(1.0, normalized));
}

function computeEncodingFeatures(territory, territoryMap) {
    const currentPlayerId = Number(gameState.currentPlayer || 1);
    const observedMaxOwner = Math.max(
        2,
        ...Object.values(territoryMap).map((t) => Number(t.owner || 0)),
    );
    const totalPlayers = Math.max(2, Number(gameState.numPlayers || 2), observedMaxOwner);
    const maxArmies = Math.max(1, Number(gameState.maxArmies || 1));

    const isMine = territory.owner === currentPlayerId ? 1.0 : 0.0;
    const armiesNormalized = Math.min(1.0, Number(territory.armies || 0) / maxArmies);
    const enemyRelative = normalizeEnemyRelative(territory.owner, currentPlayerId, totalPlayers);

    const enemyNeighborArmies = (territory.neighbors || []).reduce((sum, nId) => {
        const neighbor = territoryMap[nId];
        if (!neighbor) return sum;
        if (!neighbor.owner || neighbor.owner === currentPlayerId) return sum;
        return sum + Number(neighbor.armies || 0);
    }, 0);
    const maxThreat = maxArmies * Math.max(1, (territory.neighbors || []).length);
    const threatLevel = Math.min(1.0, enemyNeighborArmies / maxThreat);

    return { isMine, armiesNormalized, enemyRelative, threatLevel };
}

function pointerFromMouseEvent(evt) {
    const boardRect = DOM.boardSvg.getBoundingClientRect();
    return {
        x: evt.clientX - boardRect.left,
        y: evt.clientY - boardRect.top,
    };
}

function bindHoverDebugEvents(targetElement, territoryId) {
    targetElement.addEventListener("mouseenter", (evt) => {
        const territoryMap = getTerritoryMap();
        const territory = territoryMap[territoryId];
        if (!territory) return;
        const encoding = computeEncodingFeatures(territory, territoryMap);
        showEncodingDebug(territoryId, encoding, pointerFromMouseEvent(evt));
    });
    targetElement.addEventListener("mousemove", (evt) => {
        const territoryMap = getTerritoryMap();
        const territory = territoryMap[territoryId];
        if (!territory) return;
        const encoding = computeEncodingFeatures(territory, territoryMap);
        showEncodingDebug(territoryId, encoding, pointerFromMouseEvent(evt));
    });
    targetElement.addEventListener("mouseleave", () => {
        clearEncodingDebug();
    });
}

// ---- Board Rendering ----
export function renderBoard() {
    if (!gameState.boardData || !gameState.boardData.territories) return;

    const territories = gameState.boardData.territories;
    const cols = gameState.boardData.grid_cols || 5;
    const rows = gameState.boardData.grid_rows || 5;
    const svgW = cols * CONSTANTS.CELL_W + 160;
    const svgH = rows * CONSTANTS.CELL_H + 160;
    const totalPlayers = Math.max(2, Number(gameState.numPlayers || 2));

    DOM.boardSvg.setAttribute("viewBox", `0 0 ${svgW} ${svgH}`);
    DOM.boardSvg.setAttribute("width", svgW);
    DOM.boardSvg.setAttribute("height", svgH);
    DOM.boardSvg.innerHTML = "";

    // Create Zoom Group (Game Layer)
    const gameLayer = document.createElementNS("http://www.w3.org/2000/svg", "g");
    gameLayer.id = "game-layer";
    gameLayer.style.transform = `translate(${gameState.panX}px, ${gameState.panY}px) scale(${gameState.currentZoom})`;
    gameLayer.style.transformBox = "view-box";
    gameLayer.style.transformOrigin = "center";
    DOM.boardSvg.appendChild(gameLayer);

    // Connections
    const linesGroup = document.createElementNS("http://www.w3.org/2000/svg", "g");
    linesGroup.setAttribute("class", "connections");
    gameLayer.appendChild(linesGroup);

    const tMap = {};
    territories.forEach((t) => {
        tMap[t.id] = t;
    });

    const drawnPairs = new Set();
    territories.forEach((t) => {
        const cx1 = t.x + CONSTANTS.CELL_W / 2;
        const cy1 = t.y + CONSTANTS.CELL_H / 2;
        t.neighbors.forEach((nId) => {
            const pairKey = `${Math.min(t.id, nId)}-${Math.max(t.id, nId)}`;
            if (drawnPairs.has(pairKey)) return;
            drawnPairs.add(pairKey);
            const n = tMap[nId];
            if (!n) return;
            const cx2 = n.x + CONSTANTS.CELL_W / 2;
            const cy2 = n.y + CONSTANTS.CELL_H / 2;
            const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
            line.setAttribute("x1", cx1);
            line.setAttribute("y1", cy1);
            line.setAttribute("x2", cx2);
            line.setAttribute("y2", cy2);
            line.setAttribute("data-u", t.id);
            line.setAttribute("data-v", nId);
            line.setAttribute("class", "connection-line");
            linesGroup.appendChild(line);
        });
    });

    // Territories
    const cellsGroup = document.createElementNS("http://www.w3.org/2000/svg", "g");
    cellsGroup.setAttribute("class", "territories");
    gameLayer.appendChild(cellsGroup);

    territories.forEach((t) => {
        const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
        g.setAttribute("data-id", t.id);
        g.setAttribute("class", "territory-group");

        // Cell rect
        const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
        rect.setAttribute("x", t.x);
        rect.setAttribute("y", t.y);
        rect.setAttribute("width", CONSTANTS.CELL_W);
        rect.setAttribute("height", CONSTANTS.CELL_H);
        rect.setAttribute("rx", CONSTANTS.CELL_RX);
        rect.setAttribute("ry", CONSTANTS.CELL_RX);
        rect.setAttribute("data-id", t.id);
        rect.setAttribute("class", `territory-cell owner-${t.owner || 0}`);

        const ownerColor = getOwnerColor(t.owner, totalPlayers);
        rect.style.fill = ownerColor;
        rect.style.fillOpacity = t.owner ? "0.24" : "0.08";
        rect.style.stroke = t.owner ? ownerColor : "rgba(255,255,255,0.24)";
        rect.addEventListener("click", () => onTerritoryClick(t.id));
        g.appendChild(rect);

        // Center origin for scale effect
        g.style.transformOrigin = `${t.x + CONSTANTS.CELL_W / 2}px ${t.y + CONSTANTS.CELL_H / 2}px`;

        // ID Label
        const idText = document.createElementNS("http://www.w3.org/2000/svg", "text");
        idText.setAttribute("x", t.x + 8);
        idText.setAttribute("y", t.y + 16);
        idText.setAttribute("class", "territory-id");
        idText.textContent = `#${t.id}`;
        g.appendChild(idText);

        // Armies
        const armyText = document.createElementNS("http://www.w3.org/2000/svg", "text");
        armyText.setAttribute("x", t.x + CONSTANTS.CELL_W / 2);
        armyText.setAttribute("y", t.y + CONSTANTS.CELL_H / 2 + 6);
        armyText.setAttribute("text-anchor", "middle");
        armyText.setAttribute("class", `territory-armies owner-${t.owner || 0}`);
        armyText.textContent = t.armies;
        g.appendChild(armyText);

        // Owner Icon
        const ownerText = document.createElementNS("http://www.w3.org/2000/svg", "text");
        ownerText.setAttribute("x", t.x + CONSTANTS.CELL_W / 2);
        ownerText.setAttribute("y", t.y + CONSTANTS.CELL_H - 10);
        ownerText.setAttribute("text-anchor", "middle");
        ownerText.setAttribute("class", "territory-owner-icon");
        ownerText.textContent = t.owner ? `P${t.owner}` : "-";
        ownerText.style.fill = t.owner ? ownerColor : "#64748b";
        ownerText.style.fontSize = "10px";
        ownerText.style.fontWeight = "600";
        g.appendChild(ownerText);

        bindHoverDebugEvents(g, t.id);
        cellsGroup.appendChild(g);
    });

    clearEncodingDebug();
    applySelectionHighlights();
}

// ---- Update Board Visuals (without re-rendering) ----
export function updateBoardVisuals() {
    if (!gameState.boardData || !gameState.boardData.territories) return;
    const totalPlayers = Math.max(2, Number(gameState.numPlayers || 2));

    const tMap = {};
    gameState.boardData.territories.forEach((t) => {
        tMap[t.id] = t;
    });

    document.querySelectorAll(".territory-group").forEach((g) => {
        const id = parseInt(g.getAttribute("data-id"), 10);
        const t = tMap[id];
        if (!t) return;

        const rect = g.querySelector("rect");
        if (rect) {
            rect.classList.remove("owner-1", "owner-2", "owner-0", "owner-null");
            rect.classList.add(`owner-${t.owner || 0}`);
            const ownerColor = getOwnerColor(t.owner, totalPlayers);
            rect.style.fill = ownerColor;
            rect.style.fillOpacity = t.owner ? "0.24" : "0.08";
            rect.style.stroke = t.owner ? ownerColor : "rgba(255,255,255,0.24)";
        }

        const armyEl = g.querySelector(".territory-armies");
        if (armyEl) {
            armyEl.textContent = t.armies;
            armyEl.classList.remove("owner-1", "owner-2", "owner-0");
            armyEl.classList.add(`owner-${t.owner || 0}`);
        }

        const ownerEl = g.querySelector(".territory-owner-icon");
        if (ownerEl) {
            const ownerColor = getOwnerColor(t.owner, totalPlayers);
            ownerEl.textContent = t.owner ? `P${t.owner}` : "-";
            ownerEl.style.fill = t.owner ? ownerColor : "#64748b";
        }
    });

    applySelectionHighlights();
}

export function updateZoom() {
    const layer = document.getElementById("game-layer");
    if (layer) {
        layer.style.transform = `translate(${gameState.panX}px, ${gameState.panY}px) scale(${gameState.currentZoom})`;
        layer.style.transformBox = "view-box";
        layer.style.transformOrigin = "center";
    }
}

export function flashTerritory(id, className) {
    if (id === undefined || id === null) return;
    const rect = document.querySelector(`.territory-cell[data-id="${id}"]`);
    const group = document.querySelector(`.territory-group[data-id="${id}"]`);
    if (!rect) return;
    const pulseClass = className.replace("flash-", "pulse-");
    rect.classList.remove(className);
    if (group) {
        group.classList.remove(className);
        group.classList.remove(pulseClass);
    }
    void rect.offsetWidth;
    rect.classList.add(className);
    if (group) {
        group.classList.add(className);
        group.classList.add(pulseClass);
    }
    setTimeout(() => {
        rect.classList.remove(className);
        if (group) {
            group.classList.remove(className);
            group.classList.remove(pulseClass);
        }
    }, 1100);
}
