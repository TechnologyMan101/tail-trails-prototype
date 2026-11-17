// Run with: node tests/test_branding_ui.js (Node built-ins only).
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('static/app.js', 'utf8');
const script = source.slice(source.indexOf('const createSelectionCropper'), source.indexOf('const photoCropForm'));

class Element extends EventTarget {
  constructor() {
    super(); Object.assign(this, {style: {}, dataset: {}, nodes: {}, lists: {}, hidden: true, disabled: false, value: '', textContent: '', files: []});
  }
  querySelector(selector) { return this.nodes[selector] || null; }
  querySelectorAll(selector) { return this.lists[selector] || []; }
  append(...children) { (this.children ||= []).push(...children); }
  replaceChildren(...children) { this.children = children; }
  focus() { this.focused = true; }
  scrollIntoView(options) { this.scrolledIntoView = options; }
}
const event = (name, values = {}) => Object.assign(new Event(name, {cancelable: true}), values);
const settle = () => new Promise(setImmediate);

function setup({cached = true, hasImage = true} = {}) {
  const form = new Element();
  form.dataset.previewUrlTemplate = '/branding-preview/ASSET_KIND';
  const names = ['branding-session', 'branding-session-status', 'branding-countdown', 'branding-discard', 'branding-errors', 'branding-save-status', 'branding-save-message', 'branding-save-progress'];
  const nodes = Object.fromEntries(names.map((name) => [name, new Element()]));
  for (const [name, node] of Object.entries(nodes)) form.nodes[`[data-${name}]`] = node;
  nodes['branding-save-status'].nodes.label = new Element();
  const csrf = new Element(); csrf.value = 'csrf';
  form.nodes['[name="csrfmiddlewaretoken"]'] = csrf;
  const cropper = new Element(); cropper.dataset = {kind: 'logo', ratio: '1'};
  const stage = new Element(); stage.parentElement = {clientWidth: 600};
  const image = new Element();
  Object.assign(image, {src: hasImage ? '/branding-preview/logo' : '', complete: cached, naturalWidth: cached && hasImage ? 1000 : 0, naturalHeight: cached && hasImage ? 500 : 0});
  const selection = new Element(), cropInput = new Element(), fileInput = new Element();
  for (const [selector, node] of Object.entries({
    '[data-crop-stage]': stage, '[data-crop-image]': image, '[data-crop-selection]': selection,
    '[data-crop-placeholder]': new Element(), '[data-crop-status]': new Element(),
    '[name="logo_upload"]': fileInput, '[name="logo_crop"]': cropInput,
  })) cropper.nodes[selector] = node;
  form.lists['[data-branding-cropper]'] = [cropper];
  form.lists['input,select,textarea,button'] = [csrf, fileInput, cropInput, nodes['branding-discard']];
  form.lists['input[type=file]'] = [fileInput];
  const requests = [], fetches = [], captures = [], navigations = [];
  const window = new EventTarget();
  Object.assign(window, {innerHeight: 900, location: {href: '/organization', assign: (url) => navigations.push(url), reload: () => navigations.push('reload')}});
  class FormData {
    constructor(target) { if (target) captures.push(target.querySelectorAll('input,select,textarea,button').map((control) => control.disabled)); }
    append() {}
  }
  class XMLHttpRequest {
    constructor() { this.upload = new EventTarget(); this.headers = {}; requests.push(this); }
    open(method, url) { Object.assign(this, {method, url}); }
    setRequestHeader(name, value) { this.headers[name] = value; }
    send(data) { this.data = data; }
    complete(status, result) { this.status = status; this.responseText = JSON.stringify(result); this.onload(); }
  }
  const document = {createElement: () => new Element(), open: () => { throw new Error('Must navigate, never rewrite the document'); }};
  vm.runInNewContext(script, {
    $: (selector, root) => root ? root.querySelector(selector) : selector === '[data-branding-form]' ? form : null,
    $$: (selector, root) => root ? root.querySelectorAll(selector) : [],
    window, location: window.location, document, Event, FormData, XMLHttpRequest,
    performance: {now: () => 0}, setTimeout() {},
    fetch: async (...args) => { fetches.push(args); return {ok: true, json: async () => ({remaining_seconds: 1800})}; },
    URL: {createObjectURL: () => 'blob:preview', revokeObjectURL() {}},
  });
  return {form, nodes, image, selection, cropInput, fileInput, window, requests, fetches, captures, navigations};
}

