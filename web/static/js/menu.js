const btnPlay = document.getElementById("btn-mode-play");
const btnWatch = document.getElementById("btn-mode-watch");
const numPlayersInput = document.getElementById("num-players-input");
const playerTypesList = document.getElementById("player-types-list");

// Genera colori dinamici basati sull'ID del player
function getPlayerColor(playerID, totalPlayers) {
    const hue = (playerID * (360 / totalPlayers));
    return `hsl(${hue}, 70%, 50%)`;
}

function clampPlayers(value) {
    const parsed = Number(value);
    if (!Number.isFinite(parsed)) return 2;
    return Math.max(2, Math.min(8, Math.round(parsed)));
}

function buildDefaultRoles(totalPlayers) {
    const roles = [];
    for (let p = 1; p <= totalPlayers; p += 1) {
        roles.push(p === 1 ? "HUMAN" : "AI");
    }
    return roles;
}

function readRolesFromDOM(totalPlayers) {
    const roles = buildDefaultRoles(totalPlayers);
    const rows = playerTypesList ? playerTypesList.querySelectorAll(".player-type-row") : [];
    rows.forEach((row) => {
        const id = Number(row.dataset.playerId);
        const toggle = row.querySelector("input[type='checkbox']");
        if (!Number.isFinite(id) || id < 1 || id > totalPlayers || !toggle) return;
        roles[id - 1] = toggle.checked ? "HUMAN" : "AI";
    });
    return roles;
}

function renderPlayerTypes() {
    if (!playerTypesList || !numPlayersInput) return;
    const totalPlayers = clampPlayers(numPlayersInput.value);
    const previous = readRolesFromDOM(totalPlayers);

    playerTypesList.innerHTML = "";
    for (let p = 1; p <= totalPlayers; p += 1) {
        const row = document.createElement("div");
        row.className = "player-type-row";
        row.dataset.playerId = String(p);

        const swatch = document.createElement("span");
        swatch.className = "player-swatch";
        swatch.style.background = getPlayerColor(p, totalPlayers);

        const label = document.createElement("span");
        label.className = "player-type-label";
        label.textContent = `Player ${p}`;

        const toggleWrap = document.createElement("label");
        toggleWrap.className = "player-type-toggle";
        const toggle = document.createElement("input");
        toggle.type = "checkbox";
        toggle.checked = previous[p - 1] === "HUMAN";
        const toggleText = document.createElement("span");
        toggleText.textContent = toggle.checked ? "Human" : "AI";
        toggle.addEventListener("change", () => {
            toggleText.textContent = toggle.checked ? "Human" : "AI";
        });
        toggleWrap.appendChild(toggle);
        toggleWrap.appendChild(toggleText);

        row.appendChild(swatch);
        row.appendChild(label);
        row.appendChild(toggleWrap);
        playerTypesList.appendChild(row);
    }
}

function go(mode) {
    const totalPlayers = clampPlayers(numPlayersInput ? numPlayersInput.value : 2);
    const roles = readRolesFromDOM(totalPlayers);
    const normalizedRoles = mode === "WATCH" ? roles.map(() => "AI") : roles;

    if (mode === "PLAY" && !normalizedRoles.includes("HUMAN")) {
        normalizedRoles[0] = "HUMAN";
    }

    const params = new URLSearchParams();
    params.set("mode", mode);
    params.set("players", String(totalPlayers));
    params.set("types", normalizedRoles.join(","));
    window.location.href = `/app?${params.toString()}`;
}

if (numPlayersInput) {
    numPlayersInput.addEventListener("input", () => {
        numPlayersInput.value = String(clampPlayers(numPlayersInput.value));
        renderPlayerTypes();
    });
}

if (btnPlay) btnPlay.addEventListener("click", () => go("PLAY"));
if (btnWatch) btnWatch.addEventListener("click", () => go("WATCH"));

renderPlayerTypes();
