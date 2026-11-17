// Run with: node tests/test_unsigned_inputs.js
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('static/app.js', 'utf8');
const helper = source.slice(source.indexOf('const initializeUnsignedNumbers'), source.indexOf('const initializePhotoEditor'));
const fields = [0, 1, 2, 3].map((precision) => ({
  dataset: { nonnegativeDecimal: String(precision) }, value: '', handlers: {},
  addEventListener(name, fn) { this.handlers[name] = fn; },
}));
vm.runInNewContext(helper, { document: {}, $$: () => fields });
for (const field of fields) {
  field.value = '12'; field.handlers.input(); assert.equal(field.value, '12');
  for (const invalid of ['-1', '-0.01', '1e2', '+2', 'NaN', 'Infinity']) {
    field.value = invalid; field.handlers.input(); assert.equal(field.value, '12');
  }
  let prevented = false;
  field.handlers.beforeinput({ data: '-', preventDefault() { prevented = true; } });
  assert.equal(prevented, true);
}
fields[0].value = '2.5'; fields[0].handlers.input(); assert.equal(fields[0].value, '12');
fields[1].value = '.5'; fields[1].handlers.input(); fields[1].handlers.blur(); assert.equal(fields[1].value, '0.5');
fields[2].value = '1.23'; fields[2].handlers.input(); assert.equal(fields[2].value, '1.23');
fields[2].value = '1.234'; fields[2].handlers.input(); assert.equal(fields[2].value, '1.23');
fields[3].value = '1.234'; fields[3].handlers.input(); assert.equal(fields[3].value, '1.234');
console.log('Unsigned input interactions passed: invalid typing/paste, integers, decimal precision and leading decimal normalization.');
