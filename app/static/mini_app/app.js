/* ─── Telegram WebApp bootstrap ─────────────────────────── */
const tg = window.Telegram.WebApp;
tg.ready();
tg.expand();

/* ─── State ──────────────────────────────────────────────── */
const state = {
  userId: tg.initDataUnsafe?.user?.id ?? null,
  track: null,       // currently loaded track object
  isPlaying: false,
  isLiked: false,
  playCountSent: false,
  likedIds: new Set(),
};

/* ─── DOM refs ───────────────────────────────────────────── */
const $ = (sel) => document.querySelector(sel);

const audioEl     = $('#audio');
const playerBar   = $('#player-bar');
const pbSeek      = $('#pb-seek');
const pbPlay      = $('#pb-play');
const pbLike      = $('#pb-like');
const pbTitle     = $('#pb-title');
const pbArtist    = $('#pb-artist');
const pbCover     = $('#pb-cover');
const pbCurrent   = $('#pb-current');
const pbDuration  = $('#pb-duration');

/* ─── Helpers ────────────────────────────────────────────── */
function fmt(sec) {
  if (!sec || isNaN(sec)) return '0:00';
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60).toString().padStart(2, '0');
  return `${m}:${s}`;
}

async function api(path, opts = {}) {
  const res = await fetch(path, opts);
  if (!res.ok) throw new Error(`${res.status}`);
  if (res.status === 204) return null;
  return res.json();
}

function coverEl(coverKey, size = 50) {
  const wrap = document.createElement('div');
  wrap.className = 'track-card-cover';
  wrap.style.width = size + 'px';
  wrap.style.height = size + 'px';
  if (coverKey) {
    const img = document.createElement('img');
    img.src = `/api/v1/tracks/cover_proxy?key=${encodeURIComponent(coverKey)}`;
    img.alt = '';
    img.onerror = () => { wrap.textContent = '🎵'; };
    wrap.appendChild(img);
  } else {
    wrap.textContent = '🎵';
  }
  return wrap;
}

/* ─── Player ─────────────────────────────────────────────── */
async function playTrack(track) {
  try {
    const { url } = await api(`/api/v1/tracks/${track.id}/stream`);
    audioEl.src = url;
    state.track = track;
    state.isPlaying = false;
    state.playCountSent = false;
    state.isLiked = state.likedIds.has(track.id);

    await audioEl.play();
    state.isPlaying = true;
    updatePlayerBar();
    playerBar.classList.remove('hidden');
    markPlayingCard(track.id);
  } catch (e) {
    console.error('playTrack error', e);
  }
}

function updatePlayerBar() {
  const t = state.track;
  if (!t) return;

  pbTitle.textContent = t.title;
  pbArtist.textContent = t.artist || '—';
  pbPlay.textContent = state.isPlaying ? '⏸' : '▶';
  pbLike.textContent = state.isLiked ? '❤️' : '🤍';

  if (t.cover_key) {
    const img = document.createElement('img');
    img.src = `/api/v1/tracks/cover_proxy?key=${encodeURIComponent(t.cover_key)}`;
    img.alt = '';
    img.onerror = () => { pbCover.textContent = '🎵'; };
    pbCover.innerHTML = '';
    pbCover.appendChild(img);
  } else {
    pbCover.innerHTML = '🎵';
  }
}

function markPlayingCard(trackId) {
  document.querySelectorAll('.track-card').forEach((c) => {
    c.classList.toggle('playing', +c.dataset.id === trackId);
  });
}

/* ─── Audio events ───────────────────────────────────────── */
audioEl.addEventListener('play', () => {
  state.isPlaying = true;
  pbPlay.textContent = '⏸';
  if (!state.playCountSent && state.track) {
    state.playCountSent = true;
    api(`/api/v1/tracks/${state.track.id}/play`, { method: 'POST' })
      .catch(() => {});
  }
});

audioEl.addEventListener('pause', () => {
  state.isPlaying = false;
  pbPlay.textContent = '▶';
});

audioEl.addEventListener('ended', () => {
  state.isPlaying = false;
  pbPlay.textContent = '▶';
  pbSeek.value = 0;
});

audioEl.addEventListener('timeupdate', () => {
  if (!audioEl.duration) return;
  pbSeek.value = (audioEl.currentTime / audioEl.duration) * 100;
  pbCurrent.textContent = fmt(audioEl.currentTime);
});

audioEl.addEventListener('durationchange', () => {
  pbDuration.textContent = fmt(audioEl.duration);
});

pbPlay.addEventListener('click', () => {
  if (!state.track) return;
  if (audioEl.paused) {
    audioEl.play();
  } else {
    audioEl.pause();
  }
});

pbSeek.addEventListener('input', () => {
  if (!audioEl.duration) return;
  audioEl.currentTime = (pbSeek.value / 100) * audioEl.duration;
});

