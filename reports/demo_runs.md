# Demo rehearsal (API level, automated)

3 of 3 runs passed, 16 checks per run, frozen rules.

Covers: decisions, scores, trusted-person notification (simulated), officer actions, fail-open. Does NOT cover: the screens, the camera switch, real Telegram, a live audience.

Checks per run:
- 1 ATM 017, 500k: decision: 'ask'
- 1 score: 45
- 1 answer no -> cash: 'approve'
- 2 ATM 042, 500k, camera off: decision: 'hold'
- 2 score: 95
- 2 reasons include S11: True
- 2 trusted person notified: True
- 3 cash desk 2.5M: decision: 'pause'
- 3 score: 65
- 3 no consent -> no message: True
- 4 app transfer: decision: 'pause'
- 4 score: 75
- 5 officer release (false alarm): 'approve'
- 5 officer confirm fraud: 'decline'
- 6 control 20k: decision: 'allow'
- 7 engine down -> approve: 'approve'
