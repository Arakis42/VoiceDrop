# 05 — Konzept: Ein wirklich besserer Autoplay-Algorithmus

Prämisse (korrekt beobachtet): **Statische Kartenbewertungen (à la RateCard) sind
Draft-/Deckbau-Wissen.** Im Spiel ist der Wert einer Karte kontextabhängig —
ein Removal ist gegen ein leeres Board wertlos, ein 2/2 gegen ein 4/4-Board tot.
Was zählt, ist der **Zustand**: Lebenspunkte beider Seiten, Handkarten, Ressourcen
auf dem Board, Mana-Entwicklung und wie das alles zusammen einen Plan ergibt.
Ziel jeder Entscheidung: nicht „Material maximieren“, sondern
**Gewinnwahrscheinlichkeit maximieren**.

## 1. Domänenmodell: Worauf es beim echten Magic-Spielen ankommt

Diese sieben Konzepte muss der Algorithmus abbilden — sie sind das, was der
heutige Evaluator (Leben + Permanents + Handkartenzahl) alles NICHT sieht:

### 1.1 Race-/Clock-Rechnung („Philosophy of Fire“)
Lebenspunkte sind eine Ressource, nur der letzte Punkt zählt. Zentral ist die
**Clock**: In wie vielen Zügen tötet mein Board den Gegner, in wie vielen seins
mich? Zwei Zahlen (`myClock`, `oppClock`), berechenbar aus Board + Leben:
- ungeblockt (Gegner blockt nicht) und realistisch (Gegner blockt optimal)
- inkl. bekannter Direktschaden-Reichweite aus der Hand

Fast jede Kampfentscheidung ist eine Funktion dieser zwei Zahlen.

### 1.2 Rollenzuweisung („Who's the Beatdown?“)
Aus dem Clock-Vergleich folgt die Rolle: `myClock < oppClock` → ich bin der
Beatdown (aggressiv traden, Leben des Gegners angreifen, Risiko nehmen);
sonst Kontrolle (Karten tauschen, Board stabilisieren, das Spiel verlängern).
Die Rolle ist **pro Spielzustand**, nicht pro Deck — sie kippt im Spielverlauf.
Sie parametrisiert den Evaluator (Gewichte für Leben vs. Karten vs. Tempo).

### 1.3 Card Advantage — Menge UND Qualität
- Rohe CA: Karten gezogen/getauscht (heute: Handgröße × 5, immerhin).
- **Virtuelle CA**: tote Karten zählen nicht (Removal ohne Ziele, 6-Drops bei
  3 Ländern, Farbscrew). Eine Handkarte ist nur so viel wert, wie sie in diesem
  Spielzustand tun kann.
- Tausch-Bilanz: 1-für-2 ist gut für mich als Kontrolle, oft egal als Beatdown.

### 1.4 Tempo & Mana-Effizienz
- Wieviel Mana bleibt pro Zug ungenutzt („mana leak“)? Curve-out schlägt Wert.
- Sequencing: erst Bedrohung, dann Antwort offen halten; Länder so legen, dass
  künftige Züge maximal flexibel sind.
- Tempo-Bewertung: Board-Delta pro aufgewendetem Mana in den letzten N Zügen.

### 1.5 Threat Assessment (was muss sterben?)
Removal-Ziel ist nicht die dickste Kreatur, sondern die, deren Entfernung
**meine Gewinnwahrscheinlichkeit am meisten hebt**: Was tötet mich am schnellsten
(Clock-Beitrag)? Was generiert laufend Vorteil (Engine-Permanents: Draw-Trigger,
Anthems, Planeswalker)? Formal: Threat(P) = Score(Zustand) − Score(Zustand ohne P),
mit dem besseren Evaluator gerechnet — das ist billig (eine Kopie, ein Delta).

