# BO3 AO-Mod (Version 2.4a) [ZEN].gpc

This doc describes how the mods work and how to use them based on the current Zen-ported script logic.

## Active button mappings (as defined in the script)
These are the bindings the script actually uses. Make sure your in-game layout matches.

- ADS = L2
- TACTICAL = L1
- SHOOT = R2
- GRENADE = R1
- CROUCH = CIRCLE
- MELEE = R3
- JUMP = CROSS
- RELOAD = SQUARE
- SWAP_WEAPONS = TRIANGLE
- D-PAD = UP / DOWN / LEFT / RIGHT
- SPRINT = L3

## Rumble and LED rules
- Single rumble = ON (SingleNotifier, A + B motors).
- Double rumble = OFF (RumbleNotifier, A + B motors).
- Lightbar colors use `set_ps4_lbar()` (RGB).
- Blue lightbar = default/off state.

## Modifier rules
- **Modifier exclusivity: ADS/CROUCH/GRENADE toggles only work when the other two are released.**
- **Modifier timing: ADS/CROUCH/GRENADE/TACTICAL/D-PAD DOWN must be held for at least MODIFIER_TIMER (default 250ms) to count for toggles.**
- **Modifier-ready indicator: when a modifier becomes active (including D-PAD DOWN), the lightbar blinks cyan/amber, then stays amber.**

## Mod conflicts (mutual exclusivity)

- Rapid Fire ↔ Burst Fire ↔ Jitter ↔ HLX Bypass (only one at a time).
- Akimbo ↔ Jitter, HLX Bypass, ZAim, ADS Fire, Quick Scope.
- ZAim ↔ Akimbo (direct). Quick Scope and HLX Bypass are disabled when ZMode is TRUE.
- Quick Scope ↔ Rapid Fire, Anti-Recoil.
- ADS Fire ↔ Drop Shot.
- Drop Shot ↔ Side Shot.

## In-game toggles (what toggles what)
### SYSTEM
- **L3 + R3 hold 6000ms: ZMode ON/OFF**
  - ON: double rumble + red blink (4x), stays red.
  - OFF: double rumble + blue blink (4x), stays blue.
  - ZMode TRUE disables: INFNade, Long Jump, Quick Scope, Drop Shot, Side Shot, HLX Bypass, Jitter.
  - ZMode FALSE disables ZAim.
- **TouchPad hold 6000ms: INFNade master ON/OFF**
  - ON: double rumble + red blink (4x), stays red.
  - OFF: double rumble + blue blink (4x), stays blue.
  - Blocked when ZMode = TRUE.
  - Enables LEFT-hold and LEFT-tap INF grenade behaviors below.

### ZMode behavior summary
- **ZMode = TRUE (Zombies):** ON/working: Rapid Fire, Burst Fire, Anti-Recoil, ADS Fire, Hold Breath, Auto Sprint, Akimbo, Turbo Melee, ZAim. OFF/blocked: INFNade, Long Jump, Quick Scope, Drop Shot, Side Shot, HLX Bypass, Jitter.
- **ZMode = FALSE (Multiplayer):** OFF/blocked: ZAim. All other mods behave normally.

### ADS + D-PAD
- **ADS + LEFT: Rapid Fire ON/OFF**
  - ON: green LED + single rumble; forces Jitter OFF, Quick Scope OFF.
  - OFF: blue LED + double rumble.
  - Enabling Rapid Fire forces Burst Fire OFF and HLX Bypass OFF.
  > Disables: Jitter, Quick Scope, Burst Fire, HLX Bypass.
- **ADS + RIGHT: Rapid Fire preset cycle (only if RapidFireON is already ON)**
  - Presets 1-7:
    - 10/10, 15/15, 20/20, 25/25, 30/30, 40/40, 50/50 (ms).
  - Each press triggers a fast OFF<->GREEN blink + single rumble.
  - When it wraps back to preset 1, it uses a BLUE<->GREEN blink + double rumble.
  > Changes Rapid Fire preset only.
- **ADS + UP: Jitter mode cycle**
  - 0 = OFF (blue LED + double rumble)
  - 1 = Normal Jitter (green LED + single rumble)
  - Pump Jitter is disabled.
  - Enabling Jitter forces Rapid Fire OFF, Burst Fire OFF, HLX Bypass OFF, and Akimbo OFF.
  > Disables: Rapid Fire, Burst Fire, HLX Bypass, Akimbo.
- **ADS + DOWN: Drop Shot ON/OFF**
  - ON: amber LED + single rumble.
  - OFF: blue LED + double rumble.
  - Enabling Drop Shot forces Side Shot OFF.
  > Disables: Side Shot.
- **ADS + double-tap TouchPad then hold 800ms: Akimbo ON/OFF**
  - ON: white LED + single rumble.
  - OFF: blue LED + double rumble.
  - When ON, firing also presses ADS (works with Rapid Fire and Burst Fire).
  - Enabling Akimbo forces Jitter OFF, HLX Bypass OFF, ZAim OFF, ADS Fire OFF, and Quick Scope OFF.
  - Enabling Akimbo forces Drop Shot mode to 2 (ADS allowed). Disabling Akimbo resets Drop Shot mode to 1.
  > Disables: Jitter, HLX Bypass, ZAim, ADS Fire, Quick Scope; sets Drop Shot mode to 2 (resets to 1 when OFF).

