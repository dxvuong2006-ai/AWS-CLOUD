// Windows Chrome/Edge smoke test; isolated browser profile and Vite mock server.
// Run: npm run test:browser. Optional CHROME_PATH points to a Chromium executable.
const assert = require("node:assert/strict");
const fs = require("node:fs"), os = require("node:os"), path = require("node:path"), net = require("node:net");
const {spawn} = require("node:child_process");
const root=path.resolve(__dirname,"..");
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
async function port(){const server=net.createServer();await new Promise(r=>server.listen(0,"127.0.0.1",r));const value=server.address().port;await new Promise(r=>server.close(r));return value;}
async function poll(fn,description,timeout=20000){const end=Date.now()+timeout;while(Date.now()<end){try{const value=await fn();if(value)return value;}catch{}await sleep(100);}throw Error("Timed out: "+description);}
(async()=>{
  const executable=[process.env.CHROME_PATH,"C:/Program Files/Google/Chrome/Application/chrome.exe","C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"].find(p=>p&&fs.existsSync(p));
  assert.ok(executable,"Install Chrome/Edge or provide CHROME_PATH");
  const webPort=await port(),debugPort=await port(),base=`http://127.0.0.1:${webPort}`;
  const profile=fs.mkdtempSync(path.join(os.tmpdir(),"learncloud-ui-test-"));
  const vite=spawn(process.execPath,[path.join(root,"node_modules/vite/bin/vite.js"),"--host","127.0.0.1","--port",String(webPort),"--strictPort"],
    {cwd:root,windowsHide:true,stdio:"ignore",env:{...process.env,VITE_USE_MOCK:"true",VITE_USE_AUTH_MOCK:"true",VITE_MOCK_COMPLETION_PERCENT:"95"}});
  let browser,socket;const exceptions=[];
  try {
    await poll(async()=> (await fetch(base)).ok,"Vite startup");
    browser=spawn(executable,["--headless=new","--no-first-run","--no-default-browser-check","--autoplay-policy=no-user-gesture-required",`--user-data-dir=${profile}`,`--remote-debugging-port=${debugPort}`,"about:blank"],{windowsHide:true,stdio:"ignore"});
    const target=await poll(async()=>{const rows=await (await fetch(`http://127.0.0.1:${debugPort}/json`)).json();return rows.find(r=>r.type==="page");},"browser startup");
    socket=new WebSocket(target.webSocketDebuggerUrl);await new Promise((r,j)=>{socket.onopen=r;socket.onerror=j;});
    let id=0;const pending=new Map();
    socket.onmessage=event=>{const data=JSON.parse(event.data);if(data.method==="Runtime.exceptionThrown")exceptions.push(data.params.exceptionDetails.exception?.description || data.params.exceptionDetails.text);
      if(data.id){const task=pending.get(data.id);if(task){pending.delete(data.id);clearTimeout(task.timer);data.error?task.reject(Error(data.error.message)):task.resolve(data.result);}}};
    const send=(method,params={})=>new Promise((resolve,reject)=>{const current=++id;const timer=setTimeout(()=>{pending.delete(current);reject(Error("CDP timeout: "+method));},15000);pending.set(current,{resolve,reject,timer});socket.send(JSON.stringify({id:current,method,params}));});
    const evaluate=async expression=>{const result=await send("Runtime.evaluate",{expression,awaitPromise:true,returnByValue:true});if(result.exceptionDetails)throw Error(JSON.stringify(result.exceptionDetails));return result.result.value;};
    const wait=async expression=>{try{return await poll(()=>evaluate(`Boolean(${expression})`),expression);}catch(error){console.error(await evaluate("({url:location.href,text:document.body.innerText.slice(0,1600)})"),exceptions);throw error;}};
    const navigate=async route=>{await send("Page.navigate",{url:base+route});};
    const fill=(selector,value)=>evaluate(`(()=>{const input=document.querySelector(${JSON.stringify(selector)});Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(input,${JSON.stringify(value)});input.dispatchEvent(new Event('input',{bubbles:true}));})()`);
    const click=selector=>evaluate(`document.querySelector(${JSON.stringify(selector)}).click()`);
    const clickText=text=>evaluate(`(()=>{const b=[...document.querySelectorAll('button')].find(b=>b.textContent.trim()===${JSON.stringify(text)});if(!b)throw Error('Missing button');b.click();})()`);
    const bodyContains=text=>`document.body.innerText.includes(${JSON.stringify(text)})`;
    await send("Runtime.enable");await send("Page.enable");
    await navigate("/register");await wait("document.querySelector('#register-name')");
    const email="smoke@example.com",password="demo-pass-123";
    await fill("#register-name","Học viên kiểm thử");await fill("#register-email",email);await fill("#register-password",password);await fill("#register-confirm",password);await click("form button");
    await wait("document.querySelector('#verify-code')");
    await fill("#verify-code","000000");await click("form button");await wait("document.querySelector('[role=alert]')");
    await fill("#verify-code","123456");await click("form button");await wait(bodyContains("Đăng ký thành công"));
    await navigate("/login");await wait("document.querySelector('#login-email')");
    await fill("#login-email",email);await fill("#login-password",password);await click("form button.login-submit");
    await wait("document.querySelector('a[href=\"/courses/1\"]')");
    assert.equal(await evaluate("!!document.querySelector('a[href=\"/courses/3\"]')"),false);
    await navigate("/courses/1");await wait(bodyContains("Đăng ký học"));await clickText("Đăng ký học");
    await wait("document.querySelector('dialog[open]')");await click("dialog button");
    await wait("document.querySelector('a[href=\"/courses/1/lessons/l1\"]')");
    assert.equal(await evaluate("!!document.querySelector('a[href=\"/courses/1/lessons/l3\"]')"),false);
    await navigate("/my-courses");await wait("document.querySelector('a[href=\"/courses/1/lessons/l1\"]')");
    await navigate("/courses/1/lessons/l1");await wait("document.querySelector('video')?.readyState >= 1");
    await evaluate("(()=>{const v=document.querySelector('video');v.currentTime=v.duration-0.2;})()");await sleep(250);
    await evaluate("(()=>{const v=document.querySelector('video');v.muted=true;return v.play();})()");await sleep(700);
    const progressExpression="JSON.parse(localStorage.getItem(Object.keys(localStorage).find(k=>k.startsWith('learncloud.mock.progress.v2:'))) || '{}').l1";
    await wait(progressExpression);
    let saved=await evaluate(progressExpression);assert.ok(saved.watched_ranges.reduce((n,[a,b])=>n+b-a,0)<1,"Seeking to end must not count whole video");
    assert.equal(await evaluate("!!document.querySelector('a[href$=checkpoint]')"),false);
    await evaluate("(()=>{const v=document.querySelector('video');v.currentTime=0;v.playbackRate=2;})()");await sleep(250);
    await evaluate("document.querySelector('video').play()");await sleep(3200);await evaluate("document.querySelector('video').pause()");await sleep(500);
    saved=await evaluate(progressExpression);assert.ok(saved.watched_ranges.reduce((n,[a,b])=>n+b-a,0)>4,"Actual playback records intervals");
    const before=JSON.stringify(saved.watched_ranges);await sleep(1200);assert.equal(JSON.stringify((await evaluate(progressExpression)).watched_ranges),before,"Pause must not add watch time");
    const position=saved.last_position_seconds;
    await evaluate("document.querySelector('video').dispatchEvent(new Event('error'))");await sleep(800);
    assert.ok(Math.abs(await evaluate("document.querySelector('video').currentTime")-position)<2,"URL refresh restores position");
    // Seed completion through the demo API after exercising real playback above.
    await evaluate("(async()=>{const api=await import('/src/api/progress.api.js');const d=document.querySelector('video').duration;await api.saveLessonProgress('l1',{courseId:'1',lastPositionSeconds:8,durationSeconds:d,watchedRanges:[[0,d]]});})()");
    await navigate("/courses/1/lessons/l1");await wait("document.querySelector('a[href$=checkpoint]')");
    await click("a[href$=checkpoint]");await wait(bodyContains("Bắt đầu làm bài"));await clickText("Bắt đầu làm bài");
    const quiz=require("../src/mocks/quiz.mock.json")["1:s1"];
    for(let i=0;i<quiz.questions.length;i++){
      await wait(bodyContains(quiz.questions[i].text));
      const option=quiz.questions[i].options.findIndex(o=>o.id===quiz.questions[i].correct_option_id);
      await evaluate(`document.querySelectorAll('[role=radio]')[${option}].click()`);
      await click(".quiz-actions .btn-primary");
    }
    await wait("document.querySelector('[role=dialog]')");await click(".modal .btn-primary");await wait(bodyContains("Kết quả checkpoint"));
    await navigate("/courses/1");await wait("document.querySelector('a[href=\"/courses/1/lessons/l3\"]')");
    await navigate("/profile");await wait("document.querySelector('#profile-name')");await fill("#profile-name","Học viên mới");await click("form .btn-primary");await wait(bodyContains("Đã lưu hồ sơ."));
    await fill("#profile-current",password);await fill("#profile-password","updated-pass-123");await fill("#profile-confirm","updated-pass-123");await click("form:nth-of-type(2) .btn-primary");await wait("document.querySelector('#login-email')");
    await navigate("/forgot-password");await wait("document.querySelector('#forgot-email')");await fill("#forgot-email",email);await click("form button");
    await wait("document.querySelector('#reset-code')");await fill("#reset-code","123456");await fill("#reset-password","reset-pass-123");await fill("#reset-confirm","reset-pass-123");await click("form button");
    await wait("document.querySelector('#login-email')");await fill("#login-email",email);await fill("#login-password","reset-pass-123");await click("form button.login-submit");await wait("document.querySelector('nav')");
    await navigate("/my-courses");await wait("document.querySelector('a[href=\"/courses/1/lessons/l1\"]')");
    await navigate("/admin/users");await wait(bodyContains("Không có quyền truy cập"));
    assert.deepEqual(exceptions,[],"No unhandled browser exceptions");
    console.log("PASS browser: register, verification, login, enrollment, roadmap, seek/play/pause, URL refresh, checkpoint, profile/password/recovery, persistence, role denial");
  } finally {
    socket?.close();browser?.kill();vite.kill();
    // The generated disposable profile belongs exclusively to this test run.
    if(path.dirname(profile)===path.resolve(os.tmpdir()) && path.basename(profile).startsWith("learncloud-ui-test-")) {
      await sleep(800);try{fs.rmSync(profile,{recursive:true,force:true});}catch{}
    }
  }
})().catch(error=>{console.error(error);process.exitCode=1;});
