# Camera detector: "phone at the ear" (signal S10)

A coached victim usually stays on the phone with the scammer while withdrawing cash. S10 adds
10 points when the customer holds a hand at the ear for more than 3 seconds
(`params.phone_at_ear_min_sec` in `engine/rules.yaml`). The engine was always able to take this
signal; until 2026-11-25 the demo could only simulate it. Now the ATM screen can also measure it
with the laptop webcam.

## How it works

- **Model:** MediaPipe Pose Landmarker, lite version (Google, Apache 2.0), package
  `@mediapipe/tasks-vision`. It finds 33 body points on each video frame. It runs in the browser
  (WebAssembly, GPU if available, otherwise CPU).
- **Rule per frame** (`web/src/camera/phoneAtEar.js`, `handAtEar`): a hand is "at the ear" when one of
  its points (wrist, index, thumb, pinky) is closer to the ear on the same side than 0.45 of the
  shoulder width. Shoulder width makes the rule independent of the distance to the camera. Hand and shoulder
  points the model is less than 50% sure about are ignored. Ears count down to 20%: a phone at the
  ear covers it and its visibility drops, but the predicted position is still close. Without both
  shoulders there is no decision.
- **Time** (`EarTimer`): continuous time in the pose. A gap shorter than 0.6 s (missed frames) does
  not break it; separate short touches do not add up. The longest stretch since the start of the
  operation is sent as `extra.phone_at_ear_sec` with the withdrawal. "New operation" starts a new
  measurement.
- **Unit tests:** `cd web && npm test` (17 tests on synthetic landmarks: hands down, either ear, hand
  at the chin, ear covered by the hand, low confidence, no shoulders, far from the camera, timer gaps
  and resets).

## Covered camera (signal S15)

A coached victim, or the scammer on the phone, can simply cover the camera. Honest customers almost
never do. Four times a second the page shrinks the frame to 32 x 24 pixels and measures its
brightness (`web/src/camera/covered.js`): the lens counts as covered when the frame is almost one
flat colour (spread of luminance below 12 of 255: a finger, a palm, tape, paper) or almost black
(mean below 18). Covered for 2 s or more during the operation sends `extra.camera_blocked: true`.

- **Engine:** S15 "ATM camera was covered during the operation", **+20**. The weight is set by
  reasoning, not tuned: no scenario in the tune or holdout sets has this field, so the frozen metrics
  do not change and cannot say anything about S15. Alone it is 20 (allow: a scarf or a child on the
  arm can cover a camera); with a fresh loan it is 50 (ask); with a loan and a large amount, 65
  (pause instead of ask). It runs only when the rules weight S15 and the camera is enabled.
- **Not covered:** an ordinary scene, also a dim room with a person in it, keeps the spread well above
  the threshold. A blank wall with nobody in front might read as covered; at an ATM there is always a
  person. Not measured on real footage.
- **Unit tests:** black lens, finger in a lit room, paper, ordinary scene, dim room, 1 s vs 2 s.
- **Demo backup:** "Camera signal" = "Simulated: camera covered".

## Slow devices

Both timers (phone at ear, covered) allow a gap of at least 2.5 usual frame intervals, so a laptop
that processes only a few frames a second (no GPU, or a background tab) still accumulates time.

## Privacy

- Frames are processed in the browser tab only. They are not sent anywhere and not stored. The API
  receives one number per operation: the seconds.
- While the camera is on, the ATM screen shows "Camera on".
- The camera stops when the mode is switched off or the screen is left.
- Whether a bank may use such a camera at an ATM is not confirmed by a lawyer (see README, Known limits).

## Running it

1. ATM screen, Scenario panel, "Camera signal" = "Live camera (this computer)". Allow camera access.
2. Sit so that head and shoulders are in the frame. Hold the phone (or just a hand) at the ear: the
   frame turns red, the bar fills, after 3 s the number turns red.
3. Press "Withdraw". The panel shows what was sent; the officer console shows S10 among the reasons.

The browser gives the camera only on `https` or `localhost` (`http://localhost:5173` in development,
`http://localhost:8080` with Docker). Opening the demo from another computer by IP address will
not get the camera.

**Offline:** the model file is not in the repository. Without it the page loads it from Google's
storage on first use (needs internet). For a demo without internet run once, with internet:

```
cd web
npm run get-model
```

It saves `web/public/mediapipe/pose_landmarker_lite.task`; the page then uses the local copy (the panel
no longer says "loaded from Google servers"). The WASM runtime is copied from `node_modules` by
`npm run dev` / `npm run build` automatically.

## Limits (read before the pitch)

- **Accuracy is not measured.** No labelled video set exists. Do not quote a precision or recall for
  the camera. Metric 7 in the README is the effect of the simulated signal on synthetic scenarios.
- It detects the pose "hand at the ear", not a phone. False positives: scratching the head, fixing
  hair or a headscarf, holding a hand at the face for more than 3 s. Misses: a headset or earbuds, a
  phone on speaker, a phone held in front of the face (video call), a face turned away, a hat or hood
  over the ears, a person too close (shoulders out of frame).
- A real ATM camera looks from above at a different angle than a laptop webcam; the thresholds
  (0.45 shoulder width, 3 s) were chosen by reasoning, not tuned on data.
- Performance depends on the laptop: on a weak machine without GPU fewer frames per second are
  processed; the 0.6 s gap tolerance covers short drops.

## Manual check protocol (to run before the demo)

One person in front of the laptop, normal room light, 10 tries of each, about 5 s per try.
Record "S10 fired" (longest > 3 s) yes or no:

| # | Action | Expected |
|---|---|---|
| A | Phone at the left ear | yes |
| B | Phone at the right ear | yes |
| C | Hands down, looking at the screen | no |
| D | Hand at the chin, thinking | no |
| E | Scratching the head for 2 s | no |
| F | Earbuds, talking, hands down | no (known miss) |
| G | Talking on speakerphone, phone in front of the face | no (known miss) |
| H | Palm or finger over the lens for 3 s | "Camera covered", S15 sent |
| I | Sit normally in a dim room | not covered |

Report A+B hit rate and C+D+E false rate, with the number of tries. With 20 tries a result is still a
rough check, not a measurement.
