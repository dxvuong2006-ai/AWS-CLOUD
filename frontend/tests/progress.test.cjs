const {test}=require("node:test"), assert=require("node:assert/strict"),fs=require("node:fs"),vm=require("node:vm");
const {webcrypto}=require("node:crypto");
const courses=require("../src/mocks/courses.mock.json");
function load(file,names,context={}) {
  const source=fs.readFileSync(__dirname+"/../src/"+file,"utf8").replace(/^import\s[\s\S]*?;\r?$/gm,"").replace(/export /g,"").replace(/import.meta.env.VITE_USE_MOCK === "true"/g,String(context.mock??true));
  return vm.runInNewContext(source+`;({${names}})`,context);
}
const ranges=load("utils/watchedRanges.js","mergeWatchedRanges,getWatchedSeconds");
const playback=load("utils/playback.js","acceptedPlaybackRange,createSerialWriter");
function setup(mock=true){
  const storage=new Map(),calls=[];let account="one";
  class ApiError extends Error {constructor(status,message){super(message);this.status=status;}}
  const context={...ranges,mock,MOCK_COMPLETION_PERCENT:95,ApiError,courses,crypto:webcrypto,
    mockStorageKey:k=>k+account,localStorage:{getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v)},
    normalizeProgress:data=>data,request:async(path,options)=>{calls.push({path,options});return {id:"server-session"};}};
  Object.assign(context,load("mocks/enrollment.mock.js","mockEnroll,requireMockEnrollment,mockRecordPass",context));
  context.mockEnroll("1");context.mockEnroll("2");
  const api=load("api/progress.api.js","fetchCourseProgress,saveLessonProgress,startViewingSession",context);
  return {...api,context,calls,setAccount:v=>account=v};
}
test("seek, pause and playback speed use content intervals rather than position",()=>{
  const before={position:10,wallTime:0,rate:1};
  assert.equal(playback.acceptedPlaybackRange(before,100,1000,false),null);
  assert.equal(playback.acceptedPlaybackRange(before,11,1000,true),null);
  assert.equal(playback.acceptedPlaybackRange(null,30,20000,false),null);
  assert.equal(playback.acceptedPlaybackRange(before,10,20000,false),null);
  assert.deepEqual(Array.from(playback.acceptedPlaybackRange({...before,rate:2},12,1000,false)),[10,12]);
});
test("mock merges retries, separates resume, clips bounds, and uses exact threshold",async()=>{
  const a=setup();const save=(position,watched)=>a.saveLessonProgress("l1",{courseId:"1",lastPositionSeconds:position,durationSeconds:100,watchedRanges:watched});
  await save(100,[]);let p=await a.fetchCourseProgress("1");assert.equal(p.lessons[0].completed,false);assert.equal(p.lessons[0].watched_seconds,0);
  await save(10,[[0,10]]);await save(10,[[0,10]]);await save(20,[[5,20]]);
  p=await a.fetchCourseProgress("1");assert.equal(p.lessons[0].watched_seconds,20);
  await save(94.9,[[0,94.9]]);assert.equal((await a.fetchCourseProgress("1")).lessons[0].completed,false);
  await save(95,[[0,95]]);assert.equal((await a.fetchCourseProgress("1")).lessons[0].completed,true);
  assert.throws(()=>a.context.requireMockEnrollment("1","s2"),e=>e.status===403);
  a.setAccount("two");assert.equal((await a.fetchCourseProgress("1")).lessons[0].watched_seconds,0);
  assert.deepEqual(JSON.parse(JSON.stringify(ranges.mergeWatchedRanges([[-5,4],[2,150],[NaN,4],[40,20]],100))),[[0,100]]);
});
test("real saves send ranges and session metadata, never client completion or duration",async()=>{
  const a=setup(false);assert.equal((await a.startViewingSession("4","1")).id,"server-session");
  await a.saveLessonProgress("4",{courseId:"1",lastPositionSeconds:100,durationSeconds:200,watchedRanges:[[0,10]],sessionId:"server-session",sequence:1,requestId:"id1",completed:true});
  const call=a.calls[1];assert.equal(call.path,"/lessons/4/progress");assert.equal(call.options.method,"PUT");
  assert.equal(call.options.body.playback_session_id,"server-session");assert.equal(call.options.body.completed,undefined);assert.equal(call.options.body.duration_seconds,undefined);
});
test("serial writes preserve order and recover after a failed save",async()=>{
  const order=[];let release;
  const write=playback.createSerialWriter(async value=>{order.push(value);if(value===1)await new Promise(r=>release=r);if(value===2)throw Error("offline");return value;});
  const first=write(1),second=write(2),third=write(3);
  const rejected=assert.rejects(second,/offline/);await Promise.resolve();assert.deepEqual(order,[1]);
  release();await first;await rejected;assert.equal(await third,3);assert.deepEqual(order,[1,2,3]);
});
