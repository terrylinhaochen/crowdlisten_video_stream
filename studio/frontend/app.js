// CrowdListen Studio — app.js

const S = {
  activeTab: 'intake',
  videoType: 'meme',
  selectedClip: null,
  clips: [],
  filters: { source: 'all', minScore: 7 },
  ttsAudio: null,
  queueJobs: [],
  reviewVideos: [],
  published: { videos: [], today_count: 0, daily_target: 2 },
  activeTasks: {},   // job_id → { name, steps, pct }
  intakeHistory: [], // { filename, status, job_id }
  currentReviewFile: null,
};

// ── Utils ─────────────────────────────────────────────────────────────────

const $ = id => document.getElementById(id);
const esc = s => String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');

function relTime(iso) {
  const d = (Date.now() - new Date(iso)) / 1000;
  if (d < 60) return 'just now';
  if (d < 3600) return `${Math.floor(d/60)}m ago`;
  if (d < 86400) return `${Math.floor(d/3600)}h ago`;
  return `${Math.floor(d/86400)}d ago`;
}

function slugify(t) {
  return t.toLowerCase().replace(/[^a-z0-9]+/g,'_').replace(/^_+|_+$/g,'').slice(0,40);
}

function scoreClass(s) {
  return s >= 9 ? 'score-high' : s >= 7 ? 'score-mid' : 'score-low';
}

function wordCount(t) { return t.trim().split(/\s+/).filter(Boolean).length; }
function estSecs(t)   { return Math.ceil(wordCount(t) / 2.5); }

async function api(path, opts={}) {
  const r = await fetch(path, { headers:{'Content-Type':'application/json'}, ...opts });
  if (!r.ok) { const e = await r.json().catch(()=>({detail:r.statusText})); throw new Error(e.detail||r.statusText); }
  return r.json();
}

function toast(msg, type='success') {
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.innerHTML = `<span>${type==='success'?'✓':type==='error'?'✕':'ℹ'}</span><span>${msg}</span>`;
  $('toast-container').appendChild(el);
  setTimeout(()=>el.remove(), 3500);
}

// ── Tabs ──────────────────────────────────────────────────────────────────

function switchTab(name) {
  document.querySelectorAll('.tab').forEach(t=>t.classList.toggle('active', t.dataset.tab===name));
  document.querySelectorAll('.tab-page').forEach(p=>p.classList.toggle('active', p.id===`tab-${name}`));
  S.activeTab = name;
  if (name==='library') fetchClips();
  if (name==='review')  fetchReview();
  if (name==='published') fetchPublished();
}

document.querySelectorAll('.tab').forEach(t=>t.addEventListener('click',()=>switchTab(t.dataset.tab)));

// ── SSE ───────────────────────────────────────────────────────────────────

function connectSSE() {
  const es = new EventSource('/api/events');
  es.addEventListener('progress', e => {
    const d = JSON.parse(e.data);
    handleProgress(d);
  });
  es.addEventListener('status', e => {
    const d = JSON.parse(e.data);
    handleStatusEvent(d);
  });
  es.addEventListener('intake', e => {
    const d = JSON.parse(e.data);
    handleIntakeEvent(d);
  });
  es.onerror = () => setTimeout(connectSSE, 3000);
}

const STEPS = {
  meme:       ['render'],
  narration:  ['hook','tts','body','cta','assemble'],
  cta_only:   ['cta'],
};

function handleProgress(d) {
  const { job_id, step, pct } = d;
  if (!S.activeTasks[job_id]) {
    const job = S.queueJobs.find(j=>j.id===job_id);
    const name = job ? job.output_name : job_id.slice(0,8);
    const mode = job ? (job.mode||'narration') : 'narration';
    S.activeTasks[job_id] = { name, mode, steps: {}, pct: 0 };
  }
  S.activeTasks[job_id].steps[step] = pct;
  S.activeTasks[job_id].pct = pct;
  renderTasks();
}

function handleStatusEvent(d) {
  const { job_id, status } = d;
  if (status === 'review') {
    delete S.activeTasks[job_id];
    toast(`Video ready for review: ${d.output_file?.split('/').pop()||job_id}`, 'success');
    fetchQueue();
    fetchReview();
    updateReviewBadge();
  } else if (status === 'failed') {
    delete S.activeTasks[job_id];
    toast(`Render failed: ${d.error||'unknown error'}`, 'error');
    fetchQueue();
  }
  renderTasks();
}

