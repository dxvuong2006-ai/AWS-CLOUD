const fs = require('node:fs'), path = require('node:path'), vm = require('node:vm');
const {webcrypto} = require('node:crypto');
function drafts(sessionStorage, mockStorageKey) {
  const source = fs.readFileSync(path.join(__dirname, '../src/utils/checkpointDraft.js'), 'utf8')
    .replace(/^import .*;$/gm, '').replace(/export /g, '');
  return vm.runInNewContext(source + ';({checkpointScope,createCheckpointDraft,restoreCheckpointDraft,saveCheckpointDraft,completeCheckpointDraft})',
    {sessionStorage, mockStorageKey, crypto: webcrypto});
}
function explanations() {
  const source = fs.readFileSync(path.join(__dirname, '../src/mocks/quizExplanations.js'), 'utf8').replace(/export /g, '');
  return vm.runInNewContext(source + ';quizExplanations');
}
module.exports = {drafts, explanations};
