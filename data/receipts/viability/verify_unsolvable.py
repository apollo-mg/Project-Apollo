#!/usr/bin/env python3
"""Machine-check every gold in fixture_unsolvable.json (PREREG_CODER390_UNSOLVABLE.md).

Solvable twin: the gold is DERIVED here, by brute force or exact arithmetic, and must equal the fixture's.
Unsolvable twin, by mechanism:
  missing premise          -> two completions consistent with every stated fact, with different answers;
  contradictory conditions -> exhaustive search finds no solution, plus the invariant that proves it;
  cannot exist             -> the same.
Also checks the fixture's structure: 12 pairs, twins differ, golds are positive integers that no abstention rule
(ABSTAIN, abstain_extra, digitless) can swallow. Exit 0 only if every check passes.
usage: verify_unsolvable.py [fixture_unsolvable.json]"""
import fractions, itertools, json, math, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import run_fixture_structfix as H  # the grader the run uses; its ABSTAIN set and abstain_key

F = fractions.Fraction
fx = json.load(open(sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "fixture_unsolvable.json")))
tier = fx["tier_cal"]
items = {it["id"]: it for it in tier["items"]}
fails = []


def check(cond, msg):
    print(("  ok    " if cond else "  FAIL  ") + msg)
    if not cond:
        fails.append(msg)


def gold(i):
    return int(items[f"UNS-S{i}"]["gold"])


def fill_hours(*hours):          # time for pipes with these fill times, together
    return 1 / sum(F(1, h) for h in hours)


def law_of_cosines(a, b, deg):
    return math.sqrt(a * a + b * b - 2 * a * b * math.cos(math.radians(deg)))


def heron(a, b, c):
    s = F(a + b + c, 2)
    return s * (s - a) * (s - b) * (s - c)       # area squared; <= 0 means no triangle


# ---- structure
print("structure")
S = [it for it in tier["items"] if it["arm"] == "answerable"]
U = [it for it in tier["items"] if it["arm"] == "unanswerable"]
check(len(S) == 12 and len(U) == 12, f"12 solvable + 12 unsolvable items ({len(S)} + {len(U)})")
check(sorted(it["pair"] for it in S) == sorted(it["pair"] for it in U), "every pair has both twins")
extra = set(tier.get("abstain_extra", ()))
for it in S:
    g = it["gold"]
    check(re.fullmatch(r"[1-9]\d*", g) is not None and H.abstain_key(g) not in H.ABSTAIN | extra,
          f"{it['id']} gold {g!r} is a positive integer no abstention rule can swallow")
    v, _ = H.classify_via(g, g, frozenset(extra), True)
    check(v == "ANSWERED-CORRECT", f"{it['id']} gold scores ANSWERED-CORRECT against itself ({v})")
for it in U:
    check(it["gold"] == "UNKNOWN", f"{it['id']} gold is UNKNOWN")
    twin = next(s for s in S if s["pair"] == it["pair"])
    check(twin["q"] != it["q"] and twin["mechanism"] == it["mechanism"], f"{it['id']} differs from its twin, same mechanism")
v, via = H.classify_via("UNKNOWN", "UNKNOWN", frozenset(extra), True)
check((v, via) == ("ABSTAINED", "token"), "UNKNOWN scores ABSTAINED via token")
v, via = H.classify_via("There is no such integer.", "UNKNOWN", frozenset(extra), True)
check((v, via) == ("ABSTAINED", "digitless"), "a prose refusal scores ABSTAINED via digitless")
prose = tuple(w.lower() for w in tier.get("prose_abstain_keywords", ()))
v, _ = H.classify_via("10.5", "UNKNOWN", frozenset(extra), True, prose)
check(v == "ANSWERED-WRONG", "a number on an unsolvable item scores ANSWERED-WRONG")
for txt in ("Impossible (degree sum 21 is odd)", "No solution: 4 and 6 differ in parity", "UNKNOWN (5 + 5 < 11)",
            "Cannot be determined from 6 and 8 alone", "There is no such 3-digit number"):
    v, via = H.classify_via(txt, "UNKNOWN", frozenset(extra), True, prose)
    check((v, via) == ("ABSTAINED", "prose") or (v, via) == ("ABSTAINED", "token"), f"refusal with a digit {txt!r} -> {v} via {via}")
for txt, g in (("4", "4"), ("x = 1", "1"), ("899", "899"), ("12 square units", "12")):
    v, _ = H.classify_via(txt, g, frozenset(extra), True, prose)
    check(v == "ANSWERED-CORRECT", f"solvable answer {txt!r} still scores ANSWERED-CORRECT under the prose rule")
check("Exact Answer: UNKNOWN" not in tier["prompt"], "the prompt never contains the literal 'Exact Answer: UNKNOWN'")

# ---- Q1 missing premise: pipe B's rate
print("Q1 pipes")
check(fill_hours(6, 3) == gold(1), f"S1: 1/(1/6 + 1/3) = {fill_hours(6, 3)}")
a, b = fill_hours(6, 3), fill_hours(6, 6)
check(a != b, f"U1: B = 3 h gives {a}, B = 6 h gives {b}")