function handleIntakeEvent(d) {
  const idx = S.intakeHistory.findIndex(i=>i.job_id===d.job_id);
  if (idx >= 0) {
    S.intakeHistory[idx].status = d.status;
  }
  renderIntakeHistory();
  if (d.status === 'done') {
    toast(`Analysis complete: ${d.filename}`, 'success');
    fetchClips();
  }
}

// ── INTAKE ────────────────────────────────────────────────────────────────

const dropZone = $('drop-zone');
dropZone.addEventListener('dragover', e=>{ e.preventDefault(); dropZone.classList.add('dragging'); });
dropZone.addEventListener('dragleave', ()=>dropZone.classList.remove('dragging'));
dropZone.addEventListener('drop', e=>{ e.preventDefault(); dropZone.classList.remove('dragging'); uploadFile(e.dataTransfer.files[0]); });

function handleFileSelect(input) {
  if (input.files[0]) uploadFile(input.files[0]);
}

async function uploadFile(file) {
  if (!file || !file.type.startsWith('video/')) { toast('Please upload a video file', 'error'); return; }
  const fd = new FormData();
  fd.append('file', file);
  const item = { filename: file.name, status: 'analyzing', job_id: null };
  S.intakeHistory.unshift(item);
  renderIntakeHistory();
  try {
    const r = await fetch('/api/intake', { method:'POST', body: fd });
    const data = await r.json();
    item.job_id = data.job_id;
    item.status = 'analyzing';
    toast(`Uploaded ${file.name} — analyzing…`, 'info');
  } catch(e) {
    item.status = 'failed';
    toast(`Upload failed: ${e.message}`, 'error');
  }
  renderIntakeHistory();
}

function renderIntakeHistory() {
  const el = $('intake-history');
  if (!S.intakeHistory.length) { el.innerHTML=''; return; }
  el.innerHTML = S.intakeHistory.map(i=>`
    <div class="intake-item">
      <span class="intake-name" title="${esc(i.filename)}">${esc(i.filename)}</span>
      <span class="intake-status ${i.status}">${
        i.status==='analyzing' ? '⟳ Analyzing…' :
        i.status==='done'      ? '✓ Done — clips added' :
                                 '✕ Failed'
      }</span>
    </div>`).join('');
}

// ── LIBRARY ───────────────────────────────────────────────────────────────

async function fetchClips() {
  const p = new URLSearchParams({ min_score: S.filters.minScore });
  if (S.filters.source !== 'all') p.set('source', S.filters.source);
  try {
    S.clips = await api(`/api/clips?${p}`);
    renderClipGrid();
  } catch(e) { $('clip-grid').innerHTML = `<div class="empty-state" style="color:var(--red)">Failed: ${e.message}</div>`; }
}

function renderClipGrid() {
  const el = $('clip-grid');
  if (!S.clips.length) { el.innerHTML='<div class="empty-state">No clips match filters</div>'; return; }
  el.innerHTML = S.clips.map(c => {
    const sel = S.selectedClip?.clip_id === c.clip_id ? ' selected' : '';
    return `
      <div class="clip-card${sel}" onclick="selectClip('${c.clip_id}')">
        <div class="clip-thumb-placeholder" onclick="event.stopPropagation(); openModal('/api/clips/${c.clip_id}/preview', false)" title="▶ Preview">
        <span style="font-size:32px">${c.source_slug==='office'?'🏢':'💻'}</span>
        <span class="thumb-play">▶</span>
      </div>
        <div class="clip-card-body">
          <div class="clip-card-top">
            <span class="score-badge ${scoreClass(c.meme_score)}">${c.meme_score}/10</span>
            <span class="source-tag">${esc(c.source_label)}</span>
            <span class="clip-ts">${c.timestamp}</span>
          </div>
          <div class="clip-caption">${esc(c.meme_caption)}</div>
          <div class="clip-visual">${esc(c.what_happens_visually)}</div>
          <div class="clip-card-foot">
            <span class="audience-tag">${esc(c.audience)}</span>
            <span class="rendered-dot ${c.rendered?'yes':'no'}" title="${c.rendered?'Rendered':'Not rendered'}"></span>
          </div>
        </div>
      </div>`;
  }).join('');
}

function selectClip(clipId) {
  S.selectedClip = S.clips.find(c=>c.clip_id===clipId)||null;
  if (!S.selectedClip) return;
  renderClipGrid(); // update selected state
  updateSelectedClipCard();
  // Pre-fill captions
  $('meme-caption').value = S.selectedClip.meme_caption || '';
  if ($('narr-caption')) $('narr-caption').value = S.selectedClip.meme_caption || '';
  // Auto-fill output name
  $('output-name').value = slugify(S.selectedClip.meme_caption || S.selectedClip.clip_id);
  // Switch to compose
  switchTab('compose');
  toast(`Selected: ${S.selectedClip.source_label} @${S.selectedClip.timestamp}`, 'info');
}

