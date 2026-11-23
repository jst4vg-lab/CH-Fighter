const test = require('node:test');
const assert = require('node:assert/strict');
const { CAPABILITIES, channelUrl, createAdapter } = require('../desktop/communications.cjs');

test('manual adapter reports only navigation and rejects unsupported operations', async () => {
  const opened = [];
  const adapter = createAdapter(async url => opened.push(url));
  assert.equal(CAPABILITIES.channelNavigation, true);
  for (const name of ['messageRetrieval','realtimeSubscriptions','composition','fileAttachment','messageSending','deliveryConfirmation']) {
    assert.equal(CAPABILITIES[name], false);
  }
  assert.deepEqual(await adapter.sendMessage({ text: 'fixture' }), { ok: false, code: 'unsupported' });
  assert.deepEqual(await adapter.retrieveMessages(), { ok: false, code: 'unsupported' });
  assert.deepEqual(await adapter.navigateChannel('https://discord.com/channels/123/456'), { ok: true });
  assert.deepEqual(opened, ['https://discord.com/channels/123/456']);
  assert.deepEqual(await adapter.navigateChannel('file:///tmp/secret'), { ok: false, code: 'invalid_channel' });
  assert.equal(channelUrl('https://discord.com.evil.test/channels/123/456'), null);
  const broken = createAdapter(async () => { throw Error('Client unavailable'); });
  await assert.rejects(broken.navigateChannel('https://discord.com/channels/123/456'), /unavailable/);
});
