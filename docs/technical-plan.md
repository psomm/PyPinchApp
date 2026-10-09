# PyPinch als Flet-App: technische Bestandsaufnahme und Migrationsplan

Stand der Analyse: 24. September 2026. Dieser Plan dokumentiert die Lage vor
der Implementierung. Der aktuelle Entwicklungsstand steht in der [README](../README.md);
Upstream-Commit und Originaldateien sind in [upstream.md](upstream.md) belegt.

## A. Repository Assessment

### Tatsächlicher Ausgangspunkt

Das lokale Repository ist **kein Checkout von `anicusan/PyPinch`**: Es hat keinen Remote, keinen Commit und nur ein unversioniertes Gerüst (`main.py` mit „Hello from pinch-app!“, leere `README.md`, `pyproject.toml` ohne Dependencies, `.python-version` mit `3.11`, `.gitignore`). Insbesondere fehlen `src/PyPinch.py`, `src/usage.py`, CSV-Dateien und Notebooks. Ein lokaler Golden-Test gegen den Originalsolver ist daher heute nicht ausführbar. Ein Git-Zugriff auf GitHub war aus dieser Umgebung nicht möglich; die folgende Upstream-Analyse basiert auf den öffentlich einsehbaren Quelldateien. **Der erste Implementierungsschritt muss den unveränderten Upstream-Stand samt Commit-ID und Herkunft reproduzierbar ins Projekt holen.**

