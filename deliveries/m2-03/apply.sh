#!/bin/bash
# Delivery m2-03 (M2, 2026-10-23). Documents only, no project code is changed. It replaces the earlier m2-01 and m2-02 downloads.
# Puts in place: context/mathematician/NOTES.md, docs/PROTOCOL.md (section 6 roster only), docs/correspondence/answer-s2-rulings.md
# (the single message for D2, forward v20 including v19), docs/history/m2-sandbox-calibration-2026-10-20.md,
# docs/work-orders/1.7.md and docs/work-orders/1.7-task3_reference.py (Work Order 1.7, Task 3).
# Run from anywhere:  bash deliveries/m2-03/apply.sh
set -e

DONE=0
FAILED=0
trap 'rc=$?; if [ "$DONE" != "1" ] && [ "$FAILED" != "1" ]; then echo; echo "FAIL: delivery m2-03 stopped unexpectedly (exit code $rc). Nothing was committed. Paste this whole output to M2."; fi' EXIT
fail() { FAILED=1; echo; echo "FAIL: $1"; echo "Nothing was committed. Paste this whole output to M2."; exit 1; }

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
[ "$(basename "$HERE")" = "m2-03" ] || fail "this script must sit in <repo>/deliveries/m2-03/ (found $HERE)"
git -C "$REPO" rev-parse --is-inside-work-tree >/dev/null 2>&1 || fail "$REPO is not a git repository"
[ -f "$REPO/docs/PROTOCOL.md" ] || fail "docs/PROTOCOL.md not found under $REPO: is this the crypto_bot folder?"
echo "Repo: $REPO"

# 1. SHA-256 of every delivered file against the list M2 gave
if command -v shasum >/dev/null 2>&1; then SHA="shasum -a 256"; else SHA="sha256sum"; fi
echo "Checking delivered files (SHA-256):"
while read -r want name; do
  [ -n "$name" ] || continue
  [ -f "$HERE/$name" ] || fail "missing file deliveries/m2-03/$name"
  got="$($SHA "$HERE/$name" | awk '{print $1}')"
  if [ "$got" != "$want" ]; then fail "$name differs from M2's list (got $got, expected $want). Re-download it and put it in deliveries/m2-03/."; fi
  echo "  OK  $got  $name"
done <<LIST
35e638ffef83785570cad963851b7885588be9979d49c091250d2af112522c1a  NOTES.md
028ba99427603608f5486aba5f9e79aaaf0f8ba82d8a8748e07e3e811d5e0271  PROTOCOL.md
761a2488aee6aa0ce100a8052627a53f62942107341c1744be414cd3616eb3bf  answer-s2-rulings.md
d37b563604d40c6681ce4e636f9dd9307c3391bc498e7aa9caab4ad9a6f19861  m2-sandbox-calibration-2026-10-20.md
985a2c444e6767c526e2d4d5407497a0c1bc2ba91bbb0f60d10f505d4e6019ae  1.7.md
7d17a98f53c23ede9861fe355e11612288adfe93597ffbb8748f9d139a698da5  1.7-task3_reference.py
LIST

# 2. docs/PROTOCOL.md: only the section 6 roster rows may change. Compare everything before the first roster row, ignoring spacing.
norm() { tr -d '\r' < "$1" | sed -e 's/[[:space:]][[:space:]]*/ /g' -e 's/^ //' -e 's/ $//' | awk 'NF'; }
prefix_of() { norm "$1" | awk '/^\| M0 \|/{exit} {print}'; }
if ! cmp -s <(prefix_of "$REPO/docs/PROTOCOL.md") <(prefix_of "$HERE/PROTOCOL.md"); then
  echo "First differences (repo copy < , delivered copy > ):"
  diff <(prefix_of "$REPO/docs/PROTOCOL.md") <(prefix_of "$HERE/PROTOCOL.md") | head -8 || true
  fail "docs/PROTOCOL.md in your folder differs from the version M2 read above section 6. It was NOT changed."
fi
echo "  OK  docs/PROTOCOL.md: everything above the section 6 roster is identical to your copy"

