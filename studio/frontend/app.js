// CrowdListen Studio

const S = {
  tab: 'create',
  clips: [], filters: { source: 'all', minScore: 7, query: '' },
  selected: null,        // selected clip (meme flow)
  hookClip: null,        // selected hook clip (narration flow)
  clipPickerMode: 'meme',// 'meme' | 'hook'
  videoType: 'meme',
  ttsAudio: null,
  narrTtsAudio: null,
  activeTasks: {},
  jobs: [],
  review: [],
  published: { videos: [], today_count: 0, daily_target: 2 },
  reviewFile: null,
};

const STEPS = { meme: ['render'], narration: ['hook','tts','body','cta','assemble'] };

// ── Utils ─────────────────────────────────────────────────────────

const $ = id => document.getElementById(id);
const esc = s => String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
const slugify = t => t.toLowerCase().replace(/[^a-z0-9]+/g,'_').replace(/^_+|_+$/g,'').slice(0,40);
const wc = t => t.trim().split(/\s+/).filter(Boolean).length;
const estSecs = t => Math.ceil(wc(t)/2.5);
const relTime = iso => {
  const d=(Date.now()-new Date(iso))/1000;
  if(d<60) return 'just now'; if(d<3600) return `${Math.floor(d/60)}m ago`;
  if(d<86400) return `${Math.floor(d/3600)}h ago`; return `${Math.floor(d/86400)}d ago`;
};
const scoreClass = s => s>=9?'score-high':s>=7?'score-mid':'score-low';

async function api(path, opts={}) {
  const r = await fetch(path, {headers:{'Content-Type':'application/json'}, ...opts});
  if(!r.ok){const e=await r.json().catch(()=>({detail:r.statusText}));throw new Error(e.detail||r.statusText);}
  return r.json();
}

function toast(msg, type='success') {
  const el=document.createElement('div');
  el.className=`toast ${type}`;
  el.innerHTML=`<span>${type==='success'?'✓':type==='error'?'✕':'ℹ'}</span><span>${msg}</span>`;
  $('toast-container').appendChild(el);
  setTimeout(()=>el.remove(),3500);
}

// ── Tabs ──────────────────────────────────────────────────────────

function switchTab(name) {
  document.querySelectorAll('.nav-link').forEach(t=>t.classList.toggle('active',t.dataset.tab===name));
  document.querySelectorAll('.tab-page').forEach(p=>p.classList.toggle('active',p.id===`tab-${name}`));
  S.tab=name;
  if(name==='queue') renderQueue();
  if(name==='published'){fetchReview();fetchPublished();}
}

// ── SSE ───────────────────────────────────────────────────────────

function connectSSE() {
  const es = new EventSource('/api/events');
  es.addEventListener('progress', e => {
    const d=JSON.parse(e.data);
    if(!S.activeTasks[d.job_id]){
      const j=S.jobs.find(x=>x.id===d.job_id)||{};
      S.activeTasks[d.job_id]={name:j.output_name||d.job_id.slice(0,8),mode:j.mode||'meme',steps:{}};
    }
    S.activeTasks[d.job_id].steps[d.step]=d.pct;
    renderActiveTasks();
    updateQueueBadge();
  });
  es.addEventListener('status', e => {
    const d=JSON.parse(e.data);
    if(d.status==='review'||d.status==='done'||d.status==='failed'){
      delete S.activeTasks[d.job_id];
      renderActiveTasks();
      if(d.status==='review') toast(`Ready to review: ${d.output_file?.split('/').pop()||'video'}`, 'success');
      if(d.status==='failed') toast(`Render failed: ${d.error||'?'}`, 'error');
      fetchJobs();
      updateQueueBadge();
      updatePubBadge();
    }
  });
  es.addEventListener('intake', e => {
    const d=JSON.parse(e.data);
    if(d.status==='done'){toast(`Analysis done: ${d.filename} — clips added!`,'success');fetchClips();}
    if(d.status==='failed') toast(`Analysis failed: ${d.filename}`,'error');
    $('upload-status').textContent = d.status==='analyzing'?`Analyzing ${d.filename}…`:d.status==='done'?'':'';
  });
  es.onerror=()=>setTimeout(connectSSE,3000);
}

// ── Landing routing ───────────────────────────────────────────────

function showOnly(id) {
  ['create-landing','create-upload','create-clips','narration-page','composer-view']
    .forEach(x => $(x).classList.toggle('hidden', x!==id));
}