function updateSelectedClipCard() {
  const c = S.selectedClip;
  if (!c) {
    $('selected-clip-card').classList.add('hidden');
    $('no-clip-notice').classList.remove('hidden');
    return;
  }
  $('selected-clip-card').classList.remove('hidden');
  $('no-clip-notice').classList.add('hidden');
  $('sel-source-tag').textContent = c.source_label;
  $('sel-source-tag').className = 'source-tag';
  $('sel-score-badge').textContent = `${c.meme_score}/10`;
  $('sel-score-badge').className = `score-badge ${scoreClass(c.meme_score)}`;
  $('sel-timestamp').textContent = `@${c.timestamp}`;
  $('sel-duration').textContent = `${c.duration_seconds}s`;
  $('sel-visual').textContent = c.what_happens_visually;
  $('preview-clip-btn').disabled = false;
  $('preview-clip-btn').title = 'Preview clip (first load takes ~5s to cut)';
}

// Source pills
document.querySelectorAll('.pill').forEach(p=>p.addEventListener('click',()=>{
  document.querySelectorAll('.pill').forEach(x=>x.classList.remove('active'));
  p.classList.add('active');
  S.filters.source = p.dataset.source;
  fetchClips();
}));
$('score-slider').addEventListener('input', function(){
  S.filters.minScore = +this.value;
  $('score-val').textContent = this.value;
  fetchClips();
});

// ── COMPOSE ───────────────────────────────────────────────────────────────

// Video type buttons
document.querySelectorAll('.type-btn').forEach(b=>b.addEventListener('click',()=>{
  document.querySelectorAll('.type-btn').forEach(x=>x.classList.remove('active'));
  b.classList.add('active');
  S.videoType = b.dataset.type;
  switchVideoType(S.videoType);
}));

function switchVideoType(type) {
  ['meme','narration','cta_only'].forEach(t=>{
    $(`fields-${t}`).classList.toggle('hidden', t!==type);
  });
  // CTA only doesn't need a clip
  const needsClip = type !== 'cta_only';
  if (!needsClip) {
    $('selected-clip-card').classList.add('hidden');
    $('no-clip-notice').classList.add('hidden');
  } else {
    updateSelectedClipCard();
  }
}

function updateWordCount() {
  const script = $('narr-script').value;
  $('narr-word-count').textContent = `≈ ${estSecs(script)}s · ${wordCount(script)} words`;
}

function syncProvider() {
  const v = $('voice-select').value;
  // ElevenLabs voices are capitalized
  return ['Rachel','Bella','Adam','Antoni'].includes(v) ? 'elevenlabs' : 'openai';
}

function updateCtaPreview() {
  $('cta-prev-tagline').textContent = $('cta-tagline-input').value;
  $('cta-prev-subtitle').textContent = $('cta-subtitle-input').value;
}

function previewSelectedClip() {
  if (!S.selectedClip) return;
  openModal(`/api/clips/${S.selectedClip.clip_id}/preview`, false);
}

// ── TTS ───────────────────────────────────────────────────────────────────

async function generateTTS() {
  const script = $('narr-script').value.trim();
  if (!script) { toast('Write a narration script first', 'error'); return; }
  const btn = $('tts-btn');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Generating…';
  try {
    const r = await api('/api/tts', {
      method:'POST',
      body: JSON.stringify({ script, voice: $('voice-select').value, provider: syncProvider() })
    });
    S.ttsAudio = r;
    const el = $('audio-preview');
    el.classList.remove('hidden');
    el.innerHTML = `<audio controls src="${r.audio_url}"></audio><div class="audio-dur">⏱ ${r.duration}s</div>`;
    toast(`Voice ready (${r.duration}s)`, 'success');
  } catch(e) { toast(`TTS failed: ${e.message}`, 'error'); }
  finally { btn.disabled=false; btn.textContent='🎤 Generate Voice'; }
}

// ── RENDER ────────────────────────────────────────────────────────────────