pbLike.addEventListener('click', async () => {
  if (!state.track || !state.userId) return;
  try {
    const { liked } = await api(
      `/api/v1/likes/${state.userId}/${state.track.id}`,
      { method: 'POST' }
    );
    state.isLiked = liked;
    if (liked) {
      state.likedIds.add(state.track.id);
    } else {
      state.likedIds.delete(state.track.id);
    }
    pbLike.textContent = liked ? '❤️' : '🤍';
    updateLikeButtonsInList(state.track.id, liked);
  } catch (e) {
    console.error('like error', e);
  }
});

function updateLikeButtonsInList(trackId, liked) {
  document
    .querySelectorAll(`.track-card[data-id="${trackId}"] .track-card-like`)
    .forEach((btn) => { btn.textContent = liked ? '❤️' : '🤍'; });
}

/* ─── Track card builder ─────────────────────────────────── */
function buildTrackCard(track) {
  const card = document.createElement('div');
  card.className = 'track-card';
  card.dataset.id = track.id;

  const cover = coverEl(track.cover_key);
  const info = document.createElement('div');
  info.className = 'track-card-info';

  const title = document.createElement('p');
  title.className = 'track-card-title';
  title.textContent = track.title;

  const artist = document.createElement('p');
  artist.className = 'track-card-artist';
  artist.textContent = track.artist || 'Неизвестный исполнитель';

  const meta = document.createElement('p');
  meta.className = 'track-card-meta';
  meta.textContent = `▶ ${track.play_count}`;

  info.append(title, artist, meta);

  const likeBtn = document.createElement('button');
  likeBtn.className = 'track-card-like';
  likeBtn.title = 'Лайк';
  likeBtn.textContent = state.likedIds.has(track.id) ? '❤️' : '🤍';

  likeBtn.addEventListener('click', async (e) => {
    e.stopPropagation();
    if (!state.userId) return;
    try {
      const { liked } = await api(
        `/api/v1/likes/${state.userId}/${track.id}`,
        { method: 'POST' }
      );
      likeBtn.textContent = liked ? '❤️' : '🤍';
      if (liked) {
        state.likedIds.add(track.id);
      } else {
        state.likedIds.delete(track.id);
      }
      if (state.track?.id === track.id) {
        state.isLiked = liked;
        pbLike.textContent = liked ? '❤️' : '🤍';
      }
    } catch (e) {
      console.error('like error', e);
    }
  });

  card.append(cover, info, likeBtn);
  card.addEventListener('click', () => playTrack(track));

  if (state.track?.id === track.id) card.classList.add('playing');
  return card;
}

function renderTrackList(container, tracks, emptyMsg) {
  container.innerHTML = '';
  if (!tracks.length) {
    const p = document.createElement('p');
    p.className = 'empty-hint';
    p.textContent = emptyMsg;
    container.appendChild(p);
    return;
  }
  tracks.forEach((t) => container.appendChild(buildTrackCard(t)));
}

/* ─── Home view ──────────────────────────────────────────── */
async function loadHome() {
  const list = $('#home-list');
  list.innerHTML = '<div class="loader"></div>';
  try {
    const data = await api('/api/v1/tracks?size=50');
    renderTrackList(list, data.items, 'Треков пока нет. Загрузи первый!');
  } catch {
    list.innerHTML = '<p class="empty-hint">Ошибка загрузки. Попробуй позже.</p>';
  }
}

/* ─── Search view ────────────────────────────────────────── */
let searchTimer = null;

$('#search-input').addEventListener('input', (e) => {
  const q = e.target.value.trim();
  $('#search-clear').classList.toggle('hidden', !q);
  clearTimeout(searchTimer);
  if (!q) {
    $('#search-list').innerHTML =
      '<p class="empty-hint" id="search-hint">Начните вводить название</p>';
    return;
  }
  searchTimer = setTimeout(() => runSearch(q), 350);
});

$('#search-clear').addEventListener('click', () => {
  $('#search-input').value = '';
  $('#search-clear').classList.add('hidden');
  $('#search-list').innerHTML =
    '<p class="empty-hint" id="search-hint">Начните вводить название</p>';
});

async function runSearch(q) {
  const list = $('#search-list');
  list.innerHTML = '<div class="loader"></div>';
  try {
    const data = await api(`/api/v1/tracks?q=${encodeURIComponent(q)}&size=30`);
    renderTrackList(list, data.items, 'Ничего не найдено');
  } catch {
    list.innerHTML = '<p class="empty-hint">Ошибка поиска.</p>';
  }
}

/* ─── Liked view ─────────────────────────────────────────── */
async function loadLiked() {
  if (!state.userId) {
    $('#liked-list').innerHTML =
      '<p class="empty-hint">Войди через Telegram, чтобы видеть лайки.</p>';
    return;
  }
  const list = $('#liked-list');
  list.innerHTML = '<div class="loader"></div>';
  try {
    const data = await api(`/api/v1/likes/${state.userId}`);
    renderTrackList(list, data.items, 'Ты ещё ничего не лайкал');
  } catch {
    list.innerHTML = '<p class="empty-hint">Ошибка загрузки лайков.</p>';
  }
}

