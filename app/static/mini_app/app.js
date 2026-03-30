/* ─── Telegram WebApp bootstrap ─────────────────────────── */
const tg = window.Telegram.WebApp;
tg.ready();
tg.expand();

/* ─── Auth state ─────────────────────────────────────────── */
let jwt = localStorage.getItem('dotsound_jwt') || null;
let currentUser = null; // { id: int, is_admin: bool }

/* ─── App state ──────────────────────────────────────────── */
const state = {
  get userId() { return currentUser?.id ?? null; },
  track: null,
  isPlaying: false,
  isLiked: false,
  playCountSent: false,
  likedIds: new Set(),
};

/* ─── DOM refs ───────────────────────────────────────────── */
const $ = (sel) => document.querySelector(sel);

const audioEl        = $('#audio');
const playerBar      = $('#player-bar');
const pbSeek         = $('#pb-seek');
const pbPlay         = $('#pb-play');
const pbLike         = $('#pb-like');
const pbReport       = $('#pb-report');
const pbTitle        = $('#pb-title');
const pbArtist       = $('#pb-artist');
const pbCover        = $('#pb-cover');
const pbCurrent      = $('#pb-current');
const pbDuration     = $('#pb-duration');
const complaintModal = $('#complaint-modal');

/* ─── Helpers ────────────────────────────────────────────── */
function fmt(sec) {
  if (!sec || isNaN(sec)) return '0:00';
  const m = Math.floor(sec / 60);
  const s = Math.floor(sec % 60).toString().padStart(2, '0');
  return `${m}:${s}`;
}

/* Parse JWT payload without validation (validation is server-side) */
function parseJwtPayload(token) {
  try {
    return JSON.parse(atob(token.split('.')[1]));
  } catch {
    return null;
  }
}

function isJwtExpired(token) {
  const payload = parseJwtPayload(token);
  if (!payload?.exp) return true;
  return payload.exp < Math.floor(Date.now() / 1000);
}

/* ─── API wrapper ────────────────────────────────────────── */
async function api(path, opts = {}) {
  opts.headers = opts.headers || {};
  if (jwt) {
    opts.headers['Authorization'] = `Bearer ${jwt}`;
  }
  const res = await fetch(path, opts);
  if (res.status === 401) {
    // Token rejected — clear it so next action triggers re-auth
    jwt = null;
    localStorage.removeItem('dotsound_jwt');
    currentUser = null;
  }
  if (!res.ok) throw new Error(`${res.status}`);
  if (res.status === 204) return null;
  return res.json();
}

/* ─── Authentication ─────────────────────────────────────── */
async function authenticate() {
  // Try existing JWT first
  if (jwt && !isJwtExpired(jwt)) {
    const payload = parseJwtPayload(jwt);
    if (payload) {
      currentUser = { id: parseInt(payload.sub, 10), is_admin: !!payload.admin };
      return;
    }
  }

  // Clear stale token
  jwt = null;
  localStorage.removeItem('dotsound_jwt');
  currentUser = null;

  const initData = tg.initData;
  if (!initData) return; // running outside Telegram

  try {
    const res = await fetch('/api/v1/auth/telegram', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ init_data: initData }),
    });
    if (!res.ok) return;
    const data = await res.json();
    jwt = data.access_token;
    localStorage.setItem('dotsound_jwt', jwt);
    currentUser = { id: data.user_id, is_admin: data.is_admin };
  } catch (e) {
    console.error('Auth failed', e);
  }
}

/* Show admin nav button if user is admin */
function applyAdminAccess() {
  if (currentUser?.is_admin) {
    $('#nav-admin').classList.remove('hidden');
  }
}

/* ─── Cover element builder ──────────────────────────────── */
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
      `/api/v1/likes/${state.track.id}`,
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
        `/api/v1/likes/${track.id}`,
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
const coverInput    = $('#cover-input');
const coverPreview  = $('#cover-preview');
const audioInput    = $('#audio-input');
const audioFileName = $('#audio-file-name');
const uploadForm    = $('#upload-form');
const uploadBtn     = $('#upload-btn');
const uploadError   = $('#upload-error');
const uploadProgress = $('#upload-progress');
const progressFill  = $('#progress-fill');

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

  if (!state.userId) {
    showUploadError('Необходима авторизация через Telegram');
    return;
  }

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
        : err.message === '401'
        ? 'Сессия истекла, обновите страницу'
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
  if (name === 'admin') loadAdminTab('tracks');
}

document.querySelectorAll('.nav-btn').forEach((btn) => {
  btn.addEventListener('click', () => switchView(btn.dataset.view));
});

/* ─── Load liked IDs ─────────────────────────────────────── */
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

/* ─── Complaint modal ────────────────────────────────────── */
pbReport.addEventListener('click', () => {
  if (!state.track) return;
  openComplaintModal(state.track.id);
});