### TACTICAL + D-PAD
- **L1 + RIGHT: Rapid Fire slow presets (only if RapidFireON is already ON)**
  - Preset Slow 1-7:
    - 40/80, 40/90, 40/100, 40/200, 40/300, 40/400, 40/500 (ms).
  - Each press triggers a fast AMBER<->GREEN blink + single rumble.
  - When it wraps back to Preset Slow 1, it uses a BLUE<->AMBER blink + double rumble.
  > Changes Rapid Fire slow preset only.

### CROUCH + D-PAD
- **CROUCH + UP: Quick Scope ON/OFF**
  - ON: cyan LED + single rumble; disables Rapid Fire, Anti-Recoil, and Akimbo.
  - OFF: blue LED + double rumble.
  > Disables: Rapid Fire, Anti-Recoil, Akimbo.
- **CROUCH + DOWN: Anti-Recoil ON/OFF**
  - ON: pink LED + single rumble.
  - OFF: blue LED + double rumble.
  - Works only while firing; with ONLY_WITH_SCOPE = TRUE, it applies only while ADS is held.
  > No other mods affected.
- **CROUCH + RIGHT: ADS Fire ON/OFF**
  - ON: white LED + single rumble; also forces Drop Shot OFF and Akimbo OFF.
  - OFF: blue LED + double rumble.
  > Disables: Drop Shot, Akimbo.
- **CROUCH + LEFT: Hold Breath ON/OFF**
  - ON: red lightbar + single rumble.
  - OFF: blue lightbar + double rumble.
  > No other mods affected.

### GRENADE + D-PAD
- **GRENADE + DOWN: Side Shot ON/OFF**
  - ON: orange LED + single rumble.
  - OFF: blue LED + double rumble.
  - While ON, Side Shot runs when ADS is held, or while SHOOT is held when hip firing.
  - Enabling Side Shot forces Drop Shot OFF.
  > Disables: Drop Shot.
- **GRENADE + LEFT: Burst Fire ON/OFF**
  - ON: amber -> green -> blue blink + single rumble.
  - OFF: blue LED + double rumble.
  - Enabling Burst Fire forces Rapid Fire OFF, Jitter OFF, and HLX Bypass OFF.
  > Disables: Rapid Fire, Jitter, HLX Bypass.
- **GRENADE + RIGHT: Drop Shot ADS mode (requires Drop Shot ON)**
  - Single rumble on Mode 2, double rumble on Mode 1 (wrap).
  - Amber/blue blink, returns to amber.
  - Mode 1: Drop Shot blocked when ADS.
  - Mode 2: Drop Shot allowed with ADS.
  > Changes Drop Shot ADS mode only.
- **GRENADE + hold JUMP (500ms): Long Jump ON/OFF**
  - ON: dim green LED + single rumble.
  - OFF: blue LED + double rumble.
  > No other mods affected.
- **GRENADE + double-tap L3 then hold 500ms: Auto Sprint ON/OFF**
  - ON: dim red LED + single rumble.
  - OFF: blue LED + double rumble.
  > No other mods affected.

### D-PAD DOWN + BUTTONS
- **D-PAD DOWN + single-tap RELOAD: HLX Recharge Bypass ON/OFF**
  - ON: magenta LED + single rumble.
  - OFF: blue LED + double rumble.
  - While ON, releasing SHOOT runs the HLXBypass combo. Pressing RELOAD stops it.
  - Enabling HLX Bypass forces Rapid Fire OFF, Burst Fire OFF, Jitter OFF, and Akimbo OFF.
  > Disables: Rapid Fire, Burst Fire, Jitter, Akimbo.
- **D-PAD DOWN + single-tap MELEE (R3): Turbo Melee ON/OFF**
  - ON: purple LED + single rumble.
  - OFF: blue LED + double rumble.
  - Note: single-tap is confirmed after DT_WINDOW to allow double-tap ZAim.
  > No other mods affected.
- **D-PAD DOWN + double-tap MELEE (R3) then hold 500ms: ZAim ON/OFF**
  - ON: cherry red LED + single rumble.
  - OFF: blue LED + double rumble.
  - Requires ZMode = TRUE (ZAim is disabled when ZMode = FALSE).
  - Enabling ZAim forces Akimbo OFF.
  > Disables: Akimbo.

## What each mod does
- Rapid Fire: runs while SHOOT is held.
  - If ADS Fire is OFF: RapidFire combo.
  - If ADS Fire is ON: ADSRapidFire combo (holds ADS + SHOOT).
