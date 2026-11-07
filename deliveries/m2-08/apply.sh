#!/bin/bash
# Delivery m2-08 (M2, 2026-11-05). Documents only, no project code is changed.
# Re-files the two files of M2's delivery m2-06 that never reached GitHub (Work Order 1.8 and the v23 message), unchanged, plus the
# short v25 message for D2. It does NOT touch context/mathematician/NOTES.md (revision 7 from m2-07 stays). Do NOT run m2-06 itself.
# Run from anywhere:  bash deliveries/m2-08/apply.sh
set -e

DONE=0
FAILED=0
trap 'rc=$?; if [ "$DONE" != "1" ] && [ "$FAILED" != "1" ]; then echo; echo "FAIL: delivery m2-08 stopped unexpectedly (exit code $rc). Nothing was committed. Paste this whole output to M2."; fi' EXIT
fail() { FAILED=1; echo; echo "FAIL: $1"; echo "Nothing was committed. Paste this whole output to M2."; exit 1; }

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
[ "$(basename "$HERE")" = "m2-08" ] || fail "this script must sit in <repo>/deliveries/m2-08/ (found $HERE)"
git -C "$REPO" rev-parse --is-inside-work-tree >/dev/null 2>&1 || fail "$REPO is not a git repository"
[ -f "$REPO/docs/PROTOCOL.md" ] || fail "docs/PROTOCOL.md not found under $REPO: is this the crypto_bot folder?"
echo "Repo: $REPO"

# 1. SHA-256 of every delivered file against the list M2 gave
if command -v shasum >/dev/null 2>&1; then SHA="shasum -a 256"; else SHA="sha256sum"; fi
sha_of() { $SHA "$1" | awk '{print $1}'; }
echo "Checking delivered files (SHA-256):"
while read -r want name; do
  [ -n "$name" ] || continue
  [ -f "$HERE/$name" ] || fail "missing file deliveries/m2-08/$name"
  got="$(sha_of "$HERE/$name")"
  if [ "$got" != "$want" ]; then fail "$name differs from M2's list (got $got, expected $want). Re-download it and put it in deliveries/m2-08/."; fi
  echo "  OK  $got  $name"
done <<LIST
bfc6e9c09c27cc3e533ed76632c87f284decf778549d0e625c5c307547ecb815  1.8.md
cc0328d5ffd33807175563d340c519cb8344d9cd960b280f346d74f731b15412  answer-t3-accepted.md
ef8e47cd6e001205c6dda658c55e73cfd4fe8d13aecbaec2f7c1d013a8fc6072  answer-wo18-proceed.md
LIST

# 2. Self-test of the delivered documents
echo "Checking the documents:"
W="$HERE/1.8.md"; T="$HERE/answer-t3-accepted.md"; A="$HERE/answer-wo18-proceed.md"
head -1 "$W" | grep -q '^# Work Order 1.8 -- NSE mid-cap panel' || fail "1.8.md: wrong first line"
for k in '## 0. Decisions of the owner' '## 1. Universe' '## 2. Data format and store' '## 3. Validation report' '## 4. Rules files' '## 5. Order of work'; do grep -q "^$k" "$W" || fail "1.8.md: heading '$k' missing"; done
head -1 "$T" | grep -Eq '^From: M2 \| To: D2 \| Re: .+ \| Date: 2026-10-29$' || fail "answer-t3-accepted.md: bad header line"
grep -q 'forward v23' "$T" || fail "answer-t3-accepted.md: not the v23 message"
head -1 "$A" | grep -Eq '^From: M2 \| To: D2 \| Re: .+ \| Date: 2026-11-05$' || fail "answer-wo18-proceed.md: bad header line"
grep -q 'forward v25' "$A" || fail "answer-wo18-proceed.md: not the v25 message"
if LC_ALL=C grep -q '[^ -~]' "$W" "$T" "$A"; then fail "a delivered file contains a non-ASCII character"; fi
echo "  OK  documents"

# 3. Secret safety (the files are never opened; only git metadata is read): temp/secret_keys.txt and the owner's .env
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

# 4. Is the folder up to date with GitHub?
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

# 5. Copy into place, then verify the copies
mkdir -p "$REPO/docs/work-orders" "$REPO/docs/correspondence"
cp "$HERE/1.8.md" "$REPO/docs/work-orders/1.8.md"
cp "$HERE/answer-t3-accepted.md" "$REPO/docs/correspondence/answer-t3-accepted.md"
cp "$HERE/answer-wo18-proceed.md" "$REPO/docs/correspondence/answer-wo18-proceed.md"
cmp -s "$HERE/1.8.md" "$REPO/docs/work-orders/1.8.md" || fail "copy of 1.8.md does not match"
cmp -s "$HERE/answer-t3-accepted.md" "$REPO/docs/correspondence/answer-t3-accepted.md" || fail "copy of answer-t3-accepted.md does not match"
cmp -s "$HERE/answer-wo18-proceed.md" "$REPO/docs/correspondence/answer-wo18-proceed.md" || fail "copy of answer-wo18-proceed.md does not match"
echo "  OK  files copied into place"

# 6. Commit exactly these paths and push
PATHS=(
  docs/work-orders/1.8.md
  docs/correspondence/answer-t3-accepted.md
  docs/correspondence/answer-wo18-proceed.md
  deliveries/m2-08/apply.sh
  deliveries/m2-08/1.8.md
  deliveries/m2-08/answer-t3-accepted.md
  deliveries/m2-08/answer-wo18-proceed.md
)
git -C "$REPO" add -- "${PATHS[@]}" || fail "git add failed"
if git -C "$REPO" diff --cached --quiet -- "${PATHS[@]}"; then
  DONE=1
  echo
  echo "PASS: nothing to commit (GitHub already has exactly these files at $(git -C "$REPO" rev-parse --short HEAD))."
  exit 0
fi
git -C "$REPO" commit -q -m "M2 delivery m2-08: re-file Work Order 1.8 and the v23 message (m2-06 never applied), v25 message for D2" -- "${PATHS[@]}" || fail "git commit failed"
if ! git -C "$REPO" push -q origin "$BR"; then
  git -C "$REPO" reset -q --soft HEAD~1 || true
  git -C "$REPO" reset -q -- "${PATHS[@]}" || true
  fail "git push failed; the commit was undone and the files are in place. Fix the cause (for example git pull) and run this script again."
fi
git -C "$REPO" ls-files --error-unmatch docs/work-orders/1.8.md >/dev/null 2>&1 || fail "docs/work-orders/1.8.md is not tracked after the commit"
DONE=1
echo
echo "PASS: delivery m2-08 committed and pushed as $(git -C "$REPO" rev-parse --short HEAD)."
echo "  docs/work-orders/1.8.md filed (Work Order 1.8)"
echo "  docs/correspondence/answer-t3-accepted.md filed (the v23 message)"
echo "  docs/correspondence/answer-wo18-proceed.md filed (the v25 message for D2)"
