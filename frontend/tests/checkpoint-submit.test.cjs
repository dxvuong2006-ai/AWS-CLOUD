const {test} = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const {webcrypto} = require('node:crypto');
function setup(storage = new Map()) {
  const calls = []; let handler = async () => ({id: 1, can_retry: true});
  class ApiError extends Error { constructor(status, message) { super(message); this.status = status; } }
  const source = fs.readFileSync(__dirname + '/../src/api/quizzes.api.js', 'utf8')
    .replace(/^import .*;$/gm, '').replace(/export /g, '')
    .replace(/import.meta.env.VITE_USE_MOCK === "true"/g, 'false');
  const api = vm.runInNewContext(source + ';({submitAttempt,readPendingAttempt,fetchSectionQuiz,recoverPendingCheckpoint})', {
    ApiError, crypto: webcrypto, mockStorageKey: k => k + ':user:1',
    sessionStorage: {getItem: k => storage.get(k), setItem: (k,v) => storage.set(k,v), removeItem: k => storage.delete(k)},
    request: async (path, options) => {calls.push({path, options}); return handler(path, options);},
    serializeAnswers: a => a.map(x => ({question_id: Number(x.question_id), selected_answer: x.selected_option_id})),
    normalizeAttempt: value => value, normalizeQuiz: value => value,
  });
  return {...api, calls, storage, handle: fn => handler = fn};
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
  assert.ok(a.readPendingAttempt('2').request_id);
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
