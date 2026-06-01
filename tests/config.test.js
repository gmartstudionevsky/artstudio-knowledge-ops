const assert = require('assert');
const fs = require('fs');
const path = require('path');

const folders = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'config/drive-folders.json'), 'utf8'));
const canonical = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'config/canonical-files.json'), 'utf8'));

assert.ok(folders.artstudioFolderId, 'artstudioFolderId is required');
assert.ok(folders.controlCenterFolderId, 'controlCenterFolderId is required');
assert.strictEqual(folders.controlCenterFolderName, '00_CONTROL_CENTER');
assert.strictEqual(canonical.controlCenterFiles.length, 11, 'There must be 11 canonical control center files');

console.log('config.test.js passed');
