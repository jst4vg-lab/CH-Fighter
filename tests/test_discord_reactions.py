from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import Mock, patch

import discord_reactions as reactions


class QuickReactionTests(TestCase):
    def setUp(self):
        directory = self.enterContext(TemporaryDirectory())
        self.enterContext(patch('crea_core.DB', Path(directory) / 'test.sqlite'))

    def test_defaults_custom_emoji_and_reset(self):
        default = ['❌', '✅', '🧱', '🔥', '😐']
        self.assertEqual(reactions.preferences()['slots'], default)
        slots = ['<:custom_emoji:123>', '<a:animated:123>', '🇨🇦', '👩🏽‍💻', '1️⃣']
        reactions.save(slots)
        self.assertEqual(reactions.preferences()['slots'], slots)
        reactions.save(reactions.preferences()['defaults'])
        self.assertEqual(reactions.preferences()['slots'], default)

    def test_invalid_input_preserves_existing_slots(self):
        for invalid in (['🔥'], ['🔥'] * 4 + ['bad'], ['🔥'] * 4 + ['🔥😐']):
            with self.assertRaises(ValueError):
                reactions.save(invalid)
        self.assertEqual(reactions.preferences()['slots'], list(reactions.DEFAULTS))

    def test_dispatch_checks_sender_scope_permission_and_preset(self):
        bot = Mock()
        state = {'provider':'discord_bot', 'guild_id':'1', 'channel_id':'2', 'sender_id':'3',
                 'capabilities':{'react':True}}
        bot.status.return_value = state
        bot.add_reaction.return_value = {'ok': True}
        body = {'guild_id':'1', 'channel_id':'2', 'sender_id':'3', 'message_id':'4', 'emoji':'🔥'}
        for change in ({'channel_id':'9'}, {'sender_id':'9'}, {'emoji':'👀'}):
            with self.assertRaises(ValueError):
                reactions.add({**body, **change}, bot)
        bot.add_reaction.assert_not_called()
        self.assertTrue(reactions.add(body, bot)['ok'])
        bot.add_reaction.assert_called_once_with('4', '🔥')
        state['provider'] = 'discord_user'
        self.assertTrue(reactions.add(body, bot)['ok'])
        state['capabilities']['react'] = False
        with self.assertRaisesRegex(ValueError, 'cannot react'):
            reactions.add(body, bot)
