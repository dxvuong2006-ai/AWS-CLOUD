const {test} = require('node:test'), assert = require('node:assert/strict');
const fs = require('node:fs'), vm = require('node:vm');
const {drafts} = require('./checkpoint-helpers.cjs');
const quiz = {id:'quiz-1', questions:[{id:'q1',text:'First',options:[{id:'a',text:'A'},{id:'b',text:'B'}]},
  {id:'q2',text:'Second',options:[{id:'c',text:'C'},{id:'d',text:'D'}]}]};
function setup() {
  let user='one', fail=false; const storage=new Map();
  const memory={getItem:k=>storage.get(k),setItem:(k,v)=>{if(fail)throw Error('quota');storage.set(k,v);},removeItem:k=>storage.delete(k)};
  const scope=k=>k+':user:'+user;
  return {api:drafts(memory,scope),reload:()=>drafts(memory,scope),setUser:v=>user=v,fail:v=>fail=v};
}
test('choices and position survive reload, isolated by user, quiz and course',()=>{
  const a=setup();let d=a.api.createCheckpointDraft(quiz,'1','s1');
  d=a.api.saveCheckpointDraft(d,{q1:'b',q2:'c'},1);
  const restored=a.reload().restoreCheckpointDraft(quiz,'1','s1');
  assert.equal(restored.sessionId,d.sessionId);assert.equal(restored.answers.q1,'b');assert.equal(restored.index,1);
  assert.equal(a.api.restoreCheckpointDraft(quiz,'2','s1'),null);
  assert.equal(a.api.restoreCheckpointDraft({...quiz,id:'quiz-2'},'1','s1'),null);
  a.setUser('two');assert.equal(a.api.restoreCheckpointDraft(quiz,'1','s1'),null);
  assert.throws(()=>a.api.saveCheckpointDraft(d,{},0));
  a.setUser('one');assert.ok(a.api.restoreCheckpointDraft(quiz,'1','s1'));
});
test('submitted sessions cannot be restored or resurrected; new attempt stays independent',()=>{
  const a=setup();const old=a.api.createCheckpointDraft(quiz,'1','s1');
  a.api.saveCheckpointDraft(old,{q1:'a'},0);
  a.api.completeCheckpointDraft(quiz.id,old.sessionId,'attempt-1');
  assert.equal(a.api.restoreCheckpointDraft(quiz,'1','s1'),null);
  assert.throws(()=>a.api.saveCheckpointDraft(old,{q2:'d'},1));
  const next=a.api.createCheckpointDraft(quiz,'1','s1');assert.notEqual(next.sessionId,old.sessionId);
  a.api.completeCheckpointDraft(quiz.id,old.sessionId,'attempt-1');
  assert.equal(a.api.restoreCheckpointDraft(quiz,'1','s1').sessionId,next.sessionId);
  assert.deepEqual(Object.keys(next.answers),[]);
});
test('quota failure keeps last durable choices; a changed quiz cannot reuse the old draft',()=>{
  const a=setup();let d=a.api.createCheckpointDraft(quiz,'1','s1');d=a.api.saveCheckpointDraft(d,{q1:'a'},0);
  a.fail(true);assert.throws(()=>a.api.saveCheckpointDraft(d,{q1:'b'},0),/quota/);
  assert.equal(a.api.restoreCheckpointDraft(quiz,'1','s1').answers.q1,'a');a.fail(false);
  const changed={...quiz,questions:quiz.questions.slice(1)};
  assert.throws(()=>a.api.restoreCheckpointDraft(changed,'1','s1'));
});

const source=fs.readFileSync(__dirname+'/../src/api/normalizers.js','utf8').replace(/export /g,'');
const {normalizeAttempt,normalizeQuiz}=vm.runInNewContext(source+';({normalizeAttempt,normalizeQuiz})');
test('review uses post-submit fields and preserves unanswered/wrong; public quiz strips solutions',()=>{
  const question={id:7,question:'Public Q',options_json:['A','B'],correct_answer:'B',explanation:'secret'};
  const publicQuiz=normalizeQuiz({id:1,questions:[question]});
  assert.equal(publicQuiz.questions[0].explanation,undefined);assert.equal(publicQuiz.questions[0].correct_answer,undefined);
  const result=normalizeAttempt({id:9,score:0,passed:false,can_retry:false,remediation_required:true,
    answers:[{question_id:7,question_text:'Snapshot Q',selected_answer:null,correct_answer:'B',explanation:'Because B',is_correct:false}]},publicQuiz);
  assert.equal(result.question_results[0].text,'Snapshot Q');
  assert.equal(result.question_results[0].selected_answer,null);assert.equal(result.question_results[0].explanation,'Because B');
  const missing=normalizeAttempt({id:9,score:0,passed:false,answers:[{question_id:7,is_correct:false}]});
  assert.equal(missing.question_results[0].explanation,null);assert.equal(missing.question_results[0].correct_answer,null);
});
test('three result bands respect server passed flag instead of granting a client pass',()=>{
  const source=fs.readFileSync(__dirname+'/../src/utils/scoreBand.js','utf8').replace(/export /g,'');
  const {getScoreBand}=vm.runInNewContext(source+';({getScoreBand})');
  assert.equal(getScoreBand(80,{passed:true}).band,'PASS');
  assert.equal(getScoreBand(60,{passed:false}).band,'REVIEW');
  assert.equal(getScoreBand(40,{passed:false}).band,'REMEDIATION');
  assert.equal(getScoreBand(100,{passed:false}).isPassing,false);
});
