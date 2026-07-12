# 06 — Coding-Backlog: Was kann sofort gebaut werden, in welcher Reihenfolge

Jedes Item ist ein abgeschlossenes, einzeln testbares Stück Code. Reihenfolge =
Abhängigkeiten + Nutzen. Grundregel aus `05`: Ab Item 2 wird **jede** Änderung
im Harness gemessen, sonst gilt sie als nicht passiert.

## Phase 0 — Infrastruktur (kein KI-Code, sofort startbar)

### 0.1 `Mage.Simulator` — Headless-CLI-Runner ✅ UMGESETZT (mage-simulator/)
Neues Maven-Modul neben `Mage.Tests`. Kein JUnit, eigene `main()`:
`--deck1 a.dck --deck2 b.dck --games 200 --skill 5 --seed 42 --maxTurns 60 --out results.jsonl`
- Bausteine existieren alle: `CardScanner.scan()`, `DeckImporter`,
  `TwoPlayerDuel`, `ComputerPlayer7`, `game.start()` (Details in `03-…md`).
- Output pro Spiel: Seed, Decks, Sieger, Züge, Endleben, Dauer, Abbruchgrund.
- Play/Draw abwechseln, Timeout-Notbremse (`stopOnTurn`).
- Aufwand: klein. Nutzen: Voraussetzung für alles.

### 0.2 KI-vs-KI-Mess-Harness ✅ UMGESETZT (--player1/--player2, --skill1/--skill2)
`--player1 mad --player2 mad-experimental`: zwei KI-Konfigurationen gegeneinander,
identische Seeds/Decks paarweise, Ausgabe Winrate + 95%-Konfidenzintervall.
- Dazu ein Konfigurations-Flag-System für die KI (welcher Evaluator, welcher
  CombatSolver aktiv), damit A/B ohne Code-Duplikation geht.
- Aufwand: klein (auf 0.1 drauf).

### 0.3 Feature-Logger ✅ UMGESETZT (--features)
Pro Zugende: Feature-Vektor (erst grob: Leben, Handzahlen, Board-Summen, Länder)
+ Spielausgang als JSONL. Schnittstelle so bauen, dass 1.1 sie später füllt.
- Aufwand: klein. Nutzen: Datensammlung läuft ab Tag 1 mit.

## Phase 1 — Besserer Evaluator (erster Spielstärke-Gewinn)

### 1.1 `GameFeatures` — Feature-Extraktion
Reine Datenklasse aus `Game`: Leben, Clocks (aus 1.2), Handgrößen, **castbare**
Handkarten (≤2 Züge), Board-Power/Toughness, Evasion-Power, Engine-Permanents,
Manaverfügbarkeit/Farben, ungenutztes Mana, Friedhofs-Ressourcen.
- Unit-testbar mit dem bestehenden Test-Framework (Board konstruieren, Werte prüfen).

### 1.2 `RaceCalculator`
`myClock`/`oppClock` (ungeblockt + realistisch) + Rollenbestimmung
(Beatdown/Kontrolle). Klein, pure Funktion über Board+Leben.

### 1.3 `WinProbEvaluator` — Drop-in für `GameStateEvaluator2`
Rollengewichtete Linearkombination der Features, gleiche int-Schnittstelle,
per Flag (0.2) umschaltbar. **Messung:** neu vs. alt, ≥55% über 400 Spiele
auf 2–3 Deck-Paaren, sonst Gewichte nachziehen.

## Phase 2 — Synergie-Bewertung

### 2.1 Karten-Tagging: `produces`/`consumes` Event-Tags ✅ V1 UMGESETZT (--tags)
Kern der Synergie-Erkennung. Pro Karte einmalig (cachebar, beim DB-Scan):
- **consumes**: TriggeredAbilities introspizieren — Klasse + Filter auf Tags
  mappen: `CREATURE_CAST` („whenever you cast a creature spell“), `CREATURE_ETB`,
  `CREATURE_DIES`, `SPELL_CAST_NONCREATURE` (Prowess), `LIFE_GAINED`, `CARD_DRAWN`,
  `TOKEN_CREATED`, `SACRIFICE`, `GRAVEYARD_LEAVES`, `ATTACK_DECLARED`, …
  XMage hat dafür oft direkt passende Ability-Klassen
  (`SpellCastControllerTriggeredAbility`, `DiesCreatureTriggeredAbility`, …) —
  Mapping Klasse→Tag + Filterauswertung (welche Kartentypen zählen).