function goToUpload() {
  showOnly('create-upload');
}

function handleLandingSubmit() {
  const q=$('landing-input').value.trim();
  S.filters.query=q;
  // "narration" keyword → narration page, else → meme upload
  if(q.toLowerCase().includes('narrat')) { goToNarration(); return; }
  goToUpload();
}

function goToClips(mode) {
  S.clipPickerMode = mode==='hook' ? 'hook' : 'meme';
  if(mode && mode!=='hook') S.videoType=mode;
  $('create-landing').classList.add('hidden');
  $('narration-page').classList.add('hidden');
  $('composer-view').classList.add('hidden');
  $('create-clips').classList.remove('hidden');
  fetchClips();
}

function goToNarration() {
  showOnly('narration-page');
  S.hookClip=null;
  renderHookClip();
}

function pickHookClip() {
  goToClips('hook');
}

function handleClipsBack() {
  if(S.clipPickerMode==='hook') { showOnly('narration-page'); }
  else { goToUpload(); }
}

function goToLanding() {
  S.selected=null; S.filters.query=''; S.clipPickerMode='meme';
  document.querySelectorAll('.tab-page').forEach(p=>p.classList.toggle('active',p.id==='tab-create'));
  document.querySelectorAll('.nav-link').forEach(t=>t.classList.remove('active'));
  S.tab='create';
  showOnly('create-landing');
}

// ── Clips ─────────────────────────────────────────────────────────

async function fetchClips() {
  const p=new URLSearchParams({min_score:S.filters.minScore});
  if(S.filters.source!=='all') p.set('source',S.filters.source);
  try {
    let clips=await api(`/api/clips?${p}`);
    if(S.filters.query) {
      const q=S.filters.query.toLowerCase();
      clips=clips.filter(c=>
        (c.meme_caption||'').toLowerCase().includes(q)||
        (c.what_happens_visually||'').toLowerCase().includes(q)||
        (c.source_label||'').toLowerCase().includes(q)
      );
    }
    S.clips=clips;
    renderClipList();
  } catch(e) {$('clip-list').innerHTML=`<div class="loading-state" style="color:var(--red)">${e.message}</div>`;}
}

function renderClipList() {
  const el=$('clip-list');
  if(!S.clips.length){el.innerHTML='<div class="empty-state">No clips match filters</div>';return;}
  el.innerHTML=S.clips.map(c=>{
    const active=S.selected?.clip_id===c.clip_id?' active':'';
    return `<div class="clip-card${active}" onclick="selectClip('${c.clip_id}')">
      <div class="cc-top">
        <span class="score-badge ${scoreClass(c.meme_score)}">${c.meme_score}</span>
        <span class="source-tag">${c.source_label.replace('Silicon Valley ','SV')}</span>
        <span class="clip-ts">${c.timestamp}</span>
      </div>
      <div class="cc-caption">${esc(c.meme_caption)}</div>
      <div class="cc-visual">${esc(c.what_happens_visually)}</div>
    </div>`;
  }).join('');
}

function selectClip(clipId) {
  const clip=S.clips.find(c=>c.clip_id===clipId)||null;
  if(!clip) return;
  if(S.clipPickerMode==='hook') {
    S.hookClip=clip;
    renderHookClip();
    showOnly('narration-page');
  } else {
    S.selected=clip;
    renderClipList();
    showComposer();
  }
}

function renderHookClip() {
  const c=S.hookClip;
  if(!c){
    $('hook-empty').classList.remove('hidden');
    $('hook-selected').classList.add('hidden');
    $('hook-caption-group').classList.add('hidden');
    return;
  }
  $('hook-empty').classList.add('hidden');
  $('hook-selected').classList.remove('hidden');
  $('hook-caption-group').classList.remove('hidden');
  $('hook-emoji').textContent=c.source_slug==='office'?'🏢':'💻';
  $('hook-source').textContent=c.source_label;
  $('hook-source').className='source-tag';
  $('hook-score').textContent=`${c.meme_score}/10`;
  $('hook-score').className=`score-badge ${scoreClass(c.meme_score)}`;
  $('hook-ts').textContent=`@${c.timestamp}`;
  $('hook-caption-text').textContent=c.meme_caption||'';
  if(!$('narr-hook-caption').value) $('narr-hook-caption').value=c.meme_caption||'';
  if(!$('narr-output-name').value) $('narr-output-name').value=slugify(c.meme_caption||c.clip_id);
}

