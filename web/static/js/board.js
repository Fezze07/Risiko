import { gameState } from "./state.js";
import { CONSTANTS } from "./constants.js";
import { DOM, applySelectionHighlights } from "./ui.js";
import { onTerritoryClick } from "./game.js";

// ---- Board Rendering ----
export function renderBoard() {
    if (!gameState.boardData || !gameState.boardData.territories) return;

    const territories = gameState.boardData.territories;
    const cols = gameState.boardData.grid_cols || 5;
    const rows = gameState.boardData.grid_rows || 5;
    const svgW = cols * CONSTANTS.CELL_W + 160;
    const svgH = rows * CONSTANTS.CELL_H + 160;

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

    // Defs: filters & gradients
    const defs = document.createElementNS("http://www.w3.org/2000/svg", "defs");
    defs.innerHTML = `
        <filter id="glow-p1" x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur stdDeviation="4" result="coloredBlur"/>
            <feMerge><feMergeNode in="coloredBlur"/><feMergeNode in="SourceGraphic"/></feMerge>
        </filter>
        <filter id="glow-p2" x="-30%" y="-30%" width="160%" height="160%">
            <feGaussianBlur stdDeviation="4" result="coloredBlur"/>
            <feMerge><feMergeNode in="coloredBlur"/><feMergeNode in="SourceGraphic"/></feMerge>
        </filter>
        <linearGradient id="grad-p1" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" style="stop-color:#1d4ed8;stop-opacity:0.65"/>
            <stop offset="100%" style="stop-color:#3b82f6;stop-opacity:0.45"/>
        </linearGradient>
        <linearGradient id="grad-p2" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" style="stop-color:#b91c1c;stop-opacity:0.65"/>
            <stop offset="100%" style="stop-color:#ef4444;stop-opacity:0.45"/>
        </linearGradient>
    `;
    DOM.boardSvg.appendChild(defs);

    // Connections
    const linesGroup = document.createElementNS("http://www.w3.org/2000/svg", "g");
    linesGroup.setAttribute("class", "connections");
    gameLayer.appendChild(linesGroup);

    const tMap = {};
    territories.forEach(t => { tMap[t.id] = t; });

    const drawnPairs = new Set();
    territories.forEach(t => {
        const cx1 = t.x + CONSTANTS.CELL_W / 2;
        const cy1 = t.y + CONSTANTS.CELL_H / 2;
        t.neighbors.forEach(nId => {
            const pairKey = Math.min(t.id, nId) + "-" + Math.max(t.id, nId);
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

    territories.forEach(t => {
        const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
        g.setAttribute("data-id", t.id);
        g.setAttribute("class", `territory-group`);

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
        if (t.owner === 1) rect.setAttribute("fill", "url(#grad-p1)");
        else if (t.owner === 2) rect.setAttribute("fill", "url(#grad-p2)");
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
        ownerText.textContent = t.owner === 1 ? "P1" : t.owner === 2 ? "P2" : "-";
        ownerText.style.fill = t.owner === 1 ? "#60a5fa" : t.owner === 2 ? "#f87171" : "#64748b";
        ownerText.style.fontSize = "10px";
        ownerText.style.fontWeight = "600";
        g.appendChild(ownerText);

        cellsGroup.appendChild(g);
    });

    applySelectionHighlights();
}

// ---- Update Board Visuals (without re-rendering) ----
export function updateBoardVisuals() {
    if (!gameState.boardData || !gameState.boardData.territories) return;

    const tMap = {};
    gameState.boardData.territories.forEach(t => { tMap[t.id] = t; });

    document.querySelectorAll(".territory-group").forEach(g => {
        const id = parseInt(g.getAttribute("data-id"), 10);
        const t = tMap[id];
        if (!t) return;

        const rect = g.querySelector("rect");
        if (rect) {
            rect.classList.remove("owner-1", "owner-2", "owner-0", "owner-null");
            rect.classList.add(`owner-${t.owner || 0}`);
            if (t.owner === 1) rect.setAttribute("fill", "url(#grad-p1)");
            else if (t.owner === 2) rect.setAttribute("fill", "url(#grad-p2)");
            else rect.removeAttribute("fill");
        }

        const armyEl = g.querySelector(".territory-armies");
        if (armyEl) {
            armyEl.textContent = t.armies;
            armyEl.classList.remove("owner-1", "owner-2", "owner-0");
            armyEl.classList.add(`owner-${t.owner || 0}`);
        }

        const ownerEl = g.querySelector(".territory-owner-icon");
        if (ownerEl) {
            ownerEl.textContent = t.owner === 1 ? "P1" : t.owner === 2 ? "P2" : "-";
            ownerEl.style.fill = t.owner === 1 ? "#60a5fa" : t.owner === 2 ? "#f87171" : "#64748b";
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

