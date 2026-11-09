const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const root=path.join(__dirname,'../src');
function setup(env = {apiUrl:'http://api.test/'}) {
  const storage=new Map(), calls=[], events=[];
  const ctx=vm.createContext({
    sessionStorage:{getItem:k=>storage.get(k)??null,setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)},
    window:{dispatchEvent:e=>events.push(e.type)}, Event:class {constructor(type){this.type=type;}},
    fetch:async(url,options)=>{calls.push({url,options});return {ok:true,status:200,json:async()=>({ok:true})};},
  });
  const source=fs.readFileSync(path.join(root,'api/session.js'),'utf8').replace(/export /g,'');
  vm.runInContext(source,ctx);
  ctx.currentCognitoAccessToken=async()=>vm.runInContext('readSession()?.token ?? null',ctx);
  const client=fs.readFileSync(path.join(root,'api/client.js'),'utf8')
    .split(String.fromCharCode(10)).filter(l=>!l.startsWith('import ')).join(String.fromCharCode(10))
    .replace(/export /g,'')
    .replace(/import.meta.env.VITE_API_BASE_URL/g,
      env.apiBaseUrl === undefined ? 'undefined' : JSON.stringify(env.apiBaseUrl))
    .replace(/import.meta.env.VITE_API_URL/g,
      env.apiUrl === undefined ? 'undefined' : JSON.stringify(env.apiUrl));
  vm.runInContext(client,ctx);
  return {ctx,calls,events,api:vm.runInContext('({readSession,writeSession,clearSession,mockStorageKey,request})',ctx)};
}
test('API base URL accepts the documented name and normalizes its trailing slash',async()=>{
 const {api,calls}=setup({
  apiBaseUrl:'https://api.example.test/default/',
  apiUrl:'http://localhost:8000',
 });
 await api.request('/health',{auth:false});
 assert.equal(calls[0].url,'https://api.example.test/default/health');
});
test('bearer requests, public login and logout',async()=>{
 const {api,calls}=setup();
 api.writeSession({token:'test-token',expiresAt:Date.now()+60000,user:{id:1}});
 await api.request('/auth/me');
 assert.equal(calls[0].url,'http://api.test/auth/me');
 assert.equal(calls[0].options.headers.Authorization,'Bearer test-token');
 assert.ok(!('X-Demo-User' in calls[0].options.headers));
 await api.request('/auth/login',{auth:false,method:'POST',body:{email:'a',password:'b'}});
 assert.equal(calls[1].options.headers.Authorization,undefined);
 api.clearSession(); assert.equal(api.readSession(),null);
});
test('expiration, account isolation and 401 handling',async()=>{
 const {api,ctx,events}=setup();
 api.writeSession({token:'expired',expiresAt:Date.now()-1,user:{id:1}});
 assert.equal(api.readSession(),null);
 api.writeSession({token:'one',expiresAt:Date.now()+60000,user:{id:1}});
 const first=api.mockStorageKey('progress');
 api.writeSession({token:'two',expiresAt:Date.now()+60000,user:{id:2}});
 assert.notEqual(first,api.mockStorageKey('progress'));
 ctx.fetch=async()=>({ok:false,status:401,json:async()=>({detail:'Expired'})});
 await assert.rejects(()=>api.request('/auth/me'),e=>e.status===401);
 assert.equal(api.readSession(),null); assert.deepEqual(events,['learncloud:unauthorized']);
});
test('late 401 cannot clear a newer login',async()=>{
 const {api,ctx}=setup();
 api.writeSession({token:'old',expiresAt:Date.now()+60000,user:{id:1}});
 let resolve;
 ctx.fetch=()=>new Promise(r=>{resolve=r;});
 const pending=api.request('/auth/me');
 await new Promise(r=>setImmediate(r));
 api.writeSession({token:'new',expiresAt:Date.now()+60000,user:{id:2}});
 resolve({ok:false,status:401,json:async()=>({})});
 await assert.rejects(()=>pending,e=>e.status===401);
 assert.equal(api.readSession().token,'new');
});
test('role landing pages and permission decisions',()=>{
 const source=fs.readFileSync(path.join(root,'utils/roles.js'),'utf8').replace(/export /g,'');
 const {homeForRole,isAllowedRole}=vm.runInNewContext(source+';({homeForRole,isAllowedRole})');
 assert.equal(homeForRole('STUDENT'),'/courses');
 assert.equal(homeForRole('INSTRUCTOR'),'/instructor/dashboard');
 assert.equal(homeForRole('ADMIN'),'/admin/users');
 assert.equal(isAllowedRole('STUDENT',['ADMIN']),false);
 assert.equal(isAllowedRole('ADMIN',['ADMIN']),true);
 assert.equal(isAllowedRole('unknown'),false);
});
