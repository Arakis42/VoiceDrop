# Mage.Simulator — Headless Auto-Battle (KI gegen KI)

Batch-Simulator für Deck-Tests: spielt N komplette Spiele `ComputerPlayer7` gegen
`ComputerPlayer7` ohne Server/Client, schreibt ein JSONL-Ergebnis pro Spiel und
eine Zusammenfassung (Winrate mit 95%-Konfidenzintervall).

## Voraussetzungen

Einmalig alle mage-Artefakte ins lokale Maven-Repo installieren:

```bash
cd ..            # mage-Wurzel
mvn -DskipTests install
```

## Benutzung

```bash
cd Mage.Simulator
mvn -q package
mvn -q exec:java -Dexec.args="--deck1 '../Mage.Tests/RB Aggro.dck' --deck2 '../Mage.Tests/RB Aggro.dck' --games 10 --skill 5 --seed 42 --out results.jsonl"
```

Optionen: `--games N`, `--skill N` (1–8, beide), `--skill1/--skill2` (A/B-Test),
`--thinkTime S` (Denkzeit-Limit pro Entscheidung, Default skill×3),
`--seed N` (Spiel i nutzt seed+i), `--maxTurns N` (Abbruch als Draw, Default 60),
`--out DATEI`, `--verbose` (KI-Logs).

Beim ersten Lauf wird die Karten-Datenbank gebaut (`CardScanner.scan()`, dauert
einige Minuten, legt `db/` im Arbeitsverzeichnis an).

## Ausgabe

`results.jsonl`, eine Zeile pro Spiel:

```json
{"game":0,"seed":42,"deck1":"…","deck2":"…","first_choice":"AI_1","winner":"AI_2","turns":11,"life1":0,"life2":14,"duration_ms":63210,"end_reason":"game_over"}
```

`winner` ist `AI_1`/`AI_2`/`draw`/`error`; `end_reason` `game_over`, `max_turns`
(Abbruch durch `--maxTurns`) oder `error`.

## Design-Notizen

- Nutzt dieselben Bausteine wie das Unit-Test-Framework (`CardTestPlayerBaseAI`):
  `TwoPlayerDuel`, `ComputerPlayer7`, Fake-`Match` (für `MatchPlayer`-Verdrahtung),
  `GameOptions.stopOnTurn` als Notbremse.
- Jedes Spiel läuft in einem eigenen Thread mit `GAME`-Namenspräfix — die Engine
  erzwingt das (`ThreadUtils.ensureRunInGameThread`).
- Play/Draw-Balance: die „Wer beginnt?“-Entscheidung wechselt pro Spiel.
- Bewusst sequenziell: der KI-interne Simulations-Threadpool ist eine geteilte
  statische Ressource (`COMPUTER_MAX_THREADS_FOR_SIMULATIONS = 5`). Parallelität
  besser über mehrere JVM-Prozesse (verschiedene `--seed`-Bereiche, gleiche Decks).
- Mulligans sind aktiv (Spieler laufen nicht im Test-Modus).

## Nächste Schritte (siehe mage-analysis/06-coding-backlog.md)

- 0.2: `--player1/--player2`-Flags für unterschiedliche KI-Konfigurationen (A/B).
- 0.3: Feature-Logger (Zustands-Vektor pro Zug für spätere ML-Trainingsdaten).
