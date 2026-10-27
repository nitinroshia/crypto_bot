#!/bin/bash
# Delivery m2-05 (M2, 2026-10-27). Documents only, no project code is changed.
# Puts in place: context/mathematician/NOTES.md (revision 5) and docs/correspondence/answer-t3-rulings.md (the v22 message for D2).
# Run from anywhere:  bash deliveries/m2-05/apply.sh
set -e

DONE=0
FAILED=0
trap 'rc=$?; if [ "$DONE" != "1" ] && [ "$FAILED" != "1" ]; then echo; echo "FAIL: delivery m2-05 stopped unexpectedly (exit code $rc). Nothing was committed. Paste this whole output to M2."; fi' EXIT
fail() { FAILED=1; echo; echo "FAIL: $1"; echo "Nothing was committed. Paste this whole output to M2."; exit 1; }

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
[ "$(basename "$HERE")" = "m2-05" ] || fail "this script must sit in <repo>/deliveries/m2-05/ (found $HERE)"
git -C "$REPO" rev-parse --is-inside-work-tree >/dev/null 2>&1 || fail "$REPO is not a git repository"
[ -f "$REPO/docs/PROTOCOL.md" ] || fail "docs/PROTOCOL.md not found under $REPO: is this the crypto_bot folder?"
echo "Repo: $REPO"

# 1. SHA-256 of every delivered file against the list M2 gave
if command -v shasum >/dev/null 2>&1; then SHA="shasum -a 256"; else SHA="sha256sum"; fi
sha_of() { $SHA "$1" | awk '{print $1}'; }
echo "Checking delivered files (SHA-256):"
while read -r want name; do
  [ -n "$name" ] || continue
  [ -f "$HERE/$name" ] || fail "missing file deliveries/m2-05/$name"
  got="$(sha_of "$HERE/$name")"
  if [ "$got" != "$want" ]; then fail "$name differs from M2's list (got $got, expected $want). Re-download it and put it in deliveries/m2-05/."; fi
  echo "  OK  $got  $name"
done <<LIST
226b5f22928b41695a4f0dd88e2dafc10a111f2a8263d1cb1e5381a4abc2d335  NOTES.md
30a6b801f0b3cf8baba08d849f03706026544af41275d4b533f50c793361dfd3  answer-t3-rulings.md
LIST

# 2. Self-test of the delivered documents
echo "Checking the documents:"
N="$HERE/NOTES.md"; A="$HERE/answer-t3-rulings.md"
head -1 "$N" | grep -q '^# Mathematician notes$' || fail "NOTES.md: wrong first line"
grep -q '^Snapshot: 2026-10-27 (revision 5)' "$N" || fail "NOTES.md: no revision 5 Snapshot line"
for n in 1 2 3 4 5 6 7 8 9 10 11; do grep -q "^## $n\. " "$N" || fail "NOTES.md: section $n heading missing"; done
grep -q 'answer-t3-rulings.md' "$N" || fail "NOTES.md: does not reference the Task 3 rulings"
grep -q '^Tax layer (design frozen 2026-10-23' "$N" || fail "NOTES.md: tax-layer design missing"
head -1 "$A" | grep -Eq '^From: M2 \| To: D2 \| Re: .+ \| Date: 2026-10-27$' || fail "answer-t3-rulings.md: bad header line"
grep -q 'forward v22' "$A" || fail "answer-t3-rulings.md: not the v22 message"
if LC_ALL=C grep -q '[^ -~]' "$N" "$A"; then fail "a delivered file contains a non-ASCII character"; fi
echo "  OK  documents"

# 3. Secret-keys safety (the file is never opened; only git metadata is read)
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

# 4. Is the folder up to date with GitHub?
BR="$(git -C "$REPO" rev-parse --abbrev-ref HEAD)"
git -C "$REPO" fetch -q origin 2>/dev/null || fail "could not reach GitHub (git fetch origin failed)"
if git -C "$REPO" rev-parse --verify -q "origin/$BR" >/dev/null 2>&1; then
  BEHIND="$(git -C "$REPO" rev-list --count "HEAD..origin/$BR")"
  [ "$BEHIND" = "0" ] || fail "your folder is $BEHIND commit(s) behind GitHub. Run: git pull   then run this script again."
  if [ -n "$(git -C "$REPO" log --oneline "origin/$BR..HEAD" -- "$SK" | head -1)" ]; then
    fail "an unpushed local commit touches $SK. Do not push. Tell M2 now."
  fi
fi

# 5. Copy into place, then verify the copies
mkdir -p "$REPO/context/mathematician" "$REPO/docs/correspondence"
cp "$HERE/NOTES.md" "$REPO/context/mathematician/NOTES.md"
cp "$HERE/answer-t3-rulings.md" "$REPO/docs/correspondence/answer-t3-rulings.md"
cmp -s "$HERE/NOTES.md" "$REPO/context/mathematician/NOTES.md" || fail "copy of NOTES.md does not match"
cmp -s "$HERE/answer-t3-rulings.md" "$REPO/docs/correspondence/answer-t3-rulings.md" || fail "copy of answer-t3-rulings.md does not match"
PATHS=(
  context/mathematician/NOTES.md
  docs/correspondence/answer-t3-rulings.md
  deliveries/m2-05/apply.sh
  deliveries/m2-05/NOTES.md
  deliveries/m2-05/answer-t3-rulings.md
)
echo "  OK  files copied into place"

# 6. Commit exactly these paths and push
git -C "$REPO" add -- "${PATHS[@]}" || fail "git add failed"
if git -C "$REPO" diff --cached --quiet -- "${PATHS[@]}"; then
  DONE=1
  echo
  echo "PASS: nothing to commit (GitHub already has exactly these files at $(git -C "$REPO" rev-parse --short HEAD))."
  exit 0
fi
git -C "$REPO" commit -q -m "M2 delivery m2-05: NOTES.md revision 5 (Task 3 dry run and rulings), v22 message for D2" -- "${PATHS[@]}" || fail "git commit failed"
if ! git -C "$REPO" push -q origin "$BR"; then
  git -C "$REPO" reset -q --soft HEAD~1 || true
  git -C "$REPO" reset -q -- "${PATHS[@]}" || true
  fail "git push failed; the commit was undone and the files are in place. Fix the cause (for example git pull) and run this script again."
fi
DONE=1
echo
echo "PASS: delivery m2-05 committed and pushed as $(git -C "$REPO" rev-parse --short HEAD)."
echo "  context/mathematician/NOTES.md refreshed (revision 5: Task 3 dry run and rulings)"
echo "  docs/correspondence/answer-t3-rulings.md filed (the v22 message for D2)"
