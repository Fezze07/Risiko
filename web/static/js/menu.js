const btnPlay = document.getElementById("btn-mode-play");
const btnWatch = document.getElementById("btn-mode-watch");
const numPlayersInput = document.getElementById("num-players-input");

function clampPlayers(value) {
    const parsed = Number(value);
    if (!Number.isFinite(parsed)) return 2;
    return Math.max(2, Math.min(8, Math.round(parsed)));
}

function go(mode) {
    const totalPlayers = clampPlayers(numPlayersInput ? numPlayersInput.value : 2);
    const roles = Array.from({ length: totalPlayers }, (_, idx) =>
        mode === "WATCH" ? "AI" : idx === 0 ? "HUMAN" : "AI"
    );

    const params = new URLSearchParams();
    params.set("mode", mode);
    params.set("players", String(totalPlayers));
    params.set("types", roles.join(","));
    window.location.href = `/app?${params.toString()}`;
}

if (numPlayersInput) {
    numPlayersInput.addEventListener("input", () => {
        numPlayersInput.value = String(clampPlayers(numPlayersInput.value));
    });
}

if (btnPlay) btnPlay.addEventListener("click", () => go("PLAY"));
if (btnWatch) btnWatch.addEventListener("click", () => go("WATCH"));