Upstream enthält `src/` mit `PyPinch.py`, `usage.py`, `PinchTutorial.ipynb` und `streams/`, außerdem `example/` mit `PyPinch.py`, `usage.py`, `streams/streams.csv`, `streams/manystreams.csv`, `tutorial/PinchTutorial.ipynb`, `README.md` und `requirements.txt`. Der Inhalt einiger `src/`-Dateien war über den Webzugang nicht abrufbar; insbesondere darf eine Abweichung zwischen `src/PyPinch.py` und der Kopie in `example/` erst nach lokalem Import ausgeschlossen werden. Das einsehbare Tutorial beschreibt dieselbe Aufrufreihenfolge und die Temperaturverschiebung. [Upstream-Verzeichnis](https://github.com/anicusan/PyPinch), [Solver](https://raw.githubusercontent.com/anicusan/PyPinch/master/src/PyPinch.py), [Beispielaufruf](https://github.com/anicusan/PyPinch/blob/master/example/usage.py), [Tutorial](https://raw.githubusercontent.com/anicusan/PyPinch/master/tutorial/PinchTutorial.ipynb).

### Alter Code und Datenfluss

`Streams.__init__` liest einen Dateipfad mit `csv.reader`, prüft die ersten beiden Zeilen und ruft `createStreams()` auf. Das bestätigte Format lautet `Tmin,20` und `CP,TSUPPLY,TTARGET`, gefolgt von Zeilen mit `cp,ts,tt`. Leerzeichen um Headerwerte werden toleriert; die Bezeichnungen und Reihenfolge sind fest. `createStreams()` konvertiert mit `float`, klassifiziert `supply > target` als `HOT`, sonst als `COLD`, und fordert mindestens zwei Streams. CSV-Beispiele enthalten vier bzw. vierzehn Streams. [Parser und Modell im Altcode](https://raw.githubusercontent.com/anicusan/PyPinch/master/src/PyPinch.py), [kleines Beispiel](https://raw.githubusercontent.com/anicusan/PyPinch/master/example/streams/streams.csv), [großes Beispiel](https://raw.githubusercontent.com/anicusan/PyPinch/master/example/streams/manystreams.csv).

`PyPinch.__init__` erstellt ein `Streams`-Objekt und viele veränderbare Ergebnislisten/-dicts. `solve()` ruft in fester Reihenfolge `shiftTemperatures`, `constructTemperatureInterval`, `constructProblemTable`, `constructHeatCascade`, `constructShiftedCompositeDiagram`, `constructCompositeDiagram`, `constructGrandCompositeCurve` und bei `draw` schließlich `showPlots` auf. `usage.py` zeigt Options-Sets für `draw`, `csv`, `debug`; es ist ein Skriptbeispiel, keine UI. [Upstream-Solver](https://raw.githubusercontent.com/anicusan/PyPinch/master/src/PyPinch.py), [Beispielnutzung](https://github.com/anicusan/PyPinch/blob/master/example/usage.py).

Fachkern sind Intervallbildung, CP-Bilanz, Enthalpieänderungen, Kaskaden, Utility-Ziele und Kurvenkoordinaten. I/O und Darstellung sind CSV-Lesen in `Streams`, `csvProblemTable`/`csvHeatCascade`/`csv*Diagram` mit festen Dateinamen im aktuellen Verzeichnis, `draw*` mit Matplotlib, `showPlots()` mit `plt.show()` und `debug`-Ausgaben. Der Import von `matplotlib.pyplot` erfolgt bereits beim Modulimport. Upstream `requirements.txt` pinnt nur `matplotlib==3.0.2`; NumPy ist damit höchstens eine transitive Abhängigkeit, der eigentliche Solver benutzt es nicht. [Solver](https://raw.githubusercontent.com/anicusan/PyPinch/master/src/PyPinch.py), [Requirements](https://github.com/anicusan/PyPinch/blob/master/requirements.txt).

### Fachliche und technische Risiken im Altcode

- `Supply == Target` wird als `COLD` eingestuft, obwohl kein Wärmestrom vorliegt. Für neue Eingaben als Feldfehler ablehnen; alte Ergebnisse zunächst als Legacy-Verhalten charakterisieren.
- `CP <= 0`, negatives `Tmin` sowie `NaN`/`Inf` passieren die Konvertierung. In der neuen API ablehnen; jede Verhaltensänderung durch einen reproduzierbaren Test dokumentieren. Identische vollständige Streams sind dagegen physikalisch zulässig und werden nicht pauschal abgewiesen.
- `pinchTemperature` ist der **verschobene** Wert `temperatureInterval[pinchInterval]['t2']`. Das ist weder automatisch die tatsächliche Hot- noch Cold-Pinch-Temperatur. Bei nie negativer unzulässiger Kaskade bleibt `pinchInterval = 0`; eine echte interne Pinch-Lage ist dann nicht belegt. Erst Legacy-Wert einfrieren, anschließend eindeutige Felder und Beschriftung definieren.
- Die Kaskade speichert den jeweils ersten **streng kleineren** Minimalwert; bei gleich tiefen Minima wird eine mögliche Mehrfach-Pinch-Lage nicht repräsentiert. Toleranz und Semantik als separates fachliches Review behandeln.
- `solve()` ist wiederholt auf demselben Objekt nicht idempotent: Ergebnisse werden an Listen angehängt und Temperaturen teils in-place umgedreht. Die neue Funktion erhält einen frischen Zustand pro Aufruf.
- Setzen von `set(temperatures)` und direkte Float-Vergleiche können bei nahe beieinander liegenden Grenzen numerisch empfindlich sein. Vor etwaiger Toleranzänderung Vergleichstest schreiben.
- Die Plots benutzen als vertikale Füllgrenze teilweise `0` statt der unteren Temperatur; das ist eine Darstellungsannahme und kein Solverergebnis.

### Lizenz

Im Upstream-Hauptverzeichnis ist keine `LICENSE`-Datei gelistet; die Python-Dateien nennen „GNU v3.0“ und Andrei Leonard Nicusan. Vor Codeübernahme Lizenztext und genaue Lizenzbezeichnung prüfen, Copyright-/Autorenhinweise erhalten, Upstream und verwendeten Commit in README/NOTICE nennen und Quellen eines veröffentlichten Forks zugänglich halten. Dies sind technische Open-Source-Compliance-Punkte, keine Rechtsberatung. [Upstream-Dateiliste](https://github.com/anicusan/PyPinch), [Dateikopf](https://raw.githubusercontent.com/anicusan/PyPinch/master/src/PyPinch.py).

## B. Fachliche Berechnungs-Pipeline

1. CSV → `Streams.streamsData`: Liste von Dicts mit `type`, `cp`, `ts`, `tt`; `tmin` separat. Einheit: °C, kW/°C, kW.
2. `shiftTemperatures`: Hot `ts/tt - ΔTmin/2`, Cold `ts/tt + ΔTmin/2`; speichert `ss/st` in denselben Dicts.
3. `constructTemperatureInterval`: sortiert alle eindeutigen verschobenen Endtemperaturen absteigend; pro Nachbarpaar `t1`, `t2` und Indizes der aktiven Streams.
4. `constructProblemTable`: pro Intervall `deltaS = t1-t2`, `deltaCP = ΣCP_hot-ΣCP_cold`, `deltaH = deltaS*deltaCP`.
5. `constructHeatCascade`: kumuliert `deltaH` von oben nach unten zunächst mit Startwert 0. `QH,min = -min(0, kumulative Werte)`. Zweiter Durchlauf startet mit `QH,min`; sein Endwert ist `QC,min`. Der alte Pinch-Wert ist die untere verschobene Grenze des Intervalls beim ersten neuen Minimum.
6. `constructShiftedCompositeDiagram`: integriert Hot- und Cold-CP je Intervall von niedriger zu höherer verschobener Temperatur; die Cold-Kurve beginnt bei `QC,min`. Datenform `{'hot': {'H': [], 'T': []}, 'cold': ...}`.
7. `constructCompositeDiagram`: transformiert Hot-Temperaturen um `+ΔTmin/2`, Cold um `-ΔTmin/2`; H-Werte bleiben gleich.
8. `constructGrandCompositeCurve`: Punkte aus `QH,min` und den Austrittswerten der zulässigen Kaskade gegen absteigende verschobene Temperaturgrenzen.

Beibehaltung der Rechenreihenfolge und Zwischenwerte ist wichtiger als ein „schönerer“ Neuansatz. [Algorithmus im Original](https://raw.githubusercontent.com/anicusan/PyPinch/master/src/PyPinch.py).

## C. Proposed Architecture

```text
pyproject.toml                   # Metadaten, Versionen, Flet-Buildkonfiguration, Test/Lint
src/main.py                      # stabiler Flet-Einstiegspunkt, nur ft.run(main)
src/pypinch_app/
  core/
    models.py                    # unveränderliche Streams, Intervall-/Kurven-/Ergebniswerte
    validation.py                # feldbezogene fachliche Regeln
    csv_input.py                 # bytes/str -> gemeinsames Eingabemodell
    solver.py                    # reine Pinch-Berechnung
  ui/
    app.py                       # Flet-Seite, Navigation, Eingabe, Ergebnisse
    state.py                     # Zustand pro Flet-Session und Eingabezeilen
    charts.py                    # Ergebnis -> Flet-Chart-Daten
  export.py                      # Ergebnis -> CSV-bytes, ohne Dateizugriff
tests/
  fixtures/                     # originalgetreue Upstream-CSVs und Golden-Werte
  test_core.py
  test_csv.py
  test_export.py
  test_ui.py                     # wenige wertvolle Flet-Integrationstests
.vscode/tasks.json
.vscode/launch.json
.github/workflows/ci.yml
.github/workflows/pages.yml
docs/technical-plan.md
```

Kein `pages/`, `components/` oder eigener Controller-Baum vor tatsächlichem Bedarf. Der Flet-Einstiegspunkt liegt gemäß aktuellem Flet-Buildlayout in `src/main.py`; `[tool.flet.app].path = "src"` macht das für Builds ausdrücklich. `flet run --recursive src/main.py` beobachtet damit das ganze Anwendungspaket. Für reine Core-Tests wird `pythonpath = ["src"]` in der pytest-Konfiguration gesetzt. Der Core importiert weder Flet noch Matplotlib noch UI-/Exportcode. UI-Zeilen mit unvollständigen Strings und stabilen IDs gehören in `ui/state.py`; `ProcessStream` entsteht erst aus validen Werten. Resultate werden pro Analyse neu berechnet. Dieser Zuschnitt bleibt auch für optionale Desktop-Builds verwendbar. [Flet-Projektlayout](https://flet.dev/docs/publish/).

## D. Core API und Datenregeln

```python
@dataclass(frozen=True)
class ProcessStream:
    cp_kw_per_c: float
    supply_c: float
    target_c: float

    @property
    def stream_type(self) -> StreamType: ...  # HOT bei supply > target

@dataclass(frozen=True)
class AnalysisInput:
    streams: tuple[ProcessStream, ...]
    delta_t_min_c: float

@dataclass(frozen=True)
class ValidationIssue:
    field: str                 # z. B. streams[2].cp_kw_per_c
    message: str

@dataclass(frozen=True)
class PinchResult:
    hot_utility_kw: float
    cold_utility_kw: float
    legacy_pinch_shifted_c: float
    temperature_intervals: tuple[TemperatureInterval, ...]
    problem_table: tuple[ProblemRow, ...]
    infeasible_cascade: tuple[CascadeRow, ...]
    feasible_cascade: tuple[CascadeRow, ...]
    shifted_composite: CompositeCurves
    composite: CompositeCurves
    grand_composite: tuple[CurvePoint, ...]

def parse_streams_csv(data: bytes | str) -> AnalysisInput: ...
def validate_input(data: AnalysisInput) -> tuple[ValidationIssue, ...]: ...
def solve_pinch(streams: Sequence[ProcessStream], delta_t_min_c: float) -> PinchResult: ...
def export_result_csv(result: PinchResult, kind: ExportKind) -> bytes: ...
```

`parse_streams_csv` dekodiert UTF-8 (auch BOM), prüft Format, Zeilennummer und endliche Zahlen; ungültige Eingaben liefern spezifische Parse-Fehler, die die UI in `ValidationIssue` umsetzt. Import ersetzt nach erfolgreichem Parse die editierbaren UI-Zeilen und `ΔTmin`; bei Fehler bleiben bisherige Eingaben bestehen. Manuelle Felder werden mit derselben Normalisierung und denselben Fachregeln verarbeitet. `CP > 0`, `ΔTmin >= 0`, `supply != target`, endliche Zahlen und zunächst mindestens zwei Streams sind verbindlich. Duplikate bleiben zulässig. Keine willkürliche Obergrenze für Temperatur oder CP; Überlauf und unbrauchbare Intervallabstände werden explizit abgefangen. Dezimalpunkt ist das kanonische CSV-Format, eine deutsche Komma-Eingabe darf nur im manuellen Feld normalisiert werden.

Dataclasses reichen; Pydantic wäre hier eine zusätzliche Runtime-Abhängigkeit mit Binary-/Pyodide-Fragen. Für das UI dient `ValidationIssue.field` zur direkten Feldzuordnung. `legacy_pinch_shifted_c` bewahrt zunächst den Originalwert; für die Anzeige zusätzlich `hot_pinch_c = S + ΔTmin/2` und `cold_pinch_c = S - ΔTmin/2` nur bei fachlich nachgewiesener Pinch-Lage ableiten. Bei fehlender eindeutiger Lage eine explizite „kein eindeutiger interner Pinch“-Anzeige vorsehen, ohne den Golden-Wert zu überschreiben.

## E. UI Architecture

Start: leere, fokussierbare `ΔTmin`-Eingabe; „Stream hinzufügen“, „CSV importieren“, „Beispiel laden“. Erst gültige Daten aktivieren „Analyse starten“. Streamtyp ist abgeleitet und zunächst bei unvollständigen Temperaturen als „—“ dargestellt. Pro Feld Fehlertext; Datei- und Rechenfehler als verständliche Meldung, keine Tracebacks. Nach Bearbeitung bleibt das letzte Resultat sichtbar, aber deutlich als **veraltet** markiert; Export bleibt bis zur Neuberechnung deaktiviert. Ein Flet-Session-Objekt hält Eingabezeilen, Fehler, Resultat, Revision und gewählte Ergebnisansicht. Kein globaler veränderbarer Zustand.

Ab etwa 720 px verfügbarem Inhalt ist ein Tabellen-/Zeilenlayout sinnvoll; darunter je Stream eine Card mit 3 Zahlenfeldern, automatisch erkanntem Typ und Löschaktion. Der Breakpoint liegt in einer Konstante und wird im Browser bei etwa 390, 430, 768 und 1440 px geprüft. Touch-Ziele und numerische Tastatur (`TextField.keyboard_type`) werden mit echten Geräten überprüft. Breite Ergebnisansichten bekommen auf Telefonen kompakte Listen/Karten mit klaren Einheiten; Diagramme nutzen nahezu volle Breite. Auf Desktop kann eine `NavigationRail` oder horizontale Tabs die Bereiche zeigen; auf Telefon eine schlanke `NavigationBar` für Eingabe/Übersicht/Details mit Detailauswahl für die sieben Fachansichten. Nicht sieben winzige Bottom-Navigation-Items erzwingen. KPIs: QH,min, QC,min, eindeutig beschriftete Pinch-Temperatur(en), ΔTmin, Streamzahl.

Diagramme lesen nur `PinchResult`. Für Composite, Shifted Composite und Grand Composite zuerst `flet-charts`-`LineChart`; Temperaturintervalle als einfache Flet-Darstellung. Matplotlib bleibt nur für die Golden-Referenz/optional als Entwicklungsvergleich. Das vermeidet eine fachlich unnötige Runtime-Abhängigkeit, große Binärpakete und plattformspezifische Backend-Fragen. Konkret: Der alte Pin `matplotlib==3.0.2` passt nicht zur von Flet für Python 3.12 gewählten Pyodide-Version 0.27.7 (dort Matplotlib 3.8.4); Flets Android-Index listet wiederum 3.10.0/3.10.9. Ein einziger unveränderter Matplotlib-Pin für beide Ziele ist damit nicht belegt. Achsen, Einheiten, Hot/Cold-Farben, Datenpunkte, Nullpunkt und Pinch-Marker werden gegen alte Kurvenwerte geprüft. [Flet LineChart](https://flet.dev/docs/controls/charts/linechart/), [MatplotlibChart](https://flet.dev/docs/controls/charts/matplotlibchart/), [Pyodide-0.27.7-Paketliste](https://pyodide.org/en/0.27.7/usage/packages-in-pyodide.html), [Android-Wheels](https://flet.dev/docs/reference/binary-packages-android-ios/), [Flet-1.0-Migration](https://flet.dev/docs/updates/migrate-to-1-0/).

CSV-Export wird mit `csv.writer` in `io.StringIO` erzeugt und als UTF-8-Bytes an `FilePicker.save_file(src_bytes=...)` übergeben. `FilePicker.pick_files(with_data=True)` liefert die Importbytes; Web/Safari braucht für den Picker gegebenenfalls die dokumentierte `PickFiles`-Clientaktion direkt am Button. Keine Pfade im Core und keine Uploads. ZIP bleibt nach dem MVP. [FilePicker](https://flet.dev/docs/services/filepicker/).

## F. Web Strategy

| Thema | Risiko | Begründung / Nachweis im Implementierungsschritt |
| --- | --- | --- |
| Statische Flet-Web-App / Pyodide | mittel | Offiziell unterstützt; reiner Standardbibliotheks-Solver läuft grundsätzlich clientseitig. Produktionsbuild und Browser-Smoke-Test sind Pflicht. |
| Matplotlib im Web | hoch | Pyodide-Binärpaket, Ladezeit und Chart-Integration; deshalb nicht als MVP-Runtime. |
| `flet-charts` | mittel | Eigenes Erweiterungspaket seit Flet 1.0; mit derselben Flet-Version pinnen und im gebauten Web-Client prüfen. |
| CSV-Picker | niedrig bis mittel | `with_data=True` liefert Bytes; Safari-Gestenregel mit Clientaktion prüfen. |
| CSV-Download | mittel | `save_file` mit `src_bytes` ist dokumentiert; Browser und Dateinamen praktisch testen. |
| PWA | mittel | Manifest, Icon, Name und Farben sind machbar. Offline-Fähigkeit hängt zusätzlich von Caching/Service Worker und CDN-Nutzung ab; installierbar bedeutet nicht garantiert offline. |
| GitHub Pages | niedrig bis mittel | Offizielle Action-Vorlage existiert; Base-URL unter Repo-Pfad und Hash-Routing verwenden, direkte Reloads testen. |

`flet run --web --recursive main.py` ist der schnelle **Entwicklungsserver**. Er beweist nicht, dass der Solver unter Pyodide läuft. `flet build web --base-url /<repo>/ --route-url-strategy hash` erzeugt die statische Version; `flet serve` und ein echter Browser prüfen sie. `flet publish` ist ein möglicher schnellerer Fallback, lädt Python-Abhängigkeiten aber erst beim Öffnen nach; `flet build web` ist für GitHub Pages und reproduzierbare Abhängigkeiten vorzuziehen. Der Solver braucht kein Backend. PWA zunächst mit korrektem Manifest/Icon, später gezielter Offline-Test; falls Offline-Web Pflicht wird, `--no-cdn` und Cache-Verhalten im Produktionsartefakt prüfen. [Statisches Web](https://flet.dev/docs/publish/web/static-website/), [Web-Modi](https://flet.dev/docs/publish/web/), [GitHub Pages](https://flet.dev/docs/publish/web/static-website/hosting/github-pages/).

## G. Android Strategy

| Thema | Risiko | Begründung / Maßnahme |
| --- | --- | --- |
| Echtes Gerät im Entwicklungsmodus | niedrig bis mittel | `flet run --android --recursive main.py`, Flet-Android-App, QR-Code, gleiches WLAN; Host/Firewall und Reachability praktisch prüfen. Companion-Modus ist netzgebunden und ersetzt keinen APK-Test. |
| APK/AAB und Python-Runtime | mittel | Flet baut beide und bündelt CPython; JDK 17, Android SDK und Flutter müssen verfügbar sein bzw. werden beim ersten Build installiert. Build dauert deutlich länger als Hot Reload. |
| Binary Wheels / Matplotlib | hoch, falls benötigt | Android-Wheels müssen ABI/Python-Version abdecken; Flet listet NumPy/Matplotlib-Wheels, Matplotlib braucht ggf. `extract_packages`. Weglassen im MVP. |
| Charts | mittel | `flet-charts` auf echtem APK mit Touch, Achsen und Offline-Betrieb prüfen. |
| Import/Export | mittel | System-Picker und `src_bytes`; Datei tatsächlich aus Downloads/Cloud-Provider öffnen und nach Export außerhalb der App finden. |
| Offline-Berechnung | niedrig bis mittel | Reiner Python-Core und gebündelte Charts benötigen keine API; Flugmodus-Test des installierten APK/AAB ist Abnahmekriterium. |
| Größe | mittel | CPython und mehrere ABIs machen APK groß; für lokale Tests ggf. `--split-per-abi`, Store bevorzugt AAB. |
| Signing / Store | mittel bis hoch | Paketkennung und Version vor erster Store-Veröffentlichung festlegen; Release-Upload-Key sicher außerhalb des Repos; AAB signieren und auf internem Track prüfen. |

Flet dokumentiert, dass `FilePicker` über das Android Storage Access Framework ohne zusätzliche Speicherberechtigung auskommt. Für die eigentliche Offline-App nur benötigte Berechtigungen im gemergten Manifest belassen; das Entwicklungsprogramm braucht dagegen Netzverbindung. [Android-Builds und Signing](https://flet.dev/docs/publish/android/), [Mobile Live-Test](https://flet.dev/docs/getting-started/testing-on-mobile/), [Android-Binärpakete](https://flet.dev/docs/reference/binary-packages-android-ios/).

## H. Testing Strategy

**Vor jeder Solver-Refaktorierung:** Upstream-Commit und Dateien unverändert sichern. Beide Original-CSVs mit der Originalklasse ohne `draw`/`csv` ausführen und in maschinenlesbaren Golden-Fixtures alle Zwischenwerte erfassen: Streamtyp/-shift, Temperaturgrenzen, aktive Streamindizes, Problem Table, beide Kaskaden, QH/QC, alten Pinch-Wert, beide Composite-Kurven und Grand Composite Curve. Originalcode getrennt importieren, damit neue APIs ihn nicht beeinflussen. Ein einmaliger Generierungsskript darf Referenzen erzeugen; reguläre Tests vergleichen gegen fest eingecheckte Werte, nicht gegen einen live aufgerufenen zweiten Solver. Die derzeitige Umgebung kann dies mangels lokalem Upstream und Netzwerkzugriff noch nicht ausführen.

Dann `pytest.approx` mit dokumentierter absoluter/relativer Toleranz für Fließkommazahlen; exakte Vergleiche für Reihenfolge, Streamtypen und Struktur. Fokussierte Tests: Temperaturverschiebung, gleiche Intervallgrenzen, CP-Bilanz, Kaskade/Utilities, Pinch-Semantik, alle Kurven und Wiederholbarkeit. Parser: Originalformat, BOM, CRLF, Leerzeilen, fehlende Header/Spalten, zusätzliche Spalten, leere Datei, nichtnumerische Zahlen. Validierung: CP 0/negativ, NaN/Inf, `ΔTmin` 0/negativ/groß, negative Temperaturen, Supply=Target, identische Streams, nur Hot, nur Cold, zwei und ein Stream, Overflow. Mögliche fachliche Fehler erhalten je einen reproduzierbaren Test des Legacy-Verhaltens plus getrennte gewünschte Interpretation; keine stillen Korrekturen in Golden-PR.

Integration: CSV → Editorzustand → Änderung → Solver → Export; manuelle Eingabe → Solver → identisches Resultat; Export roundtrip und Einheiten. UI: wenige Tests für Feldfehler, Import-Bearbeitbarkeit, veraltetes Resultat, mobile Card/desktop Zeilenlayout und Export. Flets `flet test` kann reale Kontrollen bedienen, baut dafür jedoch einen Test-Host; deshalb als gezielte Integrationssuite, während schnelle Core-Tests mit normalem `pytest` laufen. Produktions-Web-Build im Browser und APK im Flugmodus bleiben Plattform-Abnahmetests. [Flet-Integrationstests](https://flet.dev/docs/getting-started/integration-testing/).

## I. Migration Plan

Jedes Paket ist einzeln reviewbar; „Tests“ nennt den jeweiligen Gate, nicht bereits ausgeführte Tests.

| PR | Ziel / betroffene Dateien | Abhängigkeit | Akzeptanzkriterien und Tests | Hauptrisiko |
| --- | --- | --- | --- | --- |
| 1. Upstream-Basis | `vendor/original/`, `tests/fixtures/`, Herkunfts-/Lizenznotiz. Originaldateien unverändert übernehmen und Commit-ID festhalten. | keine | Beide CSVs lokal ausführbar; Dateihashes, Herkunft und Lizenzhinweis nachvollziehbar. | Abweichung `src`/`example`, unklare Lizenzdatei |
| 2. Golden-Tests | `tests/test_legacy_regression.py`, Golden-JSON/CSV, optional Generierungsskript. | 1 | Alle Zwischenwerte und KPIs beider Beispiele erfasst; `pytest` grün; keine Solveränderung. | Referenzwerte durch Plot-Seiteneffekt oder veränderte Umgebung |
| 3. Modell/Validierung | `core/models.py`, `validation.py`, `tests/test_validation.py`. | 2 | Gemeinsame Streamstruktur, präzise Feldfehler, Einheiten, Randfalltests. | neue Regeln von Legacy getrennt halten |
| 4. CSV-Eingang | `core/csv_input.py`, `tests/test_csv.py`. | 3 | Bytes/str ohne Pfad, Originaldateien parsbar, Zeilennummern bei Fehlern. | Kompatibilitätsdetails des Altformats |
| 5. Reiner Solver | `core/solver.py`, `tests/test_core.py`; Legacy-Adapter zunächst separat. | 2–4 | Neue API liefert für beide Beispiele alle Golden-Werte, keine Flet-/Matplotlib-/Datei-/stdout-Seiteneffekte, idempotent. | höchste fachliche Regression |
| 6. Flet-Shell und Workflow | `src/main.py`, `ui/app.py`, `pyproject.toml`, `.vscode/*`, README-Development; Root-Platzhalter `main.py` entfernen. | 5 | Desktop/Web/Android-Dev-Kommandos definiert, Untermodul-Reload praktisch geprüft, Tests/Lint per CLI. | CLI-/Extension-Versionen, lokales Netzwerk |
| 7. Manueller Editor | `ui/state.py`, `ui/app.py`, UI-Tests. | 6 | Add/Edit/Delete, ΔTmin, Typ, Feldfehler, Beispiel laden, Analyse → KPIs. | Eingabefokus und Touch-UX |
| 8. CSV-Import | `ui/app.py`, UI-/Integrationstests. | 4, 7 | Import füllt bearbeitbare Zeilen, Fehler lässt Zustand intakt, Web-Safari/Android/Desktop-Test. | Picker-Gesten/Dateiberechtigung |
| 9. Detailresultate | `ui/app.py`, Ansichts-Tests. | 7 | Problem Table, beide Kaskaden, Intervallansicht und eindeutig beschrifteter Pinch erreichbar. | große Tabellen auf kleinen Displays |
| 10. Charts | `ui/charts.py`, `pyproject.toml`, Chart-/Build-Smoke-Tests. | 5, 9 | Shifted, unshifted, Grand und Intervallansicht mit Achsen/Einheiten auf Web+APK. | Erweiterungspaket, Rendering |
| 11. CSV-Export | `export.py`, `ui/app.py`, Exporttests. | 9, 10 | Problem Table, Kaskade, Composite-Daten und Grand Composite als CSV auf Web/Android/Desktop. | Downloads je Plattform |
| 12. Responsiveness | `ui/app.py`, UI-Tests, README-Screenshots. | 8–11 | 390/430/768/1440 px, Touch, kein unnötiges horizontales Scrollen. | Chart-/Tabellenbreiten |
| 13. Web/CI | `pyproject.toml`, `.github/workflows/{ci,pages}.yml`, README. | 10–12 | Lint+Tests auf PR, statischer Build in CI, Pages nur von `main`, Import/Berechnung/Export im echten Pyodide-Build. | Cache, Base-URL, Wheels |
| 14. Android Release | `pyproject.toml`, Release-Workflow/README, Assets. | 10–13 | APK/AAB gebaut; signierter interner Release, Offline- und Import/Export-Test auf Gerät. | SDK, Signing, Store-Vorgaben |

Reihenfolge gegenüber der ursprünglichen Phasenliste: Responsiveness beginnt bereits beim Editor, bevor alle Ergebnisse fertig sind; Web-Pyodide- und Android-Wheel-Smoke-Tests finden zusätzlich früh bei PR 6/10 statt. Ein spätes, einziges Plattform-Gate wäre für diese Architektur zu riskant. README, Lint und CI entstehen laufend, nicht erst als „Polish“.

## J. Proposed Commit / PR Sequence

Die konkrete Reihenfolge ist 1 Upstream-Basis → 2 Golden-Tests → 3 Modelle/Validierung → 4 CSV-Eingang → 5 reiner Solver → 6 Flet-Shell/Workflow → 7 manueller Editor → 8 CSV-Import → 9 Detailresultate → 10 Charts → 11 Export → 12 responsive Abnahme → 13 Web/CI → 14 Android-Release. Jeder PR endet mit grünem Lint-/Test-Gate und einem lauffähigen Entwicklungsstand. Fachliche Bugfixes nach PR 5 gehören in einen separaten PR mit Legacy- und Erwartungstest.

## K. Dependency Plan und Entwicklungsworkflow

Aktuell veröffentlichte Pakete sind `flet` **1.0.1** und `flet-charts` **1.0.1** (22. September 2026). Diese Versionslinie gemeinsam pinnen, nach Tests in einem Lockfile sichern. Python **3.12** zunächst als Build-Ziel festlegen: Flet unterstützt 3.12/3.13/3.14 für Web und Android; die lokale `.python-version = 3.11` reicht für die dokumentierte Bundle-Matrix nicht. `requires-python = ">=3.12,<3.13"` verhindert, dass Flet still 3.14 für den Build wählt. 3.12 minimiert hier vorerst Wheel-Risiken; die Entscheidung wird nach Produktions-Build geprüft. Für die App: `flet` und `flet-charts`; der Core braucht nur die Standardbibliothek. Für Entwicklung: `pytest`, `ruff` und CLI-/Desktop-/Test-Extras von Flet gemäß der bei PR 6 geprüften Installation. `matplotlib` nur optional für Legacy-Golden-Generierung, nicht als Ziel-Runtime. Kein NumPy, Pydantic, Pandas, Framework-State-Management oder ZIP-Paket nötig. [Flet auf PyPI](https://pypi.org/project/flet/), [Charts auf PyPI](https://pypi.org/project/flet-charts/), [Flet Python-Matrix](https://flet.dev/docs/publish/).

Vorgesehene CLI-/VS-Code-Tasks ab PR 6: `uv run flet run --recursive src/main.py` (Desktop), `uv run flet run --web --recursive src/main.py` (Web), `uv run flet run --android --recursive src/main.py` (Flet-Android-App), `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run flet build web`, `uv run flet build apk`, `uv run flet build aab`. Ein Test-Watch-Task kommt nur hinzu, wenn ein konkret ausgewähltes Plugin den Befehl bereitstellt; normales `pytest` hat keinen Watch-Schalter. Für Web lokal bei Bedarf `--port 8550`; parallele Android-Session erhält einen anderen Port. Android-Gerät und PC müssen im selben Netz sein; Firewall für den Dev-Port freigeben und die angezeigte LAN-Adresse statt `localhost` verwenden. Änderungen an Python-Untermodulen brauchen `--recursive`. Falls der Standard-Web-Client eine Chart-Erweiterung als `Unknown control` meldet, einmalig einen passenden Web-Client bauen und den Entwicklungsserver mit `FLET_WEB_PATH` auf `build/web` richten; Python-Hot-Reload bleibt nutzbar, eine Änderung am Flutter-Teil verlangt einen Neubuild. Tasks verwenden nur Workspace-relative Pfade. **Keiner dieser Befehle wurde im leeren Gerüst als App-/Build-Test ausgeführt.** [Hot Reload](https://flet.dev/docs/getting-started/running-app/), [CLI-Optionen](https://flet.dev/docs/cli/flet-run/), [Web-Client-Variable](https://flet.dev/docs/reference/environment-variables/), [Mobile-Entwicklung](https://flet.dev/docs/getting-started/testing-on-mobile/).

CI: auf Push/PR Installation aus Lockfile, Ruff, schnelle pytest-Suite, anschließend optional Web-Build als eigener Gate. Pages-Workflow baut von `main`, setzt Repo-Base-URL und Hash-Routing, lädt `build/web` als Pages-Artefakt hoch und deployt nur nach erfolgreichem Build. Android-Builds bei Release-Tag oder manuell; Signierschlüssel ausschließlich als CI-Secrets. In `.gitignore` zusätzlich lokale Builds, `.flet`/Caches, Keystores und generierte Exporte aufnehmen. `launch.json` nur für Core-Debug/Entry-Point, keine IDE-Pflicht. [Offizielles Pages-Beispiel](https://flet.dev/docs/publish/web/static-website/hosting/github-pages/).

## L. Echte offene Architekturfragen

1. Nach lokalem Upstream-Import: Sind `src/` und `example/` tatsächlich identisch, und welcher Commit ist die Referenz? Bis dahin keine Golden-Werte behaupten.
2. Soll die App bei nur Hot- oder nur Cold-Streams Ergebnisse zeigen? Der alte Solver fordert nur zwei Streams, aber die Bedeutung von Pinch und einer fehlenden Composite-Kurve ist zu klären. Empfehlung: Utilities rechnen, „kein interner Pinch“ anzeigen, Diagramm der fehlenden Seite ausblenden; zuerst Legacy- und Fachtest.
3. Wie wird ein mehrfacher bzw. fehlender Pinch fachlich dargestellt? Empfehlung: Legacy-Wert separat behalten, tatsächliche Hot-/Cold-Pinch-Temperaturen nur bei validierter Lage anzeigen.
4. Ist **Offline-PWA** bereits für 0.1.0 verbindlich? Die native APK kann offline arbeiten; Web-Offline erfordert gesonderte Cache-/Installationsprüfung. Empfehlung: PWA-Installierbarkeit im MVP, garantierter Offline-Webbetrieb später.

## M. Empfohlener Scope für 0.1.0

Enthalten: originalgetreue Regressionstests; reiner Core; manuelle, responsive Eingabe und editierbarer CSV-Import; Validierung; QH/QC und korrekt beschrifteter Pinch; Problem Table, Kaskaden, Composite/Shifted/Grand und Temperaturintervalle; CSV-Export; lokale Web-App ohne Analyse-Backend; Desktop-/Browser-/Android-Dev-Workflow; reproduzierbarer statischer Pages-Build; getesteter nativer APK-Build und AAB-Buildpfad; Offline-Test der installierten Android-App; Lizenz-/Upstream-Hinweise.

Später: ZIP-Sammel-Export, garantierter Offline-PWA-Betrieb, Plot-Image-Export, komplexe Heat-Exchanger-Network-Optimierung, Konten/Cloud und aufwendiges State-Framework. Ein Play-Store-Release setzt zusätzlich Paketkennung, Signing, Store-Eintrag und internen Track voraus und ist ein gesondertes Veröffentlichungsgate.
