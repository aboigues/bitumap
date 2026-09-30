#!/usr/bin/env bash
# Constitution, principe IX : un agent IA ne commite ni ne pousse jamais sur main.
# Hook PreToolUse (Bash) : refuse git commit / git push quand la branche courante est main,
# ou quand la commande vise explicitement main.
set -euo pipefail

cmd=$(jq -r '.tool_input.command // ""')

deny() {
  jq -n --arg r "$1" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:"deny",permissionDecisionReason:$r}}'
  exit 0
}

# Ne concerne que git commit / git push
echo "$cmd" | grep -qE '(^|[;&|[:space:]])git[[:space:]]+(-C[[:space:]]+[^[:space:]]+[[:space:]]+)?(commit|push)([[:space:]]|$)' || exit 0

if echo "$cmd" | grep -qE 'git[[:space:]].*push.*([[:space:]:+]|refs/heads/)main([[:space:]]|$)'; then
  deny "Principe IX : push vers main interdit aux agents. Poussez une branche dédiée et ouvrez une PR."
fi

branch=$(git -C "${CLAUDE_PROJECT_DIR:-.}" branch --show-current 2>/dev/null || true)
if [ "$branch" = "main" ]; then
  deny "Principe IX : commit/push sur main interdit aux agents. Créez une branche dédiée (git switch -c <branche>)."
fi

exit 0
