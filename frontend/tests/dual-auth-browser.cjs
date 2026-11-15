// Real browser + FastAPI + isolated PostgreSQL + Mailpit. No mock data/accounts.
// Requires prepared DB and Mailpit on 127.0.0.1:11025 / :18025; see implementation report.
const assert = require("node:assert/strict");
const fs = require("node:fs"), os = require("node:os"), path = require("node:path"), net = require("node:net");
const { randomBytes, randomUUID } = require("node:crypto");
const { spawn } = require("node:child_process");
const root = path.resolve(__dirname, "../..");
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
async function poll(fn, description, timeout = 20000) {
  const end = Date.now() + timeout;
  while (Date.now() < end) { try { if (await fn()) return; } catch {} await pause(100); }
  throw Error("Timed out: " + description);
}
async function port() {
  const server = net.createServer();
  await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
  const result = server.address().port;
  await new Promise(resolve => server.close(resolve));
  return result;
}

(async () => {
  const value = process.env.LEARNCLOUD_AUTH_TEST_DATABASE_URL;
  assert.ok(value, "Explicit isolated test DATABASE_URL is required");
  const url = new URL(value);
  assert.ok(["postgresql:", "postgresql+psycopg2:"].includes(url.protocol)
    && ["localhost", "127.0.0.1"].includes(url.hostname)
    && url.pathname === "/learncloud_auth_test" && url.username === "learncloud_auth_test"
    && [...url.searchParams.keys()].every(k => ["connect_timeout", "application_name"].includes(k)),
  "Only the isolated local learncloud_auth_test DB/user is permitted");
  const executable = [process.env.CHROME_PATH, "C:/Program Files/Google/Chrome/Application/chrome.exe",
    "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"].find(p => p && fs.existsSync(p));
  assert.ok(executable, "Chrome/Edge is required");
  const apiPort = await port(), debugPort = await port(), base = "http://127.0.0.1:5173";
  const profile = fs.mkdtempSync(path.join(os.tmpdir(), "learncloud-auth-browser-"));
  const children = [], exceptions = [];
  let socket;
  const launch = (file, args, cwd, env) => {
    const child = spawn(file, args, { cwd, env, windowsHide: true, stdio: "ignore" });
    children.push(child); return child;
  };
  try {
    launch(path.join(root, ".venv/Scripts/python.exe"), ["-m", "uvicorn", "app.main:app", "--app-dir", "backend",
      "--host", "127.0.0.1", "--port", String(apiPort)], root, {
      ...process.env, DATABASE_URL: value, APP_ENV: "test", LOCAL_AUTH_ENABLED: "true",
      LOCAL_AUTH_JWT_SECRET: randomBytes(48).toString("base64url"), SMTP_HOST: "127.0.0.1", SMTP_PORT: "11025",
      AWS_EC2_METADATA_DISABLED: "true", AWS_ACCESS_KEY_ID: "offline-test-key", AWS_SECRET_ACCESS_KEY: "offline-test-secret",
      AWS_CONFIG_FILE: os.devNull, AWS_SHARED_CREDENTIALS_FILE: os.devNull,
      VIDEO_PIPELINE_ENABLED: "false", VIDEO_AI_ENABLED: "false", VIDEO_PROCESSOR_BACKEND: "disabled",
      COGNITO_USER_POOL_ID: "", COGNITO_APP_CLIENT_ID: "",
    });
    await poll(async () => (await fetch(`http://127.0.0.1:${apiPort}/health`)).ok, "isolated FastAPI startup");
    launch(process.execPath, [path.join(root, "frontend/node_modules/vite/bin/vite.js"), "--host", "127.0.0.1",
      "--port", "5173", "--strictPort"], path.join(root, "frontend"), {
      ...process.env, VITE_USE_MOCK: "false", VITE_USE_AUTH_MOCK: "true",
      VITE_API_BASE_URL: `http://127.0.0.1:${apiPort}`, VITE_COGNITO_USER_POOL_ID: "", VITE_COGNITO_APP_CLIENT_ID: "",
    });
    await poll(async () => (await fetch(base)).ok, "Vite startup on port 5173");
    launch(executable, ["--headless=new", "--no-first-run", "--no-default-browser-check",
      `--user-data-dir=${profile}`, `--remote-debugging-port=${debugPort}`, "about:blank"], root, process.env);
    let target;
    await poll(async () => {
      target = (await (await fetch(`http://127.0.0.1:${debugPort}/json`)).json()).find(row => row.type === "page");
      return target;
    }, "isolated browser startup");
    socket = new WebSocket(target.webSocketDebuggerUrl);
    await new Promise((resolve, reject) => { socket.onopen = resolve; socket.onerror = reject; });
    let id = 0;
    const pending = new Map();
    socket.onmessage = event => {
      const data = JSON.parse(event.data);
      if (data.method === "Runtime.exceptionThrown") exceptions.push(data.params.exceptionDetails.text);
      if (data.id) {
        const task = pending.get(data.id);
        if (task) { pending.delete(data.id); clearTimeout(task.timer);
          data.error ? task.reject(Error(data.error.message)) : task.resolve(data.result); }
      }
    };
    const send = (method, params = {}) => new Promise((resolve, reject) => {
      const current = ++id, timer = setTimeout(() => { pending.delete(current); reject(Error("Browser command timeout")); }, 15000);
      pending.set(current, { resolve, reject, timer }); socket.send(JSON.stringify({ id: current, method, params }));
    });
    const evaluate = async expression => {
      const result = await send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
      // Avoid printing expressions/exception details that might contain passwords or codes.
      if (result.exceptionDetails) throw Error("Browser evaluation failed");
      return result.result.value;
    };
    const wait = expression => poll(() => evaluate(`Boolean(${expression})`), "page state");
    const navigate = route => send("Page.navigate", { url: base + route });
    const click = selector => evaluate(`document.querySelector(${JSON.stringify(selector)}).click()`);
    const fill = (selector, text) => evaluate(`(()=>{const input=document.querySelector(${JSON.stringify(selector)});
      Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set.call(input,${JSON.stringify(text)});
      input.dispatchEvent(new Event('input',{bubbles:true}));})()`);
    const email = `browser-${randomUUID()}@example.com`, password = "Browser-password-123!";
    const mailCode = async purpose => {
      let code;
      await poll(async () => {
        const rows = (await (await fetch("http://127.0.0.1:18025/api/v1/messages")).json()).messages;
        const row = rows.find(row => row.Subject.includes(purpose) && row.To.some(to => to.Address === email));
        if (!row) return false;
        const body = await (await fetch(`http://127.0.0.1:18025/api/v1/message/${row.ID}`)).json();
        code = body.Text.match(/\b\d{6}\b/)[0]; return true;
      }, "Mailpit delivery");
      return code;
    };
    await send("Runtime.enable"); await send("Page.enable");
    await navigate("/register"); await wait("document.querySelector('#register-name')");
    await fill("#register-name", "Browser Student"); await fill("#register-email", email);
    await fill("#register-password", password); await fill("#register-confirm", password); await click("form .login-submit");
    await wait("document.querySelector('#verify-code')");
    assert.equal(await evaluate("document.querySelector('.account-resend').disabled"), true);
    await fill("#verify-code", await mailCode("Verify email")); await click("form .login-submit");
    await wait("location.pathname === '/register-success'");
    const signIn = async pass => {
      await navigate("/login"); await wait("document.querySelector('#login-email')");
      await fill("#login-email", email); await fill("#login-password", pass); await click("form .login-submit");
      await wait("location.pathname === '/courses' && !!sessionStorage.getItem('learncloud.auth.session')");
    };
    await signIn(password);
    assert.equal(await evaluate("Object.keys(localStorage).some(k=>k.startsWith('learncloud.mock.'))"), false);
    assert.equal(await evaluate("JSON.parse(sessionStorage.getItem('learncloud.auth.session')).authProvider"), "local");
    assert.equal(await evaluate("JSON.parse(sessionStorage.getItem('learncloud.auth.session')).user.role"), "STUDENT");
    await navigate("/profile"); await wait("document.querySelector('#profile-name')");
    await fill("#profile-name", "Updated Student"); await click("form .btn-primary");
    await wait("JSON.parse(sessionStorage.getItem('learncloud.auth.session')).user.name === 'Updated Student'");
    await navigate("/admin/users"); await wait("location.pathname === '/forbidden'");
    await navigate("/profile"); await wait("document.querySelector('.btn-danger-outline')");
    await click(".btn-danger-outline"); await wait("location.pathname === '/login'");
    assert.equal(await evaluate("sessionStorage.getItem('learncloud.auth.session')"), null);
    await navigate("/forgot-password"); await wait("document.querySelector('#forgot-email')");
    await fill("#forgot-email", email); await click("form .login-submit");
    await wait("document.querySelector('#reset-code')");
    await fill("#reset-code", await mailCode("Reset password"));
    await fill("#reset-password", "Reset-browser-123!"); await fill("#reset-confirm", "Reset-browser-123!");
    await click("form .login-submit"); await wait("location.pathname === '/login'");
    await signIn("Reset-browser-123!");
    assert.deepEqual(exceptions, [], "No unhandled browser exceptions");
    console.log("PASS real browser: register, Mailpit OTP, verification, login, PostgreSQL profile, logout, recovery, role guard; no Cognito IDs or mock storage");
  } finally {
    socket?.close(); children.reverse().forEach(child => child.kill());
    // Delete only this test's generated profile, inside the explicit temp root.
    if (path.dirname(path.resolve(profile)) === path.resolve(os.tmpdir())
        && path.basename(profile).startsWith("learncloud-auth-browser-")) {
      await pause(800); try { fs.rmSync(profile, { recursive: true, force: true }); } catch {}
    }
  }
})().catch(error => { console.error(error.message); process.exitCode = 1; });
