const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");

function setup() {
  const calls = [];
  const request = (...args) => { calls.push(args); return Promise.resolve({ status: "ACTIVE" }); };
  const source = fs.readFileSync(__dirname + "/../src/api/admin.api.js", "utf8")
    .replace(/^import .*;$/gm, "")
    .replace(/export const /g, "const ");
  const api = vm.runInNewContext(source + ";({setAdminUserEnabled})", { request });
  return { api, calls };
}

test("admin account status API uses the protected status endpoint for both actions", async () => {
  const { api, calls } = setup();
  await api.setAdminUserEnabled(17, false);
  await api.setAdminUserEnabled(17, true);
  assert.deepEqual(JSON.parse(JSON.stringify(calls)), [
    ["/admin/users/17/status", { method: "PATCH", body: { enabled: false } }],
    ["/admin/users/17/status", { method: "PATCH", body: { enabled: true } }],
  ]);
});

test("admin edit UI confirms disable and renders the returned account status", () => {
  const source = fs.readFileSync(__dirname + "/../src/pages/AdminUsersPage.jsx", "utf8");
  assert.match(source, /setAdminUserEnabled\(editing\.id,enabled\)/);
  assert.match(source, /Kh&#x00f3;a t&#x00e0;i kho&#x1ea3;n n&#x00e0;y\?/);
  assert.match(source, /user\.status === "INACTIVE"/);
  assert.match(source, /role="dialog" aria-modal="true" aria-labelledby="disable-account-title"/);
  assert.match(source, /editing\.status !== "INACTIVE"/);
});
