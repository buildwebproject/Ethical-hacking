# NET_SCANNER Mobile Theme Report

Use this report to build the mobile app with the same visual identity as the web dashboard and login screen.

## Theme Identity

The interface should feel like a secure Matrix-style network terminal:

- Black/dark green base.
- Neon green text and borders.
- Monospace typography.
- CRT scanlines and subtle matrix rain.
- Thin square borders, not soft rounded cards.
- Terminal labels like `NODE_STATUS`, `SCAN_NOW`, `LOCAL_GATEWAY`.
- Glowing status lights, cable paths, and skeleton loaders.

Avoid bright white surfaces, soft pastel colors, rounded marketing cards, and normal mobile app blue buttons. The app should feel like a compact network operations console.

## Color Tokens

Use these as design tokens in the mobile app.

```text
background           #000000
loginBackground      #0c160a
surfaceDeep          #071106
surface              #001100
surfaceRaised        #141e12
surfaceVariant       #2d382a
primary              #00ff41
primaryDim           #00e639
primarySoft          #72ff70
primaryDark          #003b00
primaryOn            #000000
outline              rgba(0, 255, 65, 0.30)
outlineStrong        rgba(0, 255, 65, 0.62)
textPrimary          #00ff41
textSoft             #72ff70
textMuted            rgba(0, 255, 65, 0.60)
textFaint            rgba(0, 255, 65, 0.35)
error                #ff4d4d
loginError           #ffb4ab
errorContainer       #93000a
success              #00ff41
```

Opacity rules:

- Disabled text: 30-40% primary.
- Helper text: 50-60% primary.
- Borders: 20-45% primary.
- Active border: 70-100% primary.
- Panels: black or deep green with 85-96% opacity.

## Typography

Primary font:

```text
JetBrains Mono
```

Fallback:

```text
monospace
```

Optional display font for only large labels:

```text
Space Grotesk
```

Mobile type scale:

```text
screenTitle      20-24px, weight 700/800, uppercase
sectionTitle     11-12px, weight 700, uppercase, letter spacing 2.4-3.2px
body             13-14px, weight 400/500
dataValue        14-16px, weight 700
microLabel       8-10px, weight 700, uppercase, letter spacing 1.6-2.8px
terminalLog      11-12px, monospace
buttonLabel      11-13px, weight 700, uppercase, letter spacing 2-3px
```

Use uppercase for controls and labels. Use underscores for system-style labels, for example `CONNECTED_NETWORK_PROFILE`, `RUN_SAFE_SCAN`, `OPEN_SERVICES`.

## Layout Rules

Mobile screens should use dense operational layouts:

- Background is always black/deep green.
- Use full-width sections, not floating white cards.
- Panels have square or very small radius corners, maximum `4px`.
- Use 16px screen padding on phones.
- Use 12-16px gaps between panels.
- Use compact headers with status chips and actions.
- Keep data scannable: label above, value below.

Recommended mobile structure:

```text
Top status bar
Quick scan action
Network profile strip
Summary metrics
Wired topology preview
Port/service list
Device manifest
Activity log
Export/actions
```

## Core Components

### Panel

```text
background: #000000 or rgba(0, 17, 0, 0.90)
border: 1px solid rgba(0, 255, 65, 0.30)
shadow: 0 0 15-24px rgba(0, 255, 65, 0.15-0.25)
corner radius: 0-4px
padding: 14-18px
```

### Primary Button

```text
background: #00ff41
text: #000000
border: 1px solid #00ff41
height: 44-48px
label: uppercase, bold, tracked
pressed: scale 0.96-0.98
shadow: 0 0 15px #00ff41
```

### Secondary Button

```text
background: transparent
text: #00ff41
border: 1px solid rgba(0, 255, 65, 0.45)
pressed/active background: rgba(0, 255, 65, 0.10)
```

### Input

Inputs must never become white, including autofill.

```text
container background: rgba(7, 17, 6, 0.82)
container focus background: rgba(7, 17, 6, 0.96)
border: rgba(0, 230, 57, 0.45)
focus border: #00ff41
text: #72ff70
placeholder: rgba(0, 230, 57, 0.28)
caret: #00ff41
height: 48-56px
```

Use icons inside inputs in muted green. Add a glow on focus:

```text
0 0 16px rgba(0, 230, 57, 0.32)
inset 0 0 12px rgba(0, 230, 57, 0.08)
```

### Status Chip

```text
border: 1px solid rgba(0, 255, 65, 0.30)
background: rgba(0, 255, 65, 0.05)
text: #00ff41
label: uppercase micro text
```

### Activity Log

```text
background: #000000
rows: monospace 11-12px
prefix every row with >
normal row: rgba(0, 255, 65, 0.70)
important row: #00ff41
error row: #ff4d4d
```

## Background Effects

Use these effects carefully. They should be subtle and should not reduce readability.

### Matrix Grid

```text
linear-gradient(rgba(0,255,65,0.04) 1px, transparent 1px)
linear-gradient(90deg, rgba(0,255,65,0.04) 1px, transparent 1px)
grid size: 28-30px
```

### CRT Overlay

Use horizontal scanlines:

```text
rgba(0, 0, 0, 0.25) alternating every 4px
opacity: 0.20-0.30
```

### Matrix Rain

If implemented in mobile:

- Use `0-9`, letters, and symbols.
- Color mostly `#00ff41`, occasional `#d8ffe0`.
- Opacity 12-18%.
- Pause or reduce when battery saver or reduced motion is enabled.