- ADS Fire: forces ADS while SHOOT is held (if enabled).
- Drop Shot: triggers on initial SHOOT press; ADS behavior controlled by Drop Shot ADS mode.
- Drop Shot default: OFF (toggle with ADS + DOWN).
- Jitter: runs while SHOOT is held (normal only; pump is disabled). Works for most guns, including shotguns. Requires a lethal grenade equipped (e.g., Semtex) in the grenade slot.
- Anti-Recoil: adjusts RY/RX while firing; honors InversionON and ONLY_WITH_SCOPE.
- Quick Scope: pressing ADS runs a timed ADS -> shoot sequence.
- Hold Breath: holds Sprint while ADS is held (if enabled).
- Side Shot: strafes left/right while ADS is held, or while SHOOT is held when hip firing (if enabled).
- Burst Fire: fires a 4-shot burst pattern while SHOOT is held.
- HLX Recharge Bypass: runs a reload/swap sequence on SHOOT release to bypass HLX recharge.
- Turbo Melee: spams melee while MELEE is held.
- ZAim: auto-taps ADS while ADS is held (does not affect fire mods unless they require ADS).
- Akimbo: adds ADS presses whenever SHOOT is active (including Rapid Fire/Burst Fire).

## Config values (edit in script)
These values are not toggleable in-game; change them in the script if needed.

- ZMode (manual or in-game toggle):
  - Hold L3 + R3 for 6000ms to toggle.
  - TRUE disables INFNade, Long Jump, Quick Scope, Drop Shot, Side Shot, HLX Bypass, Jitter (forced OFF even if defaults are TRUE).
  - FALSE disables ZAim.
- INSTA_FIRE / INSTA_AIM / INSTA_OTHER / DROPSHOT_QUICKNESS:
  - Sensitivity boost percentages for faster button response.
- ANTI_RECOIL / ANTI_RECOIL_LEFT / ANTI_RECOIL_RIGHT:
  - Vertical/horizontal recoil correction values.
- ONLY_WITH_SCOPE (manual only):
  - TRUE applies anti-recoil only while ADS.
- InversionON (manual only):
  - TRUE if your in-game look inversion is enabled.
- QUICK_SCOPE_WAIT:
  - ADS hold time in the Quick Scope combo.
- RELOAD_WAIT / SHOOT_WAIT:
  - Timing for AutoSprint interruption (if AutoSprintON is enabled manually).
- DROP_SHOT_WAIT:
  - Crouch hold time in Drop Shot.
- LONGJUMP_HOLD_MS:
  - Hold time for GRENADE + JUMP Long Jump toggle (ms).
- MODIFIER_TIMER:
  - Hold time required before ADS/CROUCH/GRENADE/TACTICAL/D-PAD DOWN count as active modifiers (ms).
- AUTOSPRINT_HOLD_MS:
  - Hold time for GRENADE + L3 Auto Sprint toggle (ms).
- ZAIM_HOLD_MS:
  - Hold time after D-PAD DOWN + double-tap R3 for ZAim toggle (ms).
- DT_WINDOW:
  - Double-tap window used by Auto Sprint and ZAim (ms).
- AKIMBO_HOLD_MS:
  - Hold time after ADS + double-tap TouchPad for Akimbo toggle (ms).
- INFNADE_TOGGLE_HOLD_MS:
  - Hold time for TouchPad to toggle INFNade master enable (ms).
- AimSpeed / ZAimDelay:
  - ZAim ADS tap timing (ms).
- SideShotWait:
  - Side Shot left/right strafe wait time (ms).
- HoldTime / RestTime:
  - Rapid Fire hold/rest durations (ms).
- RapidFireCounter:
  - Preset selector (1-7) used by ADS + RIGHT.
- RapidFireCounterSlow:
  - Preset selector (1-7) used by L1 + RIGHT (Preset Slow 1-7).

## Optional features
These exist in the script but are optional toggles.
- INFNade master (default FALSE) enables LEFT-hold (no modifiers) to toggle unlimited grenades (hold 500ms). Single rumble = ON, double rumble = OFF.
  - ON: red blink then stays red. OFF: blue.
  - While INFNade is enabled, a short tap on LEFT (no modifiers) runs the EQUIPMENT combo once and blinks red then returns to blue (no rumble) only when the INF loop is OFF.
  - Note: Not compatible with Fast Hands perk.

### INF Grenades config (manual set only)
- INF_NADE_HOLD_MS = hold time for LEFT (no modifiers) before toggling.

## Legacy/unused
- AkimboSingleON and AkimboRapidON are legacy placeholders and not referenced.
- ExtraRapid is legacy (ADS + SPRINT Rapid Fire toggle is disabled).
- ManualAuthenticate is disabled and kept in the legacy block (Titan One only).
- ThrustJumpON, AutoDashON, QuickMelee_ON, QuickReloadON are legacy placeholders and not referenced.
- MULTIPLE_NOTIFIER is legacy/unused.
- ADS_SPEED is legacy/unused (ADS speed block is commented out).

## Lightbar color map used by this script
- Blue (1): default/off
- Red (2)
- Green (3)
- Pink (4)
- Cyan (5)
- Amber/Yellow (6)
- White (7)
- Orange (8)
- Dim Green (9)
- Dim Red (10)
- Purple (11)
- Cherry Red (12)