# 3. Self-test of the delivered documents
echo "Checking the documents:"
N="$HERE/NOTES.md"; P="$HERE/PROTOCOL.md"; A="$HERE/answer-s2-rulings.md"; Y="$HERE/m2-sandbox-calibration-2026-10-20.md"; W="$HERE/1.7.md"; R="$HERE/1.7-task3_reference.py"
head -1 "$N" | grep -q '^# Mathematician notes$' || fail "NOTES.md: wrong first line"
grep -q '^Snapshot: 2026-10-23' "$N" || fail "NOTES.md: no Snapshot line"
for n in 1 2 3 4 5 6 7 8 9 10 11; do grep -q "^## $n\. " "$N" || fail "NOTES.md: section $n heading missing"; done
grep -q 'answer-s2-rulings.md' "$N" || fail "NOTES.md: does not reference the S2 rulings"
grep -q '^Tax layer (design frozen 2026-10-23' "$N" || fail "NOTES.md: tax-layer design missing"
grep -q 'Work Order 1.7' "$N" || fail "NOTES.md: does not mention Work Order 1.7"
head -1 "$A" | grep -Eq '^From: M2 \| To: D2 \| Re: .+ \| Date: 2026-10-23$' || fail "answer-s2-rulings.md: bad header line"
grep -q 'forward v20, includes v19' "$A" || fail "answer-s2-rulings.md: not the combined v20 message"
grep -q '^| M2 | mathematician |' "$P" || fail "PROTOCOL.md: M2 row missing"
grep -q '^| D2 | developer |' "$P" || fail "PROTOCOL.md: D2 row missing"
for k in '1\. \*\*No money\.\*\*' '2\. \*\*The loop\.\*\*' '3\. \*\*Agents talk only through the repo\.\*\*'; do grep -q "^$k" "$P" || fail "PROTOCOL.md: a hard limit line is missing"; done
grep -q 'SANDBOX ONLY' "$Y" || fail "calibration record: missing the SANDBOX ONLY label"
head -1 "$W" | grep -q '^# Work Order 1.7 -- Task 3 shock_response' || fail "1.7.md: wrong first line"
grep -q 'START ONLY AFTER M2 HAS ACCEPTED THE S2 REPORT' "$W" || fail "1.7.md: start condition missing"
for k in '## 1. Definition' '## 2. Stability' '## 3. Order of work' '## 4. Acceptance tests' '## 5. Report contents' '## 6. Gut-checks'; do grep -q "^$k" "$W" || fail "1.7.md: heading '$k' missing"; done
grep -q 'SANDBOX-ONLY' "$R" || fail "reference script: missing the SANDBOX-ONLY label"
if command -v python3 >/dev/null 2>&1; then
  python3 -c "import ast,sys; ast.parse(open(sys.argv[1]).read())" "$R" || fail "reference script: Python syntax error"
  echo "  OK  reference script parses"
else
  echo "  (python3 not found: skipped the syntax check of the reference script)"
fi
if LC_ALL=C grep -q '[^ -~]' "$N" "$P" "$A" "$Y" "$W" "$R"; then fail "a delivered file contains a non-ASCII character"; fi
echo "  OK  documents"

# 4. Secret-keys safety (the file is never opened; only git metadata is read)
SK="temp/secret_keys.txt"
if git -C "$REPO" ls-files --error-unmatch "$SK" >/dev/null 2>&1; then
  fail "$SK is TRACKED by git. Do not push anything. Tell M2 now (the repository is public)."
fi
if [ -n "$(git -C "$REPO" log --all --oneline -- "$SK" 2>/dev/null | head -1)" ]; then
  fail "$SK appears in git history. Do not push anything. Tell M2 now; if it was ever pushed, the keys it holds must be revoked."
fi
if out="$(git -C "$REPO" check-ignore -v "$SK" 2>/dev/null)"; then
  echo "  OK  $SK is git-ignored ($(echo "$out" | awk '{print $1}'))"
else
  echo "  WARNING: $SK is NOT git-ignored. Nothing here adds it, but tell M2 and add 'temp/' to .gitignore."
fi

# 5. Is the folder up to date with GitHub?
BR="$(git -C "$REPO" rev-parse --abbrev-ref HEAD)"
git -C "$REPO" fetch -q origin 2>/dev/null || fail "could not reach GitHub (git fetch origin failed)"
if git -C "$REPO" rev-parse --verify -q "origin/$BR" >/dev/null 2>&1; then
  BEHIND="$(git -C "$REPO" rev-list --count "HEAD..origin/$BR")"
  [ "$BEHIND" = "0" ] || fail "your folder is $BEHIND commit(s) behind GitHub. Run: git pull   then run this script again."
  if [ -n "$(git -C "$REPO" log --oneline "origin/$BR..HEAD" -- "$SK" | head -1)" ]; then
    fail "an unpushed local commit touches $SK. Do not push. Tell M2 now."
  fi
