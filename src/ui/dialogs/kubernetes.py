"""Kubernetes context and namespace selection dialog."""

from __future__ import annotations

import threading
from typing import Callable, List

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk

from src.i18n import _
from src.providers.kubernetes import KubernetesClient


def show_change_kubernetes_dialog(
    parent_window: Gtk.Window,
    client: KubernetesClient,
    on_success: Callable[[], None],
) -> None:
    """Let the user pick a kubeconfig context and type a namespace.

    Args:
        parent_window: GTK parent window to transient the dialog for.
        client: KubernetesClient provider instance to configure.
        on_success: Callback invoked after the settings were applied.
    """
    dialog = Adw.MessageDialog(
        transient_for=parent_window,
        heading=_("Kubernetes context"),
        body=_("Choose a context from your kubeconfig and the namespace whose Secrets to manage."),
    )

    contexts = client.available_contexts()
    current = client.context
    if current and current not in contexts:
        contexts.insert(0, current)

    group = Adw.PreferencesGroup()
    group.set_size_request(420, -1)
    context_row = Adw.ComboRow(title=_("Context"), model=Gtk.StringList.new(contexts))
    if current in contexts:
        context_row.set_selected(contexts.index(current))
    namespace_row = Adw.EntryRow(title=_("Namespace"))
    namespace_row.set_text(client.namespace)
    namespaces_row = Adw.ComboRow(title=_("Available namespaces"))
    namespaces_row.set_sensitive(False)
    group.add(context_row)
    group.add(namespaces_row)
    group.add(namespace_row)

    namespaces: List[str] = []
    request_id = [0]
    filling = [False]

    def selected_context() -> str | None:
        index = context_row.get_selected()
        return contexts[index] if 0 <= index < len(contexts) else None

    def show_namespaces(names: List[str], loaded_id: int) -> None:
        """Fill the list of namespaces unless a newer request replaced this one."""
        if loaded_id != request_id[0]:
            return
        namespaces[:] = names
        filling[0] = True  # swapping the model selects item 0, which must not touch the text
        namespaces_row.set_model(Gtk.StringList.new(names))
        namespaces_row.set_sensitive(bool(names))
        namespaces_row.set_subtitle("" if names else _("Not available: type the namespace below"))
        if namespace_row.get_text() in names:
            namespaces_row.set_selected(names.index(namespace_row.get_text()))
        filling[0] = False

    def load_namespaces(*_args) -> None:
        """List the namespaces of the chosen context in the background."""
        request_id[0] += 1
        loaded_id = request_id[0]
        context = selected_context()
        namespaces_row.set_sensitive(False)
        namespaces_row.set_subtitle(_("Loading..."))

        def worker() -> None:
            try:
                names = client.list_namespaces(context)
            except Exception:
                names = []
            GLib.idle_add(show_namespaces, names, loaded_id)

        threading.Thread(target=worker, daemon=True).start()

    def on_namespace_picked(row: Adw.ComboRow, _param) -> None:
        """Copy the namespace picked from the list into the text field."""
        index = row.get_selected()
        if filling[0]:
            return
        if 0 <= index < len(namespaces) and namespaces[index] != namespace_row.get_text():
            namespace_row.set_text(namespaces[index])

    context_row.connect("notify::selected", load_namespaces)
    namespaces_row.connect("notify::selected", on_namespace_picked)
    load_namespaces()

    dialog.set_extra_child(group)
    dialog.add_response("cancel", _("Cancel"))
    dialog.add_response("apply", _("Apply"))
    dialog.set_response_appearance("apply", Adw.ResponseAppearance.SUGGESTED)
    dialog.set_default_response("apply")
    dialog.set_close_response("cancel")

    def on_response(dlg: Adw.MessageDialog, response: str) -> None:
        """Apply the chosen context and namespace."""
        if response != "apply":
            return
        client.configure(selected_context(), namespace_row.get_text())
        on_success()

    dialog.connect("response", on_response)
    dialog.present()
