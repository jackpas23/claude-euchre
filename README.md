# claude-euchre 🃏

**Play Euchre inside Claude Code — right in your statusline, while the agent works.**

The game board lives in your Claude Code **statusline** (the area below the prompt).
While Claude is off doing something, you deal a hand and play tricks with quick
in-session bash commands. No tab-switching, no separate app, no dependencies.

```
♥ EUCHRE  You 6·Them 4  Trump ♥Hearts  Maker You  tricks 1-1
  hand   [0]J♥  [1]J♦  [2]A♥  [3]K♠  [4]9♣
  trick   West 10♣    Partner —    East —   ▸You —
  YOUR TURN  play:  !euc 0/1/2/3/4  (your lead)
```

> You are **South**. **North** is your partner. **East** and **West** are the
> opponents. First team to **10** points wins.

---

## Install

One line (downloads the script and wires the statusline non-destructively):

```bash
curl -fsSL https://raw.githubusercontent.com/jackpas23/claude-euchre/main/install.sh | bash
```

Or from a clone:

```bash
git clone https://github.com/jackpas23/claude-euchre
cd claude-euchre && ./install.sh
```

Requirements: **Python 3** (standard library only) and **Claude Code**.
The installer puts a `euchre` launcher (and an `euc` alias) in `~/.local/bin`,
backs up `~/.claude/settings.json`, and points your statusline at the game.
If you already had a statusline, it's preserved and shown whenever no hand is
in progress.

---

## Play

Run these with the in-session `!` prefix (type them right in the Claude Code prompt):

| Command | What it does |
|---|---|
| `!euc new` | Deal a fresh hand |
| `!euc 2` | Play card **#2** from your hand |
| `!euc` | Show the full table inline (big cards) |
| `!euc auto` | Watch the AI play a whole game (demo) |
| `!euc quit` | Pause — statusline reverts to normal |
| `!euc help` | Rules + commands |

The compact board updates in your statusline as play proceeds; `!euc` prints a
full-size, coloured view inline whenever you want a closer look.

Bidding is **automatic** (stick-the-dealer) so you can jump straight to playing
cards — the fun part — while you wait.

---

## Euchre in 30 seconds

- 24-card deck: **9 10 J Q K A** in each suit. Everyone gets 5 cards; one card is
  turned up to propose **trump**.
- You must **follow the led suit** if you can. Highest trump wins the trick;
  otherwise the highest card of the led suit wins.
- **Bowers** — the bit beginners miss:
  - **Right bower** = Jack of the **trump** suit → the **highest** card in the game.
  - **Left bower** = Jack of the **same colour** → **2nd highest**, and it counts
    as a **trump** card, not its printed suit.
  - Example: trump is **♥Hearts** → `J♥` is highest, `J♦` is second and plays as a Heart.
- **Scoring:** makers win 3–4 tricks = **1**, all 5 = **2**, going alone and
  sweeping all 5 = **4**. If the makers are stopped (win fewer than 3) the other
  team is **euchred** for **2**. First to **10** wins.

The board highlights your trump cards and labels the bowers so you learn as you go.

---

## How it works

- **`euchre.py`** is the whole game: a single Python file, standard library only.
- The Claude Code statusline is configured to run `euchre board`, which renders
  the current game from a small state file at `~/.claude/euchre/state.json`.
- When no hand is active, `euchre board` transparently falls back to your
  previous statusline (or a clean default), so installing it costs you nothing
  when you're not playing.
- Moves are ordinary CLI calls (`euchre 2`, `euchre new`) that update the state
  file; the statusline re-renders on Claude Code's normal refresh.

It's a statusline program plus a tiny CLI — nothing patches or hooks Claude Code
itself.

---

## Uninstall

```bash
curl -fsSL https://raw.githubusercontent.com/jackpas23/claude-euchre/main/uninstall.sh | bash
# or, from a clone:
./uninstall.sh
```

This restores your previous statusline and removes the launcher. A backup of
your settings stays at `~/.claude/settings.json.euchre-bak`.

---

## Notes & limits

- Multi-line statuslines are supported by current Claude Code. If yours shows
  only one line, update Claude Code.
- Colours use ANSI; set `NO_COLOR=1` (or `EUCHRE_NO_COLOR=1`) to disable.
- AI opponents are heuristic — fun, not unbeatable. PRs welcome.

## License

MIT — see [LICENSE](LICENSE).