$('#complaint-close').addEventListener('click', closeComplaintModal);

complaintModal.addEventListener('click', (e) => {
  if (e.target === complaintModal) closeComplaintModal();
});

function openComplaintModal(trackId) {
  $('#complaint-reason').value = '';
  $('#complaint-email').value = '';
  $('#complaint-error').classList.add('hidden');
  $('#complaint-submit').disabled = false;
  complaintModal.dataset.trackId = trackId;
  complaintModal.classList.remove('hidden');
}

function closeComplaintModal() {
  complaintModal.classList.add('hidden');
}

$('#complaint-submit').addEventListener('click', async () => {
  const trackId = parseInt(complaintModal.dataset.trackId, 10);
  const reason = $('#complaint-reason').value.trim();
  const email = $('#complaint-email').value.trim() || null;
  const errEl = $('#complaint-error');

  if (reason.length < 10) {
    errEl.textContent = 'Укажите причину (минимум 10 символов)';
    errEl.classList.remove('hidden');
    return;
  }
  if (!state.userId) {
    errEl.textContent = 'Необходима авторизация через Telegram';
    errEl.classList.remove('hidden');
    return;
  }

  $('#complaint-submit').disabled = true;
  errEl.classList.add('hidden');

  try {
    const res = await api('/api/v1/complaints', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        track_id: trackId,
        reason,
        contact_email: email,
      }),
    });
    closeComplaintModal();
    const msg = res.track_hidden
      ? '✅ Жалоба принята. Трек скрыт.'
      : '✅ Жалоба принята и будет рассмотрена.';
    tg.showAlert(msg);
    if (res.track_hidden && state.track?.id === trackId) {
      audioEl.pause();
      playerBar.classList.add('hidden');
    }
  } catch (e) {
    errEl.textContent = e.message === '409'
      ? 'Вы уже подавали жалобу на этот трек'
      : 'Ошибка отправки. Попробуйте позже.';
    errEl.classList.remove('hidden');
    $('#complaint-submit').disabled = false;
  }
});

/* ─── Confirm modal (generic) ────────────────────────────── */
function showConfirm(title, text, onConfirm) {
  $('#confirm-title').textContent = title;
  $('#confirm-text').textContent = text;
  $('#confirm-modal').classList.remove('hidden');

  const ok = $('#confirm-ok');
  const cancel = $('#confirm-cancel');
  const close = $('#confirm-close');

  function cleanup() {
    $('#confirm-modal').classList.add('hidden');
    ok.replaceWith(ok.cloneNode(true));
    cancel.replaceWith(cancel.cloneNode(true));
    close.replaceWith(close.cloneNode(true));
  }

  $('#confirm-ok').addEventListener('click', () => { cleanup(); onConfirm(); });
  $('#confirm-cancel').addEventListener('click', cleanup);
  $('#confirm-close').addEventListener('click', cleanup);
  $('#confirm-modal').addEventListener('click', (e) => {
    if (e.target === $('#confirm-modal')) cleanup();
  });
}

/* ═══════════════════════════════════════════════════════════
   ADMIN PANEL
   ═══════════════════════════════════════════════════════════ */

const adminState = {
  activeTab: 'tracks',
  tracks: { page: 1, total: 0 },
  users: { page: 1, total: 0 },
  complaints: { page: 1, total: 0 },
};

/* ── Tab switching ── */
document.querySelectorAll('.admin-tab').forEach((btn) => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.admin-tab').forEach((b) => b.classList.remove('active'));
    document.querySelectorAll('.admin-tab-content').forEach((c) => c.classList.add('hidden'));
    btn.classList.add('active');
    const tab = btn.dataset.tab;
    $(`#admin-tab-${tab}`).classList.remove('hidden');
    adminState.activeTab = tab;
    loadAdminTab(tab);
  });
});

function loadAdminTab(tab) {
  if (tab === 'tracks') loadAdminTracks();
  else if (tab === 'users') loadAdminUsers();
  else if (tab === 'complaints') loadAdminComplaints();
}

/* ── Admin tracks ── */
async function loadAdminTracks() {
  const list = $('#admin-tracks-list');
  list.innerHTML = '<div class="loader"></div>';
  try {
    const { page } = adminState.tracks;
    const data = await api(
      `/api/v1/admin/tracks?page=${page}&size=20`
    );
    adminState.tracks.total = data.total;
    renderAdminTracks(list, data.items);
    updatePagination('tracks', page, data.total, 20);
  } catch {
    list.innerHTML = '<p class="empty-hint">Ошибка загрузки.</p>';
  }
}

