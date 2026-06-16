#!/usr/bin/env python3
"""claude-euchre — play Euchre inside your Claude Code statusline.

The board lives in your statusline (below the prompt). You make moves with
quick in-session bash commands:

    !euc new      deal a fresh hand
    !euc 2        play card #2 from your hand
    !euc          show the table (full-size cards, inline)
    !euc help     rules + commands

You are South. North is your partner. East/West are the opponents.
First team to 10 points wins. Pure Python standard library, no dependencies.
"""

import json
import os
import random
import subprocess
import sys
from pathlib import Path

# --------------------------------------------------------------------------- #
# paths
# --------------------------------------------------------------------------- #
HOME = Path.home()
EU_DIR = HOME / ".claude" / "euchre"
STATE_FILE = EU_DIR / "state.json"
PREV_SL_FILE = EU_DIR / "prev_statusline.json"

# --------------------------------------------------------------------------- #
# constants
# --------------------------------------------------------------------------- #
SUITS = ["S", "H", "D", "C"]
RANKS = ["9", "10", "J", "Q", "K", "A"]
SUIT_SYM = {"S": "♠", "H": "♥", "D": "♦", "C": "♣"}
SUIT_NAME = {"S": "Spades", "H": "Hearts", "D": "Diamonds", "C": "Clubs"}
RED = {"H", "D"}
RANK_ORD = {"9": 0, "10": 1, "J": 2, "Q": 3, "K": 4, "A": 5}
SEAT = ["You", "West", "Partner", "East"]  # seats 0,1,2,3 (clockwise)

# --------------------------------------------------------------------------- #
# colour
# --------------------------------------------------------------------------- #
COLOR = not (os.environ.get("NO_COLOR") or os.environ.get("EUCHRE_NO_COLOR"))
RST = "\033[0m" if COLOR else ""
BOLD = "\033[1m" if COLOR else ""
DIM = "\033[90m" if COLOR else ""
REDC = "\033[91m" if COLOR else ""
WHT = "\033[97m" if COLOR else ""
YEL = "\033[93m" if COLOR else ""
GRN = "\033[92m" if COLOR else ""
CYN = "\033[96m" if COLOR else ""

AUTO = False  # set true in self-play/demo mode so seat 0 is AI-driven


# --------------------------------------------------------------------------- #
# card helpers
# --------------------------------------------------------------------------- #
def rank_of(card):
    return card[:-1]


def suit_of(card):
    return card[-1]


def left_suit(trump):
    return {"S": "C", "C": "S", "H": "D", "D": "H"}[trump]


def eff_suit(card, trump):
    """Effective suit. The left bower counts as trump, not its printed suit."""
    if rank_of(card) == "J" and suit_of(card) == left_suit(trump):
        return trump
    return suit_of(card)


def card_value(card, trump, led):
    """Higher beats lower within a trick. Bowers rank above all other trump."""
    r, s = rank_of(card), suit_of(card)
    if r == "J" and s == trump:
        return 1000  # right bower
    if r == "J" and s == left_suit(trump):
        return 900  # left bower
    es = eff_suit(card, trump)
    if es == trump:
        return 100 + RANK_ORD[r]
    if es == led:
        return 50 + RANK_ORD[r]
    return RANK_ORD[r]  # off-suit: cannot win the trick


def legal_moves(hand, led, trump):
    if not led:
        return list(hand)
    follow = [c for c in hand if eff_suit(c, trump) == led]
    return follow if follow else list(hand)


def legal_indices(hand, led, trump):
    legal = legal_moves(hand, led, trump)
    return [i for i, c in enumerate(hand) if c in legal]


def team(seat):
    return seat % 2


def active_seats(maker, alone):
    if not alone:
        return [0, 1, 2, 3]
    sitter = (maker + 2) % 4
    return [s for s in range(4) if s != sitter]


def next_seat(seat, maker, alone):
    sitter = (maker + 2) % 4 if alone else -1
    s = (seat + 1) % 4
    while s == sitter:
        s = (s + 1) % 4
    return s


def pretty(card):
    """Plain (non-ANSI) glyph form, e.g. J♥ — safe to store in the state file."""
    return rank_of(card) + SUIT_SYM[suit_of(card)]


