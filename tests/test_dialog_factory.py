from __future__ import annotations

import unittest

from src.ui.dialogs import confirm, factory, secret
from tests.window_case import WindowCase


class TestDialogFactory(unittest.TestCase):
    def test_it_exposes_every_dialog_the_window_opens(self):
        dialogs = factory.DialogFactory()
        self.assertIs(dialogs.confirm_delete, confirm.show_confirm_delete_secret_dialog)
        self.assertIs(dialogs.create_secret, secret.show_create_secret_dialog)
        for name in (
            "about", "add_version", "edit_metadata", "confirm_destroy", "confirm_restore",
            "compare_versions", "compare_secrets", "export", "import_", "import_result",
        ):  # fmt: skip
            self.assertTrue(callable(getattr(dialogs, name)), name)

    def test_instances_do_not_share_replacements(self):
        first, second = factory.DialogFactory(), factory.DialogFactory()
        first.about = lambda *_a: "replaced"
        self.assertNotEqual(second.about, first.about)


class TestWindowUsesIt(WindowCase):
    def test_the_window_owns_a_factory_its_mixins_share(self):
        self.assertIsInstance(self.window.dialogs, factory.DialogFactory)


if __name__ == "__main__":
    unittest.main()
