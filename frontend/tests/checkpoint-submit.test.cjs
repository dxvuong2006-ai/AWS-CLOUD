const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const {webcrypto} = require('node:crypto');
const helpers = require('./checkpoint-helpers.cjs');
function setup(storage = new Map()) {
  const calls = []; let handler = async () => ({id: 1, can_retry: true});
  const sessionStorage = {getItem: k => storage.get(k), setItem: (k,v) => storage.set(k,v), removeItem: k => storage.delete(k)};
  const draftApi = helpers.drafts(sessionStorage, k => k + ':user:1');
  class ApiError extends Error { constructor(status, message) { super(message); this.status = status; } }
  const source = fs.readFileSync(__dirname + '/../src/api/quizzes.api.js', 'utf8')
    .replace(/^import .*;$/gm, '').replace(/export /g, '')
    .replace(/import.meta.env.VITE_USE_MOCK === "true"/g, 'false');
  const api = vm.runInNewContext(source + ';({submitAttempt,readPendingAttempt,fetchSectionQuiz,recoverPendingCheckpoint,fetchAttemptResult})', {
    ApiError, crypto: webcrypto, mockStorageKey: k => k + ':user:1',
    ...draftApi,
    sessionStorage: {getItem: k => storage.get(k), setItem: (k,v) => storage.set(k,v), removeItem: k => storage.delete(k)},
    request: async (path, options) => {calls.push({path, options}); return handler(path, options);},
    serializeAnswers: a => a.map(x => ({question_id: Number(x.question_id), selected_answer: x.selected_option_id})),
    normalizeAttempt: value => value, normalizeQuiz: value => value,
  });
  return {...api, calls, storage, drafts: draftApi, handle: fn => handler = fn};
}
const answers = [{question_id: '7', selected_option_id: 'A'}];
test('double clicks share a request and a network retry preserves exact UUID and payload', async () => {
  const a = setup(); let reject;
  a.handle(() => new Promise((_, r) => reject = r));
  const first = a.submitAttempt('2', answers, '1', '3');
  const second = a.submitAttempt('2', answers, '1', '3');
  assert.equal(a.calls.length, 1);
  const rejectedFirst = assert.rejects(first, /offline/), rejectedSecond = assert.rejects(second, /offline/);
  reject(Error('offline')); await Promise.all([rejectedFirst, rejectedSecond]);
  const body = JSON.stringify(a.calls[0].options.body);
  assert.match(a.readPendingAttempt('2').request_id,
    /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i);
  a.handle(async () => ({id: 4, can_retry: false}));
  await a.submitAttempt('2', [], '1');
  assert.equal(JSON.stringify(a.calls[1].options.body), body);
  assert.equal(a.readPendingAttempt('2'), null);
});
test('refresh recovers a pending low-score result before fetching a locked quiz', async () => {
  const a = setup();
  a.handle(async () => ({id: '2', questions: []}));
  await a.fetchSectionQuiz('5', '1', '3');
  a.handle(async () => {throw Error('response lost');});
  await assert.rejects(a.submitAttempt('2', answers, '1', '3'));
  const previous = a.readPendingAttempt('2').request_id;
  const refreshed = setup(a.storage);
  refreshed.handle(async () => ({id: 10, can_retry: false, remediation_required: true}));
  const recovered = await refreshed.recoverPendingCheckpoint('1', '5');
  assert.equal(recovered.result.id, 10);
  assert.equal(refreshed.calls[0].options.body.request_id, previous);
  assert.equal(refreshed.calls.length, 1);
});
test('definite invalid payload rejection clears pending submission', async () => {
  const a = setup(); a.handle(async () => {throw Object.assign(Error('invalid'), {status: 422});});
  await assert.rejects(a.submitAttempt('2', answers, '1'));
  assert.equal(a.readPendingAttempt('2'), null);
});

test('draft session UUID is submitted and retired only after confirmed result', async () => {
  const a=setup();const quiz={id:'2',questions:[{id:'7',text:'Q',options:[{id:'A',text:'A'}]}]};
  let draft=a.drafts.createCheckpointDraft(quiz,'1','5');
  draft=a.drafts.saveCheckpointDraft(draft,{'7':'A'},0);
  a.handle(async()=>{throw Error('offline');});
  await assert.rejects(a.submitAttempt('2',answers,'1','3',draft.sessionId));
  assert.equal(a.calls[0].options.body.request_id,draft.sessionId);
  assert.ok(a.drafts.restoreCheckpointDraft(quiz,'1','5'));
  a.handle(async()=>({id:9,can_retry:true}));
  await a.submitAttempt('2',answers,'1','3',draft.sessionId);
  assert.equal(a.drafts.restoreCheckpointDraft(quiz,'1','5'),null);
  assert.throws(()=>a.drafts.saveCheckpointDraft(draft,{},0));
});

test('reopen searches owned history pages; missing/forbidden attempts have no cache fallback', async () => {
  const a=setup();a.handle(async path=>path.endsWith('offset=0')?Array.from({length:20},(_,i)=>({id:String(100+i)})):[{id:'8'}]);
  assert.equal((await a.fetchAttemptResult('2','8')).id,'8');assert.equal(a.calls.length,2);
  await assert.rejects(a.fetchAttemptResult('2','999'),e=>e.status===404);
  a.handle(async()=>{throw Object.assign(Error('denied'),{status:403});});
  await assert.rejects(a.fetchAttemptResult('2','8'),e=>e.status===403);
});

test('storage failure after accepted response retains request UUID for safe replay', async () => {
  const a=setup();const set=a.storage.set.bind(a.storage);
  a.storage.set=(key,value)=>{if(key.includes(':submitted:'))throw Error('quota');return set(key,value);};
  a.handle(async()=>({id:15,can_retry:true}));
  await assert.rejects(a.submitAttempt('2',answers,'1'),/quota/);
  const key=a.readPendingAttempt('2').request_id;
  a.storage.set=set;
  assert.equal((await a.submitAttempt('2',answers,'1')).id,15);
  assert.equal(a.calls[1].options.body.request_id,key);
  assert.equal(a.readPendingAttempt('2'),null);
});
