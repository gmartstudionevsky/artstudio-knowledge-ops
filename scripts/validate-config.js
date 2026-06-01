const fs = require('fs');
const path = require('path');

const required = [
  'config/drive-folders.json',
  'config/canonical-files.json',
  'config/statuses.json',
  'config/naming-rules.json',
  'config/control-center.config.json'
];

let ok = true;
for (const file of required) {
  const full = path.join(__dirname, '..', file);
  if (!fs.existsSync(full)) {
    console.error(`Missing config: ${file}`);
    ok = false;
    continue;
  }
  try {
    JSON.parse(fs.readFileSync(full, 'utf8'));
  } catch (err) {
    console.error(`Invalid JSON in ${file}: ${err.message}`);
    ok = false;
  }
}
if (!ok) process.exit(1);
console.log('Config validation passed.');
