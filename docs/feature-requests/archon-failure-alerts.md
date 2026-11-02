## Problem

Archon alerts the owner only when a run pauses for them. It never alerts them when a run fails. A workflow that stops on an error waits silently until someone opens the console.

Observed on Archon CLI v0.13.2 (linux-x64), per `workflow-triggers.md` ("Get notified with the console closed" and "Get notified in chat"):

- Browser Web Push sends notices for approval gates and `wait: attention` pauses, plus one completion notice for a run that was already notified.
- A chat plugin with the `attentionNotices` capability receives one message per approval gate or `wait: attention` pause, plus one follow-up when a notified run finishes.
- Neither channel fires when a run fails, is cancelled, or times out, unless the run was notified for a pause earlier. A run that fails before its first pause produces no alert of any kind.
- A workflow cannot add its own alert: there is no on-failure hook, and `trigger_rule` (`all_success`, `one_success`, `none_failed_min_one_success`, `all_done`) has no value that runs a node only when an upstream node failed.

Concrete case: a feature pipeline runs unattended for an hour through planning, review and build. A build node fails twenty minutes in. The owner, away from the console, learns of it only on their next check, and the run has done nothing since the failure.

## Why

Unattended runs are the point of triggers and long pipelines. A failure is the event an absent owner most needs to hear about, and today it is the one event Archon never reports. Owners fall back to polling the console or wrapping runs in their own scripts, which duplicates delivery logic Archon already has for pauses.

## Desired outcome

A run that ends in failure, whether or not it paused first, sends a notice through the same channels that carry attention notices: browser Web Push and every `attentionNotices` route.

## Acceptance

- [ ] A run that ends `failed` sends one notice to every opted-in browser and every `attentionNotices` route, whether or not it paused earlier.
- [ ] The notice names the workflow, the failed node and the run, and links to the run page. Error text stays in Archon, as messages and outputs do for attention notices today.
- [ ] Delivery follows the existing attention-notice rules: once per occurrence across scans and server restarts, and excluded for runs already rendered inline by a chat plugin.
- [ ] A chat plugin can tell a failure notice apart from an attention notice in the message it receives.
- [ ] `workflow-triggers.md` documents failure notices, and which run end states send one (`failed`, and whether `cancelled` and timed-out runs do).

## Constraints and related work

- Must remain true: attention notices and completion follow-ups keep their current behavior and message shape for existing plugins.
- Scope boundary: notification only. No change to how runs fail, retry or resume.
- Solution steering: Hint — a separate opt-in (a settings toggle and a per-route flag) would let owners who want only pauses keep today's behavior.

## Additional notes

A related, smaller request: a built-in generic webhook route for `attentionNotices` (POST a JSON notice to a URL from `~/.archon/config.yaml`). It would let owners reach services such as Pushover or ntfy without writing a chat plugin. It could be filed separately.

Workaround planned: a send-only chat plugin that declares `attentionNotices` forwards pauses to Pushover. Failures send no ping until this lands.
