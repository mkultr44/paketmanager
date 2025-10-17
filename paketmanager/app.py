"""Main Tkinter user interface for the Paketmanager."""
from __future__ import annotations

import logging
import threading
from datetime import datetime
from functools import partial
from typing import Dict, Iterable, List, Optional

import tkinter as tk
from tkinter import ttk, messagebox

from . import config
from .data_fetcher import DeliveryFetcher
from .database import add_parcel, ensure_database, find_zone_for_tracking, list_parcels
from .fuzzy import best_match, fuzzy_filter
from .models import Delivery

logger = logging.getLogger(__name__)


class PaketManagerApp(tk.Tk):
    """Tkinter based application."""

    def __init__(self) -> None:
        super().__init__()
        self.title("Paketmanager")
        self.geometry("1200x800")
        self.configure(bg="#1e1e1e")
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        ensure_database()

        self.fetcher = DeliveryFetcher()
        self.deliveries: List[Delivery] = []
        self.filtered: List[Delivery] = []
        self.zone_assignments: Dict[str, str] = {}
        for parcel in list_parcels():
            self.zone_assignments[parcel.scanned_tracking_number] = parcel.zone
            if parcel.original_tracking_number:
                self.zone_assignments[parcel.original_tracking_number] = parcel.zone

        self.mode_var = tk.StringVar(value="standard")
        self.selected_zone = tk.StringVar(value="")
        self.search_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Bereit")

        self._build_widgets()
        self._schedule_sync(initial=True)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_widgets(self) -> None:
        self._build_mode_row()
        self._build_search_row()
        self._build_content()
        self._build_status_bar()

    def _build_mode_row(self) -> None:
        frame = ttk.Frame(self)
        frame.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        frame.columnconfigure(3, weight=1)

        ttk.Label(frame, text="Modus:", font=("Arial", 16, "bold")).grid(row=0, column=0, padx=(0, 10))

        standard_button = ttk.Radiobutton(
            frame,
            text="Standard",
            variable=self.mode_var,
            value="standard",
            command=self._on_mode_changed,
        )
        standard_button.grid(row=0, column=1, padx=5)

        inbound_button = ttk.Radiobutton(
            frame,
            text="Einbuchen",
            variable=self.mode_var,
            value="einbuchen",
            command=self._on_mode_changed,
        )
        inbound_button.grid(row=0, column=2, padx=5)

        finish_button = ttk.Button(frame, text="Fertig", command=self._finish_inbound)
        finish_button.grid(row=0, column=4, padx=5)
        self.finish_button = finish_button

    def _build_search_row(self) -> None:
        frame = ttk.Frame(self)
        frame.grid(row=1, column=0, sticky="ew", padx=10)
        frame.columnconfigure(1, weight=1)

        ttk.Label(frame, text="Suche:", font=("Arial", 14)).grid(row=0, column=0, padx=(0, 10))

        entry = ttk.Entry(frame, textvariable=self.search_var, font=("Arial", 14))
        entry.grid(row=0, column=1, sticky="ew", pady=5)
        entry.bind("<KeyRelease>", lambda event: self._update_filter())
        entry.bind("<Return>", lambda event: self._handle_search_enter())
        self.search_entry = entry

        clear_button = ttk.Button(frame, text="Clear", command=self._clear_search)
        clear_button.grid(row=0, column=2, padx=5)

    def _build_content(self) -> None:
        container = ttk.Frame(self)
        container.grid(row=2, column=0, sticky="nsew", padx=10, pady=10)
        container.columnconfigure(0, weight=3)
        container.columnconfigure(1, weight=0)
        container.columnconfigure(2, weight=1)
        container.rowconfigure(0, weight=1)

        self.tree = ttk.Treeview(
            container,
            columns=("tracking", "customer", "zone"),
            show="headings",
            height=25,
        )
        self.tree.heading("tracking", text="Sendungsnummer")
        self.tree.heading("customer", text="Kunde")
        self.tree.heading("zone", text="Zone")
        self.tree.column("tracking", width=250)
        self.tree.column("customer", width=400)
        self.tree.column("zone", width=100)
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)
        self.tree.grid(row=0, column=0, sticky="nsew")

        scrollbar = ttk.Scrollbar(container, orient="vertical", command=self.tree.yview)
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=scrollbar.set)

        # Zone panel
        zones_frame = ttk.LabelFrame(container, text="Zonen", padding=10)
        zones_frame.grid(row=0, column=2, sticky="nsew", padx=(10, 0))
        zones_frame.columnconfigure(0, weight=1)

        self.zone_labels: Dict[str, tk.Label] = {}
        self.zone_buttons: Dict[str, ttk.Button] = {}
        for index, zone in enumerate(config.DEFAULT_ZONES):
            label = tk.Label(
                zones_frame,
                text=zone.name,
                font=("Arial", 16, "bold"),
                width=12,
                height=2,
                relief="ridge",
                bd=2,
                bg="#3a3a3a",
                fg="white",
            )
            label.grid(row=index, column=0, sticky="ew", pady=5)
            self.zone_labels[zone.name] = label

            button = ttk.Button(
                zones_frame,
                text=f"{zone.name} wählen",
                command=partial(self._select_zone, zone.name),
            )
            button.grid(row=index, column=1, padx=5, pady=5, sticky="ew")
            self.zone_buttons[zone.name] = button

        # Hidden entry for scanner input during inbound mode
        self.scan_entry = ttk.Entry(container)
        self.scan_entry.grid_remove()
        self.scan_entry.bind("<Return>", self._handle_scan)

    def _build_status_bar(self) -> None:
        frame = ttk.Frame(self)
        frame.grid(row=3, column=0, sticky="ew", padx=10, pady=(0, 10))
        frame.columnconfigure(0, weight=1)
        status_label = ttk.Label(frame, textvariable=self.status_var, anchor="w")
        status_label.grid(row=0, column=0, sticky="ew")

    # ------------------------------------------------------------------
    # Mode handling
    # ------------------------------------------------------------------
    def _on_mode_changed(self) -> None:
        mode = self.mode_var.get()
        if mode == "einbuchen":
            self._enter_inbound_mode()
        else:
            self._enter_standard_mode()

    def _enter_standard_mode(self) -> None:
        self.status_var.set("Standardmodus aktiv")
        self.selected_zone.set("")
        self._update_zone_highlights()
        self.scan_entry.delete(0, tk.END)
        self.scan_entry.grid_remove()
        self.search_entry.focus_set()

    def _enter_inbound_mode(self) -> None:
        self.status_var.set("Einbuchmodus aktiv - bitte Zone wählen")
        self.scan_entry.grid()
        self.scan_entry.focus_set()

    def _finish_inbound(self) -> None:
        self.mode_var.set("standard")
        self._enter_standard_mode()

    def _select_zone(self, zone_name: str) -> None:
        if self.mode_var.get() != "einbuchen":
            messagebox.showinfo("Info", "Bitte zuerst den Einbuchen-Modus aktivieren.")
            return
        self.selected_zone.set(zone_name)
        self.status_var.set(f"Zone {zone_name} ausgewählt. Bitte scannen.")
        self._update_zone_highlights(active_zone=zone_name, flash=True)
        self.scan_entry.focus_set()

    # ------------------------------------------------------------------
    # Synchronisation logic
    # ------------------------------------------------------------------
    def _schedule_sync(self, initial: bool = False) -> None:
        delay = 1000 if initial else config.SYNC_INTERVAL_MS
        self.after(delay, self._sync_deliveries)

    def _sync_deliveries(self) -> None:
        def worker() -> None:
            try:
                if not self.deliveries or self.fetcher.has_updates():
                    deliveries = self.fetcher.fetch_latest()
                    self.after(0, lambda: self._on_deliveries_loaded(deliveries))
            except Exception as exc:  # pragma: no cover - network errors
                logger.exception("Fehler beim Synchronisieren: %s", exc)
                self.after(0, lambda: self.status_var.set(f"Sync-Fehler: {exc}"))

        threading.Thread(target=worker, daemon=True).start()
        self._schedule_sync()

    def _on_deliveries_loaded(self, deliveries: Iterable[Delivery]) -> None:
        self.deliveries = list(deliveries)
        self.status_var.set(f"{len(self.deliveries)} Sendungen geladen")
        self._update_filter()

    # ------------------------------------------------------------------
    # Search and filtering
    # ------------------------------------------------------------------
    def _update_filter(self) -> None:
        query = self.search_var.get()
        if not query:
            self.filtered = list(self.deliveries)
            matches = [(delivery, 1.0) for delivery in self.deliveries]
        else:
            matches = fuzzy_filter(query, self.deliveries)
            self.filtered = [delivery for delivery, _ in matches]

        self.tree.delete(*self.tree.get_children())
        for index, (delivery, _score) in enumerate(matches):
            zone = self.zone_assignments.get(delivery.tracking_number, "-")
            iid = f"{delivery.tracking_number}:{index}"
            self.tree.insert(
                "",
                "end",
                iid=iid,
                values=(delivery.tracking_number, delivery.customer, zone),
            )

        if query:
            if len(self.filtered) == 1:
                zone = self.zone_assignments.get(self.filtered[0].tracking_number)
                if zone:
                    self._update_zone_highlights(active_zone=zone)
            else:
                self._update_zone_highlights()
        else:
            self._update_zone_highlights()

    def _handle_search_enter(self) -> None:
        if self.filtered:
            delivery = self.filtered[0]
            zone = self.zone_assignments.get(delivery.tracking_number)
            if zone:
                self._update_zone_highlights(active_zone=zone, flash=True)

    def _clear_search(self) -> None:
        self.search_var.set("")
        self._update_filter()
        self.search_entry.focus_set()

    # ------------------------------------------------------------------
    # Tree selection handling
    # ------------------------------------------------------------------
    def _on_tree_select(self, _event: object) -> None:
        selected = self.tree.selection()
        if not selected:
            return
        tracking_number = self.tree.item(selected[0], "values")[0]
        zone = self.zone_assignments.get(tracking_number)
        if zone:
            self._update_zone_highlights(active_zone=zone, flash=True)
        else:
            zone = find_zone_for_tracking(tracking_number)
            if zone:
                self.zone_assignments[tracking_number] = zone
                self._update_zone_highlights(active_zone=zone, flash=True)

    # ------------------------------------------------------------------
    # Scan handling
    # ------------------------------------------------------------------
    def _handle_scan(self, _event: object) -> None:
        if self.mode_var.get() != "einbuchen":
            messagebox.showinfo("Info", "Bitte den Einbuchen-Modus aktivieren.")
            return
        zone = self.selected_zone.get()
        if not zone:
            messagebox.showwarning("Zone wählen", "Bitte zuerst eine Zone auswählen.")
            return

        scan_value = self.scan_entry.get().strip()
        self.scan_entry.delete(0, tk.END)
        if not scan_value:
            return

        if not self.deliveries:
            messagebox.showwarning("Keine Daten", "Es wurden noch keine Sendungen geladen.")
            return

        match = best_match(scan_value, self.deliveries)
        if match.delivery is None or match.score < config.FUZZY_MATCH_THRESHOLD:
            messagebox.showwarning(
                "Nicht gefunden",
                f"Keine passende Sendung für {scan_value} gefunden (Score: {match.score:.2f}).",
            )
            return

        delivery = match.delivery
        add_parcel(scan_value, delivery.customer or "", zone, original_tracking_number=delivery.tracking_number)
        self.zone_assignments[scan_value] = zone
        self.zone_assignments[delivery.tracking_number] = zone
        self.status_var.set(
            f"{datetime.now():%H:%M:%S}: {scan_value} -> {delivery.customer} in {zone} gespeichert"
        )
        self._update_filter()
        self._update_zone_highlights(active_zone=zone, flash=True)

    # ------------------------------------------------------------------
    # Zone highlighting
    # ------------------------------------------------------------------
    def _update_zone_highlights(self, active_zone: Optional[str] = None, flash: bool = False) -> None:
        for zone_name, label in self.zone_labels.items():
            if zone_name == active_zone:
                label.configure(bg="red")
            else:
                label.configure(bg="#3a3a3a")

        if flash and active_zone:
            self.after(200, lambda: self.zone_labels[active_zone].configure(bg="#8b0000"))


def run() -> None:
    logging.basicConfig(level=logging.INFO)
    app = PaketManagerApp()
    app.mainloop()


if __name__ == "__main__":
    run()
