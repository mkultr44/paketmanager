# Paketmanager Touch-Anwendung

Diese Anwendung stellt eine Touchscreen-optimierte Oberfläche für den Paket-Check-in
und die Paketabholung in einer Tankstellenfiliale bereit. Sie wurde auf die
Eingabegeräte Raspberry Pi Touchscreen (1200x800) und Honeywell HF680
Barcode-Scanner abgestimmt.

## Hauptfunktionen

* **Automatischer Import der Zustellungsliste** über eine öffentlich
  freigegebene Nextcloud-WebDAV-URL.
* **Einbuchen-Modus** für das Einsortieren neuer Sendungen mit
  Zonen-Auswahl und fuzzy matching der OCR-Liste.
* **Standardmodus** mit Suchfeld, fuzzy Suche nach Kundennamen oder
  Sendungsnummern sowie Barcode-Scan-Unterstützung.
* **Zonenanzeige**, die bei Auswahl eines Pakets die passende Zone rot
  hervorhebt.

## Projektstruktur

```
src/
  paketmanager/
    __init__.py
    app.py
    config.py
    database.py
    fuzzy.py
    models.py
    ocr_fetcher.py
    ui/
      __init__.py
      main_window.py
      zone_indicator.py
requirements.txt
```

## Installation

1. Python 3.11 oder neuer installieren.
2. Abhängigkeiten installieren:

   ```bash
   pip install -r requirements.txt
   ```

3. Anwendung starten:

   ```bash
   python -m paketmanager.app
   ```

## Konfiguration

Die Standardeinstellungen (Zonen, WebDAV-URL, Polling-Intervalle) werden über
`src/paketmanager/config.py` verwaltet. Bei Bedarf kann dort die URL zur
Zustellungsliste oder die Liste der verfügbaren Zonen angepasst werden.

## Datenbank

Die Anwendung legt beim ersten Start automatisch eine SQLite-Datenbank unter
`data/paketmanager.db` an. Enthalten sind Tabellen für eingetroffene
Sendungen sowie die zuletzt importierte OCR-Liste.

## Hinweise für die Produktion

* Auf dem Raspberry Pi sollte die Anwendung im Vollbildmodus gestartet werden,
  beispielsweise über einen Autostart-Eintrag (`~/.config/lxsession/...`).
* Für eine stabile Netzwerkverbindung empfiehlt sich eine kabelgebundene
  Ethernet-Verbindung.
* Der Honeywell HF680 sendet standardmäßig ein Wagenrücklauf-Zeichen (CR).
  Die Anwendung entfernt dieses Zeichen automatisch.
* Die Anwendung protokolliert Ereignisse und Fehler in `logs/paketmanager.log`.

## Lizenz

Dieses Projekt steht unter der MIT-Lizenz. Details siehe `LICENSE`.
