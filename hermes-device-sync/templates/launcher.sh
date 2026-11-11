# Shared `hermes` launcher (Hermes's Skills). The same code is written by every skill that plugs into
# `hermes` (Hermes's Terminal, Hermes Device Sync...), so the order of the blocks does not matter.
# Each skill defines functions hermes_hook_before_* (may set HERMES_STOP=1), one hermes_hook_open_*
# (how Hermes is opened) and hermes_hook_after_*. Plain `hermes <args>` and `hermes-new` skip all of it.
hermes() {
  if [ "$#" -gt 0 ]; then command hermes "$@"; return; fi
  HERMES_STOP=
  for _f in $(declare -F | awk '{print $3}' | grep '^hermes_hook_before_' | sort); do
    "$_f"; if [ -n "$HERMES_STOP" ]; then exit; fi
  done
  _o="$(declare -F | awk '{print $3}' | grep '^hermes_hook_open_' | sort | head -n 1)"
  if [ -n "$_o" ]; then "$_o"; else command hermes; fi
  for _f in $(declare -F | awk '{print $3}' | grep '^hermes_hook_after_' | sort); do "$_f"; done
}
hermes-new() { command hermes "$@"; }