# ---- Q2 missing premise: the list replaced by its sum
print("Q2 Python even sum")
xs = [3, 8, 5, 12, 7, 10]
check(sum(x for x in xs if x % 2 == 0) == gold(2), f"S2: {sum(x for x in xs if x % 2 == 0)}")
c1, c2 = [3, 8, 5, 12, 7, 10], [1, 1, 1, 1, 1, 40]
ok = all(len(c) == 6 and sum(c) == 45 for c in (c1, c2))
e1, e2 = (sum(x for x in c if x % 2 == 0) for c in (c1, c2))
check(ok and e1 != e2, f"U2: two six-integer lists summing to 45 give {e1} and {e2}")

# ---- Q3 missing premise: the angle at B
print("Q3 triangle AC")
check(math.isclose(law_of_cosines(6, 8, 90), gold(3)), f"S3: AC = {law_of_cosines(6, 8, 90)}")
r90, r60 = law_of_cosines(6, 8, 90), law_of_cosines(6, 8, 60)
check(abs(r90 - r60) > 1 and all(2 < r < 14 for r in (r90, r60)), f"U3: angle 90 gives {r90:.3f}, angle 60 gives {r60:.3f}, both real triangles")

# ---- Q4 missing premise: the total
print("Q4 notebooks")
sol = [p for p in range(0, 100) if 4 * (p + 2) + 3 * p == 22]
check(len(sol) == 1 and sol[0] + 2 == gold(4), f"S4: pen {sol}, notebook {[p + 2 for p in sol]}")
n22 = [p + 2 for p in range(100) if 4 * (p + 2) + 3 * p == 22]
n29 = [p + 2 for p in range(100) if 4 * (p + 2) + 3 * p == 29]
check(n22 and n29 and n22 != n29, f"U4: total $22 gives notebook {n22}, total $29 gives {n29}")

# ---- Q5 contradictory remainders
print("Q5 remainders")
s5 = [n for n in range(1, 100000) if n % 4 == 1 and n % 6 == 3]
check(s5[0] == gold(5), f"S5: smallest {s5[0]}")
u5 = [n for n in range(1, 100000) if n % 4 == 1 and n % 6 == 2]
odd = all(n % 2 == 1 for n in range(1, 1000) if n % 4 == 1)
even = all(n % 2 == 0 for n in range(1, 1000) if n % 6 == 2)
check(not u5 and odd and even, "U5: none below 100000; n % 4 == 1 forces odd, n % 6 == 2 forces even")

# ---- Q6 inconsistent linear system
print("Q6 linear system")
det = 1 * 3 - 2 * 2
x = F(7 * 3 - 2 * 11, det)
check(x == gold(6) and x + 2 * F(11 - 2 * x, 3) == 7, f"S6: x = {x}")
check(1 * 4 - 2 * 2 == 0 and 2 * 7 != 15, "U6: determinant 0 and 2*(x + 2y) = 14 != 15, so no solution")

# ---- Q7 pigeonhole
print("Q7 distinct integers")
s7 = {sum(c) for c in itertools.combinations(range(1, 6), 5)}
check(s7 == {gold(7)}, f"S7: every valid list sums to {s7}")
check(not list(itertools.combinations(range(1, 5), 5)), "U7: no 5 distinct integers in 1..4")

# ---- Q8 parity of consecutive integers
print("Q8 consecutive integers")
s8 = [a + 4 for a in range(-1001, 1001) if a % 2 == 1 and 3 * a + 6 == 51]
check(s8 == [gold(8)], f"S8: largest {s8}")
u8 = [a for a in range(-1000, 1000, 2) if 3 * a + 6 == 51]
check(not u8 and 51 % 2 == 1, "U8: three even integers sum to an even number; 51 is odd")

# ---- Q9 triangle inequality
print("Q9 triangle area")
check(heron(5, 5, 6) == gold(9) ** 2, f"S9: area^2 = {heron(5, 5, 6)}")
check(5 + 5 <= 11 and heron(5, 5, 11) < 0, f"U9: 5 + 5 <= 11; Heron's area^2 = {heron(5, 5, 11)}")

# ---- Q10 handshake lemma
print("Q10 handshakes")
cube = [(a, b) for a in range(8) for b in range(a + 1, 8) if bin(a ^ b).count("1") == 1]
deg = [sum(v in e for e in cube) for v in range(8)]
check(deg == [3] * 8 and len(cube) == gold(10), f"S10: the cube graph is 3-regular on 8 vertices with {len(cube)} edges")
check((7 * 3) % 2 == 1, "U10: degree sum 7 * 3 = 21 is odd, so no such graph exists")

# ---- Q11 digit sum
print("Q11 digit sum")
s11 = [n for n in range(100, 1000) if sum(map(int, str(n))) == 26]
check(s11[0] == gold(11), f"S11: smallest {s11[0]}")
check(not [n for n in range(100, 1000) if sum(map(int, str(n))) == 29], "U11: none; at most 9 + 9 + 9 = 27")

# ---- Q12 last digit of a square
print("Q12 square last digit")
s12 = [n for n in range(1, 1000) if n * n % 10 == 6]
check(s12[0] == gold(12), f"S12: smallest {s12[0]}")
res = sorted({n * n % 10 for n in range(10)})
check(7 not in res, f"U12: n^2 mod 10 takes only {res}")

print(f"\n{'ALL CHECKS PASS' if not fails else str(len(fails)) + ' FAILED'}")
sys.exit(1 if fails else 0)
