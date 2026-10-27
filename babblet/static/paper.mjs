// Text and page state are transient. Only display preferences use localStorage.
export class SelectionQueue {
  constructor(send) { this.send=send;this.tail=Promise.resolve(); }
  save(mode,languages) {
    const selection=[...languages];
    const result=this.tail.then(()=>this.send(mode,selection));
    this.tail=result.catch(()=>{});
    return result;
  }
}

export function columnText(item,code) {
  return code==='_spoken' ? (item.source_text || '') : (item.translations[code]?.text || '');
}

export function readerPanels(languages,layout,codes=[],angles=[]) {
  if(!languages.length) return [];
  return Array.from({length:layout==='four'?4:2},(_,index)=>({
    ...(languages.find(language=>language.code===codes[index]) || languages[index%languages.length]),
    panelIndex:index,panelAngle:angles[index] ?? (layout==='four'?(index>=2?180:0):layout==='stacked'?(index===0?180:0):(index===1?180:0))
  }));
}

// Keep positions stable across revisions and delayed translation responses.
export class SlotRing {
  constructor(count) { this.slots=Array(count).fill(null);this.next=0;this.seen=new Set(); }
  update(ids) {
    const existing=new Set(ids),evicted=[];
    for(const id of this.seen) if(!existing.has(id)) this.seen.delete(id);
    this.slots=this.slots.map(id=>existing.has(id)?id:null);
    for(const id of ids) {
      if(this.seen.has(id)) continue;
      this.seen.add(id);
      const old=this.slots[this.next];
      if(old) evicted.push(old);
      this.slots[this.next]=id;
      this.next=(this.next+1)%this.slots.length;
    }
    return evicted;
  }
}

export class FixedSlots {
  constructor(root,{element,heading,paper}) {
    this.root=root;this.element=element;this.heading=heading;this.paper=paper;
    this.ring=null;this.signature='';this.cells=[];this.previous=new Map();
  }
  update(state,languages,flipped,count,ink=false) {
    if(!this.ring || this.ring.slots.length!==count) this.ring=new SlotRing(count);
    const items=this.paper.visible(state.utterances);
    for(const id of this.ring.update(items.map(item=>item.utterance_id))) this.paper.hidden.add(id);
    void this.paper.forget(state.utterances);
    const signature=JSON.stringify([languages.map(l=>[l.code,l.panelIndex,l.panelAngle]),[...flipped],count]);
    if(signature!==this.signature || !this.root.firstElementChild?.classList.contains('language-column')) {
      this.signature=signature;this.cells=[];this.previous.clear();this.root.replaceChildren();
      for(const language of languages) {
        const column=this.element('section','language-column');
        if(language.panelIndex!==undefined) {
          column.className+=' reader-panel';
          column.style.transform=`rotate(${language.panelAngle}deg)`;
        }
        const flip=flipped.has(language.code)?' flipped':'';
        const header=this.heading(language);
        header.className+=flip;
        column.setAttribute('aria-label',language.name);column.append(header);
        const body=this.element('div','fixed-slots');body.style.gridTemplateRows=`repeat(${count},minmax(0,1fr))`;
        const cells=[];
        for(let index=0;index<count;index++) {
          const box=this.element('div',`fixed-slot${flip}`);box.dataset.slot=String(index+1);
          box.append(this.element('small','source-language','\u00a0'),this.element('p'));
          body.append(box);cells.push(box);
        }
        column.append(body);this.root.append(column);this.cells.push(cells);
      }
      this.activityCue=this.element('img','work-cue');
      this.activityCue.alt='';this.root.append(this.activityCue);
    }
    // Allocate once per utterance, then fill every language at that global row.
    // Translation completion, refinement and column flipping never advance it.
    const pending=state.pending_activity;
    let pendingIndex=pending?.active ? this.ring.slots.indexOf(pending.utterance_id) : -1;
    const placeholder=pending?.active && pendingIndex<0;
    if(placeholder) pendingIndex=this.ring.next;
    const workIndex=pending?.active?pendingIndex:this.ring.slots.indexOf(state.translation_activity?.utterance_id);
    const workLabel=pending?.active?pending.label:'Translating…';
    const level=workLabel.includes('Listening')?1:workLabel.includes('Transcribing')?2:pending?.active?3:4;
    this.activityCue.dataset.row=String(workIndex);
    this.activityCue.dataset.label=workLabel;
    this.activityCue.setAttribute('aria-label',workLabel);
    this.activityCue.title=workLabel;
    this.activityCue.src=`/art/work-${level}.svg`;
    this.activityCue.style.display=workIndex>=0?'block':'none';
    this.activityCue.style.top=`calc(var(--slot-header,92px) + (100% - var(--slot-header,92px) - 24px) * ${workIndex+.25} / ${count})`;
    const latestId=items.findLast(item=>this.ring.slots.includes(item.utterance_id))?.utterance_id;
    const latestIndex=latestId ? this.ring.slots.indexOf(latestId) : -1;
    const nextIndex=this.ring.slots[this.ring.next] && this.ring.next!==latestIndex ? this.ring.next : -1;
    this.ring.slots.forEach((id,index)=>{
      const isPlaceholder=placeholder && index===pendingIndex;
      const item=isPlaceholder?null:items.find(value=>value.utterance_id===id);
      languages.forEach((language,column)=>{
        const box=this.cells[column][index];
        const spoken=language.code==='_spoken',p=box.lastElementChild;
        box.dataset.utteranceId=isPlaceholder?'':id || '';box.dataset.phase=item?.phase || '';
        box.dataset.age=id && index===latestIndex?'latest':id && index===nextIndex?'next':'';
        box.lang=spoken ? (item?.source_language || '') : language.code;
        box.dir=spoken?'auto':language.direction;
        const result=item?.translations[language.code];
        let caption=spoken && item ? language.labelFor(item.source_language) : '\u00a0';
        box.firstElementChild.textContent=caption;
        const text=item ? this.paper.remaining(item,language.code) : '';
        const shown=isPlaceholder?'':text;
        box.dataset.activity=String(isPlaceholder);
        const key=`${column}|${index}`,previous=this.previous.get(key);
        if(previous?.id!==id) p.textContent='';
        if(ink && !isPlaceholder) reveal(p,shown,previous?.id===id?previous.text:'',getComputedStyle(p).direction==='rtl',true,language.panelIndex!==undefined);
        else p.textContent=shown;
        this.previous.set(key,{id,text:shown});
        // Fit within the fixed rectangle; never move a neighbouring slot.
        let size=24;p.style.fontSize=`${size}px`;
        while(size>12 && box.scrollHeight>box.clientHeight+1) p.style.fontSize=`${--size}px`;
        box.dataset.overflow=String(box.scrollHeight>box.clientHeight+1);
        box.title=box.dataset.overflow==='true'?text:'';
      });
    });
  }
}

