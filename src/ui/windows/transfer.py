"""Export / import actions mixin for MainWindow."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, List, Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gio, GLib, Gtk

from src.i18n import _
from src.readonly import blocks_writes, is_read_only
from src.transfer import (
    SKIP_EXISTING,
    ImportResult,
    TransferEntry,
    build_export_document,
    collect_export_entries,
    import_entries,
    read_import_file,
    write_export_file,
)
from src.ui.icons import resolve_icon_name
from src.ui.windows.base import WindowBase

if TYPE_CHECKING:
    pass


class WindowTransferMixin(WindowBase):
    """Exports the listed secrets to a JSON file and imports secrets from one."""

    def _show_toast(self, text: str) -> None: ...  # Defined in WindowNavMixin
    def _audit(
        self, action: str, secret: Optional[str] = None, **extra: object
    ) -> None: ...  # WindowNavMixin
    def _load_secrets_async(self) -> None: ...  # Defined in WindowDataMixin

    # -------------------------------------------------------------
    # Header menu
    # -------------------------------------------------------------
    def _build_transfer_menu(self) -> Gtk.MenuButton:
        """Create the header menu button with the Export / Import actions."""
        self.transfer_menu = Gio.Menu()
        for name, handler in (
            ("export-secrets", self._on_export_secrets),
            ("import-secrets", self._on_import_secrets),
        ):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", handler)
            self.add_action(action)
        self._populate_transfer_menu()
        self.transfer_btn = Gtk.MenuButton(
            icon_name=resolve_icon_name(
                ["document-send-symbolic", "document-save-symbolic", "folder-symbolic"],
                fallback="document-save-symbolic",
            ),
            menu_model=self.transfer_menu,
            tooltip_text=_("Import / Export"),
        )
        return self.transfer_btn

    def _populate_transfer_menu(self) -> None:
        """(Re)fill the menu model with localized labels."""
        self.transfer_menu.remove_all()
        self.transfer_menu.append(_("Export secrets…"), "win.export-secrets")
        if not is_read_only():
            self.transfer_menu.append(_("Import secrets…"), "win.import-secrets")

    def _update_transfer_texts(self) -> None:
        """Refresh localized texts of the transfer menu."""
        self._populate_transfer_menu()
        self.transfer_btn.set_tooltip_text(_("Import / Export"))

    # -------------------------------------------------------------
    # Export
    # -------------------------------------------------------------
    def _on_export_secrets(self, *_args) -> None:
        """Ask how to export the secrets currently listed in the sidebar."""
        if not self.secrets:
            self._show_toast(_("No secrets to export"))
            return
        self.dialogs.export(
            self,
            self.active_provider.display_name,
            len(self.secrets),
            self._choose_export_file,
        )

    def _choose_export_file(self, include_values: bool) -> None:
        """Let the user pick the destination file, then start the export."""
        dialog = Gtk.FileDialog(title=_("Export secrets"))
        dialog.set_initial_name(f"gossip-{self.active_provider.provider_id}-export.json")

        def on_finish(dlg: Gtk.FileDialog, result: Gio.AsyncResult) -> None:
            """Start the export if the user chose a file."""
            try:
                gfile = dlg.save_finish(result)
            except GLib.Error:
                return
            if gfile and gfile.get_path():
                self._start_export(gfile.get_path(), include_values)

        dialog.save(self, None, on_finish)

    def _start_export(self, path: str, include_values: bool) -> None:
        """Read the secrets in the background and write the export file."""
        client = self.active_provider
        secrets = list(self.secrets)
        self._audit("export", count=len(secrets), with_data=include_values)
        self._show_toast(_("Exporting secrets..."))

        def export() -> tuple:
            entries, errors = collect_export_entries(client, secrets, include_values)
            document = build_export_document(client.provider_id, entries, include_values)
            write_export_file(path, document)
            return len(entries), errors

        self._run_in_background(
            export,
            lambda done: self._on_export_done(path, done[0], done[1], None),
            lambda exc: self._on_export_done(path, 0, [], str(exc)),
        )

    def _on_export_done(
        self, path: str, count: int, errors: List[str], error: Optional[str]
    ) -> None:
        """Report the export outcome on the GTK main thread."""
        if error:
            self._show_toast(_("Error: {detail}").format(detail=error))
            return
        name = os.path.basename(path)
        if errors:
            self._show_toast(
                _("Exported %d secrets to %s (%d without value)") % (count, name, len(errors))
            )
        else:
            self._show_toast(_("Exported %d secrets to %s") % (count, name))

    # -------------------------------------------------------------
    # Import
    # -------------------------------------------------------------
    @blocks_writes
    def _on_import_secrets(self, *_args) -> None:
        """Let the user pick a file to import secrets from."""
        dialog = Gtk.FileDialog(title=_("Import secrets"))

        def on_finish(dlg: Gtk.FileDialog, result: Gio.AsyncResult) -> None:
            """Preview the import if the user chose a file."""
            try:
                gfile = dlg.open_finish(result)
            except GLib.Error:
                return
            if gfile and gfile.get_path():
                self._start_import_preview(gfile.get_path())

        dialog.open(self, None, on_finish)

    def _start_import_preview(self, path: str) -> None:
        """Parse the chosen file and ask for confirmation."""
        try:
            entries = read_import_file(path)
        except (ValueError, OSError) as exc:
            self._show_toast(_("Error: {detail}").format(detail=exc))
            return
        self.dialogs.import_(
            self,
            self.active_provider.display_name,
            entries,
            {secret.secret_id for secret in self.secrets},
            lambda strategy: self._start_import(entries, strategy),
        )

    def _start_import(self, entries: List[TransferEntry], on_existing: str = SKIP_EXISTING) -> None:
        """Create the secrets in the background (existing ones are skipped or get a version)."""
        client = self.active_provider
        existing = {secret.secret_id for secret in self.secrets}
        names = {secret.secret_id: secret.name for secret in self.secrets}
        self._show_toast(_("Importing secrets..."))

        self._run_in_background(
            lambda: import_entries(
                client, entries, existing, on_existing=on_existing, existing_names=names
            ),
            lambda result: self._on_import_done(result, None),
            lambda exc: self._on_import_done(ImportResult(), str(exc)),
        )

    def _on_import_done(self, result: ImportResult, error: Optional[str]) -> None:
        """Show the import summary and refresh the list on the GTK main thread."""
        if error:
            self._show_toast(_("Error: {detail}").format(detail=error))
            return
        self._audit(
            "import",
            created=len(result.created),
            updated=len(result.updated),
            skipped=len(result.skipped),
            failed=len(result.failed),
        )
        self.dialogs.import_result(self, result)
        if result.created or result.updated:
            self._load_secrets_async()