function clearClipSelection() {
  S.selected=null;
  S.ttsAudio=null;
  renderClipList();
  showOnly('create-clips');
}

function showComposer() {
  const c=S.selected;
  showOnly('composer-view');

  // Strip
  $('strip-emoji').textContent=c.source_slug==='office'?'🏢':'💻';
  $('strip-source').textContent=c.source_label;
  $('strip-source').className='source-tag';
  $('strip-score').textContent=`${c.meme_score}/10`;
  $('strip-score').className=`score-badge ${scoreClass(c.meme_score)}`;
  $('strip-ts').textContent=`@${c.timestamp}`;
  $('strip-dur').textContent=`${c.duration_seconds}s`;
  $('strip-visual').textContent=c.what_happens_visually;

  // Pre-fill
  $('meme-caption').value=c.meme_caption||'';
  $('output-name').value=slugify(c.meme_caption||c.clip_id);
}

// Filters
document.querySelectorAll('.pill').forEach(p=>p.addEventListener('click',()=>{
  document.querySelectorAll('.pill').forEach(x=>x.classList.remove('active'));
  p.classList.add('active');
  S.filters.source=p.dataset.source;
  fetchClips();
}));
$('score-slider').addEventListener('input',function(){
  S.filters.minScore=+this.value;
  $('score-val').textContent=this.value;
  fetchClips();
});

// ── Narration page ────────────────────────────────────────────────

function updateNarrWordCount() {
  const t=$('narr-script').value;
  $('narr-word-count').textContent=`≈ ${estSecs(t)}s · ${wc(t)} words`;
}

async function generateNarrTTS() {
  const script=$('narr-script').value.trim();
  if(!script){toast('Write a narration script first','error');return;}
  const btn=$('narr-tts-btn');
  btn.disabled=true;btn.innerHTML='<span class="spinner"></span> Generating…';
  try {
    const voice=$('narr-voice-select').value;
    const provider=['Rachel','Bella','Adam','Antoni'].includes(voice)?'elevenlabs':'openai';
    S.narrTtsAudio=await api('/api/tts',{method:'POST',body:JSON.stringify({script,voice,provider})});
    const el=$('narr-audio-preview');
    el.classList.remove('hidden');
    el.innerHTML=`<audio controls src="${S.narrTtsAudio.audio_url}"></audio><div class="audio-dur">⏱ ${S.narrTtsAudio.duration}s</div>`;
    toast(`Voice ready — ${S.narrTtsAudio.duration}s`);
  } catch(e){toast(`TTS failed: ${e.message}`,'error');}
  finally{btn.disabled=false;btn.textContent='🎤 Generate voice';}
}

async function submitNarration() {
  if(!S.hookClip){toast('Pick a hook clip first','error');return;}
  const script=$('narr-script').value.trim();
  if(!script){toast('Write a narration script first','error');return;}
  const outputName=$('narr-output-name').value.trim()||slugify(script.slice(0,40));
  const body={
    mode:'narration',output_name:outputName,
    hook_clip_id:S.hookClip.clip_id,
    hook_caption:$('narr-hook-caption').value,
    body_script:script,
    body_audio_file:S.narrTtsAudio?.audio_file||null,
    voice:$('narr-voice-select').value,
    provider:['Rachel','Bella','Adam','Antoni'].includes($('narr-voice-select').value)?'elevenlabs':'openai',
  };
  const btn=$('narr-render-btn');
  btn.disabled=true;btn.innerHTML='<span class="spinner"></span>';
  try {
    const job=await api('/api/render',{method:'POST',body:JSON.stringify(body)});
    S.jobs.unshift(job);
    S.activeTasks[job.id]={name:outputName,mode:'narration',steps:{}};
    renderActiveTasks();updateQueueBadge();
    toast('Added to queue!');
    switchTab('queue');
  } catch(e){toast(`Failed: ${e.message}`,'error');}
  finally{btn.disabled=false;btn.textContent='🚀 Render';}
}

// ── Render ────────────────────────────────────────────────────────

