const {test}=require("node:test");
const assert=require("node:assert/strict");
const fs=require("node:fs");
const vm=require("node:vm");

function setup(intent) {
  const source=fs.readFileSync(__dirname+"/../src/api/uploads.api.js","utf8")
    .replace(/^import .*;$/gm,"")
    .replace(/export /g,"");
  const requests=[];
  class XMLHttpRequest {
    constructor() {
      this.upload={};
      this.headers={};
      this.status=200;
      requests.push(this);
    }
    open(method,url) { this.method=method; this.url=url; }
    setRequestHeader(name,value) { this.headers[name]=value; }
    send(file) {
      this.file=file;
      this.onload();
    }
    abort() { this.onabort(); }
  }
  const context=vm.createContext({
    request:async()=>intent,
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
  };
}

test("uploads a presigned URL response without an optional pipeline upload ID",async()=>{
  const intent={
    upload_url:"https://bucket.s3.example.test/video",
    object_key:"lessons/1/raw/video.mp4",
    method:"PUT",
    content_type:"video/mp4",
  };
  const {api,requests}=setup(intent);
  const file={name:"lesson.mp4",type:"video/mp4",size:1024};
  const result=await api.uploadVideo(1,file,{
    signal:new AbortController().signal,
    onProgress:()=>{},
  });
  assert.equal(result,intent);
  assert.equal(requests.length,1);
  assert.equal(requests[0].method,"PUT");
  assert.equal(requests[0].url,intent.upload_url);
  assert.equal(requests[0].headers["Content-Type"],"video/mp4");
  assert.equal(requests[0].file,file);
});
