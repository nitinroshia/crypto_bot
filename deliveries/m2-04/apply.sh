#!/bin/bash
# Delivery m2-04 (M2, 2026-10-25). Documents only, no project code is changed.
# Puts in place: context/mathematician/NOTES.md (revision 4; the repo still shows the 2026-09-23 snapshot) and
# docs/correspondence/answer-s2-accepted.md (the v21 message for D2). It also checks that the files of delivery m2-03 are on GitHub and,
# if one is missing, restores it from deliveries/m2-03/ when that folder is still on your disk.
# Run from anywhere:  bash deliveries/m2-04/apply.sh
set -e

DONE=0
FAILED=0
trap 'rc=$?; if [ "$DONE" != "1" ] && [ "$FAILED" != "1" ]; then echo; echo "FAIL: delivery m2-04 stopped unexpectedly (exit code $rc). Nothing was committed. Paste this whole output to M2."; fi' EXIT
fail() { FAILED=1; echo; echo "FAIL: $1"; echo "Nothing was committed. Paste this whole output to M2."; exit 1; }

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
[ "$(basename "$HERE")" = "m2-04" ] || fail "this script must sit in <repo>/deliveries/m2-04/ (found $HERE)"
git -C "$REPO" rev-parse --is-inside-work-tree >/dev/null 2>&1 || fail "$REPO is not a git repository"
[ -f "$REPO/docs/PROTOCOL.md" ] || fail "docs/PROTOCOL.md not found under $REPO: is this the crypto_bot folder?"
echo "Repo: $REPO"

# 1. SHA-256 of every delivered file against the list M2 gave
if command -v shasum >/dev/null 2>&1; then SHA="shasum -a 256"; else SHA="sha256sum"; fi
sha_of() { $SHA "$1" | awk '{print $1}'; }
echo "Checking delivered files (SHA-256):"
while read -r want name; do
  [ -n "$name" ] || continue
  [ -f "$HERE/$name" ] || fail "missing file deliveries/m2-04/$name"
  got="$(sha_of "$HERE/$name")"
  if [ "$got" != "$want" ]; then fail "$name differs from M2's list (got $got, expected $want). Re-download it and put it in deliveries/m2-04/."; fi
  echo "  OK  $got  $name"
done <<LIST
b410db4a34be95b389bf38d7cdc855a30c92238aba1e92ebb57f95f449919416  NOTES.md
64b0007fe89f7993f36be05f415c8293c35bcd50e43ada165771450c25f04909  answer-s2-accepted.md
LIST

# 2. Self-test of the delivered documents
echo "Checking the documents:"
N="$HERE/NOTES.md"; A="$HERE/answer-s2-accepted.md"
head -1 "$N" | grep -q '^# Mathematician notes$' || fail "NOTES.md: wrong first line"
grep -q '^Snapshot: 2026-10-25 (revision 4)' "$N" || fail "NOTES.md: no revision 4 Snapshot line"
for n in 1 2 3 4 5 6 7 8 9 10 11; do grep -q "^## $n\. " "$N" || fail "NOTES.md: section $n heading missing"; done
grep -q 'M2 accepted the S2 report' "$N" || fail "NOTES.md: S2 acceptance missing"
grep -q '^Tax layer (design frozen 2026-10-23' "$N" || fail "NOTES.md: tax-layer design missing"
head -1 "$A" | grep -Eq '^From: M2 \| To: D2 \| Re: .+ \| Date: 2026-10-25$' || fail "answer-s2-accepted.md: bad header line"
grep -q 'forward v21' "$A" || fail "answer-s2-accepted.md: not the v21 message"
if LC_ALL=C grep -q '[^ -~]' "$N" "$A"; then fail "a delivered file contains a non-ASCII character"; fi
echo "  OK  documents"

