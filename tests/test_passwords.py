from __future__ import annotations

import string
import unittest

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk
from hypothesis import given, settings
from hypothesis import strategies as st

from src import passwords
from src.ui.dialogs.generator import build_generator_button


class TestGenerator(unittest.TestCase):
    def test_default_has_every_kind_and_the_right_length(self):
        for _ in range(50):
            value = passwords.generate_password()
            self.assertEqual(len(value), passwords.DEFAULT_LENGTH)
            self.assertTrue(any(c in string.ascii_lowercase for c in value))
            self.assertTrue(any(c in string.ascii_uppercase for c in value))
            self.assertTrue(any(c in string.digits for c in value))
            self.assertTrue(any(c in passwords.SYMBOLS for c in value))

    def test_options_restrict_the_alphabet(self):
        value = passwords.generate_password(
            40, lower=True, upper=False, digits=False, symbols=False
        )
        self.assertTrue(set(value) <= set(string.ascii_lowercase))
        digits = passwords.generate_password(
            30, lower=False, upper=False, digits=True, symbols=False
        )
        self.assertTrue(digits.isdigit())

    def test_ambiguous_characters_can_be_left_out(self):
        for _ in range(50):
            value = passwords.generate_password(64, avoid_ambiguous=True)
            self.assertFalse(set(value) & passwords.AMBIGUOUS)

    def test_passwords_are_different_every_time(self):
        self.assertEqual(len({passwords.generate_password() for _ in range(200)}), 200)

    def test_invalid_requests_are_rejected(self):
        with self.assertRaises(ValueError):
            passwords.generate_password(passwords.MIN_LENGTH - 1)
        with self.assertRaises(ValueError):
            passwords.generate_password(passwords.MAX_LENGTH + 1)
        with self.assertRaises(ValueError):
            passwords.generate_password(20, lower=False, upper=False, digits=False, symbols=False)

    @settings(max_examples=100, deadline=None)
    @given(
        st.integers(passwords.MIN_LENGTH, passwords.MAX_LENGTH),
        st.booleans(),
        st.booleans(),
        st.booleans(),
        st.booleans(),
        st.booleans(),
    )
    def test_any_valid_combination_produces_a_matching_password(self, length, lo, up, di, sy, amb):
        if not (lo or up or di or sy):
            return
        value = passwords.generate_password(length, lo, up, di, sy, amb)
        self.assertEqual(len(value), length)
        if not lo:
            self.assertFalse(set(value) & set(string.ascii_lowercase))
        if not up:
            self.assertFalse(set(value) & set(string.ascii_uppercase))
        if not di:
            self.assertFalse(set(value) & set(string.digits))
        if not sy:
            self.assertFalse(set(value) & set(passwords.SYMBOLS))
        if amb:
            self.assertFalse(set(value) & passwords.AMBIGUOUS)


class TestGeneratorButton(unittest.TestCase):
    def setUp(self):
        self.buffer = Gtk.TextBuffer()
        self.button = build_generator_button(self.buffer)

    def text(self):
        return self.buffer.get_text(self.buffer.get_start_iter(), self.buffer.get_end_iter(), True)

    def test_clicking_generate_replaces_the_text_with_a_password(self):
        self.buffer.set_text("old value")
        self.button.generate.emit("clicked")
        self.assertEqual(len(self.text()), passwords.DEFAULT_LENGTH)
        self.assertNotIn("old", self.text())

    def test_the_chosen_options_are_used(self):
        self.button.length.set_value(40)
        for key in ("upper", "digits", "symbols"):
            self.button.checks[key].set_active(False)
        self.button.generate.emit("clicked")
        self.assertEqual(len(self.text()), 40)
        self.assertTrue(set(self.text()) <= set(string.ascii_lowercase))

    def test_with_nothing_enabled_the_text_is_left_alone(self):
        self.buffer.set_text("keep me")
        for key in ("lower", "upper", "digits", "symbols"):
            self.button.checks[key].set_active(False)
        self.button.generate.emit("clicked")
        self.assertEqual(self.text(), "keep me")


if __name__ == "__main__":
    unittest.main()
