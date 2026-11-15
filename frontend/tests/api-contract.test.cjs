const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../src/api/normalizers.js'),'utf8').replace(/export /g,'');
const api=vm.runInNewContext(source+';({normalizeQuiz,serializeAnswers,normalizeAttempt,normalizeProgress})');
test('canonical wire quiz and answer mapping preserve option text',()=>{
 const quiz=api.normalizeQuiz({id:2,title:'Quiz',questions:[{id:7,question:'Q',options:['A','B'],topic:'Topic'}]});
 assert.equal(quiz.id,'2'); assert.equal(quiz.questions[0].options[1].id,'B');
 const payload=api.serializeAnswers([{question_id:'7',selected_option_id:'B'}]);
 assert.equal(payload[0].question_id,7); assert.equal(payload[0].selected_answer,'B');
 assert.throws(()=>api.serializeAnswers([{question_id:'q7',selected_option_id:'B'}]));
 const result=api.normalizeAttempt({id:1,score:'0.00',passed:false,attempt_number:1,answers:[{question_id:7,selected_answer:null,is_correct:false}]},quiz);
 assert.equal(result.score_percent,0); assert.equal(result.total_questions,1);
 assert.equal(result.review_concepts[0].concept,'Topic');
});
test('progress IDs match route strings without recomputing completion',()=>{
 const p=api.normalizeProgress({course_id:1,overall_percent:90,lessons:[{lesson_id:3,completed:false}]});
 assert.equal(p.course_id,'1'); assert.equal(p.lessons[0].lesson_id,'3'); assert.equal(p.lessons[0].completed,false);
});
