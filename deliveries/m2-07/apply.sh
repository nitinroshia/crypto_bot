#!/bin/bash
# Delivery m2-07 (M2, 2026-11-04). Documents only, no project code is changed.
# Puts in place: context/mathematician/NOTES.md (revision 7), docs/correspondence/answer-wo18-addendum.md (the v24 message for D2) and
# docs/work-orders/1.8-schema-reference.sql (M2's reference PostgreSQL schema, untested by M2). It also checks that the files of delivery
# m2-06 are on GitHub and, if one is missing, restores it from deliveries/m2-06/ when that folder is still on your disk.
# Run from anywhere:  bash deliveries/m2-07/apply.sh
set -e

DONE=0
FAILED=0
trap 'rc=$?; if [ "$DONE" != "1" ] && [ "$FAILED" != "1" ]; then echo; echo "FAIL: delivery m2-07 stopped unexpectedly (exit code $rc). Nothing was committed. Paste this whole output to M2."; fi' EXIT
fail() { FAILED=1; echo; echo "FAIL: $1"; echo "Nothing was committed. Paste this whole output to M2."; exit 1; }

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
[ "$(basename "$HERE")" = "m2-07" ] || fail "this script must sit in <repo>/deliveries/m2-07/ (found $HERE)"
git -C "$REPO" rev-parse --is-inside-work-tree >/dev/null 2>&1 || fail "$REPO is not a git repository"
[ -f "$REPO/docs/PROTOCOL.md" ] || fail "docs/PROTOCOL.md not found under $REPO: is this the crypto_bot folder?"
echo "Repo: $REPO"

# 1. SHA-256 of every delivered file against the list M2 gave
if command -v shasum >/dev/null 2>&1; then SHA="shasum -a 256"; else SHA="sha256sum"; fi
sha_of() { $SHA "$1" | awk '{print $1}'; }
echo "Checking delivered files (SHA-256):"
while read -r want name; do
  [ -n "$name" ] || continue
  [ -f "$HERE/$name" ] || fail "missing file deliveries/m2-07/$name"
  got="$(sha_of "$HERE/$name")"
  if [ "$got" != "$want" ]; then fail "$name differs from M2's list (got $got, expected $want). Re-download it and put it in deliveries/m2-07/."; fi
  echo "  OK  $got  $name"
done <<LIST
5555c3e84debe967d9f9b1422c8132b01251e64278b57fecf91fbc6e7bf2cd99  NOTES.md
b2493991710f28967c7e1a7a5d8e7ed2d1dd3213ebf8887fad31e026abc113c8  1.8-schema-reference.sql
6c61352788f8709466bccd65e0955fec887f103edbea36287535413d4b3b8aff  answer-wo18-addendum.md
LIST

# 2. Self-test of the delivered documents
echo "Checking the documents:"
N="$HERE/NOTES.md"; Q="$HERE/1.8-schema-reference.sql"; A="$HERE/answer-wo18-addendum.md"
head -1 "$N" | grep -q '^# Mathematician notes$' || fail "NOTES.md: wrong first line"
grep -q '^Snapshot: 2026-11-04 (revision 7)' "$N" || fail "NOTES.md: no revision 7 Snapshot line"
for n in 1 2 3 4 5 6 7 8 9 10 11; do grep -q "^## $n\. " "$N" || fail "NOTES.md: section $n heading missing"; done
grep -q 'answer-wo18-addendum.md' "$N" || fail "NOTES.md: does not reference the v24 addendum"
grep -q '^Tax layer (design frozen 2026-10-23' "$N" || fail "NOTES.md: tax-layer design missing"
head -1 "$Q" | grep -q '^-- Work Order 1.8: reference PostgreSQL schema' || fail "schema file: wrong first line"
grep -q '^CREATE SCHEMA IF NOT EXISTS nse;' "$Q" || fail "schema file: CREATE SCHEMA line missing"
for t in instrument universe_member data_pull daily_candle candle_flag trading_calendar; do grep -q "CREATE TABLE IF NOT EXISTS nse.$t " "$Q" || fail "schema file: table $t missing"; done
head -1 "$A" | grep -Eq '^From: M2 \| To: D2 \| Re: .+ \| Date: 2026-11-04$' || fail "answer-wo18-addendum.md: bad header line"
grep -q 'forward v24' "$A" || fail "answer-wo18-addendum.md: not the v24 message"
if LC_ALL=C grep -q '[^ -~]' "$N" "$Q" "$A"; then fail "a delivered file contains a non-ASCII character"; fi
echo "  OK  documents"

# 3. Are the files of delivery m2-06 on GitHub? (restore any missing one from deliveries/m2-06/)
RESTORE=()
check_carry() {  # repo path, file name in deliveries/m2-06, expected sha
  local rp="$1" nm="$2" want="$3"
  if [ -f "$REPO/$rp" ]; then
    if [ "$(sha_of "$REPO/$rp")" = "$want" ]; then echo "  OK  $rp is in the repo (identical to M2's m2-06 file)"
    else echo "  OK  $rp is in the repo (differs from M2's m2-06 copy: left as it is)"; fi
  elif [ -f "$REPO/deliveries/m2-06/$nm" ] && [ "$(sha_of "$REPO/deliveries/m2-06/$nm")" = "$want" ]; then
    echo "  RESTORE  $rp is missing: it will be restored from deliveries/m2-06/$nm"
    RESTORE=("${RESTORE[@]}" "$rp|$nm")
  else
    echo "  WARNING: $rp is missing from the repo and no matching copy is in deliveries/m2-06/. Tell M2."
  fi
}
echo "Checking the files of delivery m2-06:"
check_carry "docs/work-orders/1.8.md" "1.8.md" "bfc6e9c09c27cc3e533ed76632c87f284decf778549d0e625c5c307547ecb815"
check_carry "docs/correspondence/answer-t3-accepted.md" "answer-t3-accepted.md" "cc0328d5ffd33807175563d340c519cb8344d9cd960b280f346d74f731b15412"