# --------------------------------------------------------------------------- #
# AI: bidding
# --------------------------------------------------------------------------- #
def trump_strength(hand, trump):
    s = 0.0
    for c in hand:
        r, su = rank_of(c), suit_of(c)
        if r == "J" and su == trump:
            s += 4.0
        elif r == "J" and su == left_suit(trump):
            s += 3.0
        elif eff_suit(c, trump) == trump:
            s += {"A": 2.7, "K": 2.2, "Q": 1.7, "10": 1.2, "9": 1.0}[r]
        elif r == "A":
            s += 1.0  # off-suit ace
    return s


def ai_discard(hand, trump):
    """After picking up the up-card the dealer drops the weakest off-suit card."""
    nontrump = [c for c in hand if eff_suit(c, trump) != trump]
    pool = nontrump if nontrump else hand
    return min(pool, key=lambda c: card_value(c, trump, None))


def run_bidding(hands, upcard, dealer):
    """Auto-bid both rounds (stick-the-dealer so a hand always gets played).

    Returns (trump, maker, alone, log). Mutates the dealer's hand on order-up.
    """
    log = []
    up_suit = suit_of(upcard)
    order = [(dealer + 1) % 4, (dealer + 2) % 4, (dealer + 3) % 4, dealer]

    # Round 1: order up the up-card's suit, or pass.
    for seat in order:
        strength = trump_strength(hands[seat], up_suit)
        if seat == dealer:
            strength += trump_strength([upcard], up_suit)  # dealer would gain it
        threshold = 4.0 if team(seat) == team(dealer) else 4.7
        if strength >= threshold:
            trump = up_suit
            maker = seat
            hands[dealer].append(upcard)
            hands[dealer].remove(ai_discard(hands[dealer], trump))
            alone = trump_strength(hands[maker], trump) >= 8.0
            log.append("%s ordered up %s." % (SEAT[seat], SUIT_NAME[trump]))
            if alone:
                log.append("%s is going ALONE!" % SEAT[seat])
            return trump, maker, alone, log
        log.append("%s passed." % SEAT[seat])

    # Round 2: name any other suit. Dealer is stuck if it comes back around.
    for seat in order:
        best, best_v = None, -1.0
        for t in SUITS:
            if t == up_suit:
                continue
            v = trump_strength(hands[seat], t)
            if v > best_v:
                best, best_v = t, v
        forced = seat == dealer
        if best_v >= 4.2 or forced:
            trump = best
            maker = seat
            alone = trump_strength(hands[seat], trump) >= 8.0
            tag = " (stuck dealer)" if forced and best_v < 4.2 else ""
            log.append("%s called %s.%s" % (SEAT[seat], SUIT_NAME[trump], tag))
            if alone:
                log.append("%s is going ALONE!" % SEAT[seat])
            return trump, maker, alone, log
        log.append("%s passed." % SEAT[seat])

    return up_suit, dealer, False, log  # unreachable


# --------------------------------------------------------------------------- #
# AI: card play
# --------------------------------------------------------------------------- #
def ai_lead(hand, trump):
    offaces = [c for c in hand if rank_of(c) == "A" and eff_suit(c, trump) != trump]
    if offaces:
        return offaces[0]
    nontrump = [c for c in hand if eff_suit(c, trump) != trump]
    if nontrump:
        return min(nontrump, key=lambda c: RANK_ORD[rank_of(c)])
    return min(hand, key=lambda c: card_value(c, trump, trump))


def ai_play(hand, trick, trump, led, seat):
    legal = legal_moves(hand, led, trump)
    if not trick:
        return ai_lead(hand, trump)
    val = lambda c: card_value(c, trump, led)
    best_seat, best_card = max(trick, key=lambda sc: card_value(sc[1], trump, led))
    best_val = card_value(best_card, trump, led)
    if team(best_seat) == team(seat):  # partner already winning -> duck low
        return min(legal, key=val)
    beating = [c for c in legal if val(c) > best_val]
    if beating:  # win as cheaply as possible
        return min(beating, key=val)
    return min(legal, key=val)  # can't win -> throw lowest


# --------------------------------------------------------------------------- #
# engine
# --------------------------------------------------------------------------- #
def sort_hand(hand, trump):
    def key(c):
        es = eff_suit(c, trump)
        if es == trump:
            return (0, -card_value(c, trump, trump))
        grp = {"S": 1, "H": 2, "D": 3, "C": 4}[es]
        return (grp, -RANK_ORD[rank_of(c)])

    return sorted(hand, key=key)


