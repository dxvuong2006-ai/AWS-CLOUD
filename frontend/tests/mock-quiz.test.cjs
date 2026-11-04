const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.join(__dirname, '../src');
const courses = JSON.parse(fs.readFileSync(path.join(root, 'mocks/courses.mock.json')));
const quizData = JSON.parse(fs.readFileSync(path.join(root, 'mocks/quiz.mock.json')));
function setup(delay = fn => fn()) {
  let account = 'one';
  const completed = new Set(), storage = {};
  class ApiError extends Error { constructor(status, detail) { super(detail); this.status = status; } }
  const context = vm.createContext({
    courses, quizData, ApiError, mockStorageKey: key => key + account, setTimeout: delay,
    localStorage: { getItem: k => storage[k] ?? null, setItem: (k,v) => storage[k] = v },
    request: () => { throw Error('Unexpected network request'); },
    fetchCourseProgress: async id => ({lessons: courses.find(c => c.id === id).sections.flatMap(s => s.lessons).map(l => ({lesson_id:l.id,completed:completed.has(l.id)}))}),
  });
  let source = fs.readFileSync(path.join(root, 'api/quizzes.api.js'), 'utf8')
    .split(String.fromCharCode(10)).filter(line => !line.startsWith('import ')).join(String.fromCharCode(10))
    .replace(/import.meta.env.VITE_USE_MOCK === "true"/g, 'true')
    .replace(/export /g, '');
  const api = vm.runInContext(source + ';({fetchSectionQuiz, submitAttempt})', context);
  return { ...api, completed, setAccount: value => { account = value; } };
}
test('each section has a distinct valid quiz', () => {
  const ids = new Set();
  for (const course of courses) for (const section of course.sections) {
    const q = quizData[course.id + ':' + section.id];
    assert.ok(q && q.questions.length >= 5);
    assert.ok(!ids.has(q.id)); ids.add(q.id);
    assert.equal(new Set(q.questions.map(x=>x.id)).size, q.questions.length);
    for (const question of q.questions) assert.ok(question.options.some(o=>o.id===question.correct_option_id));
  }
});
test('direct access, current lesson and courses remain isolated', async () => {
  const a = setup();
  await assert.rejects(()=>a.fetchSectionQuiz('s1','1'), e=>e.status===403);
  a.completed.add('l1');
  const cloud = await a.fetchSectionQuiz('s1','1');
  assert.equal(cloud.id,'quiz-cloud-s1');
  assert.ok(!('correct_option_id' in cloud.questions[0]));
  await assert.rejects(()=>a.fetchSectionQuiz('s1','1','l2'), e=>e.status===403);
  await assert.rejects(()=>a.fetchSectionQuiz('s1','2'), e=>e.status===403);
  a.completed.add('l4');
  assert.equal((await a.fetchSectionQuiz('s1','2','l4')).id,'quiz-docker-s1');
  await assert.rejects(()=>a.submitAttempt(cloud.id,[],'2','l4'), e=>e.status===404);
});
test('grading, unanswered and attempt counters', async () => {
  const a=setup(); a.completed.add('l1'); a.completed.add('l4');
  const q=quizData['1:s1'];
  const answers=q.questions.map(x=>({question_id:x.id,selected_option_id:x.correct_option_id}));
  const pass=await a.submitAttempt(q.id,answers,'1','l1');
  assert.equal(pass.score_percent,100); assert.equal(pass.attempt_number,1);
  const fail=await a.submitAttempt(q.id,[],'1');
  assert.equal(fail.score_percent,0); assert.equal(fail.attempt_number,2);
  assert.equal((await a.submitAttempt('quiz-docker-s1',[],'2')).attempt_number,1);
  await assert.rejects(()=>a.submitAttempt(q.id,[answers[0],answers[0]],'1'),e=>e.status===400);
});


test('an in-flight submission cannot be credited to a different account', async () => {
  const pending=[];
  const a=setup(fn=>pending.push(fn)); a.completed.add('l1');
  const request=a.submitAttempt('quiz-cloud-s1',[],'1','l1');
  a.setAccount('two');
  pending.shift()();
  await assert.rejects(()=>request,e=>e.status===401);
});
