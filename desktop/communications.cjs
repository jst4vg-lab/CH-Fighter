const CAPABILITIES = Object.freeze({
  channelNavigation: true,
  messageRetrieval: false,
  realtimeSubscriptions: false,
  composition: false,
  fileAttachment: false,
  messageSending: false,
  deliveryConfirmation: false
});

function channelUrl(value) {
  if (typeof value !== 'string') return null;
  try {
    const url = new URL(value);
    if (url.protocol !== 'https:' || url.hostname !== 'discord.com' ||
        !/^\/channels\/(?:@me|\d+)(?:\/\d+)?\/?$/.test(url.pathname)) return null;
    return url.origin + url.pathname;
  } catch { return null; }
}

function createAdapter(open) {
  return Object.freeze({
    capabilities: CAPABILITIES,
    async navigateChannel(value) {
      const url = channelUrl(value);
      if (!url) return { ok: false, code: 'invalid_channel' };
      await open(url);
      return { ok: true };
    },
    retrieveMessages: async () => ({ ok: false, code: 'unsupported' }),
    subscribeMessages: async () => ({ ok: false, code: 'unsupported' }),
    compose: async () => ({ ok: false, code: 'unsupported' }),
    attachFiles: async () => ({ ok: false, code: 'unsupported' }),
    sendMessage: async () => ({ ok: false, code: 'unsupported' }),
    confirmDelivery: async () => ({ ok: false, code: 'unsupported' })
  });
}

module.exports = { CAPABILITIES, channelUrl, createAdapter };
