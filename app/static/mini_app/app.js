window.Telegram.WebApp.ready();
window.Telegram.WebApp.expand();

const audio = document.getElementById("audio");
const btnPlay = document.getElementById("btn-play");
const trackTitle = document.getElementById("track-title");
const trackArtist = document.getElementById("track-artist");

let currentTrackId = null;
let playCountSent = false;

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

audio.addEventListener("play", () => {
    if (currentTrackId && !playCountSent) {
        playCountSent = true;
        fetch(`/api/v1/tracks/${currentTrackId}/play`, {
            method: "POST",
        }).catch(() => {});
    }
});

async function loadTrack(trackId) {
    currentTrackId = trackId;
    playCountSent = false;

    const streamRes = await fetch(
        `/api/v1/tracks/${trackId}/stream`
    );
    if (!streamRes.ok) return;
    const streamData = await streamRes.json();
    audio.src = streamData.url;

    const trackRes = await fetch(`/api/v1/tracks/${trackId}`);
    if (trackRes.ok) {
        const track = await trackRes.json();
        trackTitle.textContent = track.title ?? "";
        trackArtist.textContent = track.artist ?? "";
    }

    await audio.play();
    btnPlay.textContent = "⏸";
}

function init() {
    const params = new URLSearchParams(window.location.search);
    const trackId = params.get("track_id");
    if (trackId) {
        loadTrack(Number(trackId));
    }
}

init();