async function submitRender() {
  const outputName = $('output-name').value.trim();
  if (!outputName) { toast('Set an output filename', 'error'); return; }

  let body = { mode: S.videoType, output_name: outputName };

  if (S.videoType === 'meme') {
    if (!S.selectedClip) { toast('Select a clip first', 'error'); return; }
    body.hook_clip_id = S.selectedClip.clip_id;
    body.hook_caption = $('meme-caption').value;

  } else if (S.videoType === 'narration') {
    if (!S.selectedClip) { toast('Select a clip first', 'error'); return; }
    if (!$('narr-script').value.trim()) { toast('Write a narration script first', 'error'); return; }
    body.hook_clip_id = S.selectedClip.clip_id;
    body.hook_caption = $('narr-caption').value;
    body.body_script  = $('narr-script').value;
    body.body_audio_file = S.ttsAudio?.audio_file || null;
    body.voice        = $('voice-select').value;
    body.provider     = syncProvider();
    body.cta_tagline  = $('narr-cta-tagline').value;
    body.cta_subtitle = $('narr-cta-subtitle').value;

  } else { // cta_only
    body.hook_clip_id = '';
    body.cta_tagline  = $('cta-tagline-input').value;
    body.cta_subtitle = $('cta-subtitle-input').value;
  }

  const btn = $('render-btn');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Queuing…';
  try {
    const job = await api('/api/render', { method:'POST', body: JSON.stringify(body) });
    S.queueJobs.unshift(job);
    S.activeTasks[job.id] = {
      name: outputName,
      mode: S.videoType,
      steps: {},
      pct: 0,
    };
    renderTasks();
    renderQueue();
    toast('Added to render queue!', 'success');
  } catch(e) { toast(`Failed: ${e.message}`, 'error'); }
  finally { btn.disabled=false; btn.textContent='🚀 Add to Queue'; }
}

// ── REVIEW ────────────────────────────────────────────────────────────────

async function fetchReview() {
  try {
    S.reviewVideos = await api('/api/review');
    renderReviewGrid();
    updateReviewBadge();
  } catch(e) {}
}

function updateReviewBadge() {
  const badge = $('review-badge');
  if (S.reviewVideos.length) {
    badge.textContent = S.reviewVideos.length;
    badge.classList.remove('hidden');
  } else {
    badge.classList.add('hidden');
  }
}

function renderReviewGrid() {
  const el = $('review-grid');
  if (!S.reviewVideos.length) { el.innerHTML='<div class="empty-state">No videos awaiting review</div>'; return; }
  el.innerHTML = S.reviewVideos.map(v=>`
    <div class="review-card">
      <video class="review-thumb" src="${v.url}" onclick="openReviewModal('${esc(v.filename)}')"
        muted preload="metadata" title="Click to preview"></video>
      <div class="review-card-body">
        <div class="review-name" title="${esc(v.filename)}">${esc(v.filename)}</div>
        <div class="review-meta">${v.size_mb}MB · ${relTime(v.created_at)}</div>
        <div class="review-actions">
          <button class="btn btn-success btn-sm" onclick="approveVideo('${esc(v.filename)}')">✓ Publish</button>
          <button class="btn btn-danger btn-sm" onclick="rejectVideo('${esc(v.filename)}')">✕ Reject</button>
        </div>
      </div>
    </div>`).join('');
}

function openReviewModal(filename) {
  S.currentReviewFile = filename;
  openModal(`/api/review/${filename}`, true);
}

async function approveVideo(filename) {
  try {
    await api(`/api/review/${encodeURIComponent(filename)}/approve`, { method:'POST' });
    toast(`Published: ${filename}`, 'success');
    S.reviewVideos = S.reviewVideos.filter(v=>v.filename!==filename);
    renderReviewGrid();
    updateReviewBadge();
    fetchPublished();
    closeModal();
  } catch(e) { toast(`Failed: ${e.message}`, 'error'); }
}

async function rejectVideo(filename) {
  if (!confirm(`Reject and delete "${filename}"?`)) return;
  try {
    await api(`/api/review/${encodeURIComponent(filename)}/reject`, { method:'POST' });
    toast(`Rejected: ${filename}`, 'info');
    S.reviewVideos = S.reviewVideos.filter(v=>v.filename!==filename);
    renderReviewGrid();
    updateReviewBadge();
    closeModal();
  } catch(e) { toast(`Failed: ${e.message}`, 'error'); }
}

// ── PUBLISHED ─────────────────────────────────────────────────────────────

async function fetchPublished() {
  try {
    S.published = await api('/api/published');
    renderPublished();
  } catch(e) {}
}

