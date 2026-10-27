import test from 'node:test';
import assert from 'node:assert/strict';
import {fitPrefix, columnText, SlotRing, FixedSlots, SelectionQueue, readerPanels, reveal} from '../babblet/static/paper.mjs';

test('ink reveals one readable phrase without word staggering or clipping; facing panels are quieter',t=>{
  const savedDocument=globalThis.document,savedMedia=globalThis.matchMedia;
  const animations=[];
  globalThis.document={createTextNode:text=>({textContent:text}),createElement:()=>({animate:(frames,options)=>animations.push({frames,options})})};
  globalThis.matchMedia=()=>({matches:false});
  t.after(()=>{globalThis.document=savedDocument;globalThis.matchMedia=savedMedia;});
  const node={children:[],replaceChildren(){this.children=[];},append(child){this.children.push(child);}};
  reveal(node,'Several words arrive together.','',false,true,true);
  assert.equal(animations.length,1);
  assert.equal(node.children.at(-1).textContent,'Several words arrive together.');
  assert.ok(animations[0].frames[0].opacity>=.95);
  assert.ok(animations[0].options.duration<=120);
  assert.equal(animations[0].options.delay,undefined);
  assert.ok(animations[0].frames.every(frame=>!('clipPath' in frame)));
  reveal(node,'Several words arrive together.','Several words arrive together.',false,true,true);
  assert.equal(animations.length,1);
  globalThis.matchMedia=()=>({matches:true});
  reveal(node,'Immediate text','',false,true,true);
  assert.equal(node.textContent,'Immediate text');assert.equal(animations.length,1);
});

test('reader panels keep independent language and orientation with safe selection fallback',()=>{
  const available=[{code:'en'},{code:'he'},{code:'cs'}];
  const panels=readerPanels(available,'opposite',['he','he'],[0,180]);
  assert.deepEqual(panels.map(p=>[p.code,p.panelIndex,p.panelAngle]),[['he',0,0],['he',1,180]]);
  const four=readerPanels(available,'four',['removed','he','cs','en'],[]);
  assert.deepEqual(four.map(p=>p.code),['en','he','cs','en']);
  assert.deepEqual(four.map(p=>p.panelAngle),[0,0,180,180]);
  assert.equal(readerPanels([],'opposite',[],[]).length,0);
});

test('immediate flag saves retain click order and snapshot each selection',async()=>{
  const calls=[];let release;
  const queue=new SelectionQueue(async(mode,languages)=>{
    calls.push([mode,languages]);
    if(calls.length===1) await new Promise(resolve=>{release=resolve;});
  });
  const selected=['en'];const first=queue.save('display',selected);
  selected.push('he');const second=queue.save('display',selected);
  await Promise.resolve();assert.deepEqual(calls,[['display',['en']]]);
  release();await Promise.all([first,second]);
  assert.deepEqual(calls,[['display',['en']],['display',['en','he']]]);
});
test('a failed flag save does not block later toggles',async()=>{
  const queue=new SelectionQueue(async(mode,languages)=>{
    if(languages.length===1) throw new Error('offline');return languages;
  });
  await assert.rejects(queue.save('speech',['he']),/offline/);
  assert.deepEqual(await queue.save('speech',[]),[]);
});

// Minimal DOM surface for exercising the real renderer without a browser runtime.
function slotFixture() {
  function element(tag,className='',text='') {
    return {tag,className,textContent:text,children:[],dataset:{},style:{},
      clientHeight:200,scrollHeight:100,
      classList:{contains:name=>className.split(' ').includes(name)},
      setAttribute(){},append(...nodes){this.children.push(...nodes);},
      replaceChildren(...nodes){this.children=nodes;},
      get firstElementChild(){return this.children[0];},
      get lastElementChild(){return this.children.at(-1);}};
  }
  const root=element('main'),hidden=new Set();
  const paper={hidden,visible:items=>items.filter(item=>!hidden.has(item.utterance_id)),
    forget(){},remaining:columnText};
  const renderer=new FixedSlots(root,{element,heading:()=>element('header'),paper});
  const languages=[{code:'_spoken',labelFor:code=>code},{code:'en'},{code:'he'}];
  const item=id=>({utterance_id:id,source_text:id,source_language:'en',translations:{}});
  return {root,renderer,languages,item};
}

