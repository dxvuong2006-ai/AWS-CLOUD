const {test}=require("node:test");
const assert=require("node:assert/strict"),fs=require("node:fs"),vm=require("node:vm");
function setup(mock=true){
  const calls=[];let response;let enrolled=true;
  class ApiError extends Error{constructor(status,message){super(message);this.status=status;}}
  const source=fs.readFileSync(__dirname+"/../src/api/lessons.api.js","utf8")
    .replace(/^import .*;$/gm,"").replace(/export /g,"").replace(/import.meta.env.VITE_USE_MOCK === "true"/g,String(mock));
  const api=vm.runInNewContext(source+";({fetchLesson,fetchLessonVideo,normalizeLesson})",{
    ApiError,mockStorageKey:k=>k,lessons:require("../src/mocks/lessons.mock.json"),courses:require("../src/mocks/courses.mock.json"),
    requireMockEnrollment:()=>{if(!enrolled)throw new ApiError(403,"Enroll first");},request:async path=>{calls.push(path);return response;}});
  return {...api,calls,setResponse:v=>response=v,setEnrolled:v=>enrolled=v};
}
test("media requires enrollment and matches course; every published mock lesson loads",async()=>{
  const a=setup();a.setEnrolled(false);await assert.rejects(()=>a.fetchLesson("l1","1"),e=>e.status===403);
  a.setEnrolled(true);await assert.rejects(()=>a.fetchLesson("l1","2"),e=>e.status===404);
  for(const [lesson,course] of [["l1","1"],["l2","1"],["l3","1"],["l4","2"],["l5","2"]]){
    assert.equal((await a.fetchLesson(lesson,course)).id,lesson);
    assert.ok((await a.fetchLessonVideo(lesson,course)).videoUrl);
  }
});
test("draft, processing and failed content never render as ready",()=>{
  const a=setup(),data={id:1,course_id:1,section_id:1,publication_status:"DRAFT",processing_status:"READY"};
  assert.throws(()=>a.normalizeLesson(data),e=>e.status===403);
  data.publication_status="PUBLISHED";data.processing_status="PROCESSING";
  assert.throws(()=>a.normalizeLesson(data),e=>e.status===409);
  data.processing_status="FAILED";assert.throws(()=>a.normalizeLesson(data),e=>e.status===422);
});
test("real media requests do not fall back to mock and reject expired URLs",async()=>{
  const a=setup(false);a.setResponse({video_url:"https://example.test/video",expires_at:"2000-01-01T00:00:00Z"});
  await assert.rejects(()=>a.fetchLessonVideo("7","1"),e=>e.status===502);
  a.setResponse({video_url:"https://example.test/video",expires_at:new Date(Date.now()+60000).toISOString()});
  assert.ok((await a.fetchLessonVideo("7","1")).expiresAt>Date.now());
  assert.equal(a.calls[0],"/lessons/7/video-url");
});