# 3. Are the files of delivery m2-03 on GitHub? (restore any missing one from deliveries/m2-03/)
RESTORE=()
check_carry() {  # repo path, file name in deliveries/m2-03, expected sha
  local rp="$1" nm="$2" want="$3"
  if [ -f "$REPO/$rp" ]; then
    if [ "$(sha_of "$REPO/$rp")" = "$want" ]; then echo "  OK  $rp is in the repo (identical to M2's m2-03 file)"
    else echo "  OK  $rp is in the repo (differs from M2's m2-03 copy: left as it is)"; fi
  elif [ -f "$REPO/deliveries/m2-03/$nm" ] && [ "$(sha_of "$REPO/deliveries/m2-03/$nm")" = "$want" ]; then
    echo "  RESTORE  $rp is missing: it will be restored from deliveries/m2-03/$nm"
    RESTORE=("${RESTORE[@]}" "$rp|$nm")
  else
    echo "  WARNING: $rp is missing from the repo and no matching copy is in deliveries/m2-03/. Tell M2."
  fi
}
echo "Checking the files of delivery m2-03:"
check_carry "docs/work-orders/1.7.md" "1.7.md" "985a2c444e6767c526e2d4d5407497a0c1bc2ba91bbb0f60d10f505d4e6019ae"
check_carry "docs/work-orders/1.7-task3_reference.py" "1.7-task3_reference.py" "7d17a98f53c23ede9861fe355e11612288adfe93597ffbb8748f9d139a698da5"
check_carry "docs/correspondence/answer-s2-rulings.md" "answer-s2-rulings.md" "761a2488aee6aa0ce100a8052627a53f62942107341c1744be414cd3616eb3bf"
check_carry "docs/history/m2-sandbox-calibration-2026-10-20.md" "m2-sandbox-calibration-2026-10-20.md" "d37b563604d40c6681ce4e636f9dd9307c3391bc498e7aa9caab4ad9a6f19861"
if grep -q '^| M2 | mathematician |' "$REPO/docs/PROTOCOL.md" && grep -q '^| D2 | developer |' "$REPO/docs/PROTOCOL.md"; then
  echo "  OK  docs/PROTOCOL.md has the M2 and D2 rows"
else
  echo "  WARNING: docs/PROTOCOL.md has no M2 / D2 row. Tell M2."
fi

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
mkdir -p "$REPO/context/mathematician" "$REPO/docs/correspondence"
cp "$HERE/NOTES.md" "$REPO/context/mathematician/NOTES.md"
cp "$HERE/answer-s2-accepted.md" "$REPO/docs/correspondence/answer-s2-accepted.md"
cmp -s "$HERE/NOTES.md" "$REPO/context/mathematician/NOTES.md" || fail "copy of NOTES.md does not match"
cmp -s "$HERE/answer-s2-accepted.md" "$REPO/docs/correspondence/answer-s2-accepted.md" || fail "copy of answer-s2-accepted.md does not match"
PATHS=(
  context/mathematician/NOTES.md
  docs/correspondence/answer-s2-accepted.md
  deliveries/m2-04/apply.sh
  deliveries/m2-04/NOTES.md
  deliveries/m2-04/answer-s2-accepted.md
)
for item in "${RESTORE[@]}"; do
  rp="${item%%|*}"; nm="${item##*|}"
  mkdir -p "$(dirname "$REPO/$rp")"
  cp "$REPO/deliveries/m2-03/$nm" "$REPO/$rp"
  cmp -s "$REPO/deliveries/m2-03/$nm" "$REPO/$rp" || fail "restored copy of $rp does not match"
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
git -C "$REPO" commit -q -m "M2 delivery m2-04: NOTES.md revision 4 (S2 accepted and closed), v21 message for D2" -- "${PATHS[@]}" || fail "git commit failed"
if ! git -C "$REPO" push -q origin "$BR"; then
  git -C "$REPO" reset -q --soft HEAD~1 || true
  git -C "$REPO" reset -q -- "${PATHS[@]}" || true
  fail "git push failed; the commit was undone and the files are in place. Fix the cause (for example git pull) and run this script again."
fi
DONE=1
echo
echo "PASS: delivery m2-04 committed and pushed as $(git -C "$REPO" rev-parse --short HEAD)."
echo "  context/mathematician/NOTES.md refreshed (revision 4: S2 accepted and closed, Task 3 next)"
echo "  docs/correspondence/answer-s2-accepted.md filed (the v21 message for D2)"