function renderAdminTracks(container, tracks) {
  container.innerHTML = '';
  if (!tracks.length) {
    container.innerHTML = '<p class="empty-hint">Треков нет.</p>';
    return;
  }
  tracks.forEach((track) => {
    const row = document.createElement('div');
    row.className = 'admin-row';

    const cover = coverEl(track.cover_key, 40);

    const info = document.createElement('div');
    info.className = 'admin-row-info';
    info.innerHTML = `
      <p class="admin-row-title">${escHtml(track.title)}</p>
      <p class="admin-row-sub">${escHtml(track.artist || '—')} · ID ${track.id}
        ${track.is_active ? '' : ' · <span class="badge-hidden">скрыт</span>'}
        ${track.source === 'soundcloud' ? ' · SC' : ''}
      </p>
    `;

    const actions = document.createElement('div');
    actions.className = 'admin-row-actions';

    const visBtn = document.createElement('button');
    visBtn.className = 'btn-sm';
    visBtn.textContent = track.is_active ? 'Скрыть' : 'Показать';
    visBtn.addEventListener('click', async () => {
      try {
        await api(
          `/api/v1/admin/tracks/${track.id}/visibility?is_active=${!track.is_active}`,
          { method: 'PATCH' }
        );
        loadAdminTracks();
      } catch (e) {
        tg.showAlert('Ошибка: ' + e.message);
      }
    });

    const delBtn = document.createElement('button');
    delBtn.className = 'btn-sm btn-danger';
    delBtn.textContent = '🗑';
    delBtn.addEventListener('click', () => {
      showConfirm(
        'Удалить трек',
        `Удалить «${track.title}»? Это действие необратимо.`,
        async () => {
          try {
            await api(`/api/v1/admin/tracks/${track.id}`, { method: 'DELETE' });
            loadAdminTracks();
          } catch (e) {
            tg.showAlert('Ошибка: ' + e.message);
          }
        }
      );
    });

    actions.append(visBtn, delBtn);
    row.append(cover, info, actions);
    container.appendChild(row);
  });
}

$('#admin-tracks-prev').addEventListener('click', () => {
  if (adminState.tracks.page > 1) {
    adminState.tracks.page--;
    loadAdminTracks();
  }
});
$('#admin-tracks-next').addEventListener('click', () => {
  const { page, total } = adminState.tracks;
  if (page * 20 < total) {
    adminState.tracks.page++;
    loadAdminTracks();
  }
});

/* ── Admin users ── */
async function loadAdminUsers() {
  const list = $('#admin-users-list');
  list.innerHTML = '<div class="loader"></div>';
  try {
    const { page } = adminState.users;
    const data = await api(`/api/v1/admin/users?page=${page}&size=20`);
    adminState.users.total = data.total;
    renderAdminUsers(list, data.items);
    updatePagination('users', page, data.total, 20);
  } catch {
    list.innerHTML = '<p class="empty-hint">Ошибка загрузки.</p>';
  }
}

function renderAdminUsers(container, users) {
  container.innerHTML = '';
  if (!users.length) {
    container.innerHTML = '<p class="empty-hint">Пользователей нет.</p>';
    return;
  }
  users.forEach((user) => {
    const row = document.createElement('div');
    row.className = 'admin-row';

    const info = document.createElement('div');
    info.className = 'admin-row-info';
    const name = user.display_name || user.first_name || `#${user.id}`;
    info.innerHTML = `
      <p class="admin-row-title">${escHtml(name)}
        ${user.is_admin ? ' <span class="badge-admin">admin</span>' : ''}
        ${!user.is_active ? ' <span class="badge-hidden">заблокирован</span>' : ''}
      </p>
      <p class="admin-row-sub">@${escHtml(user.username || '—')} · tg_id ${user.telegram_id}</p>
    `;

    const actions = document.createElement('div');
    actions.className = 'admin-row-actions';

    const blockBtn = document.createElement('button');
    blockBtn.className = 'btn-sm';
    blockBtn.textContent = user.is_active ? 'Блок' : 'Разблок';
    blockBtn.addEventListener('click', () => {
      const action = user.is_active ? 'заблокировать' : 'разблокировать';
      showConfirm(
        'Изменить статус',
        `${action} пользователя ${name}?`,
        async () => {
          try {
            await api(`/api/v1/admin/users/${user.id}`, {
              method: 'PATCH',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ is_active: !user.is_active }),
            });
            loadAdminUsers();
          } catch (e) {
            tg.showAlert('Ошибка: ' + e.message);
          }
        }
      );
    });

    const adminBtn = document.createElement('button');
    adminBtn.className = 'btn-sm';
    adminBtn.textContent = user.is_admin ? '−Admin' : '+Admin';
    // Prevent removing own admin rights
    if (user.id === currentUser?.id) {
      adminBtn.disabled = true;
      adminBtn.title = 'Нельзя изменить себе';
    }
    adminBtn.addEventListener('click', () => {
      const action = user.is_admin ? 'снять права администратора у' : 'назначить администратором';
      showConfirm(
        'Изменить права',
        `${action} ${name}?`,
        async () => {
          try {
            await api(`/api/v1/admin/users/${user.id}`, {
              method: 'PATCH',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ is_admin: !user.is_admin }),
            });
            loadAdminUsers();
          } catch (e) {
            tg.showAlert('Ошибка: ' + e.message);
          }
        }
      );
    });

    actions.append(blockBtn, adminBtn);
    row.append(info, actions);
    container.appendChild(row);
  });
}

