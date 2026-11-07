const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.join(__dirname, '../src');
function setup() {
  let user='one', blocked=false, fail=false;
  const storage=new Map();
  const localStorage={getItem:key=>storage.get(key)??null,setItem:(key,value)=>{if(fail)throw Error('Quota');storage.set(key,value);}};
  class ApiError extends Error {constructor(status,message){super(message);this.status=status;}}
  const context=vm.createContext({URL,localStorage,mockStorageKey:key=>`${key}:${user}`,ApiError,
    lessons:JSON.parse(fs.readFileSync(path.join(root,'mocks/lessons.mock.json'))),
    requireMockEnrollment:()=>{if(blocked)throw new ApiError(403,'Locked');return {sections:[{id:'s1',lessons:[{id:'l1'}]}]};}});
  const load=(file,exports)=>vm.runInContext(fs.readFileSync(path.join(root,file),'utf8').replace(/^import .*;\r?$/gm,'').replace(/import.meta.env.VITE_USE_MOCK === "true"/g,'true').replace(/export /g,'')+`;({${exports}})`,context);
  return {...load('utils/flashcardProgress.js','flashcardKey,freshFlashcardProgress,restoreFlashcardProgress,saveFlashcardProgress,rateFlashcard,reviewFlashcards,remediationReturn'),
    ...load('api/flashcards.api.js','fetchFlashcards,normalizeFlashcards'),storage,setUser:value=>user=value,setBlocked:value=>blocked=value,setFailure:value=>fail=value};
}
const cards=[{id:'a'},{id:'b'},{id:'c'}];
test('progress persists across reload and is isolated by owner, lesson, revision and remediation session',()=>{
  const a=setup();const key=a.flashcardKey('1','s1','l1','v1','session1');
  const p=a.rateFlashcard(a.freshFlashcardProgress(cards),'review');a.saveFlashcardProgress(key,p);
  assert.equal(a.restoreFlashcardProgress(key,cards).ratings.a,'review');
  assert.equal(a.restoreFlashcardProgress(key,cards).index,1);
  for(const args of [['1','s1','l2','v1','session1'],['1','s1','l1','v2','session1'],['1','s1','l1','v1','session2']]) assert.notEqual(a.flashcardKey(...args),key);
  a.setUser('two');assert.notEqual(a.flashcardKey('1','s1','l1','v1','session1'),key);
  assert.equal(Object.keys(a.restoreFlashcardProgress(a.flashcardKey('1','s1','l1','v1','session1'),cards).ratings).length,0);
});
test('skipping cards does not complete deck; review only repeats weak cards',()=>{
  const a=setup();let p=a.freshFlashcardProgress(cards);p.index=2;
  p=a.rateFlashcard(p,'remembered');assert.equal(p.completed,false);assert.equal(p.index,0);
  p=a.rateFlashcard(p,'review');p=a.rateFlashcard(p,'remembered');assert.equal(p.completed,true);
  p=a.reviewFlashcards(p,cards);assert.deepEqual(Array.from(p.queue),['a']);assert.equal(p.completed,false);
  p=a.rateFlashcard(p,'remembered');assert.equal(p.completed,true);assert.equal(Object.values(p.ratings).filter(x=>x==='remembered').length,3);
});
test('storage failures surface; corrupt or stale data cannot crash deck navigation',()=>{
  const a=setup();a.setFailure(true);assert.throws(()=>a.saveFlashcardProgress('key',a.freshFlashcardProgress(cards)),/Quota/);
  a.setFailure(false);a.storage.set('key','broken');assert.throws(()=>a.restoreFlashcardProgress('key',cards));
  a.storage.set('key',JSON.stringify({queue:['deleted'],index:99,ratings:{},completed:true}));
  assert.equal(a.restoreFlashcardProgress('key',cards).index,0);
});
test('API rejects unpublished, mismatched and duplicate cards; mock enforces access',async()=>{
  const a=setup();const data={course_id:'1',section_id:'s1',lesson_id:'l1',publication_status:'PUBLISHED',revision:'v1',cards:[{id:'a',front:'Q',back:'A'}]};
  assert.equal(a.normalizeFlashcards(data,'1','s1','l1').cards.length,1);
  assert.throws(()=>a.normalizeFlashcards({...data,publication_status:'DRAFT'},'1','s1','l1'),e=>e.status===403);
  assert.throws(()=>a.normalizeFlashcards(data,'2','s1','l1'),e=>e.status===502);
  assert.throws(()=>a.normalizeFlashcards({...data,cards:[...data.cards,...data.cards]},'1','s1','l1'),e=>e.status===502);
  assert.ok((await a.fetchFlashcards('1','s1','l1')).cards.length);
  await assert.rejects(()=>a.fetchFlashcards('1','s1','l2'),e=>e.status===404);
  a.setBlocked(true);await assert.rejects(()=>a.fetchFlashcards('1','s1','l1'),e=>e.status===403);
});
test('remediation return retains session and rejects external or unrelated courses',()=>{
  const a=setup();assert.equal(a.remediationReturn('1','attempt-session','/courses/1/review?step=2'),'/courses/1/review?step=2&remediationSessionId=attempt-session');
  for(const target of ['https://evil.example','//evil.example','/courses/2/review','/courses/1/../../login']) assert.equal(a.remediationReturn('1','x',target),null);
  assert.equal(a.remediationReturn('1','','/courses/1/review'),null);
});
