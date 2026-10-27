"""GCP project selection modal dialog controller."""

from __future__ import annotations

import threading
from typing import Callable, List, Optional

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib, Gtk

from src.i18n import _
from src.models import GCPProjectItem
from src.providers.gcp import GCPSecretClient


def show_change_project_dialog(
    parent_window: Gtk.Window,
    client: GCPSecretClient,
    on_confirm: Callable[[str], None],
) -> None:
    """Show a searchable modal dialog listing all available GCP projects for selection.

    Queries Google Cloud Resource Manager asynchronously, displays matching projects,
    and invokes the on_confirm callback when the user picks a project.

    Args:
        parent_window: GTK parent window to transient the dialog for.
        client: GCPSecretClient provider instance.
        on_confirm: Callback invoked with the chosen project ID string upon selection.
    """
    dialog = Adw.MessageDialog(
        transient_for=parent_window,
        heading=_("Select GCP Project"),
        body=_("Choose one of the active projects available in your Google Cloud account."),
    )

    box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
    box.set_margin_top(8)
    box.set_margin_bottom(8)
    box.set_margin_start(12)
    box.set_margin_end(12)
    box.set_size_request(460, 380)

    # Search Entry
    search_entry = Gtk.SearchEntry()
    search_entry.set_placeholder_text(_("Search project by ID or name..."))
    box.append(search_entry)

    # Stack: loading, list, error
    stack = Gtk.Stack()
    stack.set_transition_type(Gtk.StackTransitionType.CROSSFADE)
    box.append(stack)

    # Loading view
    loading_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
    loading_box.set_valign(Gtk.Align.CENTER)
    loading_box.set_halign(Gtk.Align.CENTER)
    loading_box.set_size_request(-1, 260)
    spinner = Gtk.Spinner()
    spinner.set_size_request(36, 36)
    spinner.start()
    loading_box.append(spinner)
    load_lbl = Gtk.Label(label=_("Querying projects in Google Cloud..."))
    load_lbl.add_css_class("dim-label")
    loading_box.append(load_lbl)
    stack.add_named(loading_box, "loading")

    # List view
    scrolled = Gtk.ScrolledWindow()
    scrolled.set_vexpand(True)
    scrolled.set_size_request(-1, 280)
    scrolled.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
    list_box = Gtk.ListBox()
    list_box.set_selection_mode(Gtk.SelectionMode.BROWSE)
    list_box.add_css_class("boxed-list")
    scrolled.set_child(list_box)
    stack.add_named(scrolled, "list")

    # Error view
    error_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
    error_box.set_valign(Gtk.Align.CENTER)
    error_box.set_halign(Gtk.Align.CENTER)
    error_box.set_size_request(-1, 260)
    err_lbl = Gtk.Label(label=_("Error querying projects"), wrap=True)
    err_lbl.add_css_class("error")
    error_box.append(err_lbl)
    stack.add_named(error_box, "error")

    dialog.set_extra_child(box)

    dialog.add_response("cancel", _("Cancel"))
    dialog.add_response("select", _("Select"))
    dialog.set_response_appearance("select", Adw.ResponseAppearance.SUGGESTED)
    dialog.set_default_response("select")
    dialog.set_response_enabled("select", False)
    dialog.set_close_response("cancel")

    selected_project_id: list[Optional[str]] = [None]

    def on_row_selected(lb: Gtk.ListBox, row: Optional[Adw.ActionRow]) -> None:
        """Update selected project ID and toggle select button sensitivity."""
        if row and hasattr(row, "project_id"):
            selected_project_id[0] = row.project_id
            dialog.set_response_enabled("select", True)
        else:
            dialog.set_response_enabled("select", False)

    list_box.connect("row-selected", on_row_selected)

    def on_row_activated(lb: Gtk.ListBox, row: Optional[Adw.ActionRow]) -> None:
        """Immediately confirm selection on double click or activation."""
        if row and hasattr(row, "project_id"):
            on_confirm(row.project_id)
            dialog.close()

    list_box.connect("row-activated", on_row_activated)

    def filter_func(row: Adw.ActionRow) -> bool:
        """Filter projects based on search query match."""
        query = search_entry.get_text().strip().lower()
        if not query:
            return True
        if not hasattr(row, "project_id"):
            return True
        p_id = row.project_id.lower()
        p_name = getattr(row, "project_name", "").lower()
        return query in p_id or query in p_name

    list_box.set_filter_func(filter_func)
    search_entry.connect("search-changed", lambda _: list_box.invalidate_filter())

    def on_response(dlg: Adw.MessageDialog, response: str) -> None:
        """Handle dialog action response."""
        if response == "select" and selected_project_id[0]:
            on_confirm(selected_project_id[0])

    dialog.connect("response", on_response)

    # Background worker to fetch projects
    def load_projects_worker() -> None:
        """Background thread fetching GCP projects from Resource Manager."""
        try:
            projects = client.list_available_projects()
            GLib.idle_add(on_projects_loaded, projects, None)
        except Exception as exc:
            GLib.idle_add(on_projects_loaded, [], str(exc))

    def on_projects_loaded(projects: List[GCPProjectItem], error: Optional[str]) -> None:
        """Handle projects query result on the GTK main thread."""
        spinner.stop()
        if error:
            err_lbl.set_label(f"{_('Error querying projects')}:\n{error}")
            stack.set_visible_child_name("error")
            return

        current = client.project_id
        current_row = None

        for p in projects:
            row = Adw.ActionRow(title=p.project_id)
            if p.name and p.name != p.project_id:
                row.set_subtitle(p.name)

            if p.project_id == current:
                badge = Gtk.Label(label=_("Active"))
                badge.add_css_class("pill")
                badge.add_css_class("success")
                row.add_suffix(badge)
                current_row = row

            row.project_id = p.project_id
            row.project_name = p.name
            list_box.append(row)

        stack.set_visible_child_name("list")
        if current_row:
            list_box.select_row(current_row)

    threading.Thread(target=load_projects_worker, daemon=True).start()
    dialog.present()