$('#admin-users-prev').addEventListener('click', () => {
  if (adminState.users.page > 1) {
    adminState.users.page--;
    loadAdminUsers();
  }
});
$('#admin-users-next').addEventListener('click', () => {
  const { page, total } = adminState.users;
  if (page * 20 < total) {
    adminState.users.page++;
    loadAdminUsers();
  }
});

/* ── Admin complaints ── */
$('#admin-complaints-unresolved').addEventListener('change', () => {
  adminState.complaints.page = 1;
  loadAdminComplaints();
});

async function loadAdminComplaints() {
  const list = $('#admin-complaints-list');
  list.innerHTML = '<div class="loader"></div>';
  try {
    const { page } = adminState.complaints;
    const unresolved = $('#admin-complaints-unresolved').checked;
    const data = await api(
      `/api/v1/admin/complaints?page=${page}&size=20&unresolved_only=${unresolved}`
    );
    adminState.complaints.total = data.total;
    renderAdminComplaints(list, data.items);
    updatePagination('complaints', page, data.total, 20);
  } catch {
    list.innerHTML = '<p class="empty-hint">Ошибка загрузки.</p>';
  }
}

function renderAdminComplaints(container, complaints) {
  container.innerHTML = '';
  if (!complaints.length) {
    container.innerHTML = '<p class="empty-hint">Жалоб нет.</p>';
    return;
  }
  complaints.forEach((c) => {
    const row = document.createElement('div');
    row.className = 'admin-row admin-row--complaint';

    const info = document.createElement('div');
    info.className = 'admin-row-info';
    const date = new Date(c.created_at).toLocaleDateString('ru');
    info.innerHTML = `
      <p class="admin-row-title">Трек #${c.track_id}
        ${c.is_resolved ? '<span class="badge-ok">решено</span>' : ''}
      </p>
      <p class="admin-row-sub">${escHtml(c.reason.slice(0, 80))}… · ${date}</p>
      ${c.contact_email ? `<p class="admin-row-sub">${escHtml(c.contact_email)}</p>` : ''}
    `;

    const actions = document.createElement('div');
    actions.className = 'admin-row-actions';

    if (!c.is_resolved) {
      const resolveBtn = document.createElement('button');
      resolveBtn.className = 'btn-sm';
      resolveBtn.textContent = '✓ Решено';
      resolveBtn.addEventListener('click', async () => {
        try {
          await api(
            `/api/v1/admin/complaints/${c.id}/resolve`,
            { method: 'PATCH' }
          );
          loadAdminComplaints();
        } catch (e) {
          tg.showAlert('Ошибка: ' + e.message);
        }
      });
      actions.appendChild(resolveBtn);
    }

    const delBtn = document.createElement('button');
    delBtn.className = 'btn-sm btn-danger';
    delBtn.textContent = '🗑';
    delBtn.addEventListener('click', () => {
      showConfirm(
        'Удалить жалобу',
        `Удалить жалобу #${c.id} на трек #${c.track_id}?`,
        async () => {
          try {
            await api(`/api/v1/admin/complaints/${c.id}`, { method: 'DELETE' });
            loadAdminComplaints();
          } catch (e) {
            tg.showAlert('Ошибка: ' + e.message);
          }
        }
      );
    });

    actions.appendChild(delBtn);
    row.append(info, actions);
    container.appendChild(row);
  });
}

$('#admin-complaints-prev').addEventListener('click', () => {
  if (adminState.complaints.page > 1) {
    adminState.complaints.page--;
    loadAdminComplaints();
  }
});
$('#admin-complaints-next').addEventListener('click', () => {
  const { page, total } = adminState.complaints;
  if (page * 20 < total) {
    adminState.complaints.page++;
    loadAdminComplaints();
  }
});

/* ── Pagination helper ── */
function updatePagination(tab, page, total, size) {
  $(`#admin-${tab}-page`).textContent = page;
  $(`#admin-${tab}-prev`).disabled = page <= 1;
  $(`#admin-${tab}-next`).disabled = page * size >= total;
}

/* ── XSS escape ── */
function escHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

/* ─── Init ───────────────────────────────────────────────── */
async function init() {
  await authenticate();
  applyAdminAccess();
  await preloadLikedIds();
  await loadHome();
  await handleDeepLink();
}

init();
