const assert = require('assert');
const fs = require('fs');
const path = require('path');

const rules = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'config/naming-rules.json'), 'utf8'));

assert.strictEqual(rules.reservedPrefixes['00'], '00_CONTROL_CENTER');
assert.ok(rules.knownIssuesToDetect.length >= 3, 'Expected naming issue rules');
assert.ok(rules.suggestedRenames['00_Legal_Files'], 'Expected suggested rename for 00_Legal_Files');

console.log('naming-rules.test.js passed');
