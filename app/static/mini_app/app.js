window.Telegram.WebApp.ready();
window.Telegram.WebApp.expand();

const audio = document.getElementById("audio");
const btnPlay = document.getElementById("btn-play");

btnPlay.addEventListener("click", () => {
    if (audio.paused) {
        audio.play();
        btnPlay.textContent = "⏸";
    } else {
        audio.pause();
        btnPlay.textContent = "▶";
    }
});

audio.addEventListener("ended", () => {
    btnPlay.textContent = "▶";
});

async function loadTrack(trackId) {
    const response = await fetch(`/api/v1/tracks/${trackId}/stream`);
    if (!response.ok) return;
    const data = await response.json();
    audio.src = data.url;
    document.getElementById("track-title").textContent = data.title;
    document.getElementById("track-artist").textContent = data.artist ?? "";
}
