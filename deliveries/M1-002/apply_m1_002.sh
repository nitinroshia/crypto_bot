#!/bin/bash
# apply_m1_002.sh -- delivery M1-002 (mathematician -> owner), 2026-10-19.
#
# WHAT IT DOES
#   1. Checks that your 3 downloaded files are the exact versions from the chat (SHA-256 fingerprints).
#   2. Places them in the repo:
#        answer-to-message-19.md -> docs/correspondence/answer-to-message-19.md
#        1.6.md                  -> docs/work-orders/1.6.md
#        M1-handoff.md           -> docs/handoffs/M1-handoff.md
#   3. Commits ONLY those paths (it never runs "git add -A"), pushes to GitHub and checks the push arrived.
#   If anything is wrong it prints FAIL and does not push.
#
# RUN:  bash ~/Downloads/apply_m1_002.sh
#       (optional: bash apply_m1_002.sh /path/to/repo /path/to/folder_with_the_downloads)
# Defaults: repo = ~/apps/crypto_bot, downloads = ~/Downloads.
# Good result: the last lines say PASS. Bad result: a line starting with FAIL says what to do.

set -e
SELF="$(cd "$(dirname "$0")" && pwd)/$(basename "$0")"
REPO="${1:-$HOME/apps/crypto_bot}"
DL="${2:-$HOME/Downloads}"
RAW="https://raw.githubusercontent.com/nitinroshia/crypto_bot/refs/heads/main"

H_ANSWER="6759b3ee1c97165a20dd5b21f3a8340346b61652a77fdb947bc238c07c1117b7"
H_WO16="70916005148eddf44cca9425abd4f933c208bb7ec2c36ea3d1f7bf40d2bff54c"
H_HANDOFF="f41b98bb4008c186752eeba5747f4c25d931c2616fedae944adadf89ecc4c012"

fail() { echo; echo "FAIL: $1"; exit 1; }
trap 'echo; echo "FAIL: unexpected error near line $LINENO of this script. Paste everything printed above, and the output of: git -C \"$REPO\" status -sb"' ERR

sha() {
  if command -v shasum >/dev/null 2>&1; then shasum -a 256 "$1" | cut -d' ' -f1; else sha256sum "$1" | cut -d' ' -f1; fi
}

check_download() {   # name expected_sha
  f="$DL/$1"
  [ -f "$f" ] || fail "$1 was not found in $DL. Download it from the chat again."
  got="$(sha "$f")"
  [ "$got" = "$2" ] || fail "$1 in $DL is not the version from the chat (its fingerprint differs). Delete the old copies of $1, download it again from the chat, and re-run."
  echo "ok       $1"
}

echo "== apply_m1_002.sh (M1-002) =="
echo "-- checking downloads in $DL"
check_download answer-to-message-19.md "$H_ANSWER"
check_download 1.6.md "$H_WO16"
check_download M1-handoff.md "$H_HANDOFF"

echo "-- checking the repo $REPO"
[ -d "$REPO/.git" ] || fail "$REPO is not a git repository. Re-run as: bash apply_m1_002.sh /path/to/crypto_bot"
cd "$REPO"
BR="$(git rev-parse --abbrev-ref HEAD)"
[ "$BR" = "main" ] || fail "You are on branch '$BR', not 'main'. Run: git checkout main   and re-run."
git fetch origin >/dev/null 2>&1 || fail "Could not reach GitHub (git fetch failed). Check your internet connection and GitHub login."
AHEAD="$(git rev-list --count origin/main..HEAD)"
BEHIND="$(git rev-list --count HEAD..origin/main)"
[ "$AHEAD" = "0" ] || fail "Your folder has $AHEAD commit(s) that GitHub does not have, and pushing would send them too. Run scripts/diag_state.sh and paste its output to the chat first."
if [ "$BEHIND" != "0" ]; then
  git merge --ff-only origin/main >/dev/null 2>&1 || fail "GitHub has $BEHIND newer commit(s) that could not be merged cleanly into your folder. Run scripts/diag_state.sh and paste its output to the chat."
  echo "updated  your folder with $BEHIND newer commit(s) from GitHub"