export function fitPrefix(text, fits) {
  if (fits(text)) return text;
  const characters = [...new Intl.Segmenter(undefined,{granularity:'grapheme'}).segment(text)]
    .map(part=>part.segment);
  let low = 0, high = characters.length;
  while (low < high) {
    const middle = Math.ceil((low + high) / 2);
    if (fits(characters.slice(0, middle).join(''))) low = middle;
    else high = middle - 1;
  }
  let prefix = characters.slice(0, low).join('');
  const boundary = prefix.search(/\s+\S*$/u);
  if (boundary > prefix.length / 2) prefix = prefix.slice(0, boundary + 1);
  return prefix;
}

export function reveal(node, text, previous, rtl, enabled, quiet=false) {
  if (text === previous) return;
  node.replaceChildren();
  if (!enabled || matchMedia('(prefers-reduced-motion: reduce)').matches) {
    node.textContent = text; return;
  }
  let common = 0;
  while (common < text.length && common < previous.length && text[common] === previous[common]) common++;
  const boundary = text.lastIndexOf(' ', common);
  common = boundary >= 0 ? boundary + 1 : 0;
  node.append(document.createTextNode(text.slice(0, common)));
  // Keep the phrase readable from its first frame. One inline span preserves
  // natural wrapping and script shaping, with no per-word sweep or delay.
  const ink = document.createElement('span');
  ink.className = 'ink-phrase'; ink.textContent = text.slice(common); node.append(ink);
  ink.animate([{opacity:quiet ? .96 : .85},{opacity:1}],
    {duration:quiet ? 100 : 160,easing:'ease-out'});
}