- **produces**: was tut die Karte selbst — Kreaturenzauber produziert
  `CREATURE_CAST`+`CREATURE_ETB`, Token-Macher `TOKEN_CREATED`+`CREATURE_ETB`,
  Sac-Outlet `SACRIFICE`+`CREATURE_DIES`, Lifegain `LIFE_GAINED`, Cantrip `CARD_DRAWN`.
- Fallback für nicht erkannte Abilities: neutral (kein Tag) — das System muss
  mit Teilabdeckung leben und trotzdem netto besser bewerten.
- Deliverable: `CardSynergyTags.of(card)` + Abdeckungs-Report über ein Testdeck.

### 2.2 `SynergyScore` in den Evaluator
- Board×Board: aktives Paar (Consumer liegt, Producer liegt) = laufende Engine → Bonus.
- Board×Hand: Consumer liegt, Producer auf Hand → **Handkarte wird wertvoller**
  (genau der Fall aus deinem Beispiel: „whenever you cast a creature“-Permanent
  liegt → jede Kreatur auf der Hand bekommt Aufschlag).
- Hand×Deck: Consumer auf Hand, Deck hat viele Producer → Ausspielen des
  Consumers wird attraktiver (Dichte = Anteil Producer im Restdeck).
- Gewichtung: Trigger-Häufigkeit schätzen (wie oft feuert das pro Zug realistisch)
  × Wert des Trigger-Effekts (Outcome-basiert grob).
- **Messung** mit Synergie-Decks (Tribal, Tokens, Sacrifice) gegen die Version
  ohne SynergyScore — hier muss der Effekt deutlich sichtbar sein.

### 2.3 Archetyp-Erkennung aus Decklist (klein)
Vor Spielstart: Kurve, Kreaturenanteil, Removal-Dichte, dominante Tags aus 2.1
→ Preset Aggro/Midrange/Control/Combo → Startgewichte/Rollen-Bias für 1.3.

## Phase 3 — Kampf & Targeting (nutzt Phase 1)

### 3.1 `CombatSolver`
Ersetzt `declareAttackers`/`declareBlockers` in CP6. Kandidaten-Angriffe
(kein/Alpha/sicher/Top-k) × exakte beste Block-Antwort (Branch&Bound,
Deduplizierung identischer Kreaturen), Bewertung über Race-Impact (1.2) statt
Material. Flag-schaltbar, Messung v.a. mit Aggro-Decks.

### 3.2 `TargetSelector` (Threat-Deltas)
Ersetzt die Outcome-Heuristiken der Basisklasse für Removal/Discard/Pump:
Zustand-mit/ohne-Ziel bewerten (1.3), bestes Delta. Top-N-Vorfilter fürs Budget.

### 3.3 `MulliganPlaner` (klein)
Castbarkeit erster 3 Züge + Länder/Curve + Archetyp (2.3). Mulligan in
Simulationen aktivieren (heute im Testmodus aus).

## Phase 4 — Suche

4.1 Timeout-Fix: beste bisherige Aktion spielen statt nichts (kleiner Eingriff
    in `addActionsTimed`).
4.2 Move-Ordering per Evaluator + Iterative Deepening statt hartem Node-Cap.
4.3 Determinisierung: gegnerische Hand samplen statt Perfect Info
    (Mechanik von `createMCTSGame` übernehmen).
4.4 Turn-Plan-Suche (Umbau `SimulationNode2`) — größter Brocken, zuletzt.

## Phase 5 — Lernen (parallel ab Phase 1 möglich)

5.1 Trainingsskript (Python): Win-Prob-Modell auf 0.3-Logs (logistische
    Regression → GBT), Export als Gewichte für 1.3.
5.2 Ko-Präsenz-Features (Karte×Karte) → gelernte Synergien ergänzen 2.2.
5.3 Self-Play-Iteration: bessere KI → neue Daten → Retrain.

## Abhängigkeits-Kurzfassung

```
0.1 → 0.2 → (alles Messbare)
0.1 → 0.3 → 5.1 → 5.2/5.3
1.2 → 1.1 → 1.3 → 3.1, 3.2, 2.2
2.1 → 2.2 → 2.3 (2.1 ist unabhängig startbar!)
4.x unabhängig, 4.4 zuletzt
```

**Startempfehlung:** 0.1 + 0.2 (Simulator + Harness) zuerst — danach parallel
2.1 (Karten-Tagging, unabhängig und der Schlüssel zur Synergie-Bewertung) und
1.1/1.2 (Features + Race).
