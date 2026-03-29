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

// Controlla se due territori sono collegamento "wraparound" (Alaska-Kamchatka)
function isWraparoundConnection(t1, t2) {
    const ids = [t1.id, t2.id].sort((a, b) => a - b);
    // Alaska (0) <-> Kamchatka (29)
    return ids[0] === 0 && ids[1] === 29;
}

function getContinentColor(continent) {
    return CONSTANTS.CONTINENT_COLORS[continent] || { stroke: "rgba(255,255,255,0.3)", fill: "rgba(255,255,255,0.05)" };
}

// ---- Board Rendering ----
export function renderBoard() {
    if (!gameState.boardData || !gameState.boardData.territories) return;

    const territories = gameState.boardData.territories;
    const R = CONSTANTS.TERRITORY_RADIUS;
    const totalPlayers = Math.max(2, Number(gameState.numPlayers || 2));

    DOM.boardSvg.setAttribute("viewBox", `0 0 ${CONSTANTS.SVG_W} ${CONSTANTS.SVG_H}`);
    DOM.boardSvg.removeAttribute("width");
    DOM.boardSvg.removeAttribute("height");
    DOM.boardSvg.innerHTML = "";

    // Create Zoom Group (Game Layer)
    const gameLayer = document.createElementNS("http://www.w3.org/2000/svg", "g");
    gameLayer.id = "game-layer";
    gameLayer.style.transform = `translate(${gameState.panX}px, ${gameState.panY}px) scale(${gameState.currentZoom})`;
    gameLayer.style.transformBox = "view-box";
    gameLayer.style.transformOrigin = "center";
    DOM.boardSvg.appendChild(gameLayer);

    // Build territory map for neighbor lookup
    const tMap = {};
    territories.forEach((t) => {
        tMap[t.id] = t;
    });

    // --- Continent background regions ---
    const continentGroup = document.createElementNS("http://www.w3.org/2000/svg", "g");
    continentGroup.setAttribute("class", "continent-regions");
    gameLayer.appendChild(continentGroup);

    // Group territories by continent
    const continentTerritories = {};
    territories.forEach((t) => {
        const cont = t.continent || "UNKNOWN";
        if (!continentTerritories[cont]) continentTerritories[cont] = [];
        continentTerritories[cont].push(t);
    });

    // Draw subtle continent hulls
    for (const [contName, contTs] of Object.entries(continentTerritories)) {
        const cc = getContinentColor(contName);
        if (contTs.length < 2) continue;
        // Draw a convex-hull-like enclosure using an expanded bounding ellipse
        const xs = contTs.map(t => t.x);
        const ys = contTs.map(t => t.y);
        const cx = (Math.min(...xs) + Math.max(...xs)) / 2;
        const cy = (Math.min(...ys) + Math.max(...ys)) / 2;
        const rx = (Math.max(...xs) - Math.min(...xs)) / 2 + R + 18;
        const ry = (Math.max(...ys) - Math.min(...ys)) / 2 + R + 18;

        const ellipse = document.createElementNS("http://www.w3.org/2000/svg", "ellipse");
        ellipse.setAttribute("cx", cx);
        ellipse.setAttribute("cy", cy);
        ellipse.setAttribute("rx", rx);
        ellipse.setAttribute("ry", ry);
        ellipse.setAttribute("class", "continent-hull");
        ellipse.style.fill = cc.fill;
        ellipse.style.stroke = cc.stroke;
        continentGroup.appendChild(ellipse);

        // Continent label
        const label = document.createElementNS("http://www.w3.org/2000/svg", "text");
        label.setAttribute("x", cx);
        label.setAttribute("y", cy - ry + 12);
        label.setAttribute("text-anchor", "middle");
        label.setAttribute("class", "continent-label");
        label.style.fill = cc.stroke;
        label.textContent = contName.replace("_", " ");
        continentGroup.appendChild(label);
    }

    // --- Connections ---
    const linesGroup = document.createElementNS("http://www.w3.org/2000/svg", "g");
    linesGroup.setAttribute("class", "connections");
    gameLayer.appendChild(linesGroup);

    const drawnPairs = new Set();
    territories.forEach((t) => {
        (t.neighbors || []).forEach((nId) => {
            const pairKey = `${Math.min(t.id, nId)}-${Math.max(t.id, nId)}`;
            if (drawnPairs.has(pairKey)) return;
            drawnPairs.add(pairKey);
            const n = tMap[nId];
            if (!n) return;

            if (isWraparoundConnection(t, n)) {
                // Wraparound: draw two short lines to edges
                const leftT = t.x < n.x ? t : n;
                const rightT = t.x < n.x ? n : t;

                const lineL = document.createElementNS("http://www.w3.org/2000/svg", "line");
                lineL.setAttribute("x1", leftT.x);
                lineL.setAttribute("y1", leftT.y);
                lineL.setAttribute("x2", 10);
                lineL.setAttribute("y2", (leftT.y + rightT.y) / 2);
                lineL.setAttribute("class", "connection-line wraparound");
                lineL.setAttribute("data-u", t.id);
                lineL.setAttribute("data-v", nId);
                linesGroup.appendChild(lineL);

                const lineR = document.createElementNS("http://www.w3.org/2000/svg", "line");
                lineR.setAttribute("x1", rightT.x);
                lineR.setAttribute("y1", rightT.y);
                lineR.setAttribute("x2", CONSTANTS.SVG_W - 10);
                lineR.setAttribute("y2", (leftT.y + rightT.y) / 2);
                lineR.setAttribute("class", "connection-line wraparound");
                lineR.setAttribute("data-u", t.id);
                lineR.setAttribute("data-v", nId);
                linesGroup.appendChild(lineR);
            } else {
                const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
                line.setAttribute("x1", t.x);
                line.setAttribute("y1", t.y);
                line.setAttribute("x2", n.x);
                line.setAttribute("y2", n.y);
                line.setAttribute("data-u", t.id);
                line.setAttribute("data-v", nId);
                line.setAttribute("class", "connection-line");
                linesGroup.appendChild(line);
            }
        });
    });

    // --- Territories (circles) ---
    const cellsGroup = document.createElementNS("http://www.w3.org/2000/svg", "g");
    cellsGroup.setAttribute("class", "territories");
    gameLayer.appendChild(cellsGroup);

    territories.forEach((t) => {
        const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
        g.setAttribute("data-id", t.id);
        g.setAttribute("class", "territory-group");

        const cc = getContinentColor(t.continent);
        const ownerColor = getOwnerColor(t.owner, totalPlayers);

        // Territory circle
        const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
        circle.setAttribute("cx", t.x);
        circle.setAttribute("cy", t.y);
        circle.setAttribute("r", R);
        circle.setAttribute("data-id", t.id);
        circle.setAttribute("class", `territory-circle owner-${t.owner || 0}`);
        circle.style.fill = t.owner ? ownerColor : "rgba(40,40,60,0.8)";
        circle.style.fillOpacity = t.owner ? "0.35" : "0.5";
        circle.style.stroke = t.owner ? ownerColor : cc.stroke;
        circle.addEventListener("click", () => onTerritoryClick(t.id));
        g.appendChild(circle);

        // Center for scale effect
        g.style.transformOrigin = `${t.x}px ${t.y}px`;

        // Army count (centered in circle)
        const armyText = document.createElementNS("http://www.w3.org/2000/svg", "text");
        armyText.setAttribute("x", t.x);
        armyText.setAttribute("y", t.y + 5);
        armyText.setAttribute("text-anchor", "middle");
        armyText.setAttribute("class", `territory-armies owner-${t.owner || 0}`);
        armyText.textContent = t.armies;
        g.appendChild(armyText);

        // Territory name (below circle)
        const nameText = document.createElementNS("http://www.w3.org/2000/svg", "text");
        nameText.setAttribute("x", t.x);
        nameText.setAttribute("y", t.y + R + 13);
        nameText.setAttribute("text-anchor", "middle");
        nameText.setAttribute("class", "territory-name");
        nameText.textContent = t.name || `#${t.id}`;
        g.appendChild(nameText);

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

        const circle = g.querySelector("circle");
        if (circle) {
            circle.classList.remove("owner-1", "owner-2", "owner-0", "owner-null");
            circle.classList.add(`owner-${t.owner || 0}`);
            const ownerColor = getOwnerColor(t.owner, totalPlayers);
            const cc = getContinentColor(t.continent);
            circle.style.fill = t.owner ? ownerColor : "rgba(40,40,60,0.8)";
            circle.style.fillOpacity = t.owner ? "0.35" : "0.5";
            circle.style.stroke = t.owner ? ownerColor : cc.stroke;
        }

        const armyEl = g.querySelector(".territory-armies");
        if (armyEl) {
            armyEl.textContent = t.armies;
            armyEl.classList.remove("owner-1", "owner-2", "owner-0");
            armyEl.classList.add(`owner-${t.owner || 0}`);
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
    const circle = document.querySelector(`.territory-circle[data-id="${id}"]`);
    const group = document.querySelector(`.territory-group[data-id="${id}"]`);
    if (!circle) return;
    const pulseClass = className.replace("flash-", "pulse-");
    circle.classList.remove(className);
    if (group) {
        group.classList.remove(className);
        group.classList.remove(pulseClass);
    }
    void circle.offsetWidth;
    circle.classList.add(className);
    if (group) {
        group.classList.add(className);
        group.classList.add(pulseClass);
    }
    setTimeout(() => {
        circle.classList.remove(className);
        if (group) {
            group.classList.remove(className);
            group.classList.remove(pulseClass);
        }
    }, 1100);
}
