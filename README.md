# Paketmanager

Ein Desktop-Programm für den Raspberry Pi 4 zum Verwalten von Paketen in einer Tankstelle. Die Anwendung synchronisiert Zustelllisten aus einer freigegebenen Nextcloud-WebDAV-Quelle, unterstützt einen Einbuchungsmodus für das Einsortieren von Paketen in Lagerzonen und bietet eine fuzzy Suche nach Sendungsnummern und Kundennamen.

## Voraussetzungen

* Raspberry Pi 4 mit installiertem Python 3.10 oder höher
* Touchscreen (1200x800, 8") und Honeywell HF680 Barcodescanner
* Netzwerkzugang zur Nextcloud-Instanz `https://nextcloud.aralbruehl.de/`
* Optional: virtuelle Umgebung für Python

## Installation

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Starten

```bash
python main.py
```

Beim ersten Start wird eine lokale SQLite-Datenbank unter `~/.paketmanager/paketmanager.db` erstellt.

## Bedienung

### Standardmodus

* Suchfeld verwendet fuzzy search, um nach Kunden oder Sendungsnummern zu suchen.
* Scans des Barcodes im Suchfeld filtern die Liste und heben bei eindeutiger Zuordnung die Zone hervor.
* Die Zonenanzeige wird rot, wenn eine Sendung ausgewählt oder eindeutig gefunden wird.
* `Clear` leert das Suchfeld.

### Einbuchmodus

1. Modus oben auf "Einbuchen" stellen.
2. Eine Zone auswählen.
3. Pakete scannen. Das Programm ordnet die Sendung einem Kunden aus der OCR-Liste zu und speichert sie mit Sendungsnummer, Kunde und Zone in der Datenbank.
4. Schritte 2-3 wiederholen, bis alle Pakete einsortiert sind.
5. Mit "Fertig" den Einbuchmodus beenden.

## Synchronisation

Die Anwendung synchronisiert alle 60 Sekunden mit dem Nextcloud-WebDAV-Verzeichnis. Es wird automatisch versucht, JSON- oder CSV-Dateien zu erkennen, die mindestens die Felder `tracking_number`/`sendungsnummer` und `customer`/`kunde` enthalten.

## Konfiguration

Standardmäßig gibt es vier Zonen (`Zone A` bis `Zone D`). Die Datei `paketmanager/config.py` kann angepasst werden, um weitere Zonen hinzuzufügen oder das Synchronisationsintervall zu ändern.

## Entwicklung

* `python -m compileall paketmanager` kompiliert den Code testweise.
* Logging-Ausgaben werden auf der Konsole angezeigt.
