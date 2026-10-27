import {RollingPaper,FixedSlots,SelectionQueue,readerPanels} from './paper.mjs';

let state = null, catalog = [], sequence = -1;
let pendingSignature='';
let showSpoken=localStorage.getItem('babblet.showSpoken')!=='false';
const readerModes=['off','opposite','stacked','four'];
let readerLayout=localStorage.getItem('babblet.readerLayout') || 'off';
if(!readerModes.includes(readerLayout)) readerLayout='off';
let readerCodes=[],readerAngles=[];
try { readerCodes=JSON.parse(localStorage.getItem('babblet.readerCodes') || '[]'); } catch(_) {}
try { readerAngles=JSON.parse(localStorage.getItem('babblet.readerAngles') || '[]'); } catch(_) {}
if(!Array.isArray(readerCodes)) readerCodes=[];
if(!Array.isArray(readerAngles)) readerAngles=[];
let speechCatalog=[], languageMode='display';
let view = localStorage.getItem('babblet.view') || 'slots';
let flipped;
try { flipped = new Set(JSON.parse(localStorage.getItem('babblet.flipped') || '[]')); }
catch (_) { flipped = new Set(); }
let pendingSelection = new Set();
const languageDrafts={};
const languageVersions={display:0,speech:0};
let languageSaving=0;
const languageSaves=new SelectionQueue(async(mode,languages)=>{
  const response=await fetch(mode==='speech'?'/api/speech-languages':'/api/languages',{
    method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({languages}),
    signal:AbortSignal.timeout(8000)});
  if(!response.ok) throw new Error('Could not save language changes. Toggle again to retry.');
  return response.json();
});
async function saveLanguageSelection() {
  const mode=languageMode,version=++languageVersions[mode];
  languageDrafts[mode]=new Set(pendingSelection);
  languageSaving++;
  document.getElementById('language-error').textContent='';
  document.getElementById('language-save-status').textContent='Saving…';
  try {
    const result=await languageSaves.save(mode,pendingSelection);
    if(mode==='speech') state.speech=result;
    else state.selected_languages=result.selected;
    sequence=-1;render();
  } catch(error) {
    if(languageVersions[mode]===version) {
      languageDrafts[mode]=new Set(mode==='speech'?state.speech.expected:state.selected_languages);
      if(languageMode===mode) {pendingSelection=languageDrafts[mode];renderOptions();}
    }
    document.getElementById('language-error').textContent=error.message;
  } finally {
    languageSaving--;
    document.getElementById('language-save-status').textContent=languageSaving?'Saving…':'';
  }
}
const root = document.getElementById('utterances');
const readerButton=element('button','reader-orbit');
readerButton.type='button';readerButton.id='reader-layout';
document.body.append(readerButton);
readerButton.addEventListener('click',()=>{
  readerLayout=readerModes[(readerModes.indexOf(readerLayout)+1)%readerModes.length];
  readerAngles=[];localStorage.setItem('babblet.readerAngles','[]');
  localStorage.setItem('babblet.readerLayout',readerLayout);slots.signature='';render();
});
const spokenButton=element('button','spoken-orbit');
spokenButton.id='toggle-spoken';spokenButton.type='button';
spokenButton.title='Show or hide original speech';
spokenButton.setAttribute('aria-label','Show original speech column');
const spokenIcon=element('img');spokenIcon.src='/art/spoken.svg';spokenIcon.alt='';
spokenButton.append(spokenIcon);document.body.append(spokenButton);
spokenButton.addEventListener('click',()=>{
  showSpoken=!showSpoken;localStorage.setItem('babblet.showSpoken',String(showSpoken));render();
});
const dialog = document.getElementById('language-dialog');
const languageButton=document.getElementById('open-languages');
languageButton.className='language-orbit';
languageButton.setAttribute('aria-label','Choose languages');
languageButton.title='Choose languages';
const languageIcon=element('img');languageIcon.src='/art/languages.svg';languageIcon.alt='';
languageButton.prepend(languageIcon);document.body.append(languageButton);
document.getElementById('speech-sync').addEventListener('click',async()=>{
  const button=document.getElementById('speech-sync');button.disabled=true;
  try {
    const response=await fetch('/api/speech-languages',{method:'POST',headers:{'Content-Type':'application/json'},
      body:JSON.stringify({sync_with_display:state?.speech?.sync_with_display===false}),signal:AbortSignal.timeout(8000)});
    if(!response.ok) throw new Error('Could not change the language link.');
    state.speech=await response.json();delete languageDrafts.speech;
    if(languageMode==='speech') pendingSelection=new Set(state.speech.expected);
    renderOptions();
  } catch(error) {document.getElementById('language-error').textContent=error.message;}
  finally {button.disabled=false;}
});
const inspectDialog=document.getElementById('recognition-dialog');
document.getElementById('open-inspector').addEventListener('click',()=>{
  renderInspector();inspectDialog.showModal();
});
document.getElementById('close-inspector').addEventListener('click',()=>inspectDialog.close());
function renderInspector() {
  if(!state) return;
  const trace=state.input?.recognition_trace;
  const host=document.getElementById('recognition-body');host.replaceChildren();
  const phases={decoding_primary:'Decoding with multilingual Whisper',draft:'Live draft',
    decoding_hebrew:'Hebrew second pass running',final:'Speech-end selection complete'};
  const reasons={live_draft:'Primary draft; comparison waits for speech to end.',
    decoding_primary:'Decoding the original audio with the primary recognizer.',
    waiting_for_hebrew:'Primary result is ready; waiting for the Hebrew specialist.',
    not_hebrew:'Hebrew specialist skipped because Hebrew was not detected or requested.',
    specialist_accepted:'Hebrew specialist passed the quality checks and was selected.',
    quality_veto:'Kept primary: specialist failed a quality check, scored substantially worse, or was too short.',
    secondary_failed:'Kept primary: Hebrew worker failed. Automatic recovery is attempted on later speech after a 30-second cooldown.'};
  host.append(element('p','inspection-activity',`Now: ${processingLabel.textContent}`));
  const recording=state.input?.debug_recording;
  if(recording?.enabled) host.append(element('p','inspection-reason',
    `● DEBUG RECORDING ON · ${recording.saved || 0} snippets saved · keeps latest ${recording.limit} · ${recording.directory}${recording.latest?` · latest: ${recording.latest}`:''}${recording.error?` · error: ${recording.error}`:''}`));
  if(!trace?.phase) {
    const enabled=state.input?.hebrew_recognizer?.enabled;
    host.append(element('p','empty',enabled?'Waiting for speech. The latest comparison expires after 60 seconds.':
      'The second recognizer is not enabled. Restart with the Hebrew model installed.'));
    return;
  }
  host.append(element('h2','',phases[trace.phase] || trace.phase));
  host.append(element('p','inspection-reason',reasons[trace.reason] || trace.reason));
  if(trace.failure) host.append(element('p','inspection-meta',`Hebrew worker: ${trace.failure}`));
  const detection=trace.detection;
  host.append(element('p','inspection-meta',
    `Detected: ${detection?.language || '—'}${typeof detection?.probability==='number'?` (language score ${detection.probability.toFixed(3)})`:''} · selected: ${trace.selected || 'pending'} · Hebrew decode: ${trace.secondary_seconds || 0}s`));
  if(detection) host.append(element('p','inspection-meta',
    `Hebrew language evidence: ${typeof detection.hebrew_probability==='number'?detection.hebrew_probability.toFixed(3):'—'} · Expected speech: ${(detection.expected || []).join(', ') || 'auto'} · Route: ${trace.routing || '—'}`));
  if(state.input?.speech_context) host.append(element('p','inspection-meta',
    `Audio context: ${state.input.speech_context.audio_seconds}s · ${state.input.speech_context.continuing_row?'continuing existing row':'new row'}`));
  const candidates=element('div','recognition-candidates');
  for(const [key,title] of [['primary','Whisper multilingual'],['secondary','ivrit.ai Hebrew']]) {
    const candidate=trace[key],chosen=trace.selected===(key==='primary'?'primary':'hebrew');
    const card=element('section',`recognition-candidate${chosen?' chosen':''}`);
    card.append(element('h3','',title+(chosen?' · Selected':'')));
    const text=element('p','candidate-text',candidate?.text || (key==='secondary'?'Not run / no usable result':'Waiting for primary result'));
    text.dir='auto';card.append(text);
    if(candidate) {
      card.append(element('p','inspection-meta',`Language: ${candidate.language || '—'} · Hebrew quality gate: ${candidate.quality_score==null?'not passed':candidate.quality_score.toFixed(3)}`));
      const table=element('table','score-table');
      const headings=element('tr');
      for(const label of ['Seconds','Avg log P ↑','No speech ↓','Repetition ↓']) headings.append(element('th','',label));
      const head=element('thead');head.append(headings);table.append(head);
      const body=element('tbody');
      const number=value=>typeof value==='number'?value.toFixed(3):'—';
      for(const segment of candidate.segments || []) {
        const row=element('tr');
        for(const value of [`${number(segment.start)}–${number(segment.end)}`,number(segment.avg_logprob),
          number(segment.no_speech_prob),number(segment.compression_ratio)]) row.append(element('td','',value));
        body.append(row);
      }
      table.append(body);card.append(table);
    }
    candidates.append(card);
  }
  host.append(candidates);
  host.append(element('p','inspection-note','Selection checks: mostly Hebrew letters; log P ≥ −1; no-speech ≤ 0.4; repetition ≤ 2.4. If both pass, reject the specialist when its log P is worse by more than 0.25 or its text is shorter than 35% of the primary. When Hebrew is expected and language detection is uncertain (below 0.85), try the specialist even if raw Hebrew language evidence is low. For that trial, keep a usable non-Hebrew primary if its log P is higher. Scores are heuristics, not accuracy percentages.'));
}
const statusHost=document.getElementById('status');
const processingSpinner=element('span','processing-spinner');
processingSpinner.hidden=true;processingSpinner.setAttribute('aria-hidden','true');
const processingLabel=element('span','',statusHost.textContent);
statusHost.replaceChildren(processingSpinner,processingLabel);
let ink=localStorage.getItem('babblet.ink')!=='false';
const paper=new RollingPaper(root,{element,heading,getState:()=>state,
  onError:message=>{processingLabel.textContent=message;}});