test('newest and next-to-replace cues follow FIFO, stay stable on revisions, and avoid fading a single slot',()=>{
  const {renderer,languages,item}=slotFixture();
  const items=['a','b','c'].map(item);
  const update=(rows,count=3)=>renderer.update({utterances:rows},languages,new Set(),count);
  update(items.slice(0,2));
  assert.deepEqual(renderer.cells[0].map(cell=>cell.dataset.age),['','latest','']);
  update(items);
  assert.deepEqual(renderer.cells[0].map(cell=>cell.dataset.age),['next','','latest']);
  items.push(item('d'));update(items);
  assert.deepEqual(renderer.cells[0].map(cell=>cell.dataset.age),['latest','next','']);
  items[2].translations.en={text:'late translation'};update(items);
  for(const cells of renderer.cells) assert.deepEqual(cells.map(cell=>cell.dataset.age),['latest','next','']);
  update(items.slice(-1),1);
  assert.equal(renderer.cells[0][0].dataset.age,'latest');
});

test('capture and decoding show one graphic in the next global slot without advancing FIFO',()=>{
  const {renderer,languages,item}=slotFixture();
  const utterances=['a','b','c'].map(item);
  renderer.update({utterances},languages,new Set(),3);
  const state={utterances,pending_activity:{active:true,label:'Listening…'}};
  renderer.update(state,languages,new Set(),3);
  for(const column of renderer.cells) assert.equal(column[0].lastElementChild.textContent,'');
  assert.equal(renderer.activityCue.dataset.label,'Listening…');
  assert.deepEqual(renderer.ring.slots,['a','b','c']);
  assert.equal(renderer.ring.next,0);
  state.pending_activity.label='Checking Hebrew…';
  renderer.update(state,languages,new Set(),3);
  for(const column of renderer.cells) assert.equal(column[0].lastElementChild.textContent,'');
  assert.equal(renderer.activityCue.dataset.label,'Checking Hebrew…');
  state.utterances.push(item('d'));state.pending_activity={active:false};
  renderer.update(state,languages,new Set(),3);
  for(const column of renderer.cells) assert.deepEqual(column.map(cell=>cell.dataset.utteranceId),['d','b','c']);
});

test('a single refinement graphic stays with its existing row',()=>{
  const {renderer,languages,item}=slotFixture();
  const a=item('a'),b=item('b');
  b.translations.en={status:'pending'};
  renderer.update({utterances:[a,b],pending_activity:{active:true,utterance_id:'b',label:'Refining speech…'}},languages,new Set(),3);
  assert.equal(renderer.activityCue.dataset.row,'1');
  assert.equal(renderer.activityCue.dataset.label,'Refining speech…');
  assert.doesNotMatch(renderer.cells[0][1].firstElementChild.textContent,/Refining/);
  assert.equal(renderer.cells[1][1].lastElementChild.textContent,'');
  assert.equal(renderer.ring.next,2);
});

test('flipping a language never reverses its global slot row order',()=>{
  const {root,renderer,languages,item}=slotFixture();
  renderer.update({utterances:[item('a'),item('b')]},languages,new Set(['he']),3);
  const hebrew=root.children[2];
  assert.equal(hebrew.className,'language-column');
  assert.match(hebrew.children[0].className,/flipped/);
  assert.match(hebrew.children[1].children[0].className,/flipped/);
});

test('two readers can share a language and flip independently without advancing FIFO',()=>{
  const {root,renderer,item}=slotFixture();
  const state={utterances:[item('a'),item('b')]};
  let panels=readerPanels([{code:'en'}],'opposite',['en','en'],[0,180]);
  renderer.update(state,panels,new Set(),2);
  assert.equal(root.children[0].style.transform,'rotate(0deg)');
  assert.equal(root.children[1].style.transform,'rotate(180deg)');
  const slots=[...renderer.ring.slots],next=renderer.ring.next;
  panels=readerPanels([{code:'en'}],'opposite',['en','en'],[180,180]);
  renderer.update(state,panels,new Set(),2);
  assert.equal(root.children[0].style.transform,'rotate(180deg)');
  assert.deepEqual(renderer.ring.slots,slots);assert.equal(renderer.ring.next,next);
});