## Skeleton Loaders

Skeletons must match the hacker theme:

```text
background: rgba(0, 255, 65, 0.06-0.07)
border: 1px solid rgba(0, 255, 65, 0.18-0.20)
shimmer: linear gradient transparent -> rgba(0,255,65,0.28) -> transparent
duration: 1.35s
```

Use skeletons for:

- Initial app boot.
- Login/auth request.
- Dashboard summary loading.
- Device list loading.
- Scan request.
- Project folder discovery.

Mobile skeleton layout:

```text
top title line
status line
2-4 metric blocks
topology rectangle
device row placeholders
```

## Wired Topology Style

The web dashboard now uses a realistic wired topology, not floating radar nodes. Match this in mobile.

Visual elements:

- Central `LOCAL_GATEWAY` router/switch.
- Routed copper cable paths from gateway to endpoints.
- Glowing RJ45 jack square at every endpoint.
- Device cards attached to cable ends.
- Small link LEDs.
- Animated packet movement along cable lines.

Mobile version recommendation:

- Use a horizontal or vertical mini topology.
- Keep gateway centered or at top.
- Show 3-6 devices max.
- Add `+N MORE_NODES` badge for overflow.
- Device cards show IP, hostname/vendor, and `LINK_UP`.

Cable styling:

```text
cable shadow: rgba(0, 80, 25, 0.85), thick line
cable glow: rgba(0, 255, 65, 0.22), very thick blur/glow
cable core: rgba(0, 255, 65, 0.82), 2-3px
dash animation: 1.8s linear
```

## Screen Specs

### Login Screen

Must include:

- Matrix rain background.
- Centered identity panel.
- Terminal icon.
- `IDENTITY_VERIFICATION` title.
- `OPERATOR_ID` input.
- `ACCESS_KEY` input.
- `ENTER_THE_CONSTRUCT` button.
- Small system status meters.
- `SECURE_SESSION_REQUIRED` footer.

### Dashboard Screen

Must include:

- Header with subnet/interface status.
- Primary `SCAN_NOW` action.
- Summary metrics: nodes, online devices, open services, scope.
- Connected network profile.
- Wired topology preview.
- Port scan summary.
- Activity stream.
- Inventory manifest.

### Device Detail Screen

Recommended:

- IP as primary title.
- MAC, vendor, hostname.
- Status chip `ONLINE`.
- Open services list.
- Button for `FIND_PROJECTS` when `80/HTTP` is open.
- Activity rows for latest actions.

### Project Discovery Screen

Recommended:

- Target IP/base URL.
- Root status.
- Search word progress.
- Results as terminal folder cards.
- Nested tree view using `>` depth prefixes.

## Icons

Use Material Symbols or equivalent icons:

```text
terminal
router
desktop_windows
devices
lan
vpn_key
security
folder_search
account_tree
open_in_new
warning
task_alt
download
data_object
table_view
description
login
key
alternate_email
```

Keep icons outlined, not filled, when possible.

## Motion

Use short, functional motion:

```text
fade overlays: 160-220ms
button press scale: 95-98%
skeleton shimmer: 1.35s
cable packet animation: 1.8s
terminal cursor blink: 1s step-start
scanline: slow 8s
```

Respect reduced motion:

- Disable matrix rain.
- Disable cable dash movement.
- Keep only simple fades.

## API-To-UI Mapping

Use these API endpoints for each screen:

```text
Login              POST /api/v1/auth/login
Session check      GET  /api/v1/auth/me
Dashboard boot     GET  /api/v1/summary
Network profile    GET  /api/v1/network
Device list        GET  /api/v1/devices
Fast refresh       POST /api/v1/scan with include_ports=false
Full scan          POST /api/v1/scan with include_ports=true
Common ports       GET  /api/v1/ports/common
Project search     POST /api/v1/projects/find
Project tree       POST /api/v1/projects/tree
Error logs         GET  /api/v1/errors
Export report      POST /api/v1/export
```

## Do Not Do

- Do not use white input backgrounds.
- Do not use default blue mobile controls.
- Do not use large rounded cards.
- Do not make a marketing-style landing page.
- Do not use soft beige, purple, or blue gradients.
- Do not hide the actual device data behind decorative UI.
- Do not make topology look wireless if showing wired LAN mode.

## Quick Flutter Token Example

```dart
class NetScannerTheme {
  static const background = Color(0xFF000000);
  static const loginBackground = Color(0xFF0C160A);
  static const surfaceDeep = Color(0xFF071106);
  static const surface = Color(0xFF001100);
  static const primary = Color(0xFF00FF41);
  static const primaryDim = Color(0xFF00E639);
  static const primarySoft = Color(0xFF72FF70);
  static const primaryDark = Color(0xFF003B00);
  static const error = Color(0xFFFF4D4D);

  static const monoFont = 'JetBrains Mono';
}
```

## Quick CSS Token Example

```css
:root {
  --ns-bg: #000000;
  --ns-login-bg: #0c160a;
  --ns-surface-deep: #071106;
  --ns-surface: #001100;
  --ns-primary: #00ff41;
  --ns-primary-dim: #00e639;
  --ns-primary-soft: #72ff70;
  --ns-primary-dark: #003b00;
  --ns-error: #ff4d4d;
  --ns-outline: rgba(0, 255, 65, 0.30);
}
```
