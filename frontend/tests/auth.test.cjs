const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const root=path.join(__dirname,'../src');
function setup(env = {apiUrl:'http://api.test/'}) {
  const storage=new Map(), calls=[], events=[];
  const ctx=vm.createContext({
    LOCAL_AUTH: env.localAuth === true,
    AUTH_PROVIDER: env.localAuth === true ? 'local' : 'cognito',
    sessionStorage:{getItem:k=>storage.get(k)??null,setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)},
    window:{dispatchEvent:e=>events.push(e.type)}, Event:class {constructor(type){this.type=type;}},
    fetch:async(url,options)=>{calls.push({url,options});return {ok:true,status:200,json:async()=>({ok:true})};},
  });
  const source=fs.readFileSync(path.join(root,'api/session.js'),'utf8').replace(/^import .*;$/gm,'').replace(/export /g,'');
  vm.runInContext(source,ctx);
  ctx.cognitoCalls=0;
  ctx.currentCognitoAccessToken=async()=>{ctx.cognitoCalls++;return vm.runInContext('readSession()?.token ?? null',ctx);};
  const client=fs.readFileSync(path.join(root,'api/client.js'),'utf8')
    .split(String.fromCharCode(10)).filter(l=>!l.startsWith('import ')).join(String.fromCharCode(10))
    .replace(/export /g,'')
    .replace(/import.meta.env.VITE_API_BASE_URL/g,
      env.apiBaseUrl === undefined ? 'undefined' : JSON.stringify(env.apiBaseUrl))
    .replace(/import.meta.env.VITE_API_URL/g,
      env.apiUrl === undefined ? 'undefined' : JSON.stringify(env.apiUrl));
  vm.runInContext(client,ctx);
  return {ctx,calls,events,storage,api:vm.runInContext('({readSession,writeSession,clearSession,mockStorageKey,request})',ctx)};
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

test('local auth sends its real bearer token without touching Cognito', async()=>{
  const {api,ctx,calls}=setup({localAuth:true});
  api.writeSession({token:'signed-local-jwt',expiresAt:Date.now()+60000});
  await api.request('/students/me/courses');
  assert.equal(ctx.cognitoCalls,0);
  assert.equal(calls[0].options.headers.Authorization,'Bearer signed-local-jwt');
});

test('changing the auth provider discards the other provider session',()=>{
  const {api,ctx}=setup({localAuth:true});
  api.writeSession({token:'local-jwt',expiresAt:Date.now()+60000});
  assert.equal(api.readSession().authProvider,'local');
  ctx.AUTH_PROVIDER='cognito';
  assert.equal(api.readSession(),null);
  api.writeSession({token:'cognito-jwt',expiresAt:Date.now()+60000});
  ctx.AUTH_PROVIDER='local';
  assert.equal(api.readSession(),null);
});

test('mock tokens and legacy mock sessions can never call a real API',async()=>{
  for(const localAuth of [true,false]){
    const {api,calls}=setup({localAuth});
    api.writeSession({token:'mock:1:1',expiresAt:Date.now()+60000});
    assert.equal(api.readSession(),null);
    await assert.rejects(()=>api.request('/auth/me'),e=>e.status===401);
    assert.equal(calls.length,0);
  }
});

function authSetup(localAuth){
  const calls=[];
  const source=fs.readFileSync(path.join(root,'api/auth.api.js'),'utf8')
    .replace(/^import .*;$/gm,'').replace(/export /g,'');
  const ctx=vm.createContext({LOCAL_AUTH:localAuth,
    ApiError:class extends Error{},readSession:()=>({token:'real-jwt'}),
    request:async(path,options)=>{calls.push({path,options});return {};},
    signInWithCognito:async(email,password)=>{calls.push({cognito:'login',email,password});return {};},
    signOutFromCognito:async()=>{calls.push({cognito:'logout'});},
    // Any unexpected mock storage use causes these tests to fail immediately.
    localStorage:{getItem(){throw Error('localStorage accounts are forbidden');}},
  });
  const api=vm.runInContext(source+';({loginUser,logoutUser,fetchCurrentUser,registerStudent,verifyEmail,resendVerification,forgotPassword,resetPassword,changePassword,updateProfile})',ctx);
  return {api,calls};
}

for(const localAuth of [true,false]) test(`account actions select ${localAuth?'FastAPI local':'Cognito'} auth with real API data`,async()=>{
  const {api,calls}=authSetup(localAuth);
  const prefix=localAuth?'/auth/local':'/auth';
  await api.registerStudent({name:' Student ',email:' s@example.com ',password:'Password123!',role:'ADMIN'});
  assert.equal(calls[0].path,prefix+'/register');
  assert.equal(calls[0].options.body.role,undefined);
  await api.verifyEmail(' s@example.com ','123 456');
  assert.equal(calls[1].path,prefix+'/verify-email');
  assert.equal(calls[1].options.body.code,'123456');
  await api.resendVerification('s@example.com');
  await api.forgotPassword('s@example.com');
  await api.resetPassword('s@example.com','123456','New-password!');
  await api.changePassword('Old-password!','New-password!');
  assert.deepEqual(calls.slice(2,6).map(c=>c.path),['/resend-verification','/forgot-password','/reset-password','/change-password'].map(p=>prefix+p));
  await api.fetchCurrentUser();
  await api.updateProfile(' Student ');
  assert.deepEqual(calls.slice(6).map(c=>c.path),['/auth/me','/auth/me']);
  await api.loginUser(' S@EXAMPLE.COM ','Password123!');
  await api.logoutUser();
  if(localAuth){
    assert.equal(calls[8].path,'/auth/local/login');
    assert.equal(calls[8].options.body.email,'s@example.com');
    assert.equal(calls[9].path,'/auth/local/logout');
  }else{
    assert.equal(calls[8].cognito,'login');
    assert.equal(calls[8].email,'s@example.com');
    assert.equal(calls[9].cognito,'logout');
  }
});

test('local mode initializes no Cognito SDK even when pool IDs are configured',async()=>{
  const source=fs.readFileSync(path.join(root,'api/cognito.js'),'utf8')
    .replace(/^import[\s\S]*?;\r?$/gm,'').replace(/export /g,'')
    .replace(/import.meta.env.\w+/g,'"configured-value"');
  const session=vm.runInNewContext(source+';({currentCognitoSession,signOutFromCognito})',{
    LOCAL_AUTH:true,
    Amplify:{configure(){throw Error('Cognito must stay inactive');}},
    fetchAuthSession(){throw Error('Cognito must stay inactive');},
    signOut(){throw Error('Cognito must stay inactive');},
  });
  assert.equal(await session.currentCognitoSession(),null);
  await session.signOutFromCognito();
});
