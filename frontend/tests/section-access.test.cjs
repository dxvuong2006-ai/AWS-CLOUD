const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname, '../src/utils/sectionAccess.js'), 'utf8').replace(/export /g, '');
const { sectionAccess, nextLesson } = vm.runInNewContext(source + ';({sectionAccess,nextLesson})');
const course = {status:'PUBLISHED', sections:[{id:'first',lessons:[{id:'a'},{id:'b'}]},{id:'second',lessons:[{id:'c'}]}]};
test('access requires published course, enrollment and explicit server unlock', () => {
  assert.equal(sectionAccess(course,null,'first').allowed,false);
  assert.equal(sectionAccess(course,{},'first').allowed,false);
  const enrollment={unlocked_section_ids:['first']};
  assert.equal(sectionAccess(course,enrollment,'first').allowed,true);
  assert.equal(sectionAccess(course,enrollment,'second').allowed,false);
  assert.equal(sectionAccess({...course,status:'DRAFT'},enrollment,'first').allowed,false);
  assert.equal(sectionAccess(course,enrollment,'missing').missing,true);
  assert.equal(sectionAccess(course,enrollment,'second').previous.id,'first');
});
test('next lesson follows actual section order and stops at end', () => {
  assert.equal(nextLesson(course.sections,'a').id,'b');
  assert.equal(nextLesson(course.sections,'b').id,'c');
  assert.equal(nextLesson(course.sections,'c'),null);
  assert.equal(nextLesson(course.sections,'missing'),null);
});
