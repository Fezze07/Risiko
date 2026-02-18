const btnPlay = document.getElementById("btn-mode-play");
const btnWatch = document.getElementById("btn-mode-watch");

function go(mode) {
    const target = `/app?mode=${encodeURIComponent(mode)}`;
    window.location.href = target;
}

if (btnPlay) btnPlay.addEventListener("click", () => go("PLAY"));
if (btnWatch) btnWatch.addEventListener("click", () => go("WATCH"));
