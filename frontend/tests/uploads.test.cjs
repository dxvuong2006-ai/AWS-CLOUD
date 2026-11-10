const {test}=require("node:test");
const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");

function setup(intent, {putStatus=200,putError=false,confirmError=null}={}) {
  const source=fs.readFileSync(__dirname+"/../src/api/uploads.api.js","utf8")
    .replace(/^import .*;$/gm,"")
    .replace(/export /g,"");
  const requests=[], calls=[];
  const confirmed={lesson_id:1,status:"UPLOADED",video_status:"UPLOADED",has_raw_video:true};
  class XMLHttpRequest {
    constructor() {
      this.upload={};
      this.headers={};
      this.status=putStatus;
      requests.push(this);
    }
    open(method,url) { this.method=method; this.url=url; }
    setRequestHeader(name,value) { this.headers[name]=value; }
    send(file) {
      this.file=file;
      if(putError) this.onerror(); else this.onload();
    }
    abort() { this.onabort(); }
  }
  const context=vm.createContext({
    request:async(path,options)=>{
      calls.push({path,options});
      if(path.endsWith('/confirm-upload')){
        if(confirmError) throw confirmError;
        return confirmed;
      }
      return intent;
    },
    XMLHttpRequest,
    DOMException,
    Promise,
    Error,
    RegExp,
  });
  vm.runInContext(source+";({uploadVideo,videoType})",context);
  return {
    api:vm.runInContext("({uploadVideo,videoType})",context),
    requests,
    calls,confirmed,
  };
}

const intent={upload_id:'a'.repeat(32),upload_url:'https://bucket.s3.example.test/video',
  object_key:'lessons/1/raw/video.mp4',method:'PUT',content_type:'video/mp4',
  required_headers:{'Content-Type':'video/mp4','If-None-Match':'*'}};
const file={name:"lesson.mp4",type:"video/mp4",size:1024};
const options=()=>({signal:new AbortController().signal,onProgress:()=>{}});

test("PUT is followed by mandatory backend confirmation before success",async()=>{
  const {api,requests,calls,confirmed}=setup(intent);
  const result=await api.uploadVideo(1,file,{
    signal:new AbortController().signal,
    onProgress:()=>{},
  });
  assert.equal(result,confirmed);
  assert.equal(requests.length,1);
  assert.equal(requests[0].method,"PUT");
  assert.equal(requests[0].url,intent.upload_url);
  assert.equal(requests[0].headers["Content-Type"],"video/mp4");
  assert.equal(requests[0].headers["If-None-Match"],"*");
  assert.equal(requests[0].file,file);
  assert.equal(calls.length,2);
  assert.equal(calls[1].path,'/lessons/1/confirm-upload');
  assert.equal(calls[1].options.body.upload_id,intent.upload_id);
  assert.equal(calls[1].options.body.object_key,undefined);
});

test("legacy server without a durable upload ID is rejected before PUT",async()=>{
  const {api,requests}=setup({...intent,upload_id:undefined});
  await assert.rejects(()=>api.uploadVideo(1,file,options()),/Backend/);
  assert.equal(requests.length,0);
});

test("missing overwrite protection is rejected before sending bytes",async()=>{
  const {api,requests}=setup({...intent,required_headers:{'Content-Type':'video/mp4'}});
  await assert.rejects(()=>api.uploadVideo(1,file,options()),/Backend/);
  assert.equal(requests.length,0);
});

test("failed confirmation never reports the S3 PUT as a complete upload",async()=>{
  const failure=Object.assign(new Error('metadata unavailable'),{status:503});
  const {api,calls}=setup(intent,{confirmError:failure});
  await assert.rejects(()=>api.uploadVideo(1,file,options()),e=>e===failure);
  assert.equal(calls.length,2);
});

for(const putStatus of [409,412])test(`conditional S3 ${putStatus} recovers by confirming the same upload`,async()=>{
  const {api,calls,confirmed}=setup(intent,{putStatus});
  assert.equal(await api.uploadVideo(1,file,options()),confirmed);
  assert.equal(calls.length,2);
});

test("lost PUT response can recover only after backend verifies the existing object",async()=>{
  const {api,confirmed}=setup(intent,{putError:true});
  assert.equal(await api.uploadVideo(1,file,options()),confirmed);
  const missing=Object.assign(new Error('no object'),{code:'UPLOAD_OBJECT_NOT_FOUND'});
  const failed=setup(intent,{putError:true,confirmError:missing});
  await assert.rejects(()=>failed.api.uploadVideo(1,file,options()),/kết nối/);
});