fi
if ! git diff --cached --quiet; then
  fail "You already have files staged (git add) that this script did not stage. Run: git reset   then re-run."
fi

echo "-- safety scan (read-only; prints file names only, never contents)"
WARN=0
T1="$(mktemp)"; T2="$(mktemp)"; T3="$(mktemp)"
trap 'rm -f "$T1" "$T2" "$T3"' EXIT
git ls-files | grep -Ei '(^|/)(\.env|[^/]*secret[^/]*|[^/]*\.pem)$' > "$T1" || true
if [ -s "$T1" ]; then
  while read -r p; do echo "WARNING  secrets-looking file is TRACKED on GitHub: $p"; done < "$T1"
  WARN=1
fi
git grep -IlE '"(key|secret|apiKey|api_key|password|token|bot_token)"[[:space:]]*:[[:space:]]*"[A-Za-z0-9:_-]{16,}"' -- . > "$T2" 2>/dev/null || true
if [ -s "$T2" ]; then
  while read -r p; do echo "WARNING  a tracked file seems to contain a key/secret/token value: $p"; done < "$T2"
  WARN=1
fi
if [ "$WARN" = "0" ]; then echo "ok       no secrets-looking tracked files found"; fi

echo "-- placing files"
place() {   # source_name destination_path
  mkdir -p "$(dirname "$2")"
  if [ -f "$2" ]; then
    if [ "$(sha "$2")" = "$(sha "$DL/$1")" ]; then
      echo "same     $2 (already there)"
      return 0
    fi
    fail "$2 already exists with DIFFERENT content, so nothing was committed or pushed (any files placed before this one stay in your folder, uncommitted). Paste this line to the chat."
  fi
  cp "$DL/$1" "$2"
  echo "placed   $2"
}
place answer-to-message-19.md docs/correspondence/answer-to-message-19.md
place 1.6.md docs/work-orders/1.6.md
place M1-handoff.md docs/handoffs/M1-handoff.md
mkdir -p deliveries/M1-002
cp "$SELF" deliveries/M1-002/apply_m1_002.sh

echo "-- staging exactly those paths"
git add docs/correspondence/answer-to-message-19.md docs/work-orders/1.6.md docs/handoffs/M1-handoff.md \
        deliveries/M1-002/apply_m1_002.sh

ALLOWED='^(docs/correspondence/answer-to-message-19\.md|docs/work-orders/1\.6\.md|docs/handoffs/M1-handoff\.md|deliveries/M1-002/apply_m1_002\.sh)$'
git diff --cached --name-only --no-renames > "$T3"
BAD=""
while read -r p; do
  echo "$p" | grep -Eq "$ALLOWED" || BAD="$BAD $p"
done < "$T3"
if [ -n "$BAD" ]; then
  git reset -q
  fail "these unexpected paths were about to be committed, so nothing was committed:$BAD"
fi

if git diff --cached --quiet; then
  echo "nothing to commit (everything is already in place)"
else
  git commit -q -m "[owner/M1] S1 outcome and rulings (answer-to-message-19), Work Order 1.6 (S2), M1 handoff"
  echo "committed $(git rev-parse --short HEAD)"
  git push -q origin main || fail "The commit exists on your Mac, but the push to GitHub failed (see the message above; usually a login problem). Fix the login and run: git push origin main"
fi

git fetch -q origin
if [ "$(git rev-parse HEAD)" != "$(git rev-parse origin/main)" ]; then
  fail "Your folder and GitHub still differ after the push. Run scripts/diag_state.sh and paste its output to the chat."
fi

echo
echo "PASS  GitHub main is now at commit $(git rev-parse --short origin/main). Files are on GitHub at:"
echo "  $RAW/docs/work-orders/1.6.md"
echo "  $RAW/docs/correspondence/answer-to-message-19.md"
echo "  $RAW/docs/handoffs/M1-handoff.md"
if [ "$WARN" != "0" ]; then
  echo
  echo "BUT READ THE WARNING(S) ABOVE FIRST: a secrets-looking file may be public. Do not paste its contents anywhere."
  echo "Tell the chat only the file name; the fix (replacing the keys at the exchange, which costs nothing) comes next."
fi
