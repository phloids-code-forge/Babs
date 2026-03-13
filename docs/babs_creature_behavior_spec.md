# Flying Babs: Creature Behavior Specification

**Version:** 1.0
**Date:** 2026-02-16
**Status:** Active specification, pre-implementation
**Companion to:** `babs_and_phloid_character_bible.md`
**Implements:** `static/js/flying_babs.js` + `static/css/flying_babs.css`

---

## Design Philosophy

Babs is not a cursor pet. She is a creature that lives in the dashboard.

The difference matters. A cursor pet is an accessory attached to your pointer. A creature has internal state, makes decisions, reacts to its environment, and occasionally ignores you. You learn to read a creature by watching it. That's what makes it feel alive.

Everything in this spec flows from one principle: **internal state expressed through behavior.** No animation is directly triggered by an event. Events change mood variables. Mood variables shift behavior probabilities. Behaviors drive animations. That indirection is what prevents her from feeling scripted.

### What She Must Never Do

- Block text the user is typing
- Cover buttons the user is about to click
- Move during a mousedown event (freeze position briefly)
- Be so active that she distracts during focused work
- Be difficult to dismiss
- Make sound without explicit opt-in
- Cause frame drops or performance issues

### What She Must Always Do

- Feel like she has a life independent of the cursor
- Respond to attention in a way that rewards interaction
- Reflect the state of the dashboard through her behavior
- Be dismissable instantly and naturally
- Be worth watching during idle moments

---

## Part 1: The Mood Engine

### Internal Variables

Babs has four internal state variables. None are displayed numerically anywhere. The user reads them through her behavior.

#### Energy

| Property | Value |
|----------|-------|
| Range | 0.0 to 1.0 |
| Starting value | 0.7 |
| Decay rate | -0.01 per minute while active (flying, following, playing) |
| Recharge rate | +0.03 per minute while perched and undisturbed |
| Floor | 0.05 (never hits absolute zero, she can always be roused) |

**Behavioral expression:**

| Energy Level | Movement Speed | Wing Flutter | Exploration Range | Play Responsiveness |
|-------------|---------------|-------------|-------------------|-------------------|
| 0.8 - 1.0 (Hyper) | Fast, darting | Maximum speed | Full dashboard | Initiates play |
| 0.5 - 0.8 (Normal) | Moderate, smooth | Normal speed | Nearby panels | Responds to play |
| 0.2 - 0.5 (Tired) | Slow, deliberate | Slower, wider strokes | Stays near perch | Sluggish response |
| 0.0 - 0.2 (Sleepy) | Minimal drift | Barely moving | Perched, won't leave | Needs coaxing |

**What changes energy:**

| Event | Effect |
|-------|--------|
| Following cursor | -0.01/min |
| Autonomous exploration | -0.008/min |
| Playing (chase, spin, etc.) | -0.03/min (play is tiring) |
| Perched, undisturbed | +0.03/min |
| Perched, user active nearby | +0.02/min |
| Dashboard has been idle 10+ min | +0.04/min (deep rest) |

#### Curiosity

| Property | Value |
|----------|-------|
| Range | 0.0 to 1.0 |
| Starting value | 0.5 |
| Decay rate | -0.02 per minute (natural decay) |
| Spike on new event | +0.15 to +0.3 depending on event type |

**Behavioral expression:**

| Curiosity Level | Exploration Behavior | Panel Interest | Eye Behavior |
|----------------|---------------------|---------------|-------------|
| 0.7 - 1.0 (Very curious) | Actively seeks panels | Investigates immediately | Wide, bright, darting |
| 0.4 - 0.7 (Mildly curious) | Occasional glances | Visits panels when passing | Normal tracking |
| 0.1 - 0.4 (Bored) | Stays put, restless fidgeting | Ignores panel changes | Slow, unfocused |
| 0.0 - 0.1 (Apathetic) | Perched, disengaged | No investigation | Half-closed, dim |

**What changes curiosity:**

| Event | Effect |
|-------|--------|
| New task added | +0.2 |
| Task completed | +0.15 |
| Weather data changes | +0.1 |
| New news item | +0.1 |
| New journal entry | +0.2 |
| Spotify track changes | +0.1 |
| System status changes | +0.15 |
| Email/notification arrives | +0.25 |
| Visiting the relevant panel | -0.1 (curiosity satisfied) |
| Time with no new events | -0.02/min |

#### Contentment

| Property | Value |
|----------|-------|
| Range | 0.0 to 1.0 |
| Starting value | 0.5 |
| Decay rate | -0.005 per minute (very slow natural decay) |

**Behavioral expression:**

| Contentment Level | Proximity to User | Interaction Style | Ambient Behavior |
|------------------|------------------|------------------|-----------------|
| 0.7 - 1.0 (Happy) | Stays close voluntarily | Responsive, playful | Occasional happy spin, bright eye |
| 0.4 - 0.7 (Neutral) | Normal following distance | Standard responsiveness | Default behaviors |
| 0.2 - 0.4 (Discontent) | Drifts further away | Slower to respond | More time perched alone |
| 0.0 - 0.2 (Unhappy) | Avoids cursor | Minimal response | Dim eye, minimal movement |