async function submitRender() {
  if(!S.selected){toast('Select a clip first','error');return;}
  const outputName=$('output-name').value.trim();
  if(!outputName){toast('Set an output filename','error');return;}
  const body={
    mode:'meme',output_name:outputName,
    hook_clip_id:S.selected.clip_id,
    hook_caption:$('meme-caption').value,
  };
  const btn=$('render-btn');
  btn.disabled=true;btn.innerHTML='<span class="spinner"></span>';
  try {
    const job=await api('/api/render',{method:'POST',body:JSON.stringify(body)});
    S.jobs.unshift(job);
    S.activeTasks[job.id]={name:outputName,mode:'meme',steps:{}};
    renderActiveTasks();updateQueueBadge();
    toast('Added to queue!');
    switchTab('queue');
  } catch(e){toast(`Failed: ${e.message}`,'error');}
  finally{btn.disabled=false;btn.textContent='🚀 Render';}
}

// ── Preview ───────────────────────────────────────────────────────

function openPreviewModal() {
  if(!S.selected) return;
  previewClip(S.selected.clip_id);
}

function previewClip(clipId) {
  openModal(`/api/clips/${clipId}/preview`, false);
}

// ── Upload ────────────────────────────────────────────────────────

function handleFileSelect(input) {
  if(input.files[0]) uploadFile(input.files[0]);
}

async function uploadFile(file) {
  if(!file.type.startsWith('video/')){toast('Please upload a video file','error');return;}
  $('upload-status').textContent=`Uploading ${file.name}…`;
  const fd=new FormData();fd.append('file',file);
  try {
    await fetch('/api/intake',{method:'POST',body:fd});
    $('upload-status').textContent=`Analyzing…`;
    toast(`Uploaded ${file.name}. Gemini is analyzing…`,'info');
  } catch(e){$('upload-status').textContent='';toast(`Upload failed: ${e.message}`,'error');}
}

// ── Queue tab ─────────────────────────────────────────────────────

async function fetchJobs() {
  try {S.jobs=await api('/api/queue');renderQueue();}catch(e){}
}

function renderActiveTasks() {
  const el=$('active-tasks');
  const tasks=Object.entries(S.activeTasks);
  if(!tasks.length){el.innerHTML='<div class="empty-state" style="padding:20px">Nothing rendering right now</div>';return;}
  el.innerHTML=tasks.map(([id,t])=>{
    const allSteps=STEPS[t.mode]||['render'];
    const stepsHtml=allSteps.map(s=>{
      const pct=t.steps[s];
      const cls=pct===100?'done':pct>0?'active':'';
      return `<span class="step-pill ${cls}">${pct===100?'✓ ':pct>0?'… ':''} ${s}</span>`;
    }).join('');
    const total=allSteps.length;
    const done=Object.values(t.steps).filter(v=>v===100).length;
    const pct=total?Math.round(done/total*100):0;
    return `<div class="task-card">
      <div class="task-header">
        <span class="task-name">${esc(t.name)}</span>
        <span class="task-mode">${t.mode}</span>
      </div>
      <div class="task-steps">${stepsHtml}</div>
      <div class="task-bar"><div class="task-bar-fill" style="width:${pct}%"></div></div>
    </div>`;
  }).join('');
}

function renderQueue() {
  renderActiveTasks();
  const el=$('queue-history');
  if(!S.jobs.length){el.innerHTML='<div class="empty-state">No jobs yet</div>';return;}
  el.innerHTML=S.jobs.slice(0,20).map(j=>`
    <div class="job-row">
      <span class="job-name">${esc(j.output_name)}</span>
      <span class="job-meta">${j.mode} · ${relTime(j.created_at)}</span>
      <span class="status-pill s-${j.status}">${j.status}</span>
      ${j.error?`<div class="job-error" style="width:100%">⚠ ${esc(j.error)}</div>`:''}
    </div>`).join('');
}

function updateQueueBadge() {
  const n=Object.keys(S.activeTasks).length;
  const b=$('queue-badge');
  b.textContent=n; b.classList.toggle('hidden',n===0);
}

// ── Review + Published ────────────────────────────────────────────

async function fetchReview() {
  try {
    S.review=await api('/api/review');
    renderReview();
    updatePubBadge();
  } catch(e){}
}

async function fetchPublished() {
  try {
    S.published=await api('/api/published');
    renderPublished();
  } catch(e){}
}

function updatePubBadge() {
  const n=S.review.length;
  const b=$('pub-badge');
  b.textContent=n; b.classList.toggle('hidden',n===0);
}

