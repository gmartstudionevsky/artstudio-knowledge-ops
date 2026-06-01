const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');

const scriptPath = path.join(__dirname, '..', 'apps-script/control-center/control_center_sealing.gs');
const source = fs.readFileSync(scriptPath, 'utf8');
const canonical = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'config/canonical-files.json'), 'utf8'));

new vm.Script(source, { filename: 'control_center_sealing.gs' });

[
  'mainAuditOnly',
  'mainExecuteAcceptedActions',
  'mainValidateStageOneClosure',
  'getConfig',
  'scanArtstudioFolder',
  'scanControlCenterFolder',
  'scanRootProjectFiles',
  'detectDuplicateControlFiles',
  'detectSetupArtifacts',
  'detectMethodologyFiles',
  'detectNamingIssues',
  'writeDriveAuditSnapshot',
  'writeDuplicateReport',
  'writeNamingIssues',
  'writeReorganizationPlanRows',
  'writeValidationReport',
  'appendToolRunLog'
].forEach((fn) => {
  assert.match(source, new RegExp(`function\\s+${fn}\\s*\\(`), `${fn} must exist`);
});

assert.match(source, /artstudioFolderId:\s*'17dKXkxMd_iiBz5AFbKtt7YvuEzo-bfQK'/);
assert.match(source, /controlCenterFolderId:\s*'13riY7cN6DjiYg1k9ey19sdFgva8cP7dp'/);
assert.match(source, /dryRun:\s*true/);
assert.match(source, /executeAcceptedActions:\s*false/);
assert.match(source, /allowDelete:\s*false/);

const auditOnlyBody = source.slice(source.indexOf('function mainAuditOnly'), source.indexOf('function mainExecuteAcceptedActions'));
[
  '.setSharing(',
  '.setOwner(',
  '.addEditor(',
  '.removeEditor(',
  '.moveTo(',
  '.setName(',
  'Drive.Files.remove',
  'DriveApp.removeFile',
  'DriveApp.removeFolder'
].forEach((unsafeCall) => {
  assert.ok(!auditOnlyBody.includes(unsafeCall), `mainAuditOnly must not call ${unsafeCall}`);
});

assert.strictEqual(canonical.methodologyPrefix, 'ARTSTUDIO Base —');
assert.ok(canonical.setupArtifacts.includes('ARTSTUDIO_CONTROL_CENTER_SEALING_TASK'));
assert.ok(canonical.setupArtifacts.includes('bootstrap_control_center.gs'));

console.log('control-center-sealing.test.js passed');
