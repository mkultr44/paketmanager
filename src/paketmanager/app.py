from __future__ import annotations

import logging
import threading
import time
import tkinter as tk
from pathlib import Path
from tkinter import ttk
from typing import Iterable

from .data_fetcher import RemoteConfig, RemoteShipmentFetcher
from .data_models import Shipment, Zone
from .database import Database
from .fuzzy import FuzzyMatchResult, ShipmentMatcher

logging.basicConfig(level=logging.INFO)

REMOTE_BASE_URL = "https://nextcloud.aralbruehl.de/public.php/dav/files/HMMEZAB25as8mbM/"
REMOTE_FILENAME = "shipments.json"
REFRESH_INTERVAL_SECONDS = 60
DATABASE_PATH = Path.home() / ".paketmanager" / "assignments.db"

ZONE_CONFIGURATION = [
    Zone(name="Zone A", capacity=15),
    Zone(name="Zone B", capacity=15),
    Zone(name="Zone C", capacity=15),
    Zone(name="Zone D", capacity=15),
]


class PaketManagerApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Paketmanager")
        self.geometry("1200x800")
        self.configure(background="#101820")

        DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
        self.database = Database(DATABASE_PATH)
        self.shipments: list[Shipment] = []
        self.matcher = ShipmentMatcher()
        self.assignments: dict[str, str] = {}
        self.zone_buttons: dict[str, ttk.Button] = {}
        self.selected_zone: Zone | None = None
        self.mode_var = tk.StringVar(value="standard")
        self.status_var = tk.StringVar(value="Bereit")
        self.search_var = tk.StringVar()
        self.remote_fetcher = RemoteShipmentFetcher(
            RemoteConfig(base_url=REMOTE_BASE_URL, filename=REMOTE_FILENAME)
        )

        self._build_ui()
        self._load_assignments()
        self._start_fetch_thread()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("TFrame", background="#101820")
        style.configure("TLabel", background="#101820", foreground="#f4f4f4", font=("Roboto", 14))
        style.configure("Zone.TButton", font=("Roboto", 16), padding=20)
        style.map("Zone.TButton", background=[("active", "#2d9cdb")])
        style.configure("ActiveZone.TButton", background="#2d9cdb", foreground="#101820")
        style.configure("TButton", font=("Roboto", 14), padding=12)
        style.configure("Treeview", font=("Roboto", 14), rowheight=40)
        style.configure("Treeview.Heading", font=("Roboto", 16, "bold"))

        container = ttk.Frame(self)
        container.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)

        header = ttk.Frame(container)
        header.pack(fill=tk.X)

        self.mode_button = ttk.Button(header, text="Einbuchen Modus", command=self.toggle_mode)
        self.mode_button.pack(side=tk.LEFT)

        finish_button = ttk.Button(header, text="Fertig", command=self.finish_check_in)
        finish_button.pack(side=tk.LEFT, padx=(10, 0))
        self.finish_button = finish_button

        status_label = ttk.Label(header, textvariable=self.status_var, font=("Roboto", 14))
        status_label.pack(side=tk.RIGHT)

        # Zone buttons
        zone_frame = ttk.LabelFrame(container, text="Zonen", padding=20)
        zone_frame.pack(fill=tk.X, pady=(20, 10))
        zone_frame.configure(style="TFrame")

        for zone in ZONE_CONFIGURATION:
            button = ttk.Button(
                zone_frame,
                text=f"{zone.name}\n0 / {zone.capacity}",
                style="Zone.TButton",
                command=lambda z=zone: self.select_zone(z),
            )
            button.pack(side=tk.LEFT, padx=10)
            self.zone_buttons[zone.name] = button

        # Search area
        search_frame = ttk.Frame(container)
        search_frame.pack(fill=tk.X, pady=(10, 10))

        search_label = ttk.Label(search_frame, text="Suche / Scan:")
        search_label.pack(side=tk.LEFT)

        search_entry = ttk.Entry(search_frame, textvariable=self.search_var, font=("Roboto", 16), width=40)
        search_entry.pack(side=tk.LEFT, padx=10, fill=tk.X, expand=True)
        search_entry.bind("<KeyRelease>", self.on_search_change)
        self.search_entry = search_entry

        clear_button = ttk.Button(search_frame, text="Clear", command=self.clear_search)
        clear_button.pack(side=tk.LEFT, padx=(10, 0))

        # Treeview for shipments
        tree_frame = ttk.Frame(container)
        tree_frame.pack(fill=tk.BOTH, expand=True)

        self.tree = ttk.Treeview(tree_frame, columns=("tracking", "customer", "zone"), show="headings")
        self.tree.heading("tracking", text="Sendungsnummer")
        self.tree.heading("customer", text="Kunde")
        self.tree.heading("zone", text="Zone")
        self.tree.column("tracking", anchor=tk.CENTER, width=200)
        self.tree.column("customer", anchor=tk.W, width=400)
        self.tree.column("zone", anchor=tk.CENTER, width=100)
        self.tree.pack(fill=tk.BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", self.on_tree_select)

        # Hidden entry for barcode scanner input
        self.scanner_entry = ttk.Entry(container)
        self.scanner_entry.pack_forget()
        self.scanner_entry.bind("<Return>", self.on_scan_submit)
        self.after(100, self.focus_scanner)

    # ------------------------------------------------------------------
    # Data handling
    # ------------------------------------------------------------------
    def _start_fetch_thread(self) -> None:
        threading.Thread(target=self._fetch_loop, daemon=True).start()

    def _fetch_loop(self) -> None:
        while True:
            try:
                shipments = self.remote_fetcher.fetch_if_modified()
                if shipments is not None:
                    logging.info("Remote list aktualisiert, %s Einträge", len(shipments))
                    self.after(0, lambda s=shipments: self.update_shipments(s))
            except Exception as exc:  # pragma: no cover - UI feedback only
                logging.exception("Fehler beim Abrufen der Daten: %s", exc)
                self.after(0, lambda e=exc: self.status_var.set(f"Download fehlgeschlagen: {e}"))
            time.sleep(REFRESH_INTERVAL_SECONDS)

    def update_shipments(self, shipments: Iterable[Shipment]) -> None:
        self.shipments = list(shipments)
        self.matcher.update(self.shipments)
        self.refresh_tree()
        self.status_var.set(f"Liste aktualisiert ({len(self.shipments)} Pakete)")

    def _load_assignments(self) -> None:
        for assignment in self.database.list_assignments():
            self.assignments[assignment.tracking_number] = assignment.zone
            for zone in ZONE_CONFIGURATION:
                if zone.name == assignment.zone:
                    zone.current_load += 1
        self.update_zone_buttons()

    # ------------------------------------------------------------------
    # Zone handling
    # ------------------------------------------------------------------
    def select_zone(self, zone: Zone) -> None:
        self.selected_zone = zone
        self.status_var.set(f"Zone {zone.name} ausgewählt")
        self.update_zone_buttons(active=zone.name)

    def update_zone_buttons(self, *, active: str | None = None) -> None:
        for zone in ZONE_CONFIGURATION:
            button = self.zone_buttons.get(zone.name)
            if not button:
                continue
            label = f"{zone.name}\n{zone.current_load} / {zone.capacity}"
            button.configure(text=label)
            if active and zone.name == active:
                button.configure(style="ActiveZone.TButton")
            else:
                button.configure(style="Zone.TButton")
        if hasattr(self, "finish_button"):
            if self.mode_var.get() == "einbuchen":
                self.finish_button.state(("!disabled",))
            else:
                self.finish_button.state(("disabled",))

    def highlight_zone_for_tracking(self, tracking_number: str) -> None:
        zone_name = self.assignments.get(tracking_number)
        if zone_name:
            self.update_zone_buttons(active=zone_name)
            self.status_var.set(f"Paket {tracking_number} in {zone_name}")
        else:
            self.update_zone_buttons(active=None)
            self.status_var.set(f"Keine Zone für {tracking_number}")

    # ------------------------------------------------------------------
    # Tree handling
    # ------------------------------------------------------------------
    def refresh_tree(self, *, query: str | None = None) -> list[FuzzyMatchResult]:
        for item in self.tree.get_children():
            self.tree.delete(item)
        if query is None:
            query = self.search_var.get()
        matches = self.matcher.filter(query)
        for match in matches:
            shipment = match.shipment
            zone = self.assignments.get(shipment.tracking_number, "-")
            self.tree.insert("", tk.END, iid=shipment.tracking_number, values=(
                shipment.tracking_number,
                shipment.customer_name,
                zone,
            ))
        if len(matches) == 1:
            self.highlight_zone_for_tracking(matches[0].shipment.tracking_number)
        return matches

    def on_tree_select(self, event: tk.Event) -> None:  # pragma: no cover - UI callback
        selected = self.tree.selection()
        if selected:
            self.highlight_zone_for_tracking(selected[0])

    # ------------------------------------------------------------------
    # Scanner / search handling
    # ------------------------------------------------------------------
    def focus_scanner(self) -> None:
        focused_widget = self.focus_get()
        if focused_widget not in (self.search_entry,):
            self.scanner_entry.focus_set()
        self.after(1000, self.focus_scanner)

    def on_search_change(self, event: tk.Event) -> None:
        query = self.search_var.get()
        self.refresh_tree(query=query)

    def clear_search(self) -> None:
        self.search_var.set("")
        self.refresh_tree(query="")

    def on_scan_submit(self, event: tk.Event) -> None:
        code = self.scanner_entry.get().strip()
        self.scanner_entry.delete(0, tk.END)
        if not code:
            return
        if self.mode_var.get() == "einbuchen":
            self.handle_check_in(code)
        else:
            self.search_var.set(code)
            matches = self.refresh_tree(query=code)
            if matches:
                self.highlight_zone_for_tracking(matches[0].shipment.tracking_number)
            else:
                self.highlight_zone_for_tracking(code)

    # ------------------------------------------------------------------
    # Mode handling
    # ------------------------------------------------------------------
    def toggle_mode(self) -> None:
        if self.mode_var.get() == "standard":
            self.mode_var.set("einbuchen")
            self.status_var.set("Einbuchen Modus aktiv")
            self.mode_button.configure(text="Zum Standard Modus")
        else:
            self.mode_var.set("standard")
            self.status_var.set("Standard Modus aktiv")
            self.mode_button.configure(text="Einbuchen Modus")
        self.update_zone_buttons(active=self.selected_zone.name if self.selected_zone else None)

    def handle_check_in(self, scanned_code: str) -> None:
        if not self.selected_zone:
            self.status_var.set("Bitte zuerst eine Zone wählen")
            return
        match = self.matcher.match_tracking(scanned_code)
        if not match:
            self.status_var.set(f"Keine passende Sendung für {scanned_code}")
            return
        zone = self.selected_zone
        if zone.is_full():
            self.status_var.set(f"{zone.name} ist voll")
            return
        assignment = self.database.add_assignment(
            tracking_number=match.shipment.tracking_number,
            customer_name=match.shipment.customer_name,
            scanned_tracking_number=scanned_code,
            zone=zone.name,
        )
        zone.register_package()
        self.assignments[assignment.tracking_number] = zone.name
        self.refresh_tree()
        self.update_zone_buttons(active=zone.name)
        self.status_var.set(
            f"{assignment.customer_name} ({assignment.tracking_number}) -> {zone.name} [Scan: {scanned_code}]"
        )

    def finish_check_in(self) -> None:
        if self.mode_var.get() == "einbuchen":
            self.mode_var.set("standard")
            self.selected_zone = None
            self.mode_button.configure(text="Einbuchen Modus")
            self.update_zone_buttons(active=None)
            self.status_var.set("Einbuchen abgeschlossen")


def main() -> None:
    app = PaketManagerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