test('late translations share the utterance row through refinement and wraparound',()=>{
  const {renderer,languages,item}=slotFixture();
  const a=item('a'),b=item('b');
  const update=items=>renderer.update({utterances:items},languages,new Set(),2);
  update([a,b]);
  const cells=renderer.cells.map(column=>[...column]);
  b.translations.he={text:'Hebrew B'};update([a,b]);
  a.translations.en={text:'English A'};update([a,b]);
  assert.equal(renderer.cells[2][1].lastElementChild.textContent,'Hebrew B');
  assert.equal(renderer.cells[1][0].lastElementChild.textContent,'English A');
  const c=item('c');update([a,b,c]);
  a.translations.he={text:'Late overwritten A'};
  c.source_text='Refined C';c.translations.he={text:'Hebrew C'};update([a,b,c]);
  for(let column=0;column<3;column++) {
    assert.equal(renderer.cells[column][0],cells[column][0]);
    assert.deepEqual(renderer.cells[column].map(cell=>cell.dataset.utteranceId),['c','b']);
  }
  assert.equal(renderer.cells[2][0].lastElementChild.textContent,'Hebrew C');
});

test('slots overwrite top to bottom without moving surviving paragraphs',()=>{
  const ring=new SlotRing(3);
  assert.deepEqual(ring.update(['a','b','c']),[]);
  assert.deepEqual(ring.slots,['a','b','c']);
  assert.deepEqual(ring.update(['a','b','c','d']),['a']);
  assert.deepEqual(ring.slots,['d','b','c']);
  assert.deepEqual(ring.update(['b','c','d','e']),['b']);
  assert.deepEqual(ring.slots,['d','e','c']);
});
test('FIFO wraparound replaces only the oldest row and never clears surviving cells',()=>{
  const {root,renderer,languages,item}=slotFixture();
  const items=['a','b','c'].map(item);
  renderer.update({utterances:items},languages,new Set(),3);
  const columns=[...root.children],cells=renderer.cells.map(column=>[...column]);
  for(const [id,expected] of [['d',['d','b','c']],['e',['d','e','c']],
    ['f',['d','e','f']],['g',['g','e','f']]]) {
    items.push(item(id));
    renderer.update({utterances:items},languages,new Set(),3);
    // Also exercise the subsequent snapshot after server cleanup.
    const current=items.filter(value=>expected.includes(value.utterance_id));
    renderer.update({utterances:current},languages,new Set(),3);
    assert.deepEqual(root.children,columns);
    for(let column=0;column<languages.length;column++) {
      assert.deepEqual(renderer.cells[column].map(cell=>cell.dataset.utteranceId),expected);
      for(let row=0;row<3;row++) assert.equal(renderer.cells[column][row],cells[column][row]);
    }
  }
});
test('Clean ink never leaves an overwritten translation in an empty new row',t=>{
  const oldStyle=globalThis.getComputedStyle,oldMedia=globalThis.matchMedia;
  globalThis.getComputedStyle=()=>({direction:'ltr'});
  globalThis.matchMedia=()=>({matches:true});
  t.after(()=>{globalThis.getComputedStyle=oldStyle;globalThis.matchMedia=oldMedia;});
  const {renderer,languages,item}=slotFixture();
  const a=item('a');a.translations.en={text:'Old translation'};
  renderer.update({utterances:[a]},languages,new Set(),1);
  renderer.update({utterances:[a,item('b')]},languages,new Set(),1,true);
  assert.equal(renderer.cells[1][0].lastElementChild.textContent,'');
  assert.equal(renderer.cells[0][0].lastElementChild.textContent,'b');
});
test('refinements and delayed results never reinsert an overwritten paragraph',()=>{
  const ring=new SlotRing(2);
  ring.update(['a','b','c']);
  assert.deepEqual(ring.update(['a','b','c']),[]);
  assert.deepEqual(ring.slots,['c','b']);
  ring.update(['b','c']);
  assert.deepEqual(ring.slots,['c','b']);
});

test('fits at a word boundary and retains a long remainder',()=>{
  const result=fitPrefix('one two three four',text=>text.length<=10);
  assert.equal(result,'one two ');
  assert.equal(('one two three four').slice(result.length),'three four');
});
test('handles unspaced text without splitting a Unicode surrogate pair',()=>{
  const result=fitPrefix('你好🌍再见',text=>Array.from(text).length<=3);
  assert.equal(result,'你好🌍');
});
test('returns the full text when it fits',()=>{
  assert.equal(fitPrefix('שלום עולם',()=>true),'שלום עולם');
});
test('does not separate a Hebrew letter from its vowel marks',()=>{
  assert.equal(fitPrefix('אַבָג',text=>Array.from(text).length<=3),'אַ');
});
test('spoken text and fixed-language translations are distinct columns',()=>{
  const item={source_text:'Bonjour.',translations:{en:{text:'Hello.'}}};
  assert.equal(columnText(item,'_spoken'),'Bonjour.');
  assert.equal(columnText(item,'en'),'Hello.');
});