# 4. Secret safety (the files are never opened; only git metadata is read): temp/secret_keys.txt and the owner's .env
for SK in "temp/secret_keys.txt" ".env"; do
  if git -C "$REPO" ls-files --error-unmatch "$SK" >/dev/null 2>&1; then
    fail "$SK is TRACKED by git. Do not push anything. Tell M2 now (the repository is public)."
  fi
  if [ -n "$(git -C "$REPO" log --all --oneline -- "$SK" 2>/dev/null | head -1)" ]; then
    fail "$SK appears in git history. Do not push anything. Tell M2 now; if it was ever pushed, the keys or tokens it holds must be revoked."
  fi
  if out="$(git -C "$REPO" check-ignore -v "$SK" 2>/dev/null)"; then
    echo "  OK  $SK is git-ignored ($(echo "$out" | awk '{print $1}'))"
  elif [ -e "$REPO/$SK" ]; then
    echo "  WARNING: $SK exists and is NOT git-ignored. Nothing here adds it, but tell M2 and add it to .gitignore."
  else
    echo "  NOTE: $SK does not exist yet and is not git-ignored: add it to .gitignore before you create it (D2 will also check)."
  fi
done

# 5. Is the folder up to date with GitHub?
BR="$(git -C "$REPO" rev-parse --abbrev-ref HEAD)"
git -C "$REPO" fetch -q origin 2>/dev/null || fail "could not reach GitHub (git fetch origin failed)"
if git -C "$REPO" rev-parse --verify -q "origin/$BR" >/dev/null 2>&1; then
  BEHIND="$(git -C "$REPO" rev-list --count "HEAD..origin/$BR")"
  [ "$BEHIND" = "0" ] || fail "your folder is $BEHIND commit(s) behind GitHub. Run: git pull   then run this script again."
  for SK in "temp/secret_keys.txt" ".env"; do
    if [ -n "$(git -C "$REPO" log --oneline "origin/$BR..HEAD" -- "$SK" | head -1)" ]; then
      fail "an unpushed local commit touches $SK. Do not push. Tell M2 now."
    fi
  done
fi

# 6. Copy into place, then verify the copies
mkdir -p "$REPO/context/mathematician" "$REPO/docs/correspondence" "$REPO/docs/work-orders"
cp "$HERE/NOTES.md" "$REPO/context/mathematician/NOTES.md"
cp "$HERE/answer-wo18-addendum.md" "$REPO/docs/correspondence/answer-wo18-addendum.md"
cp "$HERE/1.8-schema-reference.sql" "$REPO/docs/work-orders/1.8-schema-reference.sql"
cmp -s "$HERE/NOTES.md" "$REPO/context/mathematician/NOTES.md" || fail "copy of NOTES.md does not match"
cmp -s "$HERE/answer-wo18-addendum.md" "$REPO/docs/correspondence/answer-wo18-addendum.md" || fail "copy of answer-wo18-addendum.md does not match"
cmp -s "$HERE/1.8-schema-reference.sql" "$REPO/docs/work-orders/1.8-schema-reference.sql" || fail "copy of 1.8-schema-reference.sql does not match"
PATHS=(
  context/mathematician/NOTES.md
  docs/correspondence/answer-wo18-addendum.md
  docs/work-orders/1.8-schema-reference.sql
  deliveries/m2-07/apply.sh
  deliveries/m2-07/NOTES.md
  deliveries/m2-07/answer-wo18-addendum.md
  deliveries/m2-07/1.8-schema-reference.sql
)
for item in "${RESTORE[@]}"; do
  rp="${item%%|*}"; nm="${item##*|}"
  mkdir -p "$(dirname "$REPO/$rp")"
  cp "$REPO/deliveries/m2-06/$nm" "$REPO/$rp"
  cmp -s "$REPO/deliveries/m2-06/$nm" "$REPO/$rp" || fail "restored copy of $rp does not match"
  PATHS=("${PATHS[@]}" "$rp")
done
echo "  OK  files copied into place"

# 7. Commit exactly these paths and push
git -C "$REPO" add -- "${PATHS[@]}" || fail "git add failed"
if git -C "$REPO" diff --cached --quiet -- "${PATHS[@]}"; then
  DONE=1
  echo
  echo "PASS: nothing to commit (GitHub already has exactly these files at $(git -C "$REPO" rev-parse --short HEAD))."
  exit 0
fi
git -C "$REPO" commit -q -m "M2 delivery m2-07: NOTES.md revision 7, Work Order 1.8 addendum (v24) and reference PostgreSQL schema" -- "${PATHS[@]}" || fail "git commit failed"
if ! git -C "$REPO" push -q origin "$BR"; then
  git -C "$REPO" reset -q --soft HEAD~1 || true
  git -C "$REPO" reset -q -- "${PATHS[@]}" || true
  fail "git push failed; the commit was undone and the files are in place. Fix the cause (for example git pull) and run this script again."
fi
DONE=1
echo
echo "PASS: delivery m2-07 committed and pushed as $(git -C "$REPO" rev-parse --short HEAD)."
echo "  docs/correspondence/answer-wo18-addendum.md filed (the v24 message for D2)"
echo "  docs/work-orders/1.8-schema-reference.sql filed (reference PostgreSQL schema, untested by M2)"
echo "  context/mathematician/NOTES.md refreshed (revision 7)"
