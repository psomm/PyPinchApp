# Upstream und Lizenz

Referenz: [anicusan/PyPinch](https://github.com/anicusan/PyPinch), Commit
`2869059af580158c1c50f88c431477fdb62685c5` auf `master`.
Der ursprüngliche Autor ist Andrei Leonard Nicusan. Der Dateikopf von
`src/PyPinch.py` nennt „GNU v3.0“. Das Upstream-Repository hat keine
eigenständige LICENSE-Datei. Dieses Projekt führt daher den vollständigen
Text der [GNU GPL v3](../LICENSE) mit und bewahrt den Original-Dateikopf.

`vendor/original/PyPinch.py` ist bytegleich mit Upstreams `src/PyPinch.py`.
Die Versionen unter `example/` und `tutorial/` sind ebenfalls bytegleich.
`tests/fixtures/streams.csv` und `manystreams.csv` sind bytegleiche Kopien
aus Upstreams `src/streams/`.

SHA-256:

| Datei | Hash |
| --- | --- |
| `vendor/original/PyPinch.py` | `6ad46c5226125b46d260daf34eef79735f486111fe0fe2f12a42707c1e34ccb9` |
| `tests/fixtures/streams.csv` | `80a91fbb4dce19767f2fac0743c6115d8191dba10dc7ddaf04b49de0500e8f94` |
| `tests/fixtures/manystreams.csv` | `53f08a8fc5f9a564bfcad7bf77d394dab363fed9ab7328702c7a9f8353fd7498` |

Die ursprüngliche Klasse wird nur für Regressionstests genutzt. Der
Anwendungs-Solver wurde aus ihren Berechnungsschritten abgeleitet und trennt
Dateizugriff, Plots und Ausgabe ab. Die Golden-Dateien dokumentieren die
Originalergebnisse. Fachliche Änderungen an der Berechnung brauchen einen
eigenen Test und einen erklärten Unterschied zu diesen Referenzwerten.

## Bewusste fachliche Korrekturen

Die Originaldatei und ihre Golden-Dateien bleiben unverändert. Im App-Solver
weichen die folgenden Punkte bewusst davon ab:

- Hot-/Cold-Pinch werden aus einer internen Nullstelle der zulässigen Kaskade
  bestimmt. Der Legacy-Wert wird nur verwendet, wenn er zu einer solchen
  Nullstelle gehört. Bei mehreren Nullstellen bleibt eine gültige Legacy-Lage
  erhalten; andernfalls wird die höchste interne Nullstelle angezeigt.
- Jede Composite Curve beginnt an der niedrigsten Temperatur ihrer eigenen
  Streamseite. Im kleinen Originalbeispiel liegt der heiße Startpunkt deshalb
  bei 110 °C verschoben bzw. 120 °C tatsächlich, statt 75 bzw. 85 °C.
- Lücken zwischen Streamtemperaturbereichen bleiben als Abschnitte mit konstanter
  Enthalpie erhalten. Eine fehlende Hot-/Cold-Seite hat keine Kurvenpunkte.
- Nicht mehr unterscheidbare verschobene Temperaturen und nicht endliche
  Zwischenergebnisse erzeugen einen Eingabefehler statt eines Absturzes.

Diese Unterschiede sind in `tests/test_core.py` und `tests/test_edge_cases.py`
mit ausdrücklich erwarteten Werten abgesichert. Die Utility-Berechnung und
Kaskadenwerte der Originalbeispiele bleiben unverändert.

Bei Dezimalwerten kann die zulässige Kaskade wegen Fließkommarundung am
Pinch statt `0.0` einen Rest um `10⁻¹⁷ kW` enthalten. Die gespeicherten
Legacy-Zahlen bleiben unverändert; allein die zusätzliche UI-Eigenschaft
„interner Pinch vorhanden“ verwendet eine zur Größenordnung der Wärmeströme
relative Toleranz von `10⁻¹²`. Der reproduzierbare Fall steht in
`tests/test_edge_cases.py`.