def play_card(state, seat, card):
    trump = state["trump"]
    state["hands"][seat].remove(card)
    if not state["trick"]:
        state["led"] = eff_suit(card, trump)
    state["trick"].append([seat, card])
    state["log"].append("%s played %s" % (SEAT[seat], pretty(card)))
    if len(state["trick"]) == len(active_seats(state["maker"], state["alone"])):
        _resolve_trick(state)
    else:
        state["turn"] = next_seat(seat, state["maker"], state["alone"])


def _resolve_trick(state):
    trump, led = state["trump"], state["led"]
    win_seat, win_card = max(
        state["trick"], key=lambda sc: card_value(sc[1], trump, led)
    )
    state["tricks"][win_seat] += 1
    state["log"].append(
        "→ %s won the trick with %s" % (SEAT[win_seat], pretty(win_card))
    )
    state["last_trick"] = state["trick"]
    state["trick"] = []
    state["led"] = None
    state["leader"] = win_seat
    state["turn"] = win_seat


def _finish_hand(state):
    maker, alone = state["maker"], state["alone"]
    made = state["tricks"][maker] + state["tricks"][(maker + 2) % 4]
    if made >= 3:
        pts = (4 if alone else 2) if made == 5 else 1
        wteam = team(maker)
        verb = "a march!" if made == 5 else "made the bid"
    else:
        pts, wteam, verb = 2, 1 - team(maker), "EUCHRED!"
    state["scores"][wteam] += pts
    who = "You/Partner" if wteam == 0 else "Opponents"
    state["log"].append(
        "Hand over: makers took %d — %s  (%s +%d)" % (made, verb, who, pts)
    )
    state["phase"] = "done"
    if max(state["scores"]) >= 10:
        state["phase"] = "gameover"
        state["log"].append(
            "YOU WIN THE GAME!" if state["scores"][0] >= 10 else "Opponents win the game."
        )


def advance(state):
    """Play out AI turns until it's the human's turn, or the hand ends."""
    while True:
        if sum(state["tricks"]) == 5:
            _finish_hand(state)
            return
        seat = state["turn"]
        if seat == 0 and 0 in active_seats(state["maker"], state["alone"]) and not AUTO:
            return  # wait for the human
        card = ai_play(
            state["hands"][seat], state["trick"], state["trump"], state["led"], seat
        )
        play_card(state, seat, card)


def new_hand(prev):
    if prev and prev.get("phase") != "gameover":
        dealer = (prev["dealer"] + 1) % 4
        scores = prev["scores"]
        hand_no = prev.get("hand_no", 0) + 1
    else:
        dealer = random.randrange(4)
        scores = [0, 0]
        hand_no = 1

    deck = [r + s for s in SUITS for r in RANKS]
    random.shuffle(deck)
    hands = [deck[i * 5 : (i + 1) * 5] for i in range(4)]
    upcard = deck[20]
    trump, maker, alone, blog = run_bidding(hands, upcard, dealer)
    hands[0] = sort_hand(hands[0], trump)

    state = {
        "active": True,
        "phase": "play",
        "trump": trump,
        "maker": maker,
        "alone": alone,
        "dealer": dealer,
        "hands": hands,
        "trick": [],
        "last_trick": [],
        "led": None,
        "leader": (dealer + 1) % 4,
        "turn": (dealer + 1) % 4,
        "tricks": [0, 0, 0, 0],
        "scores": scores,
        "hand_no": hand_no,
        "upcard": upcard,
        "log": ["Dealer: %s. Up-card: %s." % (SEAT[dealer], pretty(upcard))] + blog,
    }
    advance(state)
    return state


# --------------------------------------------------------------------------- #
# state persistence
# --------------------------------------------------------------------------- #
def load_state():
    try:
        return json.loads(STATE_FILE.read_text())
    except Exception:
        return None


def save_state(state):
    EU_DIR.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state))
    tmp.replace(STATE_FILE)


# --------------------------------------------------------------------------- #
# rendering: shared
# --------------------------------------------------------------------------- #
def csuit(suit):
    sym = SUIT_SYM[suit]
    if not COLOR:
        return sym
    return (REDC if suit in RED else WHT) + sym + RST


