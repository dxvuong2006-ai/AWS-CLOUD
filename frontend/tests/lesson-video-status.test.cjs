const {test}=require("node:test");
const assert=require("node:assert/strict");
const fs=require("node:fs"),vm=require("node:vm");
const source=fs.readFileSync(__dirname+"/../src/utils/lessonVideoStatus.js","utf8").replace(/export /g,"");
const presentation=vm.runInNewContext(source+";lessonVideoPresentation");
const shouldWatch=vm.runInNewContext(source+";shouldWatchVideoStatus");

test("lesson list distinguishes the five backend video states",()=>{
  for(const [state,label,tone,action] of [
    ["NOT_UPLOADED","Chưa có video","neutral","upload"],
    ["UPLOAD_PENDING","Chờ upload / Xác nhận video","neutral","status"],
    ["UPLOADED","Đã upload RAW / Chờ xử lý","neutral","status"],
    ["PROCESSING","Đang xử lý","neutral","status"],
    ["READY","Video sẵn sàng","success","status"],
    ["FAILED","Xử lý thất bại","error","status"],
  ]){
    const actual=presentation({status:"DRAFT",video_status:state});
    assert.equal(actual.label,label);assert.equal(actual.tone,tone);assert.equal(actual.action,action);
  }
});

test("RAW in a draft is waiting for processing, not a fresh upload action",()=>{
  const actual=presentation({status:"DRAFT",video_status:"UPLOADED",has_raw_video:true,has_processed_video:false});
  assert.equal(actual.state,"UPLOADED");assert.equal(actual.action,"status");
  assert.notEqual(actual.label,"Chưa có video");
});

test("absence or presence of a processed URL never overrides backend state",()=>{
  for(const video_status of ["UPLOADED","PROCESSING","READY","FAILED"]){
    for(const url of [undefined,"https://example.test/video.mp4"]){
      const actual=presentation({status:"DRAFT",video_status,video_url:url,processed_video_url:url});
      assert.equal(actual.state,video_status);
      assert.notEqual(actual.label,"Chưa có video");
    }
  }
  assert.equal(presentation({status:"DRAFT",processed_video_url:"https://example.test/video.mp4"}).state,"UNKNOWN");
});

test("ready retains review/publication distinctions and actions",()=>{
  const review=presentation({status:"REVIEW_REQUIRED",video_status:"READY"});
  assert.equal(review.label,"Video sẵn sàng · Chờ duyệt");assert.equal(review.action,"review");
  const published=presentation({status:"PUBLISHED",video_status:"READY"});
  assert.equal(published.label,"Video sẵn sàng · Đã publish");assert.equal(published.action,null);
  assert.match(presentation({status:"TRANSCRIBING",video_status:"PROCESSING"}).label,/Đang xử lý/);
  assert.match(presentation({status:"AI_PROCESSING",video_status:"PROCESSING"}).label,/Đang xử lý/);
});

test("missing/unknown state remains unknown instead of claiming no video",()=>{
  for(const lesson of [undefined,{}, {status:"DRAFT"},{status:"PROCESSING"},{video_status:"FUTURE_STATE"}]){
    const actual=presentation(lesson);
    assert.equal(actual.state,"UNKNOWN");assert.equal(actual.action,"status");
    assert.notEqual(actual.label,"Chưa có video");
  }
});

test("refresh watches DRAFT before the upload event and stops at terminal states",()=>{
  const course=(...states)=>({sections:[{lessons:states.map(video_status=>({video_status}))}]});
  for(const state of ["NOT_UPLOADED","UPLOAD_PENDING","UPLOADED","PROCESSING","UNKNOWN",undefined])
    assert.equal(shouldWatch(course(state)),true);
  assert.equal(shouldWatch(course("READY","FAILED")),false);
  assert.equal(shouldWatch(course()),false);
  assert.equal(shouldWatch(null),false);
});