const slots=new FixedSlots(root,{element,heading,paper});
let slotCount=Number(localStorage.getItem('babblet.slotCount')) || 6;
if(!Number.isInteger(slotCount) || slotCount<1 || slotCount>10) slotCount=6;
const slotPicker=document.getElementById('slot-count');slotPicker.value=String(slotCount);
slotPicker.addEventListener('change',()=>{
  slotCount=Number(slotPicker.value);localStorage.setItem('babblet.slotCount',String(slotCount));render();
});
document.getElementById('ink-toggle').setAttribute('aria-pressed',String(ink));
document.getElementById('ink-toggle').addEventListener('click',()=>{
  ink=!ink;localStorage.setItem('babblet.ink',String(ink));
  document.getElementById('ink-toggle').setAttribute('aria-pressed',String(ink));render();
});
window.addEventListener('resize',()=>{if(view!=='list') render();});

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}
function flag(language) {
  const img = element('img', 'flag');
  img.src = `/flags/${language.flag}.svg`;
  img.alt = language.name; img.width = 40; img.height = 30;
  return img;
}
function heading(language) {
  const header = element('header', 'column-heading');
  const button = element('button', 'flag-button'); button.type = 'button';
  button.title = `${language.native} · click to flip`;
  button.setAttribute('aria-label', `Flip ${language.name} column`);
  button.setAttribute('aria-pressed', String(language.panelIndex!==undefined?language.panelAngle===180:flipped.has(language.code)));
  if(language.code==='_spoken') button.append(element('span','spoken-heading','Spoken'));
  else button.append(flag(language));
  const flipIcon=element('img','flip-mark');flipIcon.src='/art/flip.svg';flipIcon.alt='';
  button.append(flipIcon);
  button.addEventListener('click', () => {
    if(language.panelIndex!==undefined) {
      readerAngles[language.panelIndex]=language.panelAngle===180?0:180;
      localStorage.setItem('babblet.readerAngles',JSON.stringify(readerAngles));render();return;
    }
    if (flipped.has(language.code)) flipped.delete(language.code);
    else flipped.add(language.code);
    localStorage.setItem('babblet.flipped', JSON.stringify([...flipped])); render();
  });
  header.append(button);
  if(language.panelIndex!==undefined) {
    const choice=element('select','reader-language');
    choice.setAttribute('aria-label',`Language for reader panel ${language.panelIndex+1}`);
    const codes=state.selected_languages.slice();if(showSpoken) codes.unshift('_spoken');
    for(const code of codes) {
      const option=element('option','',code==='_spoken'?'Spoken':catalog.find(item=>item.code===code)?.native || code);
      option.value=code;option.selected=code===language.code;choice.append(option);
    }
    choice.addEventListener('change',()=>{
      readerCodes[language.panelIndex]=choice.value;
      localStorage.setItem('babblet.readerCodes',JSON.stringify(readerCodes));render();
    });
    header.append(choice);
  }
  return header;
}
function paragraph(item, language) {
  const spoken=language.code==='_spoken';
  const result = spoken ? {text:item.source_text,status:'transcript'} : item.translations[language.code];
  const box = element('div', `paragraph phase-${item.phase || 'final'}`);
  box.dataset.utteranceId = item.utterance_id;
  box.lang = spoken ? item.source_language : language.code; box.dir = spoken ? 'auto' : language.direction;
  const sourceLabel=element('small','source-language',spoken && result?.text ? language.labelFor(item.source_language) : '\u00a0');
  if(!spoken) sourceLabel.setAttribute('aria-hidden','true');
  box.append(sourceLabel);
  const text = element('p', '', paper.remaining(item,language.code));
  if (!result?.text) { text.className = 'pending'; text.textContent = result?.status === 'pending' ? '…' : '—'; }
  box.append(text);
  if (view === 'list') box.append(element('small', 'metadata', `${item.phase || 'final'} · ${result?.status || 'not selected'}`));
  return box;
}
function render() {
  readerButton.textContent=({off:'Readers',opposite:'Facing · columns',stacked:'Facing · stacked',four:'Facing · four'})[readerLayout];
  readerButton.title='Cycle reader layout: columns, stacked, four panels, off';
  readerButton.setAttribute('aria-pressed',String(readerLayout!=='off'));
  spokenButton.setAttribute('aria-pressed',String(showSpoken));
  document.body.dataset.view = view;
  document.getElementById('clean-view').setAttribute('aria-pressed', String(view === 'clean'));
  document.getElementById('list-view').setAttribute('aria-pressed', String(view === 'list'));
  document.getElementById('slots-view').setAttribute('aria-pressed', String(view === 'slots'));
  document.getElementById('slot-setting').hidden=view!=='slots';
  document.getElementById('ink-toggle').disabled=view!=='clean';
  if (!state || !catalog.length) return;
  const selected = state.selected_languages.map(code => catalog.find(l => l.code === code)).filter(Boolean);
  document.getElementById('language-count').textContent = selected.length;
  const spoken={code:'_spoken',name:'Spoken',native:'Original speech',direction:'auto',
    labelFor:code=>catalog.find(language=>language.code===code)?.name || code};
  const available=showSpoken?[...selected,spoken]:selected;
  const columns=readerLayout==='off'?(showSpoken?[spoken,...selected]:selected):readerPanels(available,readerLayout,readerCodes,readerAngles);
  const effectiveView=readerLayout==='off'?view:'clean';
  root.className = `conversation ${effectiveView} count-${columns.length} reader-${readerLayout}`;
  root.classList.toggle('dense-slots',slotCount>4);
  const fragment = document.createDocumentFragment();
  paper.stop();
  if(view==='slots' || view==='clean' || readerLayout!=='off') {
    slots.update(state,columns,readerLayout==='off'?flipped:new Set(),slotCount,effectiveView==='clean' && ink);return;
  }
  const items = paper.visible(state.utterances).slice(-30);
  if (view === 'list') {
    const headers = element('div', `list-heading count-${columns.length}`);
    for (const language of columns) headers.append(heading(language));
    fragment.append(headers);
    for (const item of [...items].reverse()) {
      const row = element('article', `list-row count-${columns.length}`);
      for (const language of columns) {
        const cell = paragraph(item, language);
        cell.dataset.age=item===items.at(-1)?'latest':items.length===30 && item===items[0]?'next':'';
        if (flipped.has(language.code)) cell.classList.add('flipped');
        row.append(cell);
      }
      fragment.append(row);
    }
    root.replaceChildren(fragment);
    return;
  }
}
function setView(next) { slots.signature='';view = next; localStorage.setItem('babblet.view', view); render(); }
document.getElementById('clean-view').addEventListener('click', () => setView('clean'));
document.getElementById('list-view').addEventListener('click', () => setView('list'));
document.getElementById('slots-view').addEventListener('click', () => setView('slots'));
document.getElementById('show-controls').addEventListener('click',()=>setView('slots'));
document.addEventListener('keydown',event=>{
  if(event.key==='Escape' && view==='clean' && !dialog.open) setView('slots');
});
function renderOptions() {
  const query = document.getElementById('language-search').value.trim().toLocaleLowerCase();
  const options = document.getElementById('language-options'); options.replaceChildren();
  const available = (languageMode==='speech'?speechCatalog:catalog).filter(l => `${l.name} ${l.native} ${l.code}`.toLocaleLowerCase().includes(query));
  for (const language of available) {
    const label = element('label', 'language-option');
    const checkbox = element('input'); checkbox.type = 'checkbox'; checkbox.value = language.code;
    checkbox.checked = pendingSelection.has(language.code);
    checkbox.disabled = (languageMode==='speech' && state?.speech?.sync_with_display!==false) || (!checkbox.checked && pendingSelection.size >= 6) ||
      (languageMode==='display' && checkbox.checked && pendingSelection.size===1);
    checkbox.addEventListener('change', () => {
      if (checkbox.checked) pendingSelection.add(language.code); else pendingSelection.delete(language.code);
      renderOptions(); options.querySelector(`input[value="${language.code}"]`)?.focus();
      void saveLanguageSelection();
    });
    const icon = flag(language); icon.alt = '';
    label.title=`${language.name} · ${language.native}`;
    label.append(checkbox, icon, element('span', 'language-name', language.name), element('small', '', language.native));
    options.append(label);
  }
  if (!available.length) options.append(element('p', 'empty', 'No matching languages.'));
  document.getElementById('selection-count').textContent = languageMode==='speech' && !pendingSelection.size ? 'Automatic detection' : `${pendingSelection.size} selected`;
  const linked=state?.speech?.sync_with_display!==false;
  const syncButton=document.getElementById('speech-sync');
  syncButton.setAttribute('aria-pressed',String(linked));
  syncButton.textContent=linked?'Linked · Read and hear the same languages':'Unlinked · Choose spoken languages separately';
  document.getElementById('speech-auto').hidden=languageMode!=='speech' || linked;
  renderSuggestions();
}
function renderSuggestions() {
  const host=document.getElementById('speech-suggestions');
  if(languageMode!=='speech' || state?.speech?.sync_with_display!==false) { host.replaceChildren();return; }
  const suggestions=(state?.speech?.suggested || []).filter(item=>!pendingSelection.has(item.code));
  const signature=JSON.stringify([suggestions.map(item=>item.code),pendingSelection.size]);
  if(host.dataset.signature===signature) return;
  host.dataset.signature=signature;host.replaceChildren();
  if(!suggestions.length) return;
  host.append(element('p','suggestion-label','Detected in recent speech'));
  const chips=element('div','suggestion-chips');
  for(const suggestion of suggestions) {
    const button=element('button','suggestion-chip',`+ ${suggestion.name}`);
    button.type='button';button.disabled=pendingSelection.size>=6;
    button.addEventListener('click',()=>{pendingSelection.add(suggestion.code);renderOptions();void saveLanguageSelection();});
    chips.append(button);
  }
  host.append(chips);
}
function setLanguageMode(mode) {
  languageMode=mode;
  pendingSelection=new Set(languageDrafts[mode] || (mode==='speech' ? (state?.speech?.expected || []) : (state?.selected_languages || ['en','he','ru'])));
  document.getElementById('display-languages-tab').setAttribute('aria-selected',String(mode==='display'));
  document.getElementById('speech-languages-tab').setAttribute('aria-selected',String(mode==='speech'));
  document.getElementById('language-description').textContent=mode==='speech' ?
    'Tap flags to guide speech recognition. Select up to six, or leave empty for automatic detection.' :
    'Tap flags to toggle translation languages. Changes save immediately; keep at least one selected.';
  document.getElementById('speech-auto').hidden=mode!=='speech';
  document.getElementById('speech-suggestions').dataset.signature='';
  document.getElementById('language-search').value = ''; document.getElementById('language-error').textContent = '';
  renderOptions();
}
document.getElementById('display-languages-tab').addEventListener('click',()=>setLanguageMode('display'));
document.getElementById('speech-languages-tab').addEventListener('click',()=>setLanguageMode('speech'));
document.getElementById('automatic-speech').addEventListener('click',()=>{pendingSelection.clear();renderOptions();void saveLanguageSelection();});
document.getElementById('open-languages').addEventListener('click', () => {
  if(!languageSaving) {delete languageDrafts.display;delete languageDrafts.speech;}
  setLanguageMode('display');
  renderOptions(); dialog.showModal(); document.getElementById('language-search').focus();
});
document.getElementById('close-languages').addEventListener('click', () => dialog.close());
document.getElementById('language-search').addEventListener('input', renderOptions);
document.getElementById('language-form').addEventListener('submit',event=>event.preventDefault());
async function refresh() {
  try {
    if (!catalog.length) {
      const response = await fetch('/api/languages');
      if (!response.ok) throw new Error('Languages unavailable');
      catalog = (await response.json()).available;
    }
    if(!speechCatalog.length) {
      const response=await fetch('/api/speech-languages');
      if(!response.ok) throw new Error('Speaking languages unavailable');
      speechCatalog=(await response.json()).available;
    }
    const response = await fetch('/api/snapshot'); if (!response.ok) throw new Error('Connection unavailable');
    state = await response.json();
    const nextPending=JSON.stringify([state.pending_activity,state.translation_activity?.target,state.translation_activity?.utterance_id]);
    if (state.sequence !== sequence || nextPending!==pendingSignature) {
      sequence = state.sequence;pendingSignature=nextPending;render();
    }
    else { void paper.forget(state.utterances); }
    if(dialog.open && languageMode==='speech') renderSuggestions();
    if(inspectDialog.open) renderInspector();
  } catch (_) { processingLabel.textContent = 'Reconnecting…'; }
  setTimeout(refresh, 600);
}
async function refreshMicrophone() {
  let level={active:false,level:0,rms_dbfs:-80,peak_dbfs:-80,clipping:false,label:'No input'};
  try {
    const response=await fetch('/api/audio-level',{signal:AbortSignal.timeout(1500)});
    if(response.ok) level=await response.json();
  } catch(_) { /* A stale/disconnected input must not leave a frozen meter. */ }
  const host=document.getElementById('mic-level');
  host.dataset.state=!level.active?'inactive':(level.clipping?'clipping':'active');
  host.title=level.active ? `Microphone: ${level.rms_dbfs.toFixed(1)} dBFS RMS · peak ${level.peak_dbfs.toFixed(1)} dBFS` : 'No recent microphone audio';
  document.getElementById('mic-level-fill').style.transform=`scaleX(${Math.max(0,Math.min(1,level.level))})`;
  document.getElementById('mic-level-text').textContent=level.label;
  const meter=document.getElementById('mic-level-meter');
  meter.setAttribute('aria-valuenow',String(Math.max(-60,level.rms_dbfs)));
  meter.setAttribute('aria-valuetext',`${level.label}, ${level.rms_dbfs} dBFS`);
  setTimeout(refreshMicrophone,document.hidden?500:100);
}
async function refreshProcessing() {
  try {
    const response=await fetch('/api/processing',{signal:AbortSignal.timeout(1500)});
    if(!response.ok) throw new Error('Activity unavailable');
    const activity=await response.json();
    processingSpinner.hidden=!activity.active;
    statusHost.dataset.active=String(activity.active);
    const label=activity.label+(activity.queued?` · ${activity.queued} queued`:'');
    if(processingLabel.textContent!==label) processingLabel.textContent=label;
    statusHost.title=activity.stages.map(stage=>`${stage.label}: ${stage.elapsed_seconds.toFixed(1)}s`).join(' · ') || activity.label;
  } catch(_) {
    processingSpinner.hidden=true;statusHost.dataset.active='false';
    processingLabel.textContent='Reconnecting…';
  }
  setTimeout(refreshProcessing,document.hidden?750:250);
}
render(); refresh(); refreshMicrophone(); refreshProcessing();
