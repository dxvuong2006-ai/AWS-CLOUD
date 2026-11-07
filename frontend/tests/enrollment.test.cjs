const {test}=require("node:test");
const assert=require("node:assert/strict"), fs=require("node:fs"), vm=require("node:vm");
const courses=require("../src/mocks/courses.mock.json");
function setup(){
  let account="one"; const storage=new Map();
  class ApiError extends Error{constructor(status,message){super(message);this.status=status;}}
  const source=fs.readFileSync(__dirname+"/../src/mocks/enrollment.mock.js","utf8").replace(/^import .*;$/gm,"").replace(/export /g,"");
  const api=vm.runInNewContext(source+";({mockEnroll,mockEnrollments,mockRecordPass,mockUnlockedSections,requireMockEnrollment})",{
    courses,ApiError,mockStorageKey:key=>key+account,localStorage:{getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v)}});
  return {...api,setAccount:value=>account=value};
}
test("enrollment is idempotent, persistent and account isolated",()=>{
  const a=setup(); assert.throws(()=>a.requireMockEnrollment("1"),e=>e.status===403);
  a.mockEnroll("1");const date=a.mockEnroll("1").enrolled_at;
  assert.equal(Object.keys(a.mockEnrollments()).length,1);
  assert.equal(a.mockEnroll("1").enrolled_at,date);
  a.setAccount("two");assert.throws(()=>a.requireMockEnrollment("1"),e=>e.status===403);
  a.setAccount("one");assert.equal(a.requireMockEnrollment("1").id,"1");
  assert.throws(()=>a.mockEnroll("3"),e=>e.status===404);
});
test("only checkpoint passes unlock later sections, separately per course",()=>{
  const a=setup();a.mockEnroll("1");a.mockEnroll("2");
  assert.throws(()=>a.requireMockEnrollment("1","s2"),e=>e.status===403);
  a.mockRecordPass("2","s1");
  assert.throws(()=>a.requireMockEnrollment("1","s2"),e=>e.status===403);
  a.mockRecordPass("1","s1");assert.equal(a.requireMockEnrollment("1","s2").id,"1");
});
