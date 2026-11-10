const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const { webcrypto } = require("node:crypto");
function setup() {
  const storage = new Map(); let session = null;
  class ApiError extends Error { constructor(status,message) { super(message); this.status=status; } }
  const source = fs.readFileSync(__dirname+"/../src/mocks/account.mock.js","utf8")
    .replace(/^import .*;$/gm, "").replace(/export /g, "");
  const api = vm.runInNewContext(source+";accountMock", {ApiError,crypto:webcrypto,TextEncoder,
    readSession:()=>session, localStorage:{getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v)}});
  return {api, storage, login:token=>session={token}};
}
const payload = {name:"Student",email:"test@example.com",password:"test123456",role:"ADMIN"};
test("registration requires verification and never accepts elevated roles", async()=>{
  const {api}=setup(); await api("register",payload);
  await assert.rejects(()=>api("login",payload),e=>e.status===403);
  await assert.rejects(()=>api("verify",{...payload,code:"000000"}),e=>e.status===400);
  await api("verify",{...payload,code:"123456"});
  const session=await api("login",payload); assert.equal(session.user.role,"STUDENT");
  await assert.rejects(()=>api("verify",{...payload,code:"123456"}),e=>e.status===400);
  await assert.rejects(()=>api("register",payload),e=>e.status===409);
});
test("recovery has a neutral response; reset invalidates old sessions",async()=>{
  const {api,login}=setup(); await api("register",payload); await api("verify",{...payload,code:"123456"});
  login((await api("login",payload)).access_token);
  const known=await api("forgot",payload), unknown=await api("forgot",{email:"missing@example.com"});
  assert.equal(known.message,unknown.message); assert.ok(known.retry_after>0);
  await api("reset",{...payload,code:"123456",password:"new123456"});
  await assert.rejects(()=>api("me"),e=>e.status===401);
  await assert.rejects(()=>api("login",payload),e=>e.status===401);
  assert.equal((await api("login",{...payload,password:"new123456"})).user.email,payload.email);
});
test("expired codes and repeated guesses are rejected",async()=>{
  const {api,storage}=setup(); await api("register",payload);
  for(let i=0;i<5;i++) await assert.rejects(()=>api("verify",{...payload,code:"000000"}));
  await assert.rejects(()=>api("verify",{...payload,code:"123456"}),e=>e.status===400);
  const key="learncloud.mock.accounts.v1", data=JSON.parse(storage.get(key));
  data.codes["verify:"+payload.email].attempts=0;
  data.codes["verify:"+payload.email].expiresAt=Date.now()-1;
  storage.set(key,JSON.stringify(data));
  await assert.rejects(()=>api("verify",{...payload,code:"123456"}),e=>e.status===400);
});
