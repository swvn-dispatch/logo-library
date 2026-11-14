import unittest

from src.channel_patterns import channel_matches, compile_patterns


class ChannelPatternTests(unittest.TestCase):
    def test_modes_and_case(self):
        rows = [{"mode": "contains", "text": "sports"},
                {"mode": "starts_with", "text": "CA |", "case_sensitive": True},
                {"mode": "regex", "text": r"^ca\s*\|"}]
        rules, errors = compile_patterns(rows)
        self.assertEqual(errors, [])
        self.assertTrue(all(channel_matches("CA | Sportsnet", rule) for rule in rules))
        self.assertFalse(channel_matches("ca | Sportsnet", rules[1]))
        self.assertFalse(channel_matches("Other CA | Sportsnet", rules[2]))

    def test_invalid_and_blank_rows(self):
        rules, errors = compile_patterns([{}, {"mode": "regex", "text": "["},
                                           {"mode": "contains", "text": "abc", "case_sensitive": "false"},
                                           {"mode": "contains", "text": "abc", "path_mode": "regex", "path_text": "["},
                                           {"mode": "contains", "text": "abc", "path_mode": "contains"}], hints=True)
        self.assertEqual(rules, [])
        self.assertEqual(len(errors), 4)
        self.assertTrue(compile_patterns("invalid")[1])


if __name__ == "__main__":
    unittest.main()