function renderReview() {
  const section=$('review-section');
  $('review-count').textContent=S.review.length;
  section.classList.toggle('hidden',S.review.length===0);
  if(!S.review.length) return;
  $('review-grid').innerHTML=S.review.map(v=>`
    <div class="video-card">
      <video class="video-thumb" src="${v.url}" muted preload="metadata"
        onclick="openReviewModal('${esc(v.filename)}')" title="Click to preview"></video>
      <div class="video-card-body">
        <div class="video-name" title="${esc(v.filename)}">${esc(v.filename)}</div>
        <div class="video-meta">${v.size_mb}MB · ${relTime(v.created_at)}</div>
        <div class="video-actions">
          <button class="btn btn-success btn-sm" onclick="approveVideo('${esc(v.filename)}')">✓ Publish</button>
          <button class="btn btn-danger btn-sm" onclick="rejectVideo('${esc(v.filename)}')">✕ Reject</button>
        </div>
      </div>
    </div>`).join('');
}

function renderPublished() {
  const {videos,today_count,daily_target}=S.published;
  $('daily-tracker').textContent=`${today_count} / ${daily_target} today`;
  const el=$('published-grid');
  if(!videos.length){el.innerHTML='<div class="empty-state">No published videos yet</div>';return;}
  el.innerHTML=videos.map(v=>`
    <div class="video-card">
      <video class="video-thumb" src="${v.url}" muted preload="metadata"
        onclick="openModal('${v.url}',false)" title="Preview"></video>
      <div class="video-card-body">
        <div class="video-name" title="${esc(v.filename)}">${esc(v.filename)}</div>
        <div class="video-meta">${v.size_mb}MB · ${relTime(v.created_at)}</div>
        <div class="video-actions">
          <a class="btn btn-secondary btn-sm" href="${v.url}" download="${esc(v.filename)}">↓ Download</a>
        </div>
      </div>
    </div>`).join('');
}

function openReviewModal(filename) {
  S.reviewFile=filename;
  openModal(`/api/review/${filename}`,true);
}

async function approveVideo(filename) {
  try {
    await api(`/api/review/${encodeURIComponent(filename)}/approve`,{method:'POST'});
    toast(`Published: ${filename}`);
    S.review=S.review.filter(v=>v.filename!==filename);
    renderReview();updatePubBadge();fetchPublished();closeModal();
  } catch(e){toast(`Failed: ${e.message}`,'error');}
}

async function rejectVideo(filename) {
  if(!confirm(`Delete "${filename}"?`)) return;
  try {
    await api(`/api/review/${encodeURIComponent(filename)}/reject`,{method:'POST'});
    toast('Rejected','info');
    S.review=S.review.filter(v=>v.filename!==filename);
    renderReview();updatePubBadge();closeModal();
  } catch(e){toast(`Failed: ${e.message}`,'error');}
}

// ── Modal ─────────────────────────────────────────────────────────

function openModal(src, showActions) {
  const v=$('modal-video');
  v.style.opacity='.3'; v.src=src;
  v.oncanplay=()=>v.style.opacity='1';
  $('modal-actions').classList.toggle('hidden',!showActions);
  $('video-modal').classList.remove('hidden');
}
function closeModal() {
  const v=$('modal-video');v.pause();v.src='';
  $('video-modal').classList.add('hidden');S.reviewFile=null;
}
$('modal-close').addEventListener('click',closeModal);
$('modal-backdrop').addEventListener('click',closeModal);
$('modal-approve').addEventListener('click',()=>{if(S.reviewFile)approveVideo(S.reviewFile);});
$('modal-reject').addEventListener('click',()=>{if(S.reviewFile)rejectVideo(S.reviewFile);});

// ── Drag & drop on Create tab ─────────────────────────────────────

document.addEventListener('dragover', e=>{
  if(S.tab==='create'){e.preventDefault();}
});
document.addEventListener('drop', e=>{
  if(S.tab==='create'){
    e.preventDefault();
    const f=e.dataTransfer.files[0];
    if(f) uploadFile(f);
  }
});

// ── Polling fallback ──────────────────────────────────────────────

setInterval(()=>{
  fetchJobs();
  if(S.tab==='published'){fetchReview();fetchPublished();}
}, 10000);

// ── Init ──────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded',()=>{
  connectSSE();
  fetchClips();
  fetchJobs();
  fetchPublished();
  fetchReview();
});