### 1.6 Synergie & Pläne
Karten sind Teile von Plänen, keine Einzelwerte. Drei umsetzbare Stufen:
1. **Engine-Introspektion** (XMage-spezifischer Vorteil!): Abilities sind
   strukturierte Java-Objekte. Trigger-Bedingungen („whenever a creature dies“,
   „whenever you cast an instant“) und Filter sind maschinenlesbar. Daraus lässt
   sich ein **Synergie-Graph** bauen: Karte A produziert Events, die Karte B
   konsumiert → Bonus, wenn beide im Spiel/auf der Hand sind (Sacrifice-Outlets +
   Death-Trigger, Tokens + Anthem, Spells + Prowess, Friedhof + Reanimation).
2. **Archetyp-Erkennung vor Spielbeginn**: Decklist analysieren (Kurve,
   Removal-Dichte, Kreaturenanteil, Keyword-Tags) → Preset Aggro/Midrange/
   Control/Combo → Startgewichte für Rolle/Evaluator.
3. **Gelernt** (siehe Abschnitt 4): Ko-Präsenz-Features im Modell fangen
   Synergien, die niemand von Hand kodiert.

### 1.7 Information & Wahrscheinlichkeiten
- Nicht mit perfekter Information planen (heutiger „mad“-Bot cheatet mit der
  Gegnerhand in der Simulation) — stattdessen **Determinisierung**: K plausible
  Gegnerhände aus bekannten Infos samplen (Deck-Archetyp, bereits gesehene
  Karten, Mana offen gehalten = wahrscheinlich Antwort) und über die Ergebnisse
  mitteln. Das MCTS-Modul macht das Grundprinzip schon vor.
- „Play around X“: Wahrscheinlichkeit gängiger Antworten (Counter offen? Mass
  Removal am Zug 4?) als Risikoabschlag in die Aktionsbewertung.
- Eigene Outs zählen: Wie viele meiner verbleibenden Karten retten diese Lage?

## 2. Architektur: DecisionEngine in Schichten

Heute ist die Intelligenz verstreut (Minimax für Prioritäten, Heuristik für Kampf,
Basis-Heuristiken für alle Auswahlen). Vorschlag: **eine zentrale DecisionEngine**,
an die alle `Player`-Callbacks delegieren:

```
Layer 3  SUCHE          Turn-Plan-Suche (Minimax/MCTS über Makro-Aktionen)
Layer 2  SOLVER         CombatSolver | RaceCalculator | TargetSelector | ManaPlanner | MulliganPlaner
Layer 1  EVALUATOR      WinProb(Zustand) aus Features (erst Gewichte, später gelernt)
Layer 0  FEATURES       GameFeatures: alles Messbare aus dem Game-Objekt
```

### Layer 0 — Feature-Extraktion (`GameFeatures`)
Ein Objekt, das aus `Game` alles Zählbare zieht (pro Spieler):
Leben + Lebens-Trend, Clock beider Seiten, Kartenzahl Hand/Deck, **nutzbare**
Handkarten (castbar in ≤2 Zügen), Board: Power/Toughness-Summen, Evasion-Power
(Flying/Trample/Menace ungeblockt), Engine-Permanents (wiederkehrende Trigger),
Mana: Länder, verfügbare Farben, Curve-Fit der Hand, ungenutztes Mana letzter Zug,
Friedhofs-Ressourcen (wenn Deck sie nutzt), Synergie-Graph-Aktivierung.
→ Reine Datenklasse, einzeln testbar, Grundlage für alles Weitere inkl. ML-Export.

### Layer 1 — Evaluator: `WinProb(features, rolle)`
Ersetzt `GameStateEvaluator2.evaluate()` (Interface behalten: int-Score, damit
Minimax-Code weiterläuft; intern Win-Prob × Skala).
- Phase 1: handgewichtete Linearkombination der Features, **rollenabhängige
  Gewichte** (Beatdown gewichtet Clock/Tempo, Kontrolle CA/Stabilität).