function renderPublished() {
  const { videos, today_count, daily_target } = S.published;
  $('daily-tracker-text').textContent = `${today_count} / ${daily_target} published today`;

  const dots = $('daily-dots');
  dots.innerHTML = Array.from({length:daily_target},(_,i)=>
    `<div class="daily-dot ${i<today_count?'filled':''}"></div>`).join('');

  const el = $('published-grid');
  if (!videos.length) { el.innerHTML='<div class="empty-state">No published videos yet</div>'; return; }
  el.innerHTML = videos.map(v=>`
    <div class="pub-card">
      <video class="pub-thumb" src="${v.url}" muted preload="metadata"
        onclick="openModal('${v.url}',false)" title="Preview"></video>
      <div class="pub-card-body">
        <div class="pub-info">
          <div class="pub-name" title="${esc(v.filename)}">${esc(v.filename)}</div>
          <div class="pub-meta">${v.size_mb}MB · ${relTime(v.created_at)}</div>
        </div>
        <a class="btn btn-secondary btn-sm" href="${v.url}" download="${esc(v.filename)}">↓</a>
      </div>
    </div>`).join('');
}

// ── TASKS ─────────────────────────────────────────────────────────────────

function renderTasks() {
  const el = $('tasks-list');
  const tasks = Object.entries(S.activeTasks);
  $('active-task-count').textContent = tasks.length;

  const summary = $('tasks-summary');
  summary.textContent = tasks.length ? `${tasks.length} rendering…` : '';

  if (!tasks.length) {
    el.innerHTML='<div class="empty-state" style="padding:16px;font-size:12px">No active tasks</div>';
    return;
  }

  el.innerHTML = tasks.map(([id,t])=>{
    const allSteps = STEPS[t.mode] || ['render'];
    const stepHtml = allSteps.map(s=>{
      const pct = t.steps[s];
      const cls = pct===100?'done':pct>0?'active':'';
      return `<span class="step-pill ${cls}">${pct===100?'✓':pct>0?'…':'○'} ${s}</span>`;
    }).join('');
    const overallPct = t.steps ? Math.round(
      Object.values(t.steps).reduce((a,b)=>a+b,0) / (allSteps.length*100) * 100
    ) : 0;
    return `
      <div class="task-card">
        <div class="task-name">${esc(t.name)}</div>
        <div class="task-steps">${stepHtml}</div>
        <div class="task-bar"><div class="task-bar-fill" style="width:${overallPct}%"></div></div>
      </div>`;
  }).join('');
}

// ── QUEUE ─────────────────────────────────────────────────────────────────

async function fetchQueue() {
  try {
    S.queueJobs = await api('/api/queue');
    renderQueue();
  } catch(e) {}
}

function renderQueue() {
  const el = $('queue-list');
  if (!S.queueJobs.length) {
    el.innerHTML='<div class="empty-state" style="padding:12px;font-size:12px">Empty</div>';
    return;
  }
  el.innerHTML = S.queueJobs.slice(0,15).map(j=>`
    <div class="job-card">
      <div class="job-top">
        <span class="job-name" title="${esc(j.output_name)}">${esc(j.output_name)}</span>
        <span class="job-badge badge-${j.status}">${j.status}</span>
      </div>
      <div class="job-time">${relTime(j.created_at)} · ${j.mode||'narration'}</div>
      ${j.error?`<div class="job-error">⚠ ${esc(j.error)}</div>`:''}
    </div>`).join('');
}

// ── VIDEO MODAL ───────────────────────────────────────────────────────────

function openModal(src, showActions) {
  const modal = $('video-modal');
  const video = $('modal-video');
  video.src = '';
  modal.classList.remove('hidden');
  $('modal-actions').classList.toggle('hidden', !showActions);
  // Show loading state, then load video
  video.poster = '';
  video.style.opacity = '0.3';
  video.src = src;
  video.oncanplay = () => { video.style.opacity = '1'; };
  video.onerror = () => { video.style.opacity='1'; toast('Preview failed — try again in a moment', 'error'); };
}

function closeModal() {
  const v = $('modal-video');
  v.pause(); v.src='';
  $('video-modal').classList.add('hidden');
  S.currentReviewFile = null;
}

$('modal-close').addEventListener('click', closeModal);
$('modal-backdrop').addEventListener('click', closeModal);

$('modal-approve').addEventListener('click', ()=>{
  if (S.currentReviewFile) approveVideo(S.currentReviewFile);
});
$('modal-reject').addEventListener('click', ()=>{
  if (S.currentReviewFile) rejectVideo(S.currentReviewFile);
});

// ── POLLING (fallback) ────────────────────────────────────────────────────

setInterval(()=>{
  fetchQueue();
  if (S.activeTab==='review') fetchReview();
  if (S.activeTab==='published') fetchPublished();
}, 8000);

// ── INIT ─────────────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded', ()=>{
  connectSSE();
  fetchClips();
  fetchQueue();
  fetchPublished();
  fetchReview();
  switchVideoType('meme');
  updateSelectedClipCard();
});
