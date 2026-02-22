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
  calendar: [],          // calendar entries
};

const STEPS = { meme: ['render','cta','assemble'], narration: ['hook','tts','body','cta','assemble'] };

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
  if(name==='create'){fetchSources();}
  if(name==='calendar'){fetchCalendar();}
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
    if(d.status==='done'){
      await api('/api/sync',{method:'POST'});
      fetchClips();
      goToClips('meme');
      toast(`${d.filename} analyzed — clips ready!`,'success');
    }
    if(d.status==='failed'){
      showOnly('create-upload');
      toast(`Analysis failed: ${d.filename}`,'error');
    }
  });
  es.onerror=()=>setTimeout(connectSSE,3000);
}

// ── Landing routing ───────────────────────────────────────────────

function showOnly(id) {
  ['create-landing','create-upload','create-analyzing','create-clips','narration-page','composer-view']
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
  fetchHooks();
}

function pickHookClip() {
  goToClips('hook');
}

async function fetchHooks() {
  try {
    const data = await api('/api/clips?min_score=8');
    const clips = data.clips || data || [];
    renderHookLibrary(clips);
  } catch(e) {
    $('hook-library-list').innerHTML = '<div class="hook-lib-loading">Failed to load clips</div>';
  }
}

function renderHookLibrary(clips) {
  const el = $('hook-library-list');
  if (!clips.length) { el.innerHTML = '<div class="hook-lib-loading">No high-score clips found</div>'; return; }
  el.innerHTML = clips.map(c => {
    const active = S.hookClip?.clip_id === c.clip_id ? ' hook-lib-card-active' : '';
    const emoji = c.source_slug === 'office' ? '🏢' : '💻';
    return `<div class="hook-lib-card${active}" onclick="selectHookClip('${c.clip_id}')">
      <div class="hook-lib-video-wrap">
        <video class="hook-lib-thumb" src="/api/clips/${c.clip_id}/preview" muted preload="none"
          onmouseenter="this.play()" onmouseleave="this.pause();this.currentTime=0"></video>
        <div class="hook-lib-overlay">${emoji} <span class="hook-lib-score">${c.meme_score}</span></div>
      </div>
      <div class="hook-lib-caption">${esc(c.meme_caption||'')}</div>
    </div>`;
  }).join('');
}

function selectHookClip(clipId) {
  const clip = S.clips.find(c => c.clip_id === clipId);
  if (!clip) return;
  S.hookClip = clip;
  renderHookClip();
  renderHookLibrary(
    (S.clips || []).filter(c => c.meme_score >= 8)
  );
}

function handleClipsBack() {
  if(S.clipPickerMode==='hook') { showOnly('narration-page'); }
  else if(S.clipPickerMode==='calendar') { switchTab('calendar'); S.clipPickerMode='meme'; }
  else { goToUpload(); }
}