**What changes contentment:**

| Event | Effect |
|-------|--------|
| Gentle hover interaction (slow approach) | +0.05 per interaction |
| Successful play session (chase, spin) | +0.1 |
| Trust approach completed (landed on cursor) | +0.15 |
| Being near active user (companionship) | +0.01/min |
| Glass bonk gets a click response | +0.08 |
| Ignored for 5+ minutes while active | -0.02/min |
| Dashboard has errors/problems | -0.01/min |
| Shooed away (fast swat gesture) | -0.03 per shoo |
| Overdue tasks visible | -0.005/min |

#### Startle

| Property | Value |
|----------|-------|
| Range | 0.0 to 1.0 |
| Starting value | 0.0 |
| Decay rate | -0.15 per second (fast decay, startle is momentary) |

**Behavioral expression:**

| Startle Level | Movement | Eye | Wings | Duration |
|--------------|---------|-----|-------|----------|
| 0.7 - 1.0 (Shocked) | Rapid dodge, erratic | Wide, bright flash | Frantic burst | 0.5 - 1s |
| 0.4 - 0.7 (Startled) | Quick flinch, reposition | Widened briefly | Fast flutter spike | 0.3 - 0.5s |
| 0.1 - 0.4 (Alert) | Slight twitch | Slightly widened | Marginally faster | 0.1 - 0.3s |
| 0.0 - 0.1 (Calm) | No startle response | Normal | Normal | N/A |

**What changes startle:**

| Event | Effect |
|-------|--------|
| Fast cursor movement toward her | +0.5 |
| Click near her (within 80px) | +0.4 |
| Sudden panel state change (error popup) | +0.3 |
| Waking from sleep state | +0.6 |
| Glass bonk impact moment | +0.3 (she startles herself) |

---

## Part 2: Core States

Babs is always in exactly one of these states. Transitions are driven by user actions and internal mood.

### State: Perched

**The default home state.** She sits in the header area near her name/logo.

**Entry conditions:**
- Dashboard loads (initial state)
- Mouse idle for 15+ seconds while she's following (she goes home)
- Shooed away by fast cursor swipe
- Energy below 0.15 (too tired, must rest)