export class RollingPaper {
  constructor(root, {element, heading, getState, onError}) {
    this.root=root; this.element=element; this.heading=heading; this.getState=getState; this.onError=onError;
    this.hidden=new Set(); this.offsets=new Map(); this.previous=new Map();
    this.trims=new Map();
    this.timer=null; this.flushing=false; this.active=false; this.ink=true;
    this.pageNumber=1;
  }
  visible(items) { return items.filter(item=>!this.hidden.has(item.utterance_id)); }
  remaining(item,code) {
    const offset=this.offsets.get(`${item.utterance_id}|${code}`);
    return columnText(item,code).slice(offset?.revision===item.revision?offset.count:0);
  }
  stop() { this.active=false; clearTimeout(this.timer); this.timer=null; this.previous.clear(); }
  async forget(items) {
    if (this.flushing) return;
    const receipts=items.filter(item=>this.hidden.has(item.utterance_id)
      && ['final','unrefined'].includes(item.phase || 'final'))
      .map(item=>({utterance_id:item.utterance_id,revision:item.revision}));
    for(const item of items) {
      const trim=this.trims.get(item.utterance_id);
      if(trim && trim.revision!==item.revision) this.trims.delete(item.utterance_id);
      else if(trim && ['final','unrefined'].includes(item.phase)) receipts.push(trim);
    }
    if (!receipts.length) return;
    this.flushing=true;
    try {
      const response=await fetch('/api/rollover',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({utterances:receipts})});
      if (!response.ok) throw new Error('Page cleared; retrying memory cleanup');
    } catch(error) { this.onError(error.message); }
    finally { this.flushing=false; }
  }
  update(state,languages,flipped,ink) {
    this.active=true; this.ink=ink;
    this.languages=languages; this.flipped=flipped;
    const existing=new Set(state.utterances.map(item=>item.utterance_id));
    for(const uid of this.hidden) if(!existing.has(uid)) this.hidden.delete(uid);
    for(const uid of this.trims.keys()) if(!existing.has(uid)) this.trims.delete(uid);
    for(const key of this.offsets.keys()) if(!existing.has(key.split('|')[0])) this.offsets.delete(key);
    void this.forget(state.utterances);
    this.draw(state);
  }
  draw(state) {
    clearTimeout(this.timer); this.timer=null;
    const previous=this.previous; this.previous=new Map();
    this.root.replaceChildren();
    this.root.dataset.page=String(this.pageNumber);
    const bodies=[];
    for(const language of this.languages) {
      const column=this.element('section',`language-column${this.flipped.has(language.code)?' flipped':''}`);
      column.setAttribute('aria-label',language.name);
      column.append(this.heading(language));
      const body=this.element('div','paragraphs');
      column.append(body);this.root.append(column);bodies.push(body);
    }
    const fits=()=>bodies.every(body=>body.scrollHeight<=body.clientHeight+1);
    const pageItems=[], advances=[];
    let overflow=false;
    for(const item of this.visible(state.utterances)) {
      const nodes=[],texts=[];
      this.languages.forEach((language,index)=>{
        const box=this.element('div',`paragraph phase-${item.phase || 'final'}`);
        const spoken=language.code==='_spoken';
        box.lang=spoken ? item.source_language : language.code;
        box.dir=spoken ? 'auto' : language.direction;box.dataset.utteranceId=item.utterance_id;
        const key=`${item.utterance_id}|${language.code}`;
        let offset=this.offsets.get(key);
        if(offset && offset.revision!==item.revision) { this.offsets.delete(key);offset=null; }
        const full=columnText(item,language.code);
        const text=full.slice(offset?.count || 0);
        const p=this.element('p','',text || (item.translations[language.code]?.status==='pending'?'…':''));
        const sourceLabel=this.element('small','source-language',
          spoken && text ? language.labelFor(item.source_language) : '\u00a0');
        if(!spoken) sourceLabel.setAttribute('aria-hidden','true');
        box.append(sourceLabel);
        box.append(p);bodies[index].append(box);nodes.push(box);texts.push({key,text,p,language,full,offset});
      });
      if(!fits() && pageItems.length) {
        nodes.forEach(node=>node.remove());overflow=true;break;
      }
      let split=false;
      if(!fits()) {
        texts.forEach((entry,index)=>{
          const prefix=fitPrefix(entry.text,value=>{
            entry.p.textContent=value;
            return bodies[index].scrollHeight<=bodies[index].clientHeight+1;
          });
          // On tiny windows, always advance by at least a complete Unicode character.
          entry.shown=prefix || [...new Intl.Segmenter(undefined,{granularity:'grapheme'})
            .segment(entry.text)].slice(0,1).map(part=>part.segment).join('');
          entry.p.textContent=entry.shown;
          advances.push({key:entry.key,revision:item.revision,
            count:(entry.offset?.count || 0)+entry.shown.length});
          if(entry.shown.length<entry.text.length) split=true;
        });
      }
      for(const entry of texts) {
        const shown=entry.shown ?? entry.text;
        const cacheKey=`${entry.key}|${entry.offset?.count || 0}`;
        reveal(entry.p,shown,previous.get(cacheKey)||'',getComputedStyle(entry.p).direction==='rtl',this.ink);
        this.previous.set(cacheKey,shown);
      }
      // Keep each original paragraph level with its corresponding translations.
      const rowHeight=Math.ceil(Math.max(...nodes.map(node=>node.getBoundingClientRect().height)));
      nodes.forEach(node=>{node.style.minHeight=`${rowHeight}px`;});
      if(split) { overflow=true;break; }
      pageItems.push(item);
    }
    if(overflow) {
      const words=Math.max(0,...bodies.map(body=>[...new Intl.Segmenter(undefined,{granularity:'word'})
        .segment(body.textContent)].filter(part=>part.isWordLike).length));
      const readingPause=Math.max(2500,Math.min(12000,words*200));
      const delay=readingPause+(this.ink && !matchMedia('(prefers-reduced-motion: reduce)').matches?1300:0);
      this.timer=setTimeout(()=>{
        if(!this.active) return;
        pageItems.forEach(item=>this.hidden.add(item.utterance_id));
        advances.forEach(offset=>this.offsets.set(offset.key,{revision:offset.revision,count:offset.count}));
        for(const offset of advances) {
          const [uid,code]=offset.key.split('|');
          const item=this.getState().utterances.find(value=>value.utterance_id===uid);
          if(!item) continue;
          const trim=this.trims.get(uid) || {utterance_id:uid,revision:offset.revision,consumed:{}};
          trim.consumed[code]=Array.from(columnText(item,code).slice(0,offset.count)).length;
          this.trims.set(uid,trim);
        }
        this.previous.clear();this.pageNumber++;
        const current=this.getState();
        void this.forget(current.utterances);
        this.draw(current);
      },delay);
    }
  }
}