def ctoken(card, trump):
    """Compact coloured card token, e.g. J♥ — trump/bowers highlighted."""
    txt = pretty(card)
    if not COLOR:
        return txt
    r, s = rank_of(card), suit_of(card)
    if r == "J" and s in (trump, left_suit(trump)):
        return BOLD + YEL + txt + RST  # bower
    if eff_suit(card, trump) == trump:
        return YEL + txt + RST
    return (REDC if s in RED else WHT) + txt + RST


def big_card(card):
    r, s = rank_of(card), SUIT_SYM[suit_of(card)]
    lines = [
        "┌─────┐",
        "│%-2s   │" % r,
        "│  %s  │" % s,
        "│   %2s│" % r,
        "└─────┘",
    ]
    if not COLOR:
        return lines
    col = REDC if suit_of(card) in RED else WHT
    return [col + ln + RST for ln in lines]


def big_row(cards, labels=None, labels_below=False):
    blocks = [big_card(c) for c in cards]
    body = ["  ".join(b[i] for b in blocks) for i in range(5)]
    if not labels:
        return body
    lab = "  ".join(l.center(7) for l in labels)
    return body + [lab] if labels_below else [lab] + body


def bower_note(hand, trump):
    notes = []
    for c in hand:
        if rank_of(c) == "J" and suit_of(c) == trump:
            notes.append("%s = right bower (highest)" % pretty(c))
        elif rank_of(c) == "J" and suit_of(c) == left_suit(trump):
            notes.append("%s = left bower (counts as %s)" % (pretty(c), SUIT_NAME[trump]))
    return "   ".join(notes)


# --------------------------------------------------------------------------- #
# rendering: statusline board (compact, lives below the prompt)
# --------------------------------------------------------------------------- #
def render_board(state):
    """Clean two-line scoreboard mirror for the statusline. Play happens in the
    interactive game in a separate terminal; this is a glanceable status only."""
    trump = state["trump"]
    you, them = state["scores"]
    won = state["tricks"][0] + state["tricks"][2]
    lost = state["tricks"][1] + state["tricks"][3]

    head = "%s %sEUCHRE%s   You %s%d%s · Them %s%d%s   trump %s %s   tricks %d-%d" % (
        csuit(trump), BOLD, RST,
        GRN, you, RST, REDC, them, RST,
        csuit(trump), SUIT_NAME[trump], won, lost,
    )

    if state["phase"] == "gameover":
        msg = "YOU WIN! \U0001f389" if you >= 10 else "Opponents win."
        tail = "  " + BOLD + msg + RST + DIM + "   (deal again in your euchre terminal)" + RST
    elif state["phase"] == "done":
        tail = "  " + DIM + "hand over — deal the next one in your euchre terminal" + RST
    else:
        seats = active_seats(state["maker"], state["alone"])
        if state["turn"] == 0 and 0 in seats:
            tail = "  " + BOLD + YEL + "▸ your turn" + RST + DIM + " — play in your euchre terminal" + RST
        else:
            tail = "  " + DIM + "…%s to play…" % SEAT[state["turn"]] + RST
    return head + "\n" + tail


# --------------------------------------------------------------------------- #
# rendering: full inline view (printed as command output after a move)
# --------------------------------------------------------------------------- #
def render_full(state):
    trump = state["trump"]
    you, them = state["scores"]
    out = ["", "  %s%s EUCHRE %s%s   You %s%d%s  ·  Them %s%d%s   "
           "Trump: %s %s   Maker: %s%s" % (
               BOLD, csuit(trump), csuit(trump), RST,
               GRN, you, RST, REDC, them, RST,
               csuit(trump), SUIT_NAME[trump], SEAT[state["maker"]],
               "  (going alone)" if state["alone"] else "")]
    out.append("")

    for ev in state["log"]:
        out.append("  " + DIM + ev + RST)
    if state["log"]:
        out.append("")

    table = state["trick"] if state["trick"] else state.get("last_trick", [])
    if table:
        out.append("  " + ("On the table:" if state["trick"] else "Last trick:"))
        labels = [SEAT[s] for s, _ in table]
        cards = [c for _, c in table]
        out += ["  " + ln for ln in big_row(cards, labels)]
        out.append("")

    seats = active_seats(state["maker"], state["alone"])
    if 0 not in seats:
        out.append("  " + DIM + "(your partner is going alone — sit back and watch)" + RST)
    elif state["phase"] == "play" and state["turn"] == 0:
        hand = state["hands"][0]
        out.append("  Your hand:")
        out += ["  " + ln for ln in big_row(hand, ["[%d]" % i for i in range(len(hand))], True)]
        note = bower_note(hand, trump)
        if note:
            out.append("  " + DIM + note + RST)
        legal = legal_indices(hand, state["led"], trump)
        if state["led"]:
            out.append("  %sFollow %s if you can.%s  Play:  %s!euc %s%s"
                       % (YEL, SUIT_NAME[state["led"]], RST, BOLD,
                          "/".join(str(i) for i in legal), RST))
        else:
            out.append("  Your lead.  Play:  %s!euc 0-%d%s" % (BOLD, len(hand) - 1, RST))
    elif state["phase"] == "gameover":
        msg = "YOU WIN THE GAME! \U0001f389" if you >= 10 else "Opponents win the game."
        out.append("  %s%s%s   Final: You %d · Them %d" % (BOLD, msg, RST, you, them))
        out.append("  New game:  %s!euc new%s" % (BOLD, RST))
    elif state["phase"] == "done":
        out.append("  Hand complete.  Next hand:  %s!euc new%s" % (BOLD, RST))

    out.append("")
    return "\n".join(out)


