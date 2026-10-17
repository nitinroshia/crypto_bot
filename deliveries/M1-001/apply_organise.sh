#!/bin/bash
# apply_organise.sh -- delivery M1-001 (mathematician -> owner), 2026-10-17.
#
# WHAT IT DOES
#   1. Checks that your 4 downloaded files are the exact versions from the chat (SHA-256 fingerprints).
#   2. Places them in the repo:
#        PROTOCOL.md            -> docs/PROTOCOL.md
#        1.5.md                 -> docs/work-orders/1.5.md
#        stability_reference.py -> user_data/analysis/stability_reference.py
#        diag_state.sh          -> scripts/diag_state.sh
#   3. Moves the 13 loose logs from the repo root into docs/history/s1-pre-fix/ and docs/history/wo1.4/.
#   4. Commits ONLY those paths (it never runs "git add -A"), pushes to GitHub and checks the push arrived.
#   If anything is wrong it prints FAIL and does not push.
#
# RUN:  bash ~/Downloads/apply_organise.sh
#       (optional: bash apply_organise.sh /path/to/repo /path/to/folder_with_the_downloads)
# Defaults: repo = ~/apps/crypto_bot, downloads = ~/Downloads.
# Good result: the last line says PASS. Bad result: a line starting with FAIL says what to do.

set -e
SELF="$(cd "$(dirname "$0")" && pwd)/$(basename "$0")"
REPO="${1:-$HOME/apps/crypto_bot}"
DL="${2:-$HOME/Downloads}"
RAW="https://raw.githubusercontent.com/nitinroshia/crypto_bot/refs/heads/main"

H_PROTOCOL="0c85442f3ade3af192d9a02a0e4d071caf4b081c9f9e1c8ac39640a5f3503114"
H_WO15="4354052b004eb2d40b1f2891286fa2e4df58c2501a796d615fc56f735f5f54d9"
H_STABREF="4d20c7abaf28809a9c97ef952cbfac9cfee1ccfac8b4cdf0cffebb5443d9bfc2"
H_DIAG="ed1f3821708be7c7fe6e25361d30506e47ee3c454a75562794e42e282cc99b91"

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

echo "== apply_organise.sh (M1-001) =="
echo "-- checking downloads in $DL"
check_download PROTOCOL.md "$H_PROTOCOL"
check_download 1.5.md "$H_WO15"
check_download stability_reference.py "$H_STABREF"
check_download diag_state.sh "$H_DIAG"

echo "-- checking the repo $REPO"
[ -d "$REPO/.git" ] || fail "$REPO is not a git repository. Re-run as: bash apply_organise.sh /path/to/crypto_bot"
cd "$REPO"
BR="$(git rev-parse --abbrev-ref HEAD)"
[ "$BR" = "main" ] || fail "You are on branch '$BR', not 'main'. Run: git checkout main   and re-run."
git fetch origin >/dev/null 2>&1 || fail "Could not reach GitHub (git fetch failed). Check your internet connection and GitHub login."
AHEAD="$(git rev-list --count origin/main..HEAD)"
BEHIND="$(git rev-list --count HEAD..origin/main)"
[ "$AHEAD" = "0" ] || fail "Your folder has $AHEAD commit(s) that GitHub does not have, and pushing would send them too. Paste the output of diag_state.sh to the chat first."
if [ "$BEHIND" != "0" ]; then
  git merge --ff-only origin/main >/dev/null 2>&1 || fail "GitHub has $BEHIND newer commit(s) that could not be merged cleanly into your folder. Paste the output of diag_state.sh to the chat."
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
[ "$WARN" = "0" ] && echo "ok       no secrets-looking tracked files found"

echo "-- placing files"
place() {   # source_name destination_path
  mkdir -p "$(dirname "$2")"
  if [ -f "$2" ] && [ "$(sha "$2")" = "$(sha "$DL/$1")" ]; then
    echo "same     $2 (already there)"
  else
    cp "$DL/$1" "$2"
    echo "placed   $2"
  fi
}
place PROTOCOL.md docs/PROTOCOL.md
place 1.5.md docs/work-orders/1.5.md
place stability_reference.py user_data/analysis/stability_reference.py
place diag_state.sh scripts/diag_state.sh
mkdir -p deliveries/M1-001
cp "$SELF" deliveries/M1-001/apply_organise.sh

echo "-- moving loose logs out of the repo root"
movelog() {   # file destination_folder
  if [ ! -f "$1" ]; then echo "skip     $1 (not at the repo root)"; return 0; fi
  mkdir -p "$2"
  if git ls-files --error-unmatch "$1" >/dev/null 2>&1; then git mv "$1" "$2/"; else mv "$1" "$2/"; fi
  echo "moved    $1 -> $2/"
}
for f in temp_s1_btc.log temp_s1_btc_v2.log temp_s1_eth.log temp_s1_eth_v2.log; do
  movelog "$f" docs/history/s1-pre-fix
done
for f in wo1.4_breakeven.log wo1.4_breakeven_v2.log wo1.4_breakeven_v3.log wo1.4_breakeven_v4.log \
         wo1.4_derive_15m.log wo1.4_fetch_5m.log wo1.4_gaps_15m.log wo1.4_gaps_5m.log wo1.4_volatility.log; do
  movelog "$f" docs/history/wo1.4
done

echo "-- staging exactly those paths"
git add docs/PROTOCOL.md docs/work-orders/1.5.md user_data/analysis/stability_reference.py \
        scripts/diag_state.sh deliveries/M1-001/apply_organise.sh
if [ -d docs/history/s1-pre-fix ]; then git add docs/history/s1-pre-fix; fi
if [ -d docs/history/wo1.4 ]; then git add docs/history/wo1.4; fi

ALLOWED='^(docs/PROTOCOL\.md|docs/work-orders/1\.5\.md|user_data/analysis/stability_reference\.py|scripts/diag_state\.sh|deliveries/M1-001/apply_organise\.sh|docs/history/(s1-pre-fix|wo1\.4)/[A-Za-z0-9_.-]+\.log|temp_s1_[A-Za-z0-9_]+\.log|wo1\.4_[A-Za-z0-9_]+\.log)$'
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
  git commit -q -m "[owner/M1] add PROTOCOL, WO 1.5, stability reference, diag script; move 13 loose root logs into docs/history"
  echo "committed $(git rev-parse --short HEAD)"
  git push -q origin main || fail "The commit exists on your Mac, but the push to GitHub failed (see the message above; usually a login problem). Fix the login and run: git push origin main"
fi

git fetch -q origin
if [ "$(git rev-parse HEAD)" != "$(git rev-parse origin/main)" ]; then
  fail "Your folder and GitHub still differ after the push. Paste the output of diag_state.sh to the chat."
fi

echo
echo "PASS  GitHub main is now at commit $(git rev-parse --short origin/main). Files are on GitHub at:"
echo "  $RAW/docs/PROTOCOL.md"
echo "  $RAW/docs/work-orders/1.5.md"
echo "  $RAW/user_data/analysis/stability_reference.py"
echo "  $RAW/scripts/diag_state.sh"
if [ "$WARN" != "0" ]; then
  echo
  echo "BUT READ THE WARNING(S) ABOVE FIRST: a secrets-looking file may be public. Do not paste its contents anywhere."
  echo "Tell the chat only the file name; the fix (replacing the keys at the exchange, which costs nothing) comes next."
fi