**Visual behavior:**
- Position: fixed spot in header, near the "Babs" logo
- Body: slight bobbing animation (2px vertical, 4s cycle) simulating perch settling
- Wings: very slow flutter (0.8s animation duration, down from 0.1s active)
- Eye: lazy tracking of cursor position across the screen (eye moves within sphere, body stays still)
- Scale: 0.9x (she's settled, slightly compact)

**Eye tracking while perched:**
- Calculate angle from her perch position to current cursor position
- Offset eye div by up to 4px in that direction
- Smooth interpolation (lerp 0.03) so eye movement feels organic, not snappy
- If cursor leaves the window, eye slowly drifts to center (looking forward)

**Idle progression (if mouse doesn't move):**
- 0-30s: Eye tracks cursor, normal perch behavior
- 30-60s: Eye starts to droop (slight downward drift), wing flutter slows further
- 60-120s: Sleepy state. Eye half-closes (reduce eye height via scaleY). Minimal wing movement. Very slow breathing-scale pulse (1% size oscillation, 6s cycle)
- 120s+: Asleep. Eye nearly closed (scaleY: 0.3). Wings folded (flutter stops, wings rotate to resting angle). No movement except breathing pulse. Adorable.

**Wake-up behavior:**
- Mouse moves anywhere: eye opens first (0.2s), then wings resume (0.3s), then bobbing resumes (0.5s). Staggered wake-up feels natural.
- Mouse moves near her: faster wake, plus startle spike (+0.3). She wasn't expecting company.

### State: Following

**Companion mode.** She's traveling with the cursor.

**Entry conditions:**
- User hovers over her while she's perched (deliberate activation)
- User hovers over her while she's exploring (she joins you)

**Visual behavior:**
- Position: offset 60-80px upper-right of cursor (never directly on cursor)
- Offset adjusts based on cursor direction (always trailing, like a bird riding a thermal behind you)
- Body: smooth lerp following (existing lerpFactor: 0.05 works)
- Wings: normal flutter speed, increases with movement speed
- Eye: looks in direction of travel (offset toward where cursor is heading)
- Scale: 1.0x (normal size)

**Smart avoidance while following:**
- If cursor enters a text input area (.panel-capture input, .task-input, search bar): offset increases to 120px. She backs off from your work.
- If cursor is clicking rapidly (3+ clicks in 2 seconds): offset increases to 100px. You're busy.
- If cursor moves slowly (< 50px/s): offset decreases to 40px. She comes closer for company.
- If cursor is over .panel-chat: she positions herself near the chat panel edge, looking at the conversation. She's interested in what Babs-brain is saying.

**Hover response on interactive elements:**
- Existing behavior: she grows to 50px and glows on hoverable elements
- Enhancement: eye looks at the element you're hovering. She's curious about what you're interested in.

**Exit conditions:**
- Mouse idle for 15 seconds: she yawns (eye dims, wings slow over 2s), then drifts back to perch
- Fast swipe toward her: startle + dodge + zip to perch (dismissal)
- Energy drops below 0.15: she visibly tires (slower, drooping), then drifts to perch to recharge

### State: Exploring

**Autonomous mode.** She's living her own life.

**Entry conditions:**
- Perched for 30+ seconds AND energy > 0.3 AND curiosity > 0.3
- Higher curiosity = sooner she leaves to explore

**Behavior loop:**

```
1. Select a destination panel (weighted by curiosity triggers)
2. Fly to panel (speed based on energy)
3. Arrive at panel: hover near header, eye examines content
4. Dwell for 10-25 seconds (random)
5. Small chance of special behavior at panel (see Panel Interactions)
6. Select next destination or return to perch
7. Repeat until interrupted or energy depleted
```

**Destination selection weights:**

| Condition | Weight Modifier |
|-----------|----------------|
| Panel had recent event (new data) | 3x |
| Panel has error/warning state | 4x |
| Panel hasn't been visited recently | 1.5x |
| Panel is far from current position | 0.7x (prefers nearby) |
| Same panel just visited | 0.1x (avoids repetition) |

**Flight behavior while exploring:**
- Speed: proportional to energy (fast when hyper, gentle when tired)
- Path: not straight lines. Slight curves and organic deviation (enhance existing noise function)
- Scale: varies with vertical position. Higher on screen = 0.85x (farther away). Lower = 1.1x (closer). Creates depth illusion.
- Eye: looks toward destination during flight, looks at panel content on arrival

**Panel-specific interactions:**

| Panel | Behavior |
|-------|---------|
| Weather | If clear: basks (wings spread wider, slows down). If rain: shivers (quick vibration). If storm: eye goes amber, hurries away. |
| Spotify (playing) | Bobs gently. Not beat-matched, just a relaxed rhythmic bounce. Contentment +0.02/visit. |
| Spotify (nothing playing) | Looks at it briefly, loses interest, moves on faster. |
| Tasks (items exist) | Hovers near list, eye scans down as if reading. Longer dwell time. |
| Tasks (overdue items) | Eye shifts slightly amber. Hovers with concern. |
| News | Hovers near a headline. Eye moves as if reading left to right. |
| Journal | Lands on the header. Settles in. Longer dwell (she likes reading). |
| System Status (healthy) | Quick glance, moves on. |
| System Status (error) | Eye goes amber/red. Wings speed up. Stays near it. Urgency behavior. |
| Chat | Hovers at panel edge, eye on conversation area. If last message was recent, stays longer. |
| Gallery | Hovers near an image, eye examines it. Appreciative pause. |

**Interruption behavior:**
- Mouse moves (anywhere): she notices. Eye snaps toward cursor.
- Mouse moves near her: she pauses exploration, waits to see if you want her
- Mouse hovers over her: she transitions to Following state
- Mouse moves away from her: she resumes exploring after 2s pause

### State: Playing

**Interactive play mode.** Triggered by specific cursor patterns near her.

**Entry conditions:**
- She's in Following or Exploring state
- User performs a play trigger gesture (see Part 3)
- Energy > 0.3 (too tired to play otherwise; she dodges once then perches)

**General play behavior:**
- Eye is bright, wide
- Wings at high flutter speed
- Scale pulses slightly with excitement (1.0 to 1.05, fast cycle)
- Movement is quicker and more erratic than normal
- Energy drains faster (-0.03/min)

**Exit conditions:**
- No play interaction for 8 seconds (she calms down, returns to Following)
- Energy drops below 0.2 (she's tired, visibly slows, returns to perch)
- Play session exceeds 30 seconds (natural end, she does a victory spin and returns to Following)

### State: Sleeping

**Deep idle state.** She's fully asleep on her perch.

**Entry conditions:**
- Perched idle progression reaches 120+ seconds
- Energy below 0.1

**Visual behavior:**
- Wings: fully folded (rotate to body-parallel, no flutter animation)
- Eye: nearly closed (scaleY: 0.2 to 0.3)
- Body: very slow breathing pulse (0.97x to 1.03x scale, 6s cycle)
- Position: settled onto perch surface (1-2px lower than normal perch)
- Optional: tiny "Z" particle that drifts up occasionally (cute but might be too much, test it)

**Wake-up:**
- Any mouse movement within 200px: gradual wake (1s transition)
- Click anywhere: immediate wake with startle spike
- Dashboard event (new task, notification): eye opens, evaluates, may go back to sleep if not interesting (curiosity check)

---

## Part 3: Play Interactions

### Chase

**Trigger:** Fast cursor movement directly toward her (velocity > 300px/s, heading within 30 degrees of her position)

**Behavior:**
1. She dodges perpendicular to the approach vector
2. Pauses 40-60px away, eye locked on cursor
3. If cursor approaches again within 3 seconds: she dodges again but loops back closer (inviting pursuit)
4. After 3-4 successful dodges: she's warmed up, starts zigzagging playfully
5. Finale (after 15-20s): barrel roll over the cursor, zips to opposite side of screen. Victory.

**Rewards:**
- Contentment +0.1
- Energy -0.05 (tiring but fun)

### Peek-a-boo

**Trigger:** Cursor moves to within 20px of any screen edge and stays there for 2+ seconds

**Behavior:**
1. She notices (eye looks toward the edge)
2. Flies to that edge, hovers near where cursor is "hiding"
3. Peeks: body leans toward the edge, eye wide and searching
4. If cursor moves to opposite edge: she zips across to find you. Eye darts around on arrival.
5. When she "finds" the cursor: eye locks on, brightens. Brief happy wing-spread.

**Rewards:**
- Contentment +0.08
- Curiosity +0.1 (this is interesting!)

### The Slow Approach (Trust)

**Trigger:** Cursor moves toward her at very slow speed (< 30px/s) from at least 200px away

**Behavior:**
1. She notices the slow approach. Eye locks onto cursor. Wings slow slightly (cautious).
2. At 150px: she holds position but eye is fully focused
3. At 100px: she takes a small step toward you (10px closer). Testing.
4. At 60px: another step. Wings slow further. She's committing.
5. At 30px: if cursor is still moving slowly, she closes the gap herself. Flies to the cursor position.
6. Contact: she "lands" on the cursor. Eye half-closes contentedly. Wings fold to gentle idle. Small scale-down (she's settled).
7. Moving the cursor slowly while she's landed: she rides along. Adorable.
8. Sudden fast movement: startle, she launches off and zips away.

**Rewards:**
- Contentment +0.15 (biggest contentment reward)
- Trust interaction is the most rewarding thing you can do

### Spin Command

**Trigger:** Cursor makes a circular motion (360+ degrees within 1.5 seconds) near her (within 100px)

**Detection:** Track cursor position history. Calculate cumulative angle change. If it exceeds 360 degrees in the time window, trigger.

**Behavior:**
1. She picks up the rotation. Her body starts spinning (match the cursor's rotation direction).
2. Full barrel roll (360 degree rotation on her movement axis).
3. Brief pause, eye slightly dizzy (tiny wobble).
4. If you spin again within 3 seconds: double spin. She's showing off.
5. Third spin in sequence: she spins and does a figure-8 loop. Maximum showoff.

**Rewards:**
- Contentment +0.06
- Energy -0.02

### Glass Bonk

**Trigger:** Not user-triggered. Autonomous behavior during Exploring state.

**Probability:** 3% chance per exploration flight path, max once per 3 minutes

**Behavior:**
1. During normal exploration flight, she suddenly veers toward the "camera" (the screen)
2. Scale rapidly increases (1.0 to 1.4 over 0.3s). She's flying right at you.
3. Eye goes wide (pupil dilates) right before impact
4. Impact: brief squish animation (scaleX: 1.3, scaleY: 0.7 for 1 frame/50ms)
5. Bounce back: scale drops to 0.8, she drifts backward
6. Recovery: shakes it off (small rapid horizontal oscillation, 3 cycles)
7. Returns to normal scale and resumes exploration
8. Eye blinks once (brief close/open)

**If user clicks within 1.5s of bonk location:**
- She reacts. Eye goes surprised.
- Backs up, then comes back and bonks the same spot again (harder: scale to 1.5, bigger squish)
- Second click: she backs way up, charges, and bonks a third time with maximum drama
- Third time: she bounces off and tumbles (spinning drift away). Comedy complete.
- Contentment +0.08 per click response (you're playing with her!)

**Bonk glass effect (optional visual):**
- On impact, a subtle circular ripple emanates from the impact point
- Implemented as a brief CSS radial gradient overlay that expands and fades
- Very subtle, barely visible, just enough to sell the "glass" illusion

---

## Part 4: Eye System

### Eye Anatomy

The eye is a 12px circle inside a 40px sphere. It can travel up to 5px in any direction from center.

```
Eye offset = direction_to_target * max_offset (5px)
```

Direction is always normalized, so the eye never leaves the body regardless of target distance.

### Eye Tracking Targets (Priority Order)

1. **During play:** Tracks the cursor precisely. Locked on.
2. **While following:** Looks in the direction of travel (momentum-based). When stopped, tracks cursor.
3. **While exploring:** Looks toward destination during flight. On arrival, scans panel content (sweeps left-to-right for text panels, examines center for visual panels).
4. **While perched:** Lazily tracks cursor across screen. Slow lerp (0.02) for dreamy quality.
5. **While sleeping:** Eye drifts to center and closes.

### Eye States

| State | Color | Size (scaleY) | Glow Intensity | Pulse |
|-------|-------|---------------|---------------|-------|
| Normal | `#00BFFF` | 1.0 | 1.0 | Slow 3s pulse |
| Bright/Excited | `#00E5FF` | 1.0 | 1.5 | Faster 1.5s pulse |
| Curious | `#00BFFF` | 1.1 (slightly larger) | 1.2 | Medium 2s pulse |
| Concerned | `#FFAA00` (amber) | 0.9 | 1.0 | Irregular flicker |
| Alarm | `#FF4444` (red) | 1.2 (wide) | 2.0 | Rapid flash |
| Sleepy | `#0088AA` (dimmed blue) | 0.3 - 0.5 (half closed) | 0.4 | Very slow 6s pulse |
| Contented | `#00BFFF` | 0.8 (slightly narrowed, like a smile) | 0.8 | Gentle 4s pulse |
| Startled | `#00E5FF` | 1.3 (wide) | 2.0 | Single bright flash |

### Eye Transitions

All eye state changes interpolate over 0.2-0.4 seconds. No instant jumps except startle (which flashes bright in 0.05s then transitions to next state).

Color transitions use CSS transition on background-color and box-shadow.
Size transitions use CSS transition on transform: scaleY.

---

## Part 5: Wing System

### Wing Speed as Emotion

Current implementation: fixed `0.1s` animation duration. This becomes a CSS custom property controlled by JS.

```css
.babs-wing {
    animation-duration: var(--wing-speed, 0.1s);
}
```

| State | Wing Duration | Visual Effect |
|-------|-------------|--------------|
| Frantic (alarm, high startle) | 0.04s | Blur of motion, almost invisible |
| Excited (play, discovery) | 0.07s | Fast, energetic |
| Normal (following, exploring) | 0.10s | Default, clearly visible |
| Relaxed (perched, content) | 0.25s | Slow, lazy sweeps |
| Idle (low energy) | 0.50s | Very slow, deliberate |
| Sleepy | 0.80s | Barely moving |
| Sleeping/folded | Paused | Wings rotated to resting angle, no animation |

### Wing Amplitude

In addition to speed, wing flutter amplitude (how far they rotate) changes with state.

Implemented by adjusting keyframe values via CSS custom properties:

```css
@keyframes flutter-front-left {
    from { transform: rotate(calc(-45deg * var(--wing-amplitude, 1))) scaleX(0.9); }
    to { transform: rotate(calc(-40deg * var(--wing-amplitude, 1))) scaleX(1.1); }
}
```

| State | Amplitude | Visual Effect |
|-------|-----------|--------------|
| Excited / Playing | 1.3 | Big sweeping strokes |
| Normal | 1.0 | Default |
| Relaxed | 0.7 | Gentle, smaller strokes |
| Sleepy | 0.3 | Tiny movements |
| Folded | 0.0 | No flutter, wings at rest angle |

---

## Part 6: Scale and Depth System

### Z-Axis Illusion

Scale creates the illusion of depth. Larger = closer to the screen/viewer. Smaller = deeper in the dashboard.

| Context | Scale | Shadow Blur | Shadow Opacity | Perceived Depth |
|---------|-------|-------------|---------------|-----------------|
| Glass bonk (max approach) | 1.4 - 1.5 | 25px | 0.4 | Right at the glass |
| Close approach / play | 1.1 - 1.2 | 15px | 0.3 | Near the surface |
| Normal (following, perched) | 1.0 | 10px | 0.2 | Default depth |
| Exploring (mid-dashboard) | 0.85 - 0.95 | 6px | 0.15 | Mid-depth |
| Far exploration | 0.7 - 0.8 | 3px | 0.1 | Deep in dashboard |
| Sleeping (settled) | 0.9 | 8px | 0.15 | Settled on surface |

### Scale Transitions

All scale changes interpolate smoothly (CSS transition: transform 0.3s ease).

Exception: glass bonk squish is instant (0.05s) for comedic impact.

### Depth During Exploration

When she flies between panels, her scale varies based on a pseudo-random depth curve:

```
depth = 0.85 + (sin(time * 0.5) * 0.1) + (noise * 0.05)
scale = depth
```

This creates gentle depth oscillation during flight. She moves through 3D space, not on a flat plane.

---

## Part 7: Dashboard Event Integration

### Event Bus Architecture

The dashboard emits custom DOM events that the creature engine listens to.

```javascript
// Panels emit events like this:
document.dispatchEvent(new CustomEvent('babs:dashboard-event', {
    detail: {
        type: 'task-added',       // event type
        panel: 'panel-tasks',     // source panel class
        severity: 'info',         // info | warning | error
        data: { taskName: '...' } // optional context
    }
}));
```

### Event-to-Mood Mapping

| Event Type | Curiosity | Contentment | Energy | Startle |
|-----------|-----------|-------------|--------|---------|
| `task-added` | +0.20 | 0 | 0 | 0 |
| `task-completed` | +0.15 | +0.05 | 0 | 0 |
| `task-overdue` | +0.10 | -0.05 | 0 | 0 |
| `weather-changed` | +0.10 | 0 | 0 | 0 |
| `weather-alert` | +0.20 | -0.03 | +0.05 | +0.2 |
| `news-updated` | +0.10 | 0 | 0 | 0 |
| `spotify-playing` | +0.10 | +0.05 | +0.03 | 0 |
| `spotify-stopped` | 0 | -0.02 | 0 | 0 |
| `journal-new` | +0.20 | +0.03 | 0 | 0 |
| `email-received` | +0.25 | 0 | +0.05 | +0.1 |
| `system-error` | +0.15 | -0.05 | +0.10 | +0.3 |
| `system-recovered` | 0 | +0.08 | 0 | 0 |
| `gallery-new-image` | +0.15 | +0.03 | 0 | 0 |
| `chat-message-sent` | +0.10 | 0 | 0 | 0 |
| `chat-message-received` | +0.15 | +0.02 | 0 | 0 |

### Event-Driven Navigation

When curiosity is above 0.3 and an event fires, Babs adds the source panel to her exploration queue with high priority. She'll visit it on her next exploration cycle (or immediately if she's idle and energy permits).

---

## Part 8: Chat Mood Integration (Spark Feature)

This section activates when Babs Chat is connected to a real AI backend (local Spark models or cloud API).

### Mood Protocol

The chat backend includes a mood tag in each response:

```json
{
    "message": "I found the bug. It was a missing await.",
    "mood": {
        "state": "satisfied",
        "intensity": 0.7,
        "valence": "positive"
    }
}
```

Alternatively, the frontend infers mood from simple keyword/pattern analysis of the AI response until the backend supports explicit mood tags.

### Chat Mood States

| Mood State | Eye Color | Wing Speed | Movement | Meaning |
|-----------|-----------|-----------|---------|---------|
| `neutral` | Normal blue | Normal | Default position | Standard conversation |
| `thinking` | Slight dim, slow pulse | Slower | Drifts toward chat panel | Processing complex request |
| `excited` | Bright blue | Fast | Quick movements, closer to chat | Found something good |
| `satisfied` | Warm blue | Relaxed | Settles near chat | Problem solved, pleased |
| `frustrated` | Amber tint | Erratic | Twitchy, jittery | Stuck on something |
| `concerned` | Amber | Faster | Hovers near relevant panel | Detected a problem |
| `alarmed` | Red shift | Frantic | Zips to system status or relevant panel | Critical issue |
| `amused` | Bright blue | Quick burst | Barrel roll or spin | Something funny happened |
| `empathetic` | Soft blue | Very slow | Moves close, gentle | User seems frustrated |
| `proud` | Bright, warm blue | Spread wide | Brief celebration loop | Achievement unlocked |

### Chat Session Behavior

During an active chat conversation (messages exchanged in last 60 seconds):
- Babs gravitates toward the chat panel
- She positions herself at the panel edge, eye on the conversation
- She tracks the latest message (eye follows text appearance)
- Her mood shifts in real-time based on conversation tone
- Between user messages (user is typing), she hovers patiently with a "thinking" lean

During an intense session (rapid message exchange, 5+ messages in 2 minutes):
- She moves very close to the chat panel
- Wing speed increases with conversation intensity
- Eye stays locked on conversation
- She doesn't wander or explore (she's engaged)

When conversation goes quiet (no messages for 2+ minutes after active chat):
- She slowly relaxes
- Drifts slightly away from chat panel
- May glance at other panels briefly
- Eventually resumes normal behavior loop

---

## Part 9: Sound Design

### Opt-In System

**Sounds are OFF by default.** A small speaker icon appears near the Babs perch area in the header. Click to toggle sound on. Visual indicator when sound is active (icon change or subtle glow). Volume is very low by default. All sounds are short (under 1 second except ambient hum).

### Sound Sources

**Procedural (Web Audio API):** No audio files needed. Generated in real-time.

| Sound | Implementation | Trigger |
|-------|---------------|---------|
| Wing hum | Low-frequency oscillator (80-120Hz) + noise. Pitch proportional to wing speed. | Continuous while flying, fades when perched |
| Glass bonk | Short noise burst with quick decay, slight low-frequency thump | Glass bonk impact |
| Wake chirp | Quick ascending sine sweep (200Hz to 800Hz, 0.15s) | Waking from sleep |
| Startle | Short noise pop | Startle event |
| Happy trill | Three quick ascending tones (C-E-G, 0.05s each) | Play completion, celebration |
| Sleepy sigh | Descending filtered noise (0.5s, quiet) | Entering sleep state |
| Landing click | Single very short noise tick | Landing on perch or panel |
| Contented hum | Very quiet, low sustained tone with slight vibrato | Landed on cursor (trust interaction) |

### Volume Levels

| Sound | Max Volume (0.0 - 1.0) |
|-------|----------------------|
| Wing hum (ambient) | 0.03 (barely perceptible) |
| Glass bonk | 0.15 |
| Chirps and trills | 0.10 |
| Landing click | 0.05 |
| Startle pop | 0.12 |
| Sleepy sigh | 0.06 |
| Contented hum | 0.04 |

Everything is quiet. The sounds are meant to be felt more than heard. If someone in the room notices Babs's sounds, they're too loud.

### Sound Variation

Each sound has slight randomization on pitch and timing to prevent robotic repetition:

```
actualPitch = basePitch * (0.95 + Math.random() * 0.1)
actualDuration = baseDuration * (0.9 + Math.random() * 0.2)
```

---

## Part 10: Performance Budget

### Constraints

- Target: 60fps at all times. Babs must never cause frame drops.
- CPU budget: < 5% of one core for the entire creature system
- DOM operations: minimize. Use transform and opacity only (GPU-composited).
- No layout thrashing. Position changes via transform: translate(), not left/top.
- requestAnimationFrame for all animation. No setInterval for visual updates.
- Mood engine ticks: once per second (not every frame). Mood changes are slow.

### Optimization Strategies

**Animation:**
- All positioning via CSS transform (GPU composited)
- Wing animation via CSS @keyframes (GPU composited)
- Eye color via CSS transition (GPU composited)
- Scale via CSS transform (GPU composited)
- Only JS calculates targets; CSS handles interpolation where possible

**State management:**
- Mood engine: tick every 1000ms via setInterval (not per-frame)
- Behavior selector: evaluate every 2000ms (not per-frame)
- Event listeners: passive where possible
- Exploration destination: calculate once, animate until arrival

**Debounce/throttle:**
- Mouse movement: already per-frame via rAF (existing pattern), no additional throttle needed
- Dashboard events: debounce by 500ms (prevent spam from rapid updates)
- Play gesture detection: evaluate every 100ms, not per-frame

### Memory

- No images or audio files to load (all procedural)
- Cursor history buffer: fixed-size ring buffer, 60 entries (1 second at 60fps)
- Exploration visit history: last 10 panels visited
- Total additional memory: < 50KB

---

## Part 11: Implementation Architecture

### File Structure

```
static/
  js/
    flying_babs.js          (current file, will be refactored into:)
    babs_creature/
      creature.js            Main controller, state machine, animation loop
      mood_engine.js         Internal state variables, tick logic, decay/spike
      behavior_selector.js   State transitions, behavior probability weights
      eye_controller.js      Eye tracking, color, size, gaze direction
      wing_controller.js     Flutter speed, amplitude, CSS variable updates
      scale_controller.js    Depth system, scale transitions
      play_detector.js       Cursor pattern recognition (chase, spin, approach)
      event_listener.js      Dashboard event bus integration
      sound_engine.js        Web Audio API procedural sounds
      perch_manager.js       Perch position, landing/takeoff animations
      exploration_ai.js      Destination selection, flight paths, panel interactions
      chat_mood.js           Chat mood integration (Spark feature, can be stub)
      config.js              All tunable constants in one place
  css/
    flying_babs.css          (current file, will be extended)
```

### Module Communication

```
                    ┌─────────────────┐
                    │   creature.js   │  Main loop (rAF)
                    │   State Machine │  Owns current state
                    └────────┬────────┘
                             │ reads/writes
              ┌──────────────┼──────────────┐
              │              │              │
     ┌────────▼──────┐ ┌────▼─────┐ ┌──────▼────────┐
     │  mood_engine   │ │ behavior │ │ play_detector  │
     │  (tick 1s)     │ │ selector │ │ (cursor track) │
     │  energy        │ │ (tick 2s)│ │                │
     │  curiosity     │ └────┬─────┘ └───────┬────────┘
     │  contentment   │      │               │
     │  startle       │      │ selects       │ triggers
     └───────┬────────┘      │               │
             │ drives        │               │
    ┌────────┼────────┬──────┼───────┬───────┘
    │        │        │      │       │
┌───▼──┐ ┌──▼───┐ ┌──▼──┐ ┌▼────┐ ┌▼──────┐
│ eye  │ │ wing │ │scale│ │perch│ │explore│
│ ctrl │ │ ctrl │ │ctrl │ │ mgr │ │  ai   │
└──────┘ └──────┘ └─────┘ └─────┘ └───────┘
    │        │        │      │       │
    └────────┴────────┴──────┴───────┘
             │
      DOM updates via
      CSS transforms &
      custom properties
```

### Config File (All Tunable Constants)

```javascript
// config.js - Every magic number in one place
export const BABS_CONFIG = {

    // Mood Engine
    mood: {
        energy: { start: 0.7, decayActive: 0.01, decayPlay: 0.03, rechargePerch: 0.03, floor: 0.05 },
        curiosity: { start: 0.5, decayRate: 0.02 },
        contentment: { start: 0.5, decayRate: 0.005 },
        startle: { start: 0.0, decayRate: 0.15 },  // per second, fast
    },

    // Movement
    movement: {
        followLerp: 0.05,
        hoverLerp: 0.08,
        followOffset: { x: 60, y: -40 },     // upper-right of cursor
        busyOffset: { x: 100, y: -60 },      // backs off when clicking
        typingOffset: { x: 120, y: -50 },    // backs off when in text input
        closeOffset: { x: 40, y: -25 },      // comes close when idle
    },

    // Eye
    eye: {
        maxOffset: 5,          // px from center
        trackingLerp: 0.03,    // perched, lazy tracking
        activeLerp: 0.08,      // following, active tracking
        playLerp: 0.15,        // play, locked on
    },

    // Scale/Depth
    scale: {
        normal: 1.0,
        perched: 0.9,
        sleeping: 0.9,
        close: 1.15,
        far: 0.8,
        bonkApproach: 1.4,
        bonkSquish: { x: 1.3, y: 0.7 },
        bonkBounce: 0.8,
    },

    // Timing
    timing: {
        idleToPerch: 15000,         // ms idle before returning to perch
        perchToSleepy: 60000,       // ms perched before getting sleepy
        perchToSleep: 120000,       // ms perched before sleeping
        perchToExplore: 30000,      // ms perched before exploring (if mood allows)
        exploreDwell: { min: 10000, max: 25000 },  // ms at each panel
        playTimeout: 8000,          // ms without play input before play ends
        playMaxDuration: 30000,     // ms max play session
        moodTick: 1000,             // ms between mood engine ticks
        behaviorTick: 2000,         // ms between behavior evaluations
        bonkCooldown: 180000,       // ms minimum between bonks (3 min)
    },

    // Play Detection
    play: {
        chaseVelocity: 300,         // px/s to trigger chase
        chaseAngle: 30,             // degrees, heading tolerance
        spinAngle: 360,             // degrees cumulative for spin
        spinTimeWindow: 1500,       // ms to complete spin gesture
        approachMaxSpeed: 30,       // px/s for slow approach
        approachMinDistance: 200,    // px, must start from this far
        bonkChance: 0.03,           // 3% per flight path
        bonkClickWindow: 1500,      // ms to click after bonk
    },

    // Sound
    sound: {
        enabled: false,             // off by default
        masterVolume: 1.0,
        volumes: {
            wingHum: 0.03,
            bonk: 0.15,
            chirp: 0.10,
            click: 0.05,
            startle: 0.12,
            sigh: 0.06,
            hum: 0.04,
        }
    },

    // Perch
    perch: {
        selector: '.logo-area',    // DOM element to perch near
        offset: { x: 20, y: 0 },   // offset from perch element
    },
};
```

---

## Part 12: Implementation Priority

### Phase A: Core Refactor (Foundation)

Refactor existing `flying_babs.js` into module structure. Establish state machine with Perched and Following states. Move configuration into `config.js`. No new features yet, just clean architecture. Existing behavior preserved.

### Phase B: Perch and Idle

Implement Perch state with landing animation. Idle eye tracking (eye follows cursor while body stays still). Idle progression (awake, drowsy, sleepy, sleeping). Wake-up behavior.

### Phase C: Smart Following

Cursor offset (upper-right, not directly on cursor). Smart avoidance (backs off from text inputs, rapid clicking). Speed-sensitive proximity.

### Phase D: Eye System

Eye tracking toward targets. Eye color states. Eye size states. Smooth transitions between all states.

### Phase E: Wing Dynamics

CSS custom properties for wing speed and amplitude. Speed tied to movement velocity and mood. Amplitude tied to energy level.

### Phase F: Exploration AI

Autonomous exploration when conditions are met. Panel destination selection. Panel-specific interactions. Flight path variation.

### Phase G: Scale and Depth

Scale variations during exploration. Depth illusion during flight. Shadow adjustments.

### Phase H: Play Interactions

Cursor history tracking (ring buffer). Chase detection and behavior. Slow approach (trust) detection. Spin detection. Glass bonk (autonomous).

### Phase I: Dashboard Event Integration

Event bus setup. Panel event emissions. Mood responses to events.

### Phase J: Sound Engine

Web Audio API setup. Procedural sound generation. Sound opt-in UI. Volume management.

### Phase K: Chat Mood (Post-Spark)

Chat mood protocol. Behavior responses to conversation tone. Session intensity tracking.

---

## Appendix: Quick Reference Card

### How To Interact With Babs

| Action | How | Result |
|--------|-----|--------|
| Wake her up | Move mouse near her perch | She wakes, eye opens |
| Activate following | Hover directly over her | She lifts off and follows you |
| Dismiss her | Fast swipe toward her | She dodges and goes home |
| Let her rest | Stop moving for 15s | She drifts back to perch |
| Play chase | Move cursor fast toward her | She dodges, invites pursuit |
| Play spin | Circle cursor near her | She barrel rolls |
| Earn trust | Approach very slowly | She cautiously comes to you |
| Bonk response | Click where she bonked glass | She bonks again, comedy ensues |
| Peek-a-boo | Hide cursor at screen edge | She comes looking for you |
| Toggle sound | Click speaker icon in header | Enables subtle creature sounds |

### How To Read Her Mood

| Observation | Meaning |
|------------|---------|
| Fast wings, darting movement | High energy, excited |
| Slow wings, staying on perch | Low energy, tired |
| Bright eye, investigating panels | High curiosity, something changed |
| Dim eye, not moving much | Low curiosity, bored |
| Staying close to you | High contentment, happy |
| Keeping distance | Low contentment, neglected |
| Quick dodge, wide eye | Startled |
| Amber eye, near status bar | System issue detected |
| Bobbing near Spotify | Music is playing, she's vibing |
| Settled on perch, eyes closed | Sleeping. Leave her be (or don't). |

---

*This specification is the behavioral companion to the character bible. The bible defines who Babs is. This document defines how she acts. Together they form the complete reference for implementing the Flying Babs creature system.*