async function assignClipToCalendar(entryId, clipId) {
  try {
    const entry = await api(`/api/calendar/${entryId}`, {
      method: 'PUT',
      body: JSON.stringify({ clip_id: clipId })
    });
    // Update local state
    const idx = S.calendar.findIndex(e => e.id === entryId);
    if (idx !== -1) S.calendar[idx] = entry;
    S.calendarPickEntryId = null;
    S.clipPickerMode = 'meme';
    toast('Clip assigned to calendar entry');
    switchTab('calendar');
  } catch(e) {
    toast(`Failed: ${e.message}`, 'error');
  }
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
    const data=await api(`/api/clips?${p}`);
    let clips=data.clips||data;  // handle both {clips:[]} and bare array
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
    const matchReason = c.match_reason ? `<div class="match-reason">${esc(c.match_reason)}</div>` : '';
    return `<div class="clip-card${active}" onclick="selectClip('${c.clip_id}')">
      <div class="cc-top">
        <span class="score-badge ${scoreClass(c.meme_score)}">${c.meme_score}</span>
        <span class="source-tag">${c.source_label.replace('Silicon Valley ','SV')}</span>
        <span class="clip-ts">${c.timestamp}</span>
      </div>
      <div class="cc-caption">${esc(c.meme_caption)}</div>
      <div class="cc-visual">${esc(c.what_happens_visually)}</div>
      ${matchReason}
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
  } else if(S.clipPickerMode==='calendar' && S.calendarPickEntryId) {
    // Update calendar entry with selected clip
    assignClipToCalendar(S.calendarPickEntryId, clipId);
  } else {
    S.selected=clip;
    renderClipList();
    showComposer();
  }
}

function renderHookClip() {
  const c=S.hookClip;
  if(!c){
    $('hook-selected').classList.add('hidden');
    $('hook-caption-group').classList.add('hidden');
    return;
  }
  $('hook-selected').classList.remove('hidden');
  $('hook-caption-group').classList.remove('hidden');
  // Video preview
  const vid=$('hook-preview-video');
  vid.src=`/api/clips/${c.clip_id}/preview`;
  vid.load();
  // Meta
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

// ── Smart Search ──────────────────────────────────────────────────

async function smartSearch(topic) {
  if(!topic.trim()) { fetchClips(); return; }
  const el=$('clip-list');
  el.innerHTML='<div class="loading-state">🔍 Searching...</div>';
  try {
    const data = await api('/api/smart-search', {
      method: 'POST',
      body: JSON.stringify({ topic: topic.trim(), limit: 10 })
    });
    S.clips = data.clips || [];
    renderClipList();
    const method = data.method === 'ai' ? '✨ AI' : '🔤 keyword';
    toast(`Found ${S.clips.length} clips (${method})`, 'info');
  } catch(e) {
    el.innerHTML=`<div class="loading-state" style="color:var(--red)">${e.message}</div>`;
    toast(`Search failed: ${e.message}`, 'error');
  }
}

function handleSmartSearch() {
  const input = $('smart-search-input');
  if(input) smartSearch(input.value);
}

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
  showOnly('create-analyzing');
  $('analyzing-title').textContent = `Uploading ${file.name}…`;
  $('analyzing-sub').textContent = 'Transferring your file to the server';
  $('analyzing-hint').textContent = 'Gemini will then extract the best meme moments scene by scene';
  const fd=new FormData();fd.append('file',file);
  try {
    await fetch('/api/intake',{method:'POST',body:fd});
    $('analyzing-title').textContent = 'Gemini is analyzing your video…';
    $('analyzing-sub').textContent = `Scanning ${file.name} scene by scene`;
    $('analyzing-hint').textContent = 'Extracting the highest-energy meme moments — almost there';
  } catch(e){showOnly('create-upload');toast(`Upload failed: ${e.message}`,'error');}
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

  // Group by folder
  const groups={};
  videos.forEach(v=>{
    const g=v.folder||'studio';
    if(!groups[g]) groups[g]=[];
    groups[g].push(v);
  });

  const folderLabels={'studio':'Studio renders','2.21_publish':'Feb 21 · ready to post','2.21 archived':'Feb 21 · archived'};
  el.innerHTML=Object.entries(groups).map(([folder,vids])=>`
    <div class="folder-group">
      <div class="folder-label">
        <span class="folder-icon">📁</span>
        <span>${folderLabels[folder]||folder}</span>
        <span class="folder-count">${vids.length}</span>
      </div>
      <div class="video-grid-inner">
        ${vids.map(v=>`
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
          </div>`).join('')}
      </div>
    </div>`).join('');
}

async function syncLibrary() {
  const btn=document.querySelector('.sync-btn');
  if(btn){btn.style.opacity='.4';btn.style.pointerEvents='none';}
  try {
    const r=await api('/api/sync',{method:'POST'});
    await fetchClips();
    await fetchSources();
    await fetchPublished();
    toast(`Library synced — ${r.clip_count} clips`,'success');
  } catch(e){toast('Sync failed','error');}
  finally{if(btn){btn.style.opacity='';btn.style.pointerEvents='';}}
}

async function fetchSources() {
  try {
    const data = await api('/api/sources');
    renderSources(data.sources||[]);
  } catch(e){}
}

function renderSources(sources) {
  const el=$('sources-list');
  if(!el) return;
  if(!sources.length){el.innerHTML='<div class="source-empty">No source videos found</div>';return;}
  el.innerHTML=sources.map(s=>`
    <div class="source-row">
      <div class="source-info">
        <span class="source-name">${esc(s.filename)}</span>
        <span class="source-size">${s.size_mb}MB</span>
      </div>
      <div class="source-status ${s.analyzed?'analyzed':'not-analyzed'}">
        ${s.analyzed ? `✓ ${s.clip_count} clips` : '⬤ not analyzed'}
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

// ── Calendar ───────────────────────────────────────────────────────

async function fetchCalendar() {
  try {
    const data = await api('/api/calendar');
    S.calendar = data.entries || [];
    renderCalendar();
  } catch(e) {
    $('calendar-list').innerHTML = `<div class="empty-state" style="color:var(--red)">${e.message}</div>`;
  }
}

function renderCalendar() {
  const el = $('calendar-list');
  if (!S.calendar.length) {
    el.innerHTML = '<div class="empty-state">No topics scheduled yet</div>';
    return;
  }
  // Sort by date ascending
  const sorted = [...S.calendar].sort((a, b) => a.date.localeCompare(b.date));
  el.innerHTML = `
    <div class="cal-table">
      <div class="cal-header">
        <span class="cal-col-date">Date</span>
        <span class="cal-col-topic">Topic</span>
        <span class="cal-col-status">Status</span>
        <span class="cal-col-actions">Actions</span>
      </div>
      ${sorted.map(e => {
        const statusClass = `cal-status-${e.status}`;
        const canQueue = e.clip_id && e.status === 'planned';
        return `
          <div class="cal-row">
            <span class="cal-col-date">${formatCalDate(e.date)}</span>
            <span class="cal-col-topic">${esc(e.topic)}</span>
            <span class="cal-col-status"><span class="cal-status-badge ${statusClass}">${e.status}</span></span>
            <span class="cal-col-actions">
              ${canQueue ? `<button class="btn btn-primary btn-sm" onclick="queueCalendarRender('${e.id}')">Queue render</button>` : ''}
              ${!e.clip_id && e.status === 'planned' ? `<button class="btn btn-secondary btn-sm" onclick="pickClipForCalendar('${e.id}')">Pick clip</button>` : ''}
              <button class="btn btn-danger btn-sm cal-del-btn" onclick="deleteCalendarEntry('${e.id}')">Delete</button>
            </span>
          </div>`;
      }).join('')}
    </div>`;
}

function formatCalDate(dateStr) {
  const d = new Date(dateStr + 'T00:00:00');
  const days = ['Sun','Mon','Tue','Wed','Thu','Fri','Sat'];
  const months = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
  return `${days[d.getDay()]} ${months[d.getMonth()]} ${d.getDate()}`;
}

function toggleCalendarForm() {
  const form = $('calendar-add-form');
  const isHidden = form.classList.contains('hidden');
  form.classList.toggle('hidden');
  if (isHidden) {
    // Set default date to today
    const today = new Date().toISOString().split('T')[0];
    $('cal-date-input').value = today;
    $('cal-topic-input').value = '';
    $('cal-topic-input').focus();
  }
}

async function addCalendarEntry() {
  const topic = $('cal-topic-input').value.trim();
  const date = $('cal-date-input').value;
  if (!topic) { toast('Enter a topic', 'error'); return; }
  if (!date) { toast('Select a date', 'error'); return; }
  try {
    const entry = await api('/api/calendar', {
      method: 'POST',
      body: JSON.stringify({ topic, date })
    });
    S.calendar.push(entry);
    renderCalendar();
    toggleCalendarForm();
    toast('Topic added to calendar');
  } catch(e) {
    toast(`Failed: ${e.message}`, 'error');
  }
}

async function deleteCalendarEntry(id) {
  if (!confirm('Delete this calendar entry?')) return;
  try {
    await api(`/api/calendar/${id}`, { method: 'DELETE' });
    S.calendar = S.calendar.filter(e => e.id !== id);
    renderCalendar();
    toast('Entry deleted', 'info');
  } catch(e) {
    toast(`Failed: ${e.message}`, 'error');
  }
}

async function queueCalendarRender(id) {
  try {
    const result = await api(`/api/calendar/${id}/queue`, { method: 'POST' });
    // Update local state
    const entry = S.calendar.find(e => e.id === id);
    if (entry) {
      entry.status = 'rendering';
      entry.output_name = result.entry?.output_name;
    }
    renderCalendar();
    toast('Queued for render!');
    switchTab('queue');
  } catch(e) {
    toast(`Failed: ${e.message}`, 'error');
  }
}

function pickClipForCalendar(entryId) {
  // Store entry ID, go to clip picker, then handle selection
  S.calendarPickEntryId = entryId;
  S.clipPickerMode = 'calendar';
  goToClips('calendar');
}

// ── Init ──────────────────────────────────────────────────────────

document.addEventListener('DOMContentLoaded',()=>{
  connectSSE();
  fetchClips();
  fetchJobs();
  fetchPublished();
  fetchReview();
  fetchSources();
  fetchCalendar();
});
