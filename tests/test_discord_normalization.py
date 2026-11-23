from datetime import datetime, timezone
from types import SimpleNamespace as Object
from unittest import TestCase

from communications.core.normalization import normalize


class MessageNormalizationTests(TestCase):
    def message(self, reference, snapshots=()):
        return Object(id=10, channel=Object(id=20), guild=Object(id=30),
                      content='Comment', created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
                      edited_at=None, author=Object(id=1, name='sender', display_name='Sender',
                      display_avatar=Object(url='https://example.test/avatar')), attachments=[],
                      embeds=[], reactions=[], reference=reference, message_snapshots=snapshots,
                      jump_url='https://discord.com/channels/30/20/10')

    def test_forward_preserves_body_without_treating_reference_as_reply(self):
        snapshot = Object(content='Complete forwarded content',
                          created_at=datetime(2025, 1, 1, tzinfo=timezone.utc), stickers=[],
                          attachments=[Object(id=2, filename='photo.png', content_type='image/png',
                                              url='https://example.test/photo.png', size=20)],
                          embeds=[Object(to_dict=lambda: {'image': {'url': 'https://example.test/embed.png'}})])
        result = normalize(self.message(Object(message_id=8, channel_id=70, type=Object(value=1)), [snapshot]))
        self.assertTrue(result['forwarded'])
        self.assertIsNone(result['reply_to'])
        forwarded = result['forwarded_messages'][0]
        self.assertEqual(forwarded['content'], snapshot.content)
        self.assertEqual(forwarded['timestamp'], snapshot.created_at.isoformat())
        self.assertEqual(forwarded['attachments'][0]['name'], 'photo.png')
        self.assertEqual(forwarded['embeds'][0]['image']['url'], 'https://example.test/embed.png')

    def test_native_replies_are_preserved(self):
        result = normalize(self.message(Object(message_id=9, channel_id=20, type=Object(value=0))))
        self.assertFalse(result['forwarded'])
        self.assertEqual(result['reply_to'], '9')
        self.assertEqual(result['reply_channel_id'], '20')

    def test_unavailable_forward_is_still_distinguished_from_reply(self):
        result = normalize(self.message(Object(message_id=8, channel_id=70, type=Object(value=1))))
        self.assertTrue(result['forwarded'])
        self.assertIsNone(result['reply_to'])
        self.assertEqual(result['forwarded_messages'], [])