- Nichtlinearitäten, die zählen: Leben nahe 0 exponentiell (existiert schon als
  `LIFE_SCORES`-Tabelle), „tot nächsten Zug wenn kein Block“ = fast LOSE.
- Phase 2: gelerntes Modell (Abschnitt 4), gleiche Schnittstelle.

### Layer 2 — Spezialisierte Solver

**CombatSolver** (ersetzt die Angriffs-/Block-Heuristik — größter Einzelhebel):
- Kampf ist ein sauber abgegrenztes 2-Ply-Spiel: Ich wähle Angreifer, Gegner
  antwortet mit bester Block-Zuweisung → **exakt lösbar** für realistische
  Boardgrößen, wenn man den Kombinatorik-Explosionen begegnet:
  - identische Kreaturen deduplizieren (Engagement-Hashing existiert schon in
    `SimulatedPlayer2.addAttackers`),
  - dominierte Optionen streichen (Angreifer, der nie stirbt und nie stirbt
    lassen muss, ist immer dabei; 0-Power nie),
  - Kandidatenmengen statt Powerset: {kein Angriff, Alpha-Strike, alle „sicheren“,
    Solver-Top-k, ±1-Nachbarn der besten},
  - Blocks per Branch&Bound über Blocker→Angreifer-Zuweisungen.
- Bewertung eines Kampf-Ausgangs NICHT nur Material: **Race-Impact**
  (Clock-Delta beider Seiten via RaceCalculator) + Rollenkontext. Ein Chump-Block
  ist korrekt, wenn oppClock sonst < myClock wird; ein „unsicherer“ Angriff ist
  korrekt, wenn der Gegner durch Blocken mehr verliert als ich.
- First/Double Strike, Deathtouch, Trample exakt rechnen — die Engine kann das
  schon (Kampfschritte auf Game-Kopie vorspulen), nur die Auswahl war heuristisch.

**RaceCalculator**: liefert `myClock`/`oppClock`/Rolle (§1.1/1.2). Billig genug,
um in jedem Evaluator-Aufruf mitzulaufen.

**TargetSelector**: ersetzt die Outcome-Heuristiken der Basisklasse für Removal,
Discard, Pump etc. durch Threat-Deltas (§1.5): für jedes legale Ziel
Zustand-mit/ohne bewerten, bestes Delta nehmen. Deckelt man die Zielanzahl
(Top-N nach schnellem Vorfilter), bleibt das im Budget.

**ManaPlanner**: plant 2 Züge Manaentwicklung (welches Land legen, was diesen +
nächsten Zug castbar bleibt), bewertet Sequencing-Alternativen — heute entscheidet
das faktisch die Reihenfolge der Aktionsliste.

**MulliganPlaner**: Keep/Mull anhand: castbare Karten in den ersten 3 Zügen,
Länderzahl vs. Curve, Rolle des Decks. (Heute: „<2 oder fast nur Länder“.)

### Layer 3 — Suche über Makro-Aktionen
Das heutige Minimax simuliert **einzelne Prioritäten** und verbrennt Tiefe in
Trivialschritten. Besser: über **Turn-Pläne** suchen:
- Ein Knoten = „mein Zug als Paket“ (Land + Casts in Reihenfolge + Angriff),
  generiert aus ManaPlanner × CombatSolver-Kandidaten — der Baum wird flacher
  und jede Ebene bedeutungsvoller.
- Gegnerzug: 1 Ebene mit determinisierten Händen (§1.7), K Samples, Mittelwert.
- Move-Ordering per Evaluator (Alpha-Beta schneidet dann richtig), Transposition
  über den existierenden State-Hash (`game.getState().getValue()`), Iterative
  Deepening gegen das Zeitbudget statt hartem Node-Cap, bei Timeout **beste
  bisherige** Aktion spielen (heute: gar nichts).
- Reaktions-Budget: In gegnerischen Zügen nur rechnen, wenn Instants/Flash
  spielbar → behebt das „passt immer im Gegnerzug“-Problem gezielt.