(async () => {
  const initial = setup();
  assert.equal(initial.selection.hidden, false);
  assert.equal(parseFloat(initial.selection.style.width), parseFloat(initial.selection.style.height));
  initial.window.dispatchEvent(event('resize'));
  assert.equal(initial.fetches.length, 0, 'Initial layout and resize must not start the timer');
  assert.equal(initial.nodes['branding-session'].hidden, true);
  initial.selection.dispatchEvent(event('keydown', {key: 'ArrowRight'}));
  await settle();
  assert.equal(initial.fetches.length, 1);
  assert.equal(initial.nodes['branding-countdown'].textContent, '30:00');
  assert.equal(initial.nodes['branding-session'].hidden, false);

  const loading = setup({cached: false});
  assert.equal(loading.selection.hidden, true);
  Object.assign(loading.image, {naturalWidth: 1000, naturalHeight: 500});
  loading.image.dispatchEvent(event('load'));
  assert.equal(loading.selection.hidden, false);
  assert.equal(loading.fetches.length, 0);
  assert.equal(setup({hasImage: false}).selection.hidden, true);

  const preview = setup(); preview.fileInput.files = [{name: 'new-logo.png'}];
  preview.fileInput.dispatchEvent(event('change'));
  await settle();
  assert.equal(preview.requests.length, 1);
  preview.form.dispatchEvent(event('submit'));
  assert.equal(preview.requests.length, 1, 'Do not save while preview upload is running');
  Object.assign(preview.requests[0], {status: 200, response: {}});
  preview.requests[0].onload();
  await settle();
  preview.form.dispatchEvent(event('submit'));
  assert.equal(preview.requests.length, 1, 'Wait for preview image decoding and crop layout too');
  preview.image.onload();
  await settle();
  preview.form.dispatchEvent(event('submit'));
  assert.equal(preview.requests.length, 2);
  preview.requests[1].complete(200, {redirect_url: '/organization'});
  assert.deepEqual(preview.navigations, ['/organization']);

  const save = setup(); save.fileInput.files = [{name: 'logo.png'}];
  save.form.dispatchEvent(event('submit'));
  assert.equal(save.nodes['branding-save-status'].scrolledIntoView.block, 'nearest');
  assert.deepEqual(save.captures[0], [false, false, false, false], 'Capture files before disabling fields');
  assert.equal(save.fileInput.disabled, true);
  save.form.dispatchEvent(event('submit'));
  assert.equal(save.requests.length, 1, 'Prevent duplicate saves');
  save.requests[0].upload.onprogress({lengthComputable: true, loaded: 50, total: 100});
  assert.equal(save.nodes['branding-save-progress'].value, 50);
  save.requests[0].complete(200, {redirect_url: '/organization'});
  assert.deepEqual(save.navigations, ['/organization']);

  const retry = setup(); retry.fileInput.files = [{name: 'keep.png'}];
  const crop = retry.cropInput.value;
  retry.form.dispatchEvent(event('submit'));
  retry.requests[0].complete(400, {errors: {name: [{message: 'Required.'}]}, field_labels: {name: 'Organization name'}});
  assert.equal(retry.nodes['branding-errors'].hidden, false);
  assert.equal(retry.fileInput.disabled, false);
  assert.equal(retry.fileInput.files[0].name, 'keep.png');
  assert.equal(retry.cropInput.value, crop);
  retry.form.dispatchEvent(event('submit'));
  retry.requests[1].onerror();
  assert.equal(retry.fileInput.disabled, false);
  retry.form.dispatchEvent(event('submit'));
  retry.requests[2].complete(200, {redirect_url: '/organization'});
  assert.deepEqual(retry.navigations, ['/organization']);
  console.log('Branding UI checks passed: crop readiness, silent layout, timer, save navigation, progress and retry.');
})().catch((error) => { console.error(error); process.exitCode = 1; });