/* ─── Upload view ────────────────────────────────────────── */
const coverInput = $('#cover-input');
const coverPreview = $('#cover-preview');
const audioInput = $('#audio-input');
const audioFileName = $('#audio-file-name');
const uploadForm = $('#upload-form');
const uploadBtn = $('#upload-btn');
const uploadError = $('#upload-error');
const uploadProgress = $('#upload-progress');
const progressFill = $('#progress-fill');

coverInput.addEventListener('change', () => {
  const file = coverInput.files?.[0];
  if (!file) return;
  const reader = new FileReader();
  reader.onload = (e) => {
    coverPreview.innerHTML = `<img src="${e.target.result}" alt="cover" />`;
  };
  reader.readAsDataURL(file);
});

audioInput.addEventListener('change', () => {
  const file = audioInput.files?.[0];
  audioFileName.textContent = file ? file.name : 'Файл не выбран';
});

uploadForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  uploadError.classList.add('hidden');

  const title = $('#title-input').value.trim();
  const artist = $('#artist-input').value.trim();
  const audioFile = audioInput.files?.[0];
  const coverFile = coverInput.files?.[0];

  if (!title) {
    showUploadError('Введите название трека');
    return;
  }
  if (!audioFile) {
    showUploadError('Выберите аудиофайл');
    return;
  }

  uploadBtn.disabled = true;
  uploadProgress.classList.remove('hidden');
  animateProgress();

  try {
    const fd = new FormData();
    fd.append('file', audioFile);
    fd.append('title', title);
    if (artist) fd.append('artist', artist);
    if (coverFile) fd.append('cover', coverFile);
    if (state.userId) fd.append('uploader_id', state.userId);

    const track = await api('/api/v1/tracks/upload', {
      method: 'POST',
      body: fd,
    });

    progressFill.style.width = '100%';
    setTimeout(() => {
      uploadProgress.classList.add('hidden');
      progressFill.style.width = '0%';
      uploadBtn.disabled = false;
      resetUploadForm();
      switchView('home');
      loadHome();
      playTrack(track);
    }, 600);
  } catch (err) {
    uploadProgress.classList.add('hidden');
    progressFill.style.width = '0%';
    uploadBtn.disabled = false;
    showUploadError(
      err.message === '415'
        ? 'Формат файла не поддерживается'
        : err.message === '413'
        ? 'Файл слишком большой (макс. 50 МБ)'
        : 'Ошибка загрузки. Попробуй ещё раз.'
    );
  }
});

function showUploadError(msg) {
  uploadError.textContent = msg;
  uploadError.classList.remove('hidden');
}

function animateProgress() {
  let w = 0;
  const timer = setInterval(() => {
    w = Math.min(w + Math.random() * 12, 85);
    progressFill.style.width = w + '%';
    if (w >= 85) clearInterval(timer);
  }, 300);
}

function resetUploadForm() {
  uploadForm.reset();
  coverPreview.innerHTML = '<span class="cover-placeholder">🎵</span>';
  audioFileName.textContent = 'Файл не выбран';
  uploadError.classList.add('hidden');
}

/* ─── Navigation ─────────────────────────────────────────── */
function switchView(name) {
  document.querySelectorAll('.view').forEach((v) => v.classList.remove('active'));
  document.querySelectorAll('.nav-btn').forEach((b) => b.classList.remove('active'));
  $(`#view-${name}`)?.classList.add('active');
  $(`[data-view="${name}"]`)?.classList.add('active');

  if (name === 'home') loadHome();
  if (name === 'liked') loadLiked();
  if (name === 'search') $('#search-input').focus();
}

document.querySelectorAll('.nav-btn').forEach((btn) => {
  btn.addEventListener('click', () => switchView(btn.dataset.view));
});

/* ─── Load liked IDs for like button state ───────────────── */
async function preloadLikedIds() {
  if (!state.userId) return;
  try {
    const data = await api(`/api/v1/likes/${state.userId}?size=200`);
    data.items.forEach((t) => state.likedIds.add(t.id));
  } catch { /* non-critical */ }
}

/* ─── Deep link: ?track_id= ─────────────────────────────── */
async function handleDeepLink() {
  const params = new URLSearchParams(window.location.search);
  const trackId = params.get('track_id');
  if (!trackId) return;
  try {
    const track = await api(`/api/v1/tracks/${trackId}`);
    playTrack(track);
  } catch { /* ignore */ }
}

/* ─── Init ───────────────────────────────────────────────── */
async function init() {
  await preloadLikedIds();
  await loadHome();
  await handleDeepLink();
}

init();