## 3. Wo das in XMage konkret einhakt

| Baustelle | Heute | Neu |
|---|---|---|
| `GameStateEvaluator2.evaluate()` | Leben+Material+Handzahl | Layer 0+1 (WinProb), Interface bleibt |
| `ComputerPlayer6.declareAttackers/-Blockers` | Heuristik („sim minmax does not work“) | CombatSolver |
| `ComputerPlayer.chooseTarget/choose` (Basis) | Outcome-Heuristiken | TargetSelector (Threat-Delta) |
| `ComputerPlayer.chooseMulligan` | Länder zählen | MulliganPlaner |
| `ComputerPlayer7.priority` + `SimulationNode2` | Prioritäten-Minimax, perfekte Info | Turn-Plan-Suche + Determinisierung |
| `SimulatedPlayer2.triggerAbility` | Sim-Ergebnis wird verworfen (TODO) | an TargetSelector/Evaluator anschließen |

Wichtig: alles hinter dem `Player`-Interface — die Engine bleibt unberührt.
Jeder Baustein ist einzeln einbaubar und einzeln messbar.

## 4. Lern-Pfad (der Auto-Battle-Simulator macht's möglich)

Handgebaute Gewichte sind Phase 1. Die ehrliche Antwort auf „Synergie verstehen“
ist gelernt, nicht kodiert:

1. **Datenerzeugung**: Simulator (siehe `03-auto-battle.md`) loggt pro Zug den
   `GameFeatures`-Vektor + finales Spielergebnis. Zehntausende Spiele über
   verschiedene Deck-Paarungen = Trainingsset.
2. **Value-Modell**: Win-Prob-Regression (logistische Regression → GBT → kleines
   MLP, in der Reihenfolge). Ersetzt die Gewichte in Layer 1. Ko-Präsenz-Features
   (Karte×Karte auf Board/Hand) fangen Synergien automatisch.
3. **Policy-Prior**: aus denselben Logs lernen, welche Aktionstypen in welchen
   Zuständen gut waren → Move-Ordering/Pruning für Layer 3 (mehr Tiefe im Budget).
4. **Self-Play-Schleife**: neue KI erzeugt bessere Daten → Modell neu trainieren
   (AlphaZero-Prinzip im Kleinen; ohne GPU-Großprojekt machbar, weil die Suche
   die Hauptarbeit leistet und das Modell nur bewertet).
5. **Bewertungs-Infrastruktur zuerst**: KI-A-vs-KI-B-Harness mit festen Seeds
   (Idee C3 in `04-…md`) ist Voraussetzung — jede Stufe muss eine messbare
   Winrate-Verbesserung gegen die Vorstufe zeigen, sonst fliegt sie raus.

## 5. Reihenfolge (Nutzen ÷ Aufwand)

1. **GameFeatures + RaceCalculator + rollenbasierter Evaluator** — Fundament,
   sofort messbar, kein Sucheingriff nötig.
2. **CombatSolver** — behebt die peinlichsten Fehler (Angriff/Block), nutzt 1.
3. **TargetSelector (Threat-Deltas)** — Removal/Discard werden sinnvoll.
4. **Timeout-Fix + Move-Ordering + Iterative Deepening** — mehr aus dem Budget.
5. **Determinisierung statt perfekter Info** — ehrlicheres Planen.
6. **Turn-Plan-Suche** — Umbau von `SimulationNode2`, größter Suchgewinn.
7. **Lern-Pfad** (parallel ab 1., sobald der Simulator Daten liefert).

Meta-Regel: **nichts einbauen, was nicht im KI-vs-KI-Harness gemessen wurde.**
Das fehlende Mess-Harness ist vermutlich der Grund, warum die XMage-KI seit
Jahren auf Heuristik-Niveau steht — Verbesserungen waren nie beweisbar.