fi

# 6. Copy into place, then verify the copies
mkdir -p "$REPO/context/mathematician" "$REPO/docs/correspondence" "$REPO/docs/history" "$REPO/docs/work-orders"
cp "$HERE/NOTES.md" "$REPO/context/mathematician/NOTES.md"
cp "$HERE/PROTOCOL.md" "$REPO/docs/PROTOCOL.md"
cp "$HERE/answer-s2-rulings.md" "$REPO/docs/correspondence/answer-s2-rulings.md"
cp "$HERE/m2-sandbox-calibration-2026-10-20.md" "$REPO/docs/history/m2-sandbox-calibration-2026-10-20.md"
cp "$HERE/1.7.md" "$REPO/docs/work-orders/1.7.md"
cp "$HERE/1.7-task3_reference.py" "$REPO/docs/work-orders/1.7-task3_reference.py"
cmp -s "$HERE/NOTES.md" "$REPO/context/mathematician/NOTES.md" || fail "copy of NOTES.md does not match"
cmp -s "$HERE/PROTOCOL.md" "$REPO/docs/PROTOCOL.md" || fail "copy of PROTOCOL.md does not match"
cmp -s "$HERE/answer-s2-rulings.md" "$REPO/docs/correspondence/answer-s2-rulings.md" || fail "copy of answer-s2-rulings.md does not match"
cmp -s "$HERE/m2-sandbox-calibration-2026-10-20.md" "$REPO/docs/history/m2-sandbox-calibration-2026-10-20.md" || fail "copy of the calibration record does not match"
cmp -s "$HERE/1.7.md" "$REPO/docs/work-orders/1.7.md" || fail "copy of 1.7.md does not match"
cmp -s "$HERE/1.7-task3_reference.py" "$REPO/docs/work-orders/1.7-task3_reference.py" || fail "copy of the reference script does not match"
echo "  OK  files copied into place"

# 7. Commit exactly these paths and push
PATHS=(
  context/mathematician/NOTES.md
  docs/PROTOCOL.md
  docs/correspondence/answer-s2-rulings.md
  docs/history/m2-sandbox-calibration-2026-10-20.md
  docs/work-orders/1.7.md
  docs/work-orders/1.7-task3_reference.py
  deliveries/m2-03/apply.sh
  deliveries/m2-03/NOTES.md
  deliveries/m2-03/PROTOCOL.md
  deliveries/m2-03/answer-s2-rulings.md
  deliveries/m2-03/m2-sandbox-calibration-2026-10-20.md
  deliveries/m2-03/1.7.md
  deliveries/m2-03/1.7-task3_reference.py
)
git -C "$REPO" add -- "${PATHS[@]}" || fail "git add failed"
if git -C "$REPO" diff --cached --quiet -- "${PATHS[@]}"; then
  DONE=1
  echo
  echo "PASS: nothing to commit (GitHub already has exactly these files at $(git -C "$REPO" rev-parse --short HEAD))."
  exit 0
fi
git -C "$REPO" commit -q -m "M2 delivery m2-03: NOTES.md revision 3, PROTOCOL roster, the single message for D2 (v20 incl. v19), Work Order 1.7 (Task 3) and reference, sandbox calibration record" -- "${PATHS[@]}" || fail "git commit failed"
if ! git -C "$REPO" push -q origin "$BR"; then
  git -C "$REPO" reset -q --soft HEAD~1 || true
  git -C "$REPO" reset -q -- "${PATHS[@]}" || true
  fail "git push failed; the commit was undone and the files are in place. Fix the cause (for example git pull) and run this script again."
fi
DONE=1
echo
echo "PASS: delivery m2-03 committed and pushed as $(git -C "$REPO" rev-parse --short HEAD)."
echo "  docs/correspondence/answer-s2-rulings.md filed (the single message for D2: forward v20, includes v19)"
echo "  docs/work-orders/1.7.md and 1.7-task3_reference.py filed (Work Order 1.7, Task 3: D2 starts it after M2 accepts the S2 report)"
echo "  context/mathematician/NOTES.md refreshed (revision 3); docs/PROTOCOL.md section 6 roster updated"
echo "  docs/history/m2-sandbox-calibration-2026-10-20.md filed (sandbox only)"
