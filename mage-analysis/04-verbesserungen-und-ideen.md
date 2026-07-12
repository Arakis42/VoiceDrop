# 04 — Verbesserungsvorschläge & Ideen

Sortiert nach Aufwand/Nutzen. Referenzen: siehe `02-ki-analyse.md`.

## A. KI-Verbesserungen mit gutem Aufwand/Nutzen-Verhältnis

### A1. Kartenwerte in die Bewertungsfunktion (klein anfangen, große Wirkung)
`ArtificialScoringSystem.getCardDefinitionScore()` hat den Fixwert 3 pro Karte
(TODO im Code). Naheliegender Fix:
- `RateCard` (wird heute nur vom DraftBot genutzt!) als Wertquelle anzapfen:
  Ratings existieren bereits als CSV pro Set unter `resources/ratings/`.
- Zonen-Multiplikatoren umsetzen, die im TODO von `GameStateEvaluator2.java:98`
  schon beschrieben sind (Battlefield > Hand > Friedhof > Exil; Instants in Hand
  wertvoller als auf dem Feld etc.).
- Effekt: Mulligan-, Discard-, Trade-Entscheidungen („1-für-2“) werden sinnvoll;
  die KI hört auf, gute Karten wie schlechte zu behandeln.

### A2. Kampf-Simulation aktivieren (größter Spielstärke-Hebel)
Angreifer/Blocker laufen heute rein heuristisch (`ComputerPlayer6.declareAttackers`,
Kommentar „sim minmax does not work at the moment“). Statt das alte Minimax zu
reparieren, pragmatisch:
- Kandidaten-Kombinationen begrenzen (nicht Powerset 2^n): z.B. nur „alle“,
  „keine“, „alle sicheren“, Top-k nach Evaluator, + 1-Tausch-Nachbarn.
- Jede Kandidaten-Kombination per Game-Kopie bis Ende des Kampfes vorspulen
  (nur Kampfschritte, keine volle Tiefe) und mit `GameStateEvaluator2` bewerten.
- Das nutzt vorhandene Bausteine (`addAttackers`/`addBlockers` in
  `SimulatedPlayer2`, Bookmark/Undo) und ist unabhängig vom Prioritäts-Minimax.

### A3. Budget-Tuning (fast gratis)
- `maxNodes` 5000 → konfigurierbar (Code-TODO fragt selbst nach 50000).
- `COMPUTER_MAX_THREADS_FOR_SIMULATIONS` = CPU-Kerne statt fix 5 (Code-TODO).
- Wurzel-Parallelisierung: die Aktionsliste in `simulatePriority` ist eine
  saubere Arbeitsteilung für Threads (heute strikt sequenziell).
- Bei Timeout die bislang beste Teillösung spielen statt „nichts tun“
  (bekanntes Problem, siehe Kommentar in `SimulationPerformanceAITest`).

### A4. Trigger-Entscheidungen anschließen
Simulation läuft schon, Ergebnis wird verworfen
(`SimulatedPlayer2.triggerAbility`, TODO `:331`). Anschließen = die Basis-Heuristik
bei Triggern durch Sim-Ergebnisse ersetzen.

### A5. Multiplayer-Bewertung
`GameStateEvaluator2` bewertet nur den ersten Gegner. Minimal: über alle Gegner
summieren/gewichten (Bedrohungslevel = Board-Score), sonst bleibt Commander-FFA
strukturell kaputt.

## B. Größere Umbauten (mittel- bis langfristig)

### B1. MCTS wiederbeleben statt Minimax ausbauen
`ComputerPlayerMCTS` hat die richtigen Zutaten (UCT, Determinisierung der
gegnerischen Hand, Kampf im Baum, Multithreading). Schwachpunkt sind die rein
zufälligen Rollouts. Upgrade-Pfad:
- Rollout-Politik: statt `SimulatedPlayerMCTS`-Zufall die leichte Heuristik-KI
  (Basis-`ComputerPlayer`-Entscheidungen + A1-Evaluator) als Playout-Spieler.
- Oder „MCTS mit Bewertungs-Abschneiden“: Rollout nur 1–2 Züge, dann
  `GameStateEvaluator2` statt bis zum Spielende zu würfeln.
- Information-Set-MCTS: pro Iteration neu determinisieren (Gerüst existiert in
  `createMCTSGame`).

### B2. Lern-basierte Bewertung (passt perfekt zum Auto-Battle-Projekt!)
Der eigene Simulator erzeugt genau die Daten, die man dafür braucht:
- **Self-Play-Daten**: pro Spielzustand Features (Leben, Board-Scores, Handgrößen,
  Manaverfügbarkeit, …) + finales Ergebnis → einfaches Modell (logistische
  Regression/GBT/kleines Netz) als Ersatz für die handgebaute Score-Formel.
  Die Schnittstelle ist winzig: nur `GameStateEvaluator2.evaluate()` austauschen.