# --------------------------------------------------------------------------- #
# statusline fallback (when no game is active)
# --------------------------------------------------------------------------- #
def git_branch(cwd):
    try:
        r = subprocess.run(
            ["git", "-C", cwd, "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=2,
        )
        if r.returncode == 0:
            return r.stdout.strip()
    except Exception:
        pass
    return ""


def default_status(raw):
    try:
        d = json.loads(raw) if raw else {}
    except Exception:
        d = {}
    cwd = (d.get("workspace", {}) or {}).get("current_dir") or d.get("cwd") or os.getcwd()
    base = os.path.basename(cwd.rstrip("/")) or cwd
    model = (d.get("model", {}) or {}).get("display_name", "")
    branch = git_branch(cwd)
    parts = [CYN + base + RST]
    if branch:
        parts.append(YEL + branch + RST)
    if model:
        parts.append(DIM + model + RST)
    parts.append(DIM + "· play Euchre: !euc new" + RST)
    return "  ".join(parts)


def passthrough_or_default(raw):
    try:
        prev = json.loads(PREV_SL_FILE.read_text()).get("command")
    except Exception:
        prev = None
    if prev and "euchre" not in prev:
        try:
            r = subprocess.run(prev, shell=True, input=raw, capture_output=True,
                               text=True, timeout=4)
            sys.stdout.write(r.stdout)
            return
        except Exception:
            pass
    print(default_status(raw))


def cmd_board():
    raw = ""
    if not sys.stdin.isatty():
        try:
            raw = sys.stdin.read()
        except Exception:
            raw = ""
    try:
        state = load_state()
        if state and state.get("active") and state.get("phase") in ("play", "done", "gameover"):
            print(render_board(state))
            return
    except Exception:
        pass
    passthrough_or_default(raw)


# --------------------------------------------------------------------------- #
# settings.json wiring (install / uninstall helpers)
# --------------------------------------------------------------------------- #
def _load_json(path):
    try:
        return json.loads(Path(path).read_text())
    except Exception:
        return {}


def install_statusline(settings_path, eu_dir, launcher):
    settings_path = Path(settings_path)
    eu_dir = Path(eu_dir)
    eu_dir.mkdir(parents=True, exist_ok=True)
    settings = _load_json(settings_path)

    existing = settings.get("statusLine")
    if isinstance(existing, dict) and "euchre" not in (existing.get("command") or ""):
        (eu_dir / "prev_statusline.json").write_text(json.dumps(existing))

    if settings_path.exists():
        bak = settings_path.with_suffix(".json.euchre-bak")
        if not bak.exists():
            bak.write_text(settings_path.read_text())

    settings["statusLine"] = {"type": "command", "command": "%s board" % launcher, "padding": 0}
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    settings_path.write_text(json.dumps(settings, indent=2) + "\n")
    print("✓ statusline wired -> %s board" % launcher)


def uninstall_statusline(settings_path, eu_dir):
    settings_path = Path(settings_path)
    eu_dir = Path(eu_dir)
    settings = _load_json(settings_path)
    prev = None
    try:
        prev = json.loads((eu_dir / "prev_statusline.json").read_text())
    except Exception:
        prev = None
    if prev:
        settings["statusLine"] = prev
    else:
        settings.pop("statusLine", None)
    if settings_path.exists():
        settings_path.write_text(json.dumps(settings, indent=2) + "\n")
    print("✓ statusline restored")


# --------------------------------------------------------------------------- #
# commands
# --------------------------------------------------------------------------- #
HELP = """\
{b}claude-euchre{r} — a quick game of Euchre while Claude works.

{b}How to play (zero lag):{r}
  Open a {b}second terminal{r} (a new tab/window, or a tmux split) and run:
      {c}euchre{r}
  Play there in real time while Claude works in the other window. Inside the
  game just press a {b}number{r} (1-5) to play that card, then Enter.
      {c}n{r} = new hand    {c}q{r} = quit    {c}?{r} = this help

{b}Why a second terminal:{r} anything typed into the Claude prompt (including
{c}!euc{r}) waits for Claude's turn to finish — that lag defeats the point. A
separate terminal is independent, so play is instant. The Claude statusline
still shows a live scoreboard.

{b}You{r} are South; {b}Partner{r} is North; {b}West/East{r} are opponents.
Follow the led suit if you can. First team to {b}10{r} points wins.

{b}Bowers{r} (the one rule beginners miss):
  • Right bower = Jack of the trump suit  = the highest card.
  • Left bower  = Jack of the same colour  = 2nd highest, and it
    counts as a {b}trump{r} card, not its printed suit.
  Example: trump {y}Hearts{r} → J{y}♥{r} is highest, J{y}♦{r} is 2nd and plays as a Heart.

Bidding is automatic (stick-the-dealer) so you jump straight to playing.
""".format(b=BOLD, r=RST, c=CYN, y=YEL)


def cmd_play(idx):
    state = load_state()
    if not state or state.get("phase") not in ("play",):
        print(render_full(state) if state else no_game())
        return
    if state["turn"] != 0 or 0 not in active_seats(state["maker"], state["alone"]):
        print("  Not your turn yet — run %s!euc%s to see the board." % (BOLD, RST))
        return
    hand = state["hands"][0]
    if idx < 0 or idx >= len(hand):
        print("  No card #%d. You have %d cards (0-%d)." % (idx, len(hand), len(hand) - 1))
        return
    card = hand[idx]
    if card not in legal_moves(hand, state["led"], state["trump"]):
        legal = legal_indices(hand, state["led"], state["trump"])
        print("  You must follow %s. Legal: %s"
              % (SUIT_NAME[state["led"]], "/".join("!euc %d" % i for i in legal)))
        return
    state["log"] = []
    play_card(state, 0, card)
    advance(state)
    save_state(state)
    print(render_full(state))


def cmd_new():
    state = new_hand(load_state())
    save_state(state)
    print(render_full(state))


def cmd_show():
    state = load_state()
    if not state:
        print(no_game())
        return
    if state["phase"] in ("done", "gameover"):
        print(render_full(state))
    else:
        print(render_full(state))


def cmd_quit():
    state = load_state()
    if state:
        state["active"] = False
        save_state(state)
    print("  Euchre paused. Statusline back to normal. Deal again with %s!euc new%s." % (BOLD, RST))


def cmd_auto():
    global AUTO
    AUTO = True
    state = None
    hands_played = 0
    while True:
        state = new_hand(state)
        hands_played += 1
        print(render_board(state))
        print()
        if state["phase"] == "gameover" or hands_played > 60:
            break
    print("  (demo over after %d hands)" % hands_played)


def no_game():
    return "  No hand in progress. Deal one with  %s!euc new%s\n\n%s" % (BOLD, RST, HELP)


def main():
    args = sys.argv[1:]
    cmd = args[0] if args else ""

    if cmd == "board":
        cmd_board()
    elif cmd == "__install_statusline":
        install_statusline(args[1], args[2], args[3])
    elif cmd == "__uninstall_statusline":
        uninstall_statusline(args[1], args[2])
    elif cmd in ("new", "deal"):
        cmd_new()
    elif cmd in ("help", "-h", "--help"):
        print(HELP)
    elif cmd in ("auto", "demo"):
        cmd_auto()
    elif cmd in ("quit", "stop", "off"):
        cmd_quit()
    elif cmd.isdigit():
        cmd_play(int(cmd))
    elif cmd == "":
        cmd_show()
    else:
        print("  Unknown: %r\n%s" % (cmd, HELP))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