- **Karten-Embeddings light**: Winrate-Beitrag einzelner Karten aus vielen
  Simulationsläufen schätzen (Karte gezogen vs. nicht gezogen — wie 17lands
  „games in hand“-Metriken) → füttert wieder A1.
- Iterieren: bessere Bewertung → stärkere KI → bessere Daten (AlphaZero-Prinzip
  im Kleinen, ohne dass man das volle RL-Programm braucht).

### B3. Reaktionsspiel in fremden Zügen
CP7 rechnet nur in 4 eigenen Steps. Erweiterung: auch bei gegnerischen
Spells/Stack-Events rechnen, wenn man Instants/Flash hält (Kostenkontrolle über
ein kleines Budget, sonst explodiert die Rechenzeit).

## C. Konkrete Ideen rund um deine Deck-Simulation („was noch cool wäre“)

1. **CLI-Simulator + Matchup-Matrix**: N Decks, jeder gegen jeden, 200+ Spiele
   pro Paarung (Play/Draw ausbalanciert, Seeds geloggt) → Heatmap + Elo/Glicko
   pro Deck. Ergebnis als JSON/CSV + HTML-Report.
2. **Deck-Optimierer (genetischer Algorithmus)**: Kartenpool + 60er-Deck als
   Genom; Mutation = 1–3 Karten tauschen; Fitness = Winrate gegen ein
   Referenz-Gauntlet. Über Nacht laufen lassen → „evolviertes“ Deck.
   (Die Deck-Validatoren aus `Mage.Deck.Constructed` können Formate erzwingen.)
3. **KI-gegen-KI als Regressionstest für KI-Änderungen**: zwei KI-Versionen
   (z.B. mit/ohne A1) gegeneinander mit identischen Seeds/Decks → misst
   Spielstärke-Delta direkt. Ohne so ein Harness ist jede KI-Änderung Blindflug —
   das Fehlen davon ist vermutlich der Grund, warum die „mad“-KI seit Jahren
   stagniert.
4. **Spiel-Replays**: `DataCollectorServices`/GameLog pro Spiel speichern;
   auffällige Spiele (Freeze, extrem lang, überraschender Sieger) automatisch
   markieren und als Replay-Datei ablegen. Der Server hat bereits eine
   Games-History; headless kann man das Spiellog einfach mitschreiben.
5. **Mulligan-Labor**: Mulligan im Testmodus aktivieren und verschiedene
   Mulligan-Strategien (Landanzahl-Regeln vs. RateCard-basiert) nur über die
   `chooseMulligan`-Methode austauschen → Winrate-Effekt messen.
6. **Turnier-/Liga-Modus**: der Server kann Turniere (Constructed/Sealed/Draft
   in `Mage.Tournament.*`) — ein „Bot-Liga“-Skript, das nachts Turniere spielt
   und eine Tabelle pflegt, wäre mit Weg B (LoadTest-Muster) machbar.
7. **Statistik-Dashboard**: Kurvenanalyse (Mana Curve vs. tatsächlich verfügbares
   Mana pro Zug aus Logs), „Karte X blieb Y% der Spiele auf der Hand“,
   durchschnittlicher Zug des Spielendes pro Matchup.
8. **Determinismus-Modus**: `RandomUtil.setSeed` + feste Startspieler +
   `skipInitShuffling` mit vorgegebener Bibliotheksreihenfolge → exakt
   reproduzierbare Einzelspiele zum Debuggen von KI-Entscheidungen.
9. **„Goldfish-Modus“**: Gegner = Basis-`ComputerPlayer` (passt immer) →
   misst reine Deck-Geschwindigkeit (kill turn) unabhängig von KI-Interaktion.
   Praktisch schon vorhanden: einfach `ComputerPlayer` statt `ComputerPlayer7`
   einsetzen.
10. **Fernziel LLM-/Policy-Experimente**: Die `Player`-Schnittstelle ist der
    einzige Integrationspunkt, den man braucht — jede Entscheidung läuft durch
    `priority()`/`choose*()`. Ein eigener `Player`-Typ (z.B. Regelwerk +
    externem Modell via IPC) ist ein sauber abgegrenztes Experiment.

## D. Für den Anfang (konkrete Reihenfolge)

1. Simulator-CLI nach `03-auto-battle.md` bauen (Weg A) + JSON-Ausgabe.
2. Damit Baseline messen: bekanntes starkes vs. schwaches Deck — plausible Winrate?
3. A1 (Kartenwerte) einbauen, mit Idee C3 (KI vs. KI mit Seeds) den Effekt messen.
4. A2 (Kampf-Simulation) — erneut messen.
5. Dann entscheiden: Minimax weiter tunen (A3/A4) oder auf MCTS (B1) schwenken.
