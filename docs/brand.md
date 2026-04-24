# NEXUS — MASTER BRAND & DESIGN SYSTEM
### Agentic AI · Financial Intelligence · Living Interface
**Version 2.0 — Authoritative Reference**

---

> **Design Mandate**: Nexus is not a fintech app. It is a cybernetic organism. Every pixel
> must feel like it was extracted from a living nervous system, rendered as data, and served
> at the speed of thought. The UI must breathe, respond, and anticipate.

---

## TABLE OF CONTENTS

1. [Philosophy & Principles](#1-philosophy--principles)
2. [Color System](#2-color-system)
3. [Typography](#3-typography)
4. [Spacing & Layout Grid](#4-spacing--layout-grid)
5. [Depth, Surfaces & Materials](#5-depth-surfaces--materials)
6. [Borders, Radii & Shadows](#6-borders-radii--shadows)
7. [Iconography](#7-iconography)
8. [Motion & Animation System](#8-motion--animation-system)
9. [Component Specifications](#9-component-specifications)
10. [Data Visualization](#10-data-visualization)
11. [Interaction States](#11-interaction-states)
12. [Layout Compositions](#12-layout-compositions)
13. [Responsive Strategy](#13-responsive-strategy)
14. [Accessibility](#14-accessibility)
15. [Micro-interactions & Ambient Effects](#15-micro-interactions--ambient-effects)
16. [Voice & Tone](#16-voice--tone)
17. [Design Tokens (CSS Variables)](#17-design-tokens-css-variables)
18. [Do / Don't Reference](#18-do--dont-reference)

---

## 1. PHILOSOPHY & PRINCIPLES

### The Four Pillars

**1. Living Data** — Nothing is static. Every element that represents financial state must
feel like it is being computed right now. Use animation not for decoration, but as a signal
of real-time cognition.

**2. Progressive Revelation** — The system knows infinitely more than the user needs at any
moment. Surface the signal; bury the noise. Lead with a score, a narrative, a verdict.
Make depth opt-in.

**3. Trust Through Precision** — Every number, date, and percentage must be rendered with
absolute exactness. The aesthetic is only earned by the accuracy beneath it.

**4. Autonomous Presence** — The AI is not a chatbot in a corner. It pervades the interface.
Its color (Cyan `#00F0FF`) bleeds through at the moment of intervention. Its voice is
woven into every card narrative. It is the interface.

### Design Anti-Patterns (Strictly Forbidden)

- ❌ Pure white backgrounds
- ❌ Rounded sans-serif "friendly" type (use only Space Grotesk / Syne / JetBrains Mono)
- ❌ Generic loading spinners (use purposeful skeleton states with data-context)
- ❌ Pop-up modals for agent interventions (use in-flow disruption with scramble text)
- ❌ Flat, single-weight icon sets
- ❌ Charts without context narratives
- ❌ Red for anything other than genuine risk/anomaly signals
- ❌ Any gradient that spans more than 2 brand colors

---

## 2. COLOR SYSTEM

### 2.1 Background & Surface Hierarchy

The background stack creates a sense of depth. Elements rise from the void.

```css
--color-void:          #060606;  /* Base layer — the absolute darkness */
--color-surface-0:     #0A0A0A;  /* Page background */
--color-surface-1:     #0D0D0D;  /* Primary card / widget surface */
--color-surface-2:     #111111;  /* Elevated card, dropdown panels */
--color-surface-3:     #161616;  /* Hover state surfaces, nested panels */
--color-surface-4:     #1C1C1C;  /* Tooltip backgrounds, popovers */
--color-glass:         rgba(255, 255, 255, 0.03);  /* Glass overlay layer */
--color-glass-border:  rgba(255, 255, 255, 0.06);  /* Glass edge definition */
--color-glass-hover:   rgba(255, 255, 255, 0.05);  /* Glass hover state */
```

**Rule**: Never skip surface levels. A card on `surface-0` must be `surface-1`. A card on
`surface-1` must be `surface-2`. This creates natural visual hierarchy without heavy borders.

### 2.2 Typography Colors

```css
--color-text-primary:     #F0F0F0;  /* Core data, scores, primary labels */
--color-text-secondary:   #999999;  /* Supporting labels, card subtitles */
--color-text-tertiary:    #666666;  /* Metadata, timestamps, helper text */
--color-text-dim:         #444444;  /* Disabled, decorative, watermark */
--color-text-inverse:     #060606;  /* Text on light/accent backgrounds */
```

### 2.3 Accent & Signal Colors

These are the nervous system's firing patterns. Use with surgical precision.

```css
/* PRIMARY — Health, Positive, Active, Growth */
--color-acid:          #C8FF00;  /* Acid Green — primary accent */
--color-acid-dim:      rgba(200, 255, 0, 0.12);
--color-acid-glow:     rgba(200, 255, 0, 0.25);
--color-acid-text:     #A8D900;  /* For acid text on dark bg (reduced eye strain) */

/* SECONDARY — AI, Intelligence, Intervention, Cognition */
--color-cyan:          #00F0FF;  /* Cyan — AI presence color */
--color-cyan-dim:      rgba(0, 240, 255, 0.10);
--color-cyan-glow:     rgba(0, 240, 255, 0.20);
--color-cyan-text:     #00C8D4;  /* For cyan text on dark bg */

/* ALERT — Risk, Anomaly, Default, Danger */
--color-crimson:       #FF0040;  /* Neon Crimson — risk signal */
--color-crimson-dim:   rgba(255, 0, 64, 0.10);
--color-crimson-glow:  rgba(255, 0, 64, 0.20);
--color-crimson-text:  #E0003A;  /* For risk text */

/* NEUTRAL WARNING — Stress, Caution, Review Needed */
--color-amber:         #FFAA00;  /* Amber — caution/stress signal */
--color-amber-dim:     rgba(255, 170, 0, 0.10);
--color-amber-text:    #E09500;
```

### 2.4 Semantic Color Usage Matrix

| Context | Color Token | Example Usage |
|---|---|---|
| Positive trajectory | `--color-acid` | Credit score up, savings rate healthy |
| Safe zone indicator | `--color-acid` | Risk score green zone |
| AI actively reasoning | `--color-cyan` | LLM chain-of-thought pulse |
| AI intervention | `--color-cyan` | Proactive nudge card border |
| Conversation agent | `--color-cyan` | Chat bubble, highlight |
| Anomaly detected | `--color-crimson` | Synthetic identity flag |
| Payment default risk | `--color-crimson` | EMI stress, overdue marker |
| High debt ratio | `--color-crimson` | DTI warning indicator |
| Caution state | `--color-amber` | Mid-risk credit score |
| Review recommended | `--color-amber` | Subscription audit nudge |
| Income stream | `--color-acid` | Positive cash flow transaction |
| EMI / Liability | `--color-crimson` | Outflow transaction border |
| Subscription | `--color-cyan` | Recurring charge classification |
| Neural computation | `--color-cyan` gradient | Active AI processing animation |

### 2.5 Chart & Data Visualization Palette

For multi-series charts where brand accent colors aren't sufficient:

```css
--color-chart-1:   #C8FF00;  /* Acid — primary series */
--color-chart-2:   #00F0FF;  /* Cyan — secondary series */
--color-chart-3:   #FF0040;  /* Crimson — risk series */
--color-chart-4:   #FFAA00;  /* Amber — caution series */
--color-chart-5:   #A259FF;  /* Violet — supplementary */
--color-chart-6:   #FF6B6B;  /* Coral — soft warning series */
--color-chart-7:   #4ECDC4;  /* Teal — neutral positive */
--color-chart-8:   #45B7D1;  /* Sky — informational */
```

**Rule**: Never use more than 4 data series on a single chart. Above 4, use a grouped view
or progressive disclosure to a detail modal.

### 2.6 Gradient Definitions

```css
/* For hero backgrounds — use sparingly */
--gradient-void-radial: radial-gradient(ellipse at 50% 0%,
  rgba(200,255,0,0.04) 0%,
  rgba(0,240,255,0.02) 40%,
  transparent 70%
);

/* For AI active state — card backgrounds during agent thinking */
--gradient-ai-pulse: radial-gradient(ellipse at 50% 50%,
  rgba(0,240,255,0.06) 0%,
  transparent 70%
);

/* For score hero callouts */
--gradient-score-glow: radial-gradient(ellipse at 50% 100%,
  rgba(200,255,0,0.18) 0%,
  transparent 60%
);

/* For risk states */
--gradient-risk-glow: radial-gradient(ellipse at 50% 100%,
  rgba(255,0,64,0.15) 0%,
  transparent 60%
);

/* Text gradient — for hero score numbers only */
--gradient-text-score: linear-gradient(135deg, #FFFFFF 0%, #C8FF00 100%);
```

---

## 3. TYPOGRAPHY

### 3.1 Typeface Stack

```css
--font-display:  'Syne', 'SF Pro Display', system-ui, sans-serif;
--font-body:     'Space Grotesk', 'Inter', system-ui, sans-serif;
--font-data:     'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
```

**Loading Strategy**: Use `font-display: swap`. Preload Syne 700/800, Space Grotesk 400/600,
JetBrains Mono 400. CDN: `fonts.googleapis.com`.

### 3.2 Complete Type Scale

All clamp() values use: `clamp(min, preferred vw, max)`.

```css
/* ─── DISPLAY ─────────────────────────────────────────────────────── */
--text-display-hero:    clamp(4rem, 10vw, 8rem);   /* Credit score, net worth hero */
--text-display-large:   clamp(3rem, 6vw, 5.5rem);  /* Section hero numbers */
--text-display-medium:  clamp(2rem, 4vw, 3.5rem);  /* Card-level hero numbers */

/* ─── HEADINGS ────────────────────────────────────────────────────── */
--text-h1:              clamp(1.75rem, 3vw, 2.5rem);
--text-h2:              clamp(1.375rem, 2vw, 1.75rem);
--text-h3:              1.25rem;
--text-h4:              1.1rem;

/* ─── BODY ────────────────────────────────────────────────────────── */
--text-body-lg:         1rem;        /* Primary reading: LLM narratives */
--text-body-md:         0.9375rem;   /* Standard body */
--text-body-sm:         0.875rem;    /* Secondary body, card metadata */

/* ─── LABELS & UI ─────────────────────────────────────────────────── */
--text-label-lg:        0.875rem;    /* Form labels, strong UI labels */
--text-label-md:        0.8125rem;   /* Standard labels */
--text-label-sm:        0.75rem;     /* Overlines, tags, small badges */
--text-label-xs:        0.6875rem;   /* Fine print, chart axis labels */

/* ─── DATA & CODE ─────────────────────────────────────────────────── */
--text-data-lg:         0.9375rem;   /* Transaction amounts, key figures */
--text-data-md:         0.875rem;    /* Table data, simulation logs */
--text-data-sm:         0.8125rem;   /* Hash strings, IDs, timestamps */
--text-data-xs:         0.75rem;     /* JSON audit trails, fine metadata */
```

### 3.3 Font Weight System

```css
--weight-regular:   400;
--weight-medium:    500;
--weight-semibold:  600;
--weight-bold:      700;
--weight-extrabold: 800;
```

**Weight Assignments by Font:**
- `Syne`: Only 700 and 800. Never use below 700.
- `Space Grotesk`: 300, 400, 500, 600. Never use 700+ (use Syne for bold moments).
- `JetBrains Mono`: 400 only. Tabular data is weight-neutral.

### 3.4 Line Heights

```css
--leading-none:     1;
--leading-tight:    1.2;   /* Display numbers — scores, heroes */
--leading-snug:     1.35;  /* Headings */
--leading-normal:   1.5;   /* Standard body */
--leading-relaxed:  1.6;   /* LLM narrative output — long-form */
--leading-loose:    1.8;   /* Highly legible small text */
```

### 3.5 Letter Spacing

```css
--tracking-tighter: -0.03em;  /* Display hero numbers */
--tracking-tight:   -0.01em;  /* H1, H2 */
--tracking-normal:   0em;
--tracking-wide:     0.05em;  /* Labels, tags */
--tracking-wider:    0.1em;   /* Overlines */
--tracking-widest:   0.15em;  /* Category tags — all-caps labels */
```

### 3.6 Type Hierarchy Application

```
DISPLAY HERO (Score / Net Worth)
  Font: Syne 800
  Size: --text-display-hero
  Color: gradient --gradient-text-score
  Letter-spacing: --tracking-tighter
  Line-height: --leading-none
  Text-shadow: 0 0 40px rgba(200,255,0,0.15),
               0 0 80px rgba(200,255,0,0.05)

H1 (Section Titles)
  Font: Syne 700
  Size: --text-h1
  Color: --color-text-primary
  Letter-spacing: --tracking-tight

H2 (Card / Widget Titles)
  Font: Syne 700
  Size: --text-h3 to --text-h2
  Color: --color-text-primary

H3 (Sub-section / Twin State Headers)
  Font: Space Grotesk 600
  Size: --text-h4
  Color: --color-text-primary

OVERLINE / CATEGORY TAG
  Font: Space Grotesk 600
  Size: --text-label-sm
  Color: accent color (acid/cyan/crimson per context)
  Transform: uppercase
  Letter-spacing: --tracking-widest

BODY PRIMARY (LLM Narratives)
  Font: Space Grotesk 400
  Size: --text-body-lg
  Color: --color-text-secondary (not primary — less harshness)
  Line-height: --leading-relaxed

BODY SECONDARY (Metadata, Timestamps)
  Font: Space Grotesk 300
  Size: --text-body-sm
  Color: --color-text-tertiary

TABULAR DATA (Transactions, Logs)
  Font: JetBrains Mono 400
  Size: --text-data-md
  Color: --color-text-primary
  Tabular-nums: font-variant-numeric: tabular-nums
```

### 3.7 Gradient Text Rules

Only use gradient text for:
1. The primary credit/risk score number (Display Hero)
2. A tier name or system title in the hero section
3. Active AI status labels during live reasoning

**Implementation:**
```css
.text-gradient-score {
  background: var(--gradient-text-score);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
```

---

## 4. SPACING & LAYOUT GRID

### 4.1 Base Unit & Spacing Scale

Base unit: `4px`. All spacing is a multiple of 4.

```css
--space-0:    0px;
--space-1:    4px;
--space-2:    8px;
--space-3:    12px;
--space-4:    16px;
--space-5:    20px;
--space-6:    24px;
--space-8:    32px;
--space-10:   40px;
--space-12:   48px;
--space-16:   64px;
--space-20:   80px;
--space-24:   96px;
--space-32:   128px;
```

### 4.2 Layout Grid

**Desktop (1440px baseline)**
```
Max container width:  1440px
Columns:              12
Gutter:               24px
Margin:               48px (left/right)
Column width:         (1440 - 96 - 264) / 12 = ~90px
```

**Tablet (768px–1199px)**
```
Columns: 8
Gutter:  20px
Margin:  32px
```

**Mobile (< 768px)**
```
Columns: 4
Gutter:  16px
Margin:  20px
```

### 4.3 Dashboard Layout System

Nexus uses a **nested grid composition** model:

```
┌─────────────────────────────────────────────────────┐
│ SIDEBAR (280px fixed) │ MAIN CONTENT AREA            │
│                       │                              │
│ Navigation            │ ┌──────────────────────────┐ │
│ AI Status             │ │ HERO ZONE (full-width)   │ │
│ Quick Actions         │ │ Score + Digital Twin HUD │ │
│                       │ └──────────────────────────┘ │
│                       │ ┌──────┐ ┌──────┐ ┌──────┐  │
│                       │ │ 4col │ │ 4col │ │ 4col │  │
│                       │ └──────┘ └──────┘ └──────┘  │
│                       │ ┌─────────────┐ ┌─────────┐  │
│                       │ │ 8col chart  │ │ 4col   │  │
│                       │ └─────────────┘ └─────────┘  │
└─────────────────────────────────────────────────────┘
```

### 4.4 Component Sizing Reference

```css
--height-input:       44px;
--height-input-sm:    36px;
--height-input-lg:    52px;
--height-button:      44px;
--height-button-sm:   32px;
--height-button-lg:   52px;
--height-navbar:      64px;
--height-sidebar:     100vh;
--width-sidebar:      280px;
--width-sidebar-collapsed: 64px;
--width-modal-sm:     480px;
--width-modal-md:     640px;
--width-modal-lg:     860px;
--width-panel-right:  400px;  /* AI reasoning panel, timeline */
```

---

## 5. DEPTH, SURFACES & MATERIALS

### 5.1 The Void Stack (Z-Axis Layers)

```
Layer 0:  #060606  — Absolute void (page base)
Layer 1:  #0D0D0D  — Primary content surfaces
Layer 2:  Glass    — Overlapping Digital Twin visualizations
Layer 3:  #161616  — Elevated dropdowns, floating panels
Layer 4:  #1C1C1C  — Tooltips, context menus
Layer 5:  Modals   — Full overlay (bg: rgba(6,6,6,0.92))
```

### 5.2 The Grain (Mandatory Noise Layer)

Apply this globally as a fixed overlay. It grounds neon elements and gives tactility.

```css
.grain-overlay {
  position: fixed;
  inset: 0;
  width: 100vw;
  height: 100vh;
  pointer-events: none;
  z-index: 9999;
  opacity: 0.03;
  background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 512 512' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.75' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E");
  background-repeat: repeat;
  background-size: 200px 200px;
}
```

### 5.3 The Grid (Dot Matrix Background)

Apply to the primary page background:

```css
body::before {
  content: '';
  position: fixed;
  inset: 0;
  background-image: radial-gradient(
    circle,
    rgba(255, 255, 255, 0.015) 1px,
    transparent 1px
  );
  background-size: 24px 24px;
  pointer-events: none;
  z-index: 0;
}
```

### 5.4 Glassmorphism Surfaces

For Digital Twin cards, AI overlay panels, and layered data modules:

```css
.glass-card {
  background: var(--color-glass);
  backdrop-filter: blur(12px) saturate(1.2);
  -webkit-backdrop-filter: blur(12px) saturate(1.2);
  border: 1px solid var(--color-glass-border);
}

.glass-card--acid {
  border-color: rgba(200, 255, 0, 0.12);
  box-shadow: inset 0 0 0 1px rgba(200, 255, 0, 0.05);
}

.glass-card--cyan {
  border-color: rgba(0, 240, 255, 0.12);
  box-shadow: inset 0 0 0 1px rgba(0, 240, 255, 0.05);
}

.glass-card--crimson {
  border-color: rgba(255, 0, 64, 0.15);
  box-shadow: inset 0 0 0 1px rgba(255, 0, 64, 0.07);
}
```

### 5.5 Interactive Flashlight Glow (Hover Effect)

Cards should respond to mouse position with a directional glow:

```css
.interactive-card {
  --mx: 50%;
  --my: 50%;
  background: radial-gradient(
    circle at var(--mx) var(--my),
    rgba(200, 255, 0, 0.04),
    transparent 60%
  ), var(--color-surface-1);
  transition: background 0.15s;
}
```

```js
card.addEventListener('mousemove', (e) => {
  const rect = e.currentTarget.getBoundingClientRect();
  e.currentTarget.style.setProperty('--mx', `${e.clientX - rect.left}px`);
  e.currentTarget.style.setProperty('--my', `${e.clientY - rect.top}px`);
});
```

**Flashlight accent color rules:**
- Default cards: Acid Green
- AI card states: Cyan
- Risk cards: Crimson (at 50% opacity — never full crimson glow on hover)

---

## 6. BORDERS, RADII & SHADOWS

### 6.1 Border Radius Scale

```css
--radius-sm:    4px;    /* Badges, chips, small tags */
--radius-md:    8px;    /* Inputs, buttons, small cards */
--radius-lg:    12px;   /* Standard cards, panels */
--radius-xl:    16px;   /* Large cards, modals */
--radius-2xl:   24px;   /* Hero sections, major containers */
--radius-full:  9999px; /* Pills, status indicators */
```

### 6.2 Border System

```css
--border-subtle:    1px solid rgba(255, 255, 255, 0.04);
--border-default:   1px solid rgba(255, 255, 255, 0.08);
--border-strong:    1px solid rgba(255, 255, 255, 0.14);
--border-focus:     1px solid rgba(200, 255, 0, 0.5);
--border-ai:        1px solid rgba(0, 240, 255, 0.25);
--border-risk:      1px solid rgba(255, 0, 64, 0.25);
--border-caution:   1px solid rgba(255, 170, 0, 0.25);
```

**Left-edge semantic borders** (for transaction/event cards):
```css
--border-left-income:    3px solid var(--color-acid);
--border-left-outflow:   3px solid var(--color-crimson);
--border-left-ai:        3px solid var(--color-cyan);
--border-left-neutral:   3px solid rgba(255,255,255,0.1);
```

### 6.3 Shadow & Glow System

```css
/* Elevation shadows (for cards rising from the void) */
--shadow-sm:   0 1px 3px rgba(0,0,0,0.4), 0 1px 2px rgba(0,0,0,0.3);
--shadow-md:   0 4px 16px rgba(0,0,0,0.5), 0 2px 6px rgba(0,0,0,0.3);
--shadow-lg:   0 16px 48px rgba(0,0,0,0.6), 0 4px 12px rgba(0,0,0,0.4);
--shadow-xl:   0 32px 80px rgba(0,0,0,0.7);

/* Neon glows (for accented elements — use sparingly) */
--glow-acid-sm:    0 0 12px rgba(200,255,0,0.25);
--glow-acid-md:    0 0 24px rgba(200,255,0,0.2), 0 0 48px rgba(200,255,0,0.08);
--glow-acid-lg:    0 0 40px rgba(200,255,0,0.3), 0 0 80px rgba(200,255,0,0.1);
--glow-cyan-sm:    0 0 12px rgba(0,240,255,0.2);
--glow-cyan-md:    0 0 24px rgba(0,240,255,0.18), 0 0 48px rgba(0,240,255,0.06);
--glow-crimson-sm: 0 0 12px rgba(255,0,64,0.2);
--glow-crimson-md: 0 0 24px rgba(255,0,64,0.15), 0 0 48px rgba(255,0,64,0.05);
```

**Score number glow rule**: Only the primary credit score Display Hero should use `--glow-acid-lg`. All other acid glows max at `--glow-acid-md`. Crimson glows are always `--glow-crimson-sm` — large red glows cause anxiety and should be reserved for severe anomaly states only.

---

## 7. ICONOGRAPHY

### 7.1 Primary Library

**Solar Icons** (primary) or **Phosphor Icons** (fallback).

- Stroke width: `1.5px` for all linear icons
- Size default: `20px` (UI), `16px` (inline with text), `24px` (featured/section)
- Never use filled black/white. All icons must be tinted.

### 7.2 Icon Color Tinting

```css
/* Default icon style */
.icon {
  color: var(--color-text-tertiary);
  opacity: 0.75;
  transition: color 0.2s, opacity 0.2s;
}

/* Contextual tints */
.icon--acid    { color: var(--color-acid);    opacity: 0.8; }
.icon--cyan    { color: var(--color-cyan);    opacity: 0.8; }
.icon--crimson { color: var(--color-crimson); opacity: 0.8; }
.icon--amber   { color: var(--color-amber);   opacity: 0.8; }
```

### 7.3 Conceptual Icon Mapping

These metaphors must be used consistently throughout the product:

| Concept | Recommended Icon | Tint |
|---|---|---|
| Digital Twin / AI Clone | Two overlapping circles (DNA-like) | Cyan |
| 32-Dimension Fingerprint | DNA spiral | Acid |
| Semantic Classifier | Intersecting nodes | Cyan |
| Credit Score | Shield with pulse | Acid or Crimson |
| Monte Carlo Simulation | Branching probability tree | Acid |
| Kafka / Data Stream | Flowing arrows | Cyan |
| Anomaly Detection | Warning + lightning | Crimson |
| Proactive Nudge | Bell with AI mark | Cyan |
| Time Travel / Versioning | Clock with backward arrow | Neutral |
| EMI / Debt | Chain links | Crimson |
| Income | Arrow up + spark | Acid |
| Subscription | Refresh cycle | Cyan |
| LLM Reasoning | Branching paths / tree | Cyan |
| Risk Score | Gauge / meter | Crimson or Amber |
| Savings Twin | Plant / growth node | Acid |

---

## 8. MOTION & ANIMATION SYSTEM

### 8.1 Easing Curves

```css
--ease-out-expo:    cubic-bezier(0.16, 1, 0.3, 1);     /* Primary: entrances */
--ease-out-quart:   cubic-bezier(0.25, 1, 0.5, 1);     /* Secondary: transitions */
--ease-in-out-sine: cubic-bezier(0.37, 0, 0.63, 1);    /* Loops, ambient pulses */
--ease-spring:      cubic-bezier(0.34, 1.56, 0.64, 1); /* Interactive feedback */
--ease-linear:      linear;                             /* Continuous streams, countups */
```

### 8.2 Duration Scale

```css
--duration-instant:  50ms;   /* Ripple, immediate feedback */
--duration-fast:     100ms;  /* Icon state changes */
--duration-normal:   200ms;  /* Standard transitions (hover, focus) */
--duration-medium:   350ms;  /* Card entrances, panel slides */
--duration-slow:     500ms;  /* Page transitions, hero entrances */
--duration-crawl:    800ms;  /* Score number countups start */
--duration-ambient:  3000ms; /* Idle pulse animations */
```

### 8.3 Animation Catalog

**Score Count-Up (Hero)**
```css
@keyframes count-up {
  from { opacity: 0; transform: translateY(12px); }
  to   { opacity: 1; transform: translateY(0); }
}
/* Use with JS counter from 0 to target value over 1200ms, ease-out-expo */
```

**AI Pulse (Active Reasoning)**
```css
@keyframes ai-pulse {
  0%, 100% { opacity: 0.4; box-shadow: 0 0 0px var(--color-cyan-glow); }
  50%       { opacity: 1.0; box-shadow: 0 0 24px var(--color-cyan-glow); }
}
/* Apply to: AI card border, reasoning indicator dot */
/* Duration: 2s, ease-in-out-sine, infinite */
```

**Data Stream Flow**
```css
@keyframes stream-flow {
  from { stroke-dashoffset: 100; }
  to   { stroke-dashoffset: 0; }
}
/* Apply to: SVG connection lines in Digital Twin visualization */
/* Duration: 3s, linear, infinite */
```

**Scramble Text (Agent Interruption)**
```js
// Used when Proactive Intervention Agent fires
function scrambleText(el, finalText, duration = 800) {
  const chars = '!@#$%^&*ABCDEFabcdef0123456789';
  let frame = 0;
  const totalFrames = Math.floor(duration / 16);
  const interval = setInterval(() => {
    el.textContent = finalText
      .split('')
      .map((char, i) => {
        if (i < (frame / totalFrames) * finalText.length) return char;
        return chars[Math.floor(Math.random() * chars.length)];
      })
      .join('');
    if (++frame >= totalFrames) {
      clearInterval(interval);
      el.textContent = finalText;
    }
  }, 16);
}
```

**Skeleton Pulse**
```css
@keyframes skeleton-pulse {
  0%, 100% { opacity: 0.04; }
  50%       { opacity: 0.08; }
}
.skeleton {
  background: rgba(255,255,255,0.06);
  border-radius: var(--radius-md);
  animation: skeleton-pulse 1.8s var(--ease-in-out-sine) infinite;
}
```

**Card Entrance (Stagger)**
```css
.card {
  opacity: 0;
  transform: translateY(16px);
  animation: card-enter var(--duration-medium) var(--ease-out-expo) forwards;
}
@keyframes card-enter {
  to { opacity: 1; transform: translateY(0); }
}
/* Stagger: each card delays by 60ms × index */
```

**Timeline Scrub Transition**
When the temporal slider is moved, all data cards should cross-dissolve:
```css
.data-panel {
  transition:
    opacity 150ms var(--ease-out-quart),
    filter 150ms var(--ease-out-quart);
}
.data-panel.scrubbing {
  opacity: 0.6;
  filter: blur(0.5px);
}
```

### 8.4 Reduced Motion

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
  /* Keep opacity transitions for state changes (not decorative) */
  .state-transition {
    transition: opacity var(--duration-normal) !important;
  }
}
```

---

## 9. COMPONENT SPECIFICATIONS

### 9.1 Buttons

```
PRIMARY BUTTON (Acid)
  Background: var(--color-acid)
  Text: var(--color-text-inverse)  [#060606]
  Font: Space Grotesk 600, 0.875rem, tracking-wide
  Padding: 0 24px
  Height: var(--height-button)
  Radius: var(--radius-md)
  Box-shadow: var(--glow-acid-sm)
  Hover: background brightness +10%, glow strengthens to --glow-acid-md
  Active: scale(0.97), brightness -5%
  Disabled: opacity 0.3, no glow, cursor not-allowed

SECONDARY BUTTON (Ghost)
  Background: transparent
  Border: var(--border-default)
  Text: var(--color-text-primary)
  Hover: background var(--color-surface-3), border var(--border-strong)

GHOST AI BUTTON (Cyan)
  Background: var(--color-cyan-dim)
  Border: 1px solid rgba(0,240,255,0.2)
  Text: var(--color-cyan-text)
  Hover: background rgba(0,240,255,0.15), box-shadow var(--glow-cyan-sm)

DESTRUCTIVE BUTTON
  Background: var(--color-crimson-dim)
  Border: 1px solid rgba(255,0,64,0.25)
  Text: var(--color-crimson-text)
  Hover: background rgba(255,0,64,0.15)

ICON BUTTON
  Size: 36px × 36px
  Radius: var(--radius-md)
  Background: transparent on idle, var(--color-surface-3) on hover
  Icon: 18px, --color-text-tertiary on idle, --color-text-primary on hover
```

### 9.2 Input Fields

```
DEFAULT INPUT
  Height: var(--height-input)
  Background: var(--color-surface-2)
  Border: var(--border-default)
  Radius: var(--radius-md)
  Padding: 0 var(--space-4)
  Font: Space Grotesk 400, --text-body-md
  Color: var(--color-text-primary)
  Placeholder: var(--color-text-dim)

  Focus:
    Border: var(--border-focus)
    Box-shadow: 0 0 0 3px rgba(200,255,0,0.08)
    Outline: none

  Error:
    Border: var(--border-risk)
    Box-shadow: 0 0 0 3px rgba(255,0,64,0.08)

  Success:
    Border: 1px solid rgba(200,255,0,0.3)

  Disabled:
    Opacity: 0.4
    Cursor: not-allowed
```

### 9.3 Cards

**Standard Data Card**
```
Background: var(--color-surface-1)
Border: var(--border-subtle)
Radius: var(--radius-lg)
Padding: var(--space-6)
Box-shadow: var(--shadow-md)

Structure:
  ┌─────────────────────────────────┐
  │ [OVERLINE TAG]      [icon]      │ ← 12px acid/cyan/crimson overline
  │                                 │
  │ Heading 2                       │ ← 1.1rem Syne 700
  │                                 │
  │ Primary metric (large)          │ ← JetBrains Mono or Syne
  │                                 │
  │ Narrative text (Space Grotesk)  │ ← Body secondary
  │                                 │
  │ [CTA button]   [metadata]       │
  └─────────────────────────────────┘
```

**AI Intervention Card** (Proactive nudge from Tier 8)
```
Background: var(--color-glass)
Border: var(--border-ai)
Radius: var(--radius-lg)
Box-shadow: var(--glow-cyan-sm)
Left-border: var(--border-left-ai)
Animation: ai-pulse on the border/glow (while agent is active)

Special:
  - Overline: "NEXUS AI · INTERVENTION" in cyan
  - Content appears via scramble text animation
  - Has "View Reasoning" expand button → opens CoT console
```

**CoT (Chain-of-Thought) Console**
```
Background: var(--color-void)
Border: 1px solid rgba(0,240,255,0.1)
Radius: var(--radius-lg)
Padding: var(--space-6)
Font: JetBrains Mono 400, --text-data-sm
Color: var(--color-cyan-text)
Overflow-y: auto
Max-height: 320px

Line prefixes (rendered in dimmed cyan):
  [CLASSIFY]   — event classification step
  [REASON]     — LLM reasoning trace
  [SCORE]      — risk scoring output
  [ACTION]     — recommended action
  [CONFIDENCE] — probability output

Entrance: lines appear sequentially with 40ms stagger
Typing cursor: blinking block cursor (█) at end of active line
```

### 9.4 Navigation (Sidebar)

```
Width: var(--width-sidebar) [280px]
Background: var(--color-surface-1)
Border-right: var(--border-subtle)
Padding: var(--space-6) var(--space-4)

AI Status Badge (top of sidebar):
  - Live indicator: pulsing cyan dot
  - Label: "NEXUS ACTIVE" (scramble on state change)
  - Model version: JetBrains Mono xs

Nav Item (default):
  Height: 44px
  Radius: var(--radius-md)
  Padding: 0 var(--space-3)
  Color: var(--color-text-tertiary)
  Icon: 20px, tertiary tint

Nav Item (active):
  Background: rgba(200,255,0,0.06)
  Border-left: 2px solid var(--color-acid)
  Color: var(--color-text-primary)
  Icon: acid tint

Nav Item (hover):
  Background: var(--color-surface-3)
  Color: var(--color-text-secondary)

Collapsed state (64px):
  Icons only, tooltip on hover
  Transition: 200ms ease-out-quart
```

### 9.5 Badges & Status Pills

```
Base:
  Display: inline-flex
  Align-items: center
  Gap: 4px
  Padding: 2px 8px
  Radius: var(--radius-full)
  Font: Space Grotesk 600, --text-label-xs, uppercase, tracking-widest

Variants:
  --badge-health:   bg rgba(200,255,0,0.1),  border rgba(200,255,0,0.2),  text var(--color-acid-text)
  --badge-ai:       bg rgba(0,240,255,0.1),  border rgba(0,240,255,0.2),  text var(--color-cyan-text)
  --badge-risk:     bg rgba(255,0,64,0.1),   border rgba(255,0,64,0.2),   text var(--color-crimson-text)
  --badge-caution:  bg rgba(255,170,0,0.1),  border rgba(255,170,0,0.2),  text var(--color-amber-text)
  --badge-neutral:  bg rgba(255,255,255,0.05), border rgba(255,255,255,0.1), text var(--color-text-tertiary)

Live indicator dot:
  Width/height: 6px
  Radius: full
  Background: current badge accent
  Animation: pulse 2s infinite
```

### 9.6 Toast & Alert System

```
Agent Nudge (non-blocking, bottom-right):
  Width: 360px
  Background: var(--color-surface-2)
  Border: var(--border-ai)
  Radius: var(--radius-lg)
  Box-shadow: var(--shadow-lg), var(--glow-cyan-sm)
  Entrance: translateX(+380px) → translateX(0), 350ms ease-out-expo
  Exit: translateX(+380px), opacity 0, 200ms ease-in

Risk Alert (full-width banner, top):
  Background: rgba(255,0,64,0.08)
  Border-bottom: 1px solid rgba(255,0,64,0.2)
  Height: 52px
  Font: Space Grotesk 600
  Color: var(--color-crimson-text)
  Left icon: crimson warning, animated pulse
  Entrance: translateY(-52px) → translateY(0), 300ms ease-out-expo
```

### 9.7 Modals & Overlay Panels

```
Backdrop:
  Background: rgba(6,6,6,0.85)
  Backdrop-filter: blur(4px)
  Entrance: opacity 0 → 1, 200ms

Modal Panel:
  Background: var(--color-surface-2)
  Border: var(--border-default)
  Radius: var(--radius-xl)
  Box-shadow: var(--shadow-xl)
  Max-width: var(--width-modal-md)
  Entrance: scale(0.95) + opacity 0 → scale(1) + opacity 1, 300ms ease-out-expo

Right Drawer (AI Panel, Timeline):
  Width: var(--width-panel-right) [400px]
  Height: 100vh
  Background: var(--color-surface-1)
  Border-left: var(--border-subtle)
  Box-shadow: -24px 0 80px rgba(0,0,0,0.5)
  Entrance: translateX(+400px) → translateX(0), 350ms ease-out-expo
```

---

## 10. DATA VISUALIZATION

### 10.1 Chart Design Principles

1. **Always pair numbers with narratives** — Every chart must have an AI-generated
   one-sentence insight below it.
2. **No chart axes with generic labels** — Use actual context ("Monthly EMI Load ₹",
   not just "Amount").
3. **No pie charts** — Use donut charts with center callout text only.
4. **No bar charts without trend line** — Overlay a spline for trajectory context.
5. **All charts must have a temporal scrub** — Enable time-window selection.

### 10.2 Chart Color Assignment

```
Single series (positive):   var(--color-acid)
Single series (risk):       var(--color-crimson)
Single series (AI-driven):  var(--color-cyan)
Multi-series order:         acid → cyan → amber → violet → coral → teal
Reference line:             rgba(255,255,255,0.15), dashed
Axis lines:                 rgba(255,255,255,0.04)
Grid lines:                 rgba(255,255,255,0.025)
Tooltip background:         var(--color-surface-3)
Tooltip border:             var(--border-default)
```

### 10.3 Chart Types & Specifications

**Sparkline (Inline with metric)**
```
Height: 40px
No axes, no labels
Color: context-appropriate (acid/crimson)
Area fill: 15% opacity of line color
Stroke: 1.5px
```

**Area Chart (Score History, Net Worth)**
```
Height: 200px–280px
Area fill: gradient from accent at 20% → 0% at bottom
Stroke: 2px accent
Grid lines: horizontal only, 4 lines max
Crosshair on hover: vertical line, tooltip
```

**Donut Chart (Expense Breakdown)**
```
Outer radius: adaptive
Inner radius: 65% (for center text)
Center text: primary metric in --text-display-medium, Syne
Center subtext: label in --text-label-sm
Gap between segments: 3px, background color
Hover: segment lifts by scale(1.05), tooltip
```

**Monte Carlo Fan Chart (Scenario Projections)**
```
Fan scenarios rendered as:
  - P10 (worst): crimson, 1px dashed, 30% opacity
  - P25 (poor):  amber, 1px, 40% opacity
  - P50 (base):  white, 2px, 80% opacity
  - P75 (good):  acid, 1px, 40% opacity
  - P90 (best):  acid, 1px dashed, 30% opacity

Fan fill between P25–P75: acid at 4% opacity
"TODAY" marker: vertical dashed white line
Horizon labels: JetBrains Mono, xs, tertiary
```

**Timeline Heatmap (Transaction Calendar)**
```
Cell size: 12px × 12px
Gap: 2px
Color scale:
  0 transactions:    var(--color-surface-2)
  Low activity:      rgba(200,255,0,0.15)
  Mid activity:      rgba(200,255,0,0.45)
  High activity:     rgba(200,255,0,0.85)
  Risk transactions: rgba(255,0,64,0.6)
Hover: scale(1.5), tooltip with count + top category
```

---

## 11. INTERACTION STATES

### 11.1 Standard State Matrix

| State | Visual Change | Duration |
|---|---|---|
| Default | — | — |
| Hover | Surface +1 level, border brightens | 150ms |
| Focus | Acid border + 3px glow ring | 100ms |
| Active/Pressed | Scale 0.97, brightness -8% | 50ms |
| Disabled | Opacity 0.3, no pointer events | — |
| Loading | Skeleton pulse or spinner | — |
| Success | Brief acid flash, checkmark | 300ms |
| Error | Crimson border + glow | 200ms |

### 11.2 Loading States

**Skeleton screens** must always match the shape of the content they replace.

```css
/* Full card skeleton */
.skeleton-card {
  background: var(--color-surface-1);
  border: var(--border-subtle);
  border-radius: var(--radius-lg);
}
.skeleton-line {
  height: 12px;
  border-radius: var(--radius-sm);
  background: rgba(255,255,255,0.05);
  animation: skeleton-pulse 1.8s ease-in-out infinite;
}
.skeleton-line--wide  { width: 75%; }
.skeleton-line--mid   { width: 50%; }
.skeleton-line--short { width: 30%; }
.skeleton-number {
  height: 48px;
  width: 40%;
  border-radius: var(--radius-md);
}
```

**AI Thinking State** (when LLM is generating):
- Card border pulses cyan (ai-pulse animation)
- Overline changes to "NEXUS THINKING…" with dot trail animation
- Content area shows animated cursor (blinking `█`)

### 11.3 Empty States

```
Container:
  Text-align: center
  Padding: var(--space-16) var(--space-8)
  Max-width: 380px
  Margin: auto

Icon: 48px, acid or cyan tint, 50% opacity
Title: H3, Space Grotesk 600
Body: Body secondary, color text-tertiary, max-width: 280px
CTA: Secondary or primary button

Empty state copy style:
  Avoid: "No data found" (generic)
  Use: "Your Digital Twin is still learning." (contextual, brand voice)
```

### 11.4 Error States

```
Page-level error:
  Full-width crimson banner (see Toast spec)
  Icon: crimson bolt icon
  Message: concise, human, with recovery action

Inline field error:
  Below input: Space Grotesk 400, --text-label-sm, crimson text
  Icon: 14px crimson warning inline

Chart data error:
  Replace chart with: centered crimson icon + "Unable to load simulation data."
  Retry button below
```

---

## 12. LAYOUT COMPOSITIONS

### 12.1 The Hero Zone (Digital Twin HUD)

The top section of every major dashboard view. It must establish dominance.

```
Layout: Full-width, min-height 360px
Background: var(--color-surface-1) + --gradient-void-radial
Padding: var(--space-12) var(--space-8)

Zones (left → right on desktop, stacked on mobile):
  LEFT  (40%): Primary score + category + last-updated
  CENTER(30%): Live twin status visualization (WebGL/Canvas particle)
  RIGHT (30%): Top 3 risk signals as vertical stack of mini-cards
```

### 12.2 Dashboard Card Grid

```
Layout: CSS Grid, 12 columns
Card sizes:
  Micro card    (3col): Single metric, sparkline
  Standard card (4col): Metric + chart or narrative
  Wide card     (6col): Primary chart with controls
  Full card    (12col): Monte Carlo fan, Timeline slider
  
Gutter: 16px
Row gap: 16px
Card min-height: 120px
```

### 12.3 Temporal Time Travel UI

The timeline scrubber — used across Tier 4 (versioning) and Tier 6 (simulation):

```
Container:
  Full-width bar, height: 64px
  Background: var(--color-surface-2)
  Border: var(--border-subtle)
  Radius: var(--radius-lg)
  Sticky to top (z-index 100) when user is in time-travel mode

Track:
  Height: 3px
  Background: rgba(255,255,255,0.08)
  Past zone fill: rgba(200,255,0,0.3)
  Future zone fill: rgba(0,240,255,0.15)

Thumb:
  Width: 20px, height: 20px
  Background: white
  Border: 2px solid var(--color-acid)
  Glow: var(--glow-acid-sm)

"TODAY" marker: fixed notch on track, acid color

Left of thumb (past): data is REAL — label "ACTUAL"
Right of thumb (future): data is SIMULATED — label "PROJECTED" in cyan

Scrubbing behavior:
  - While dragging: all dashboard cards apply .scrubbing class (blur + dim)
  - On release: cards animate back in with cross-dissolve 150ms
  - Date display updates in real-time: JetBrains Mono, acid text

Past limit: account creation date
Future limit: 24 months ahead (1,000 scenario average)
```

---

## 13. RESPONSIVE STRATEGY

### 13.1 Breakpoints

```css
--bp-mobile:   480px;   /* xs: small phones */
--bp-tablet:   768px;   /* sm: tablets, large phones */
--bp-laptop:   1024px;  /* md: laptops */
--bp-desktop:  1280px;  /* lg: standard desktop */
--bp-wide:     1440px;  /* xl: wide desktop */
--bp-ultra:    1920px;  /* 2xl: ultra-wide */
```

### 13.2 Component Behavior at Breakpoints

| Component | Mobile | Tablet | Desktop |
|---|---|---|---|
| Sidebar | Bottom nav (5 icons) | Collapsed 64px | Full 280px |
| Hero Zone | Score only, full-width | Score + signals | Full HUD |
| Card grid | 1 column | 2 columns | 12-col grid |
| Timeline scrub | Modal sheet | Sticky bar, compact | Full scrubber |
| CoT Console | Bottom sheet | Right panel | Inline expand |
| Data table | Horizontal scroll | Horizontal scroll | Full table |

### 13.3 Touch Targets

Minimum touch target: **44px × 44px** on all interactive elements.
On mobile, increase card tap area with `padding` rather than `min-height`.

---

## 14. ACCESSIBILITY

### 14.1 WCAG Targets

- **Level AA compliance** as minimum
- Color contrast for text: ≥ 4.5:1 (normal text), ≥ 3:1 (large text)
- **Critical exceptions**: Acid Green `#C8FF00` on `#060606` = 12.4:1 ✓

### 14.2 Contrast Matrix (Pre-verified)

| Text Color | Background | Ratio | Pass |
|---|---|---|---|
| #F0F0F0 on #060606 | Primary text on void | 19.2:1 | ✓ AAA |
| #C8FF00 on #060606 | Acid on void | 12.4:1 | ✓ AAA |
| #00F0FF on #060606 | Cyan on void | 10.2:1 | ✓ AAA |
| #999999 on #060606 | Secondary text | 5.8:1 | ✓ AA |
| #FF0040 on #060606 | Crimson on void | 4.6:1 | ✓ AA |
| #FFAA00 on #060606 | Amber on void | 8.1:1 | ✓ AAA |
| #060606 on #C8FF00 | Inverse text on acid | 12.4:1 | ✓ AAA |

### 14.3 Focus Management

```css
/* Global focus ring — replace browser default */
:focus-visible {
  outline: 2px solid var(--color-acid);
  outline-offset: 3px;
  border-radius: var(--radius-sm);
}

/* For elements with their own border (inputs, cards) */
.focusable:focus-visible {
  outline: none;
  box-shadow: 0 0 0 2px var(--color-acid), 0 0 0 4px rgba(200,255,0,0.2);
}
```

### 14.4 Screen Reader Considerations

- All charts must have `aria-label` with a text summary: e.g.
  `"Credit score trend chart: 672 in January, rising to 741 in June"`
- All data-driven card metrics must have `aria-live="polite"` for real-time updates
- All icon-only buttons must have `aria-label`
- CoT Console: `role="log"`, `aria-live="polite"`, `aria-label="AI reasoning trace"`
- Timeline scrubber: `role="slider"`, `aria-valuemin`, `aria-valuemax`, `aria-valuenow`

### 14.5 Motion Accessibility

All non-essential animations must respect `prefers-reduced-motion`. See §8.4.
The scramble text effect is decorative — replace with a simple fade when reduced motion is on.

---

## 15. MICRO-INTERACTIONS & AMBIENT EFFECTS

### 15.1 Background Particle System (Digital Twin Alive State)

The hero background must never be static. A WebGL / Canvas particle system represents
the live ingestion of Kafka/Redis data streams.

```
Particle count:    120–200 (reduce to 60 on mobile)
Particle size:     0.5px–1.5px (randomized)
Particle color:    Mix of acid (60%), cyan (30%), white (10%)
Particle opacity:  0.1–0.4 (randomized, breathing animation)
Movement:          Slow drift, velocity noise (Simplex noise)
Connections:       Lines between particles < 80px apart, opacity inversely proportional to distance
Line color:        rgba(200,255,0,0.03) to rgba(200,255,0,0.08)
Interaction:       Mouse proximity repels particles (radius: 120px)
Performance:       Use `requestAnimationFrame`, cap at 60fps, pause when tab not visible
```

**Performance note**: Use `will-change: transform` on the canvas. Degrade gracefully to
the static dot-matrix CSS background if WebGL is unavailable.

### 15.2 Cursor Customization

```css
/* Default */
cursor: default;

/* Interactive elements */
cursor: pointer;

/* AI-active state (when agent is computing) */
cursor: url('nexus-cursor-thinking.svg'), wait;

/* Data dragging (timeline scrub) */
cursor: col-resize;

/* Timeline thumb dragging */
cursor: grab;
cursor: grabbing; /* :active state */
```

### 15.3 Scrollbar Styling

```css
::-webkit-scrollbar { width: 4px; height: 4px; }
::-webkit-scrollbar-track { background: transparent; }
::-webkit-scrollbar-thumb {
  background: rgba(255,255,255,0.12);
  border-radius: 2px;
}
::-webkit-scrollbar-thumb:hover {
  background: rgba(200,255,0,0.3);
}
```

### 15.4 Text Selection

```css
::selection {
  background: rgba(200,255,0,0.2);
  color: var(--color-text-primary);
}
```

### 15.5 Haptic Feedback (Mobile)

Use the Vibration API for key events:
```js
// Risk alert trigger
navigator.vibrate?.([50, 30, 50]);  // double pulse pattern

// AI intervention
navigator.vibrate?.(30);  // single short tap

// Score update (positive)
navigator.vibrate?.(20);  // very light tap
```

---

## 16. VOICE & TONE

### 16.1 Brand Voice Principles

Nexus speaks like a brilliant, silent analyst who only intervenes when it truly matters.

- **Precise over verbose** — "DTI ratio: 42% (critical)" not "Your debt-to-income ratio
  is quite high at 42%, which we consider to be in a critical range."
- **Confident over hedged** — State findings. Don't say "may" or "might" unless genuinely
  probabilistic.
- **Technical, not jargon** — Use financial terms correctly. Define them in-context
  the first time per session.
- **Proactive not reactive** — Interventions lead with the implication, not the data.
  "Your EMI load peaks in March — consider pre-emptive refinancing." Not "We detected
  a high EMI load in March."

### 16.2 LLM Narrative Style Guide

For AI-generated card narratives and intervention messages:

```
Length:       2–4 sentences. Never a bulleted list in a card narrative.
Sentence one: Current state verdict (acid = good, crimson = risk, amber = caution)
Sentence two: Primary causal factor
Sentence three: Trajectory or projection
Sentence four (optional): Recommended action
Tone:         A senior private banking analyst briefing an intelligent client.
```

**Example (good)**:
> "Your liquidity fingerprint is in a healthy state, driven by consistent UPI inflows from
> two primary income nodes. Discretionary spending compression over the past 23 days has
> improved your 90-day EMI coverage ratio to 3.2×. The Monte Carlo baseline projects
> a score improvement of 18–24 points if current behavior holds."

**Example (bad)**:
> "Great news! Your finances look good. You have been spending less and your income
> is steady. Keep it up!"

### 16.3 Error & Empty State Messaging

```
Empty:   "Your Digital Twin is building its model. Check back in 48 hours."
Error:   "Simulation failed. The Redis stream returned incomplete data. Retrying."
Risk:    "Anomaly detected in UPI cluster — synthetic identity pattern match at 87%."
```

---

## 17. DESIGN TOKENS (CSS VARIABLES)

### Complete Token File

```css
:root {
  /* ── BACKGROUNDS ─────────────────────────── */
  --color-void:             #060606;
  --color-surface-0:        #0A0A0A;
  --color-surface-1:        #0D0D0D;
  --color-surface-2:        #111111;
  --color-surface-3:        #161616;
  --color-surface-4:        #1C1C1C;
  --color-glass:            rgba(255,255,255,0.03);
  --color-glass-border:     rgba(255,255,255,0.06);

  /* ── TEXT ────────────────────────────────── */
  --color-text-primary:     #F0F0F0;
  --color-text-secondary:   #999999;
  --color-text-tertiary:    #666666;
  --color-text-dim:         #444444;
  --color-text-inverse:     #060606;

  /* ── ACCENTS ─────────────────────────────── */
  --color-acid:             #C8FF00;
  --color-acid-dim:         rgba(200,255,0,0.12);
  --color-acid-glow:        rgba(200,255,0,0.25);
  --color-acid-text:        #A8D900;
  --color-cyan:             #00F0FF;
  --color-cyan-dim:         rgba(0,240,255,0.10);
  --color-cyan-glow:        rgba(0,240,255,0.20);
  --color-cyan-text:        #00C8D4;
  --color-crimson:          #FF0040;
  --color-crimson-dim:      rgba(255,0,64,0.10);
  --color-crimson-glow:     rgba(255,0,64,0.20);
  --color-crimson-text:     #E0003A;
  --color-amber:            #FFAA00;
  --color-amber-dim:        rgba(255,170,0,0.10);
  --color-amber-text:       #E09500;

  /* ── BORDERS ─────────────────────────────── */
  --border-subtle:          1px solid rgba(255,255,255,0.04);
  --border-default:         1px solid rgba(255,255,255,0.08);
  --border-strong:          1px solid rgba(255,255,255,0.14);
  --border-focus:           1px solid rgba(200,255,0,0.5);
  --border-ai:              1px solid rgba(0,240,255,0.25);
  --border-risk:            1px solid rgba(255,0,64,0.25);

  /* ── RADII ───────────────────────────────── */
  --radius-sm:   4px;
  --radius-md:   8px;
  --radius-lg:   12px;
  --radius-xl:   16px;
  --radius-2xl:  24px;
  --radius-full: 9999px;

  /* ── SHADOWS ─────────────────────────────── */
  --shadow-sm:        0 1px 3px rgba(0,0,0,0.4);
  --shadow-md:        0 4px 16px rgba(0,0,0,0.5);
  --shadow-lg:        0 16px 48px rgba(0,0,0,0.6);
  --shadow-xl:        0 32px 80px rgba(0,0,0,0.7);
  --glow-acid-sm:     0 0 12px rgba(200,255,0,0.25);
  --glow-acid-md:     0 0 24px rgba(200,255,0,0.2), 0 0 48px rgba(200,255,0,0.08);
  --glow-acid-lg:     0 0 40px rgba(200,255,0,0.3), 0 0 80px rgba(200,255,0,0.1);
  --glow-cyan-sm:     0 0 12px rgba(0,240,255,0.2);
  --glow-cyan-md:     0 0 24px rgba(0,240,255,0.18);
  --glow-crimson-sm:  0 0 12px rgba(255,0,64,0.2);
  --glow-crimson-md:  0 0 24px rgba(255,0,64,0.15);

  /* ── SPACING ─────────────────────────────── */
  --space-1:  4px;  --space-2:  8px;  --space-3:  12px;
  --space-4: 16px;  --space-5: 20px;  --space-6:  24px;
  --space-8: 32px;  --space-10:40px;  --space-12: 48px;
  --space-16:64px;  --space-20:80px;  --space-24: 96px;

  /* ── SIZING ──────────────────────────────── */
  --height-input:     44px;
  --height-button:    44px;
  --height-button-sm: 32px;
  --height-navbar:    64px;
  --width-sidebar:    280px;
  --width-sidebar-collapsed: 64px;
  --width-panel-right: 400px;

  /* ── TYPOGRAPHY ──────────────────────────── */
  --font-display:   'Syne', system-ui, sans-serif;
  --font-body:      'Space Grotesk', system-ui, sans-serif;
  --font-data:      'JetBrains Mono', monospace;

  /* ── MOTION ──────────────────────────────── */
  --ease-out-expo:    cubic-bezier(0.16,1,0.3,1);
  --ease-spring:      cubic-bezier(0.34,1.56,0.64,1);
  --ease-in-out-sine: cubic-bezier(0.37,0,0.63,1);
  --duration-fast:    100ms;
  --duration-normal:  200ms;
  --duration-medium:  350ms;
  --duration-slow:    500ms;

  /* ── Z-INDEX ─────────────────────────────── */
  --z-base:      0;
  --z-raised:    10;
  --z-dropdown:  100;
  --z-sticky:    200;
  --z-drawer:    300;
  --z-modal:     400;
  --z-toast:     500;
  --z-tooltip:   600;
  --z-grain:     9999;
}
```

---

## 18. DO / DON'T REFERENCE

| ✅ DO | ❌ DON'T |
|---|---|
| Use Syne only for display & headings | Use Syne at body sizes |
| Pair every chart with an AI narrative | Show raw data without context |
| Use progressive disclosure for complex data | Dump all 32 dimensions on screen at once |
| Use scramble text for agent interventions | Use pop-up modals for AI nudges |
| Keep crimson for genuine risk signals only | Use red for decorative or neutral purposes |
| Animate data to signal it is live | Animate decoratively (for style) |
| Use the 5-surface depth stack | Use one flat dark background for everything |
| Apply `prefers-reduced-motion` exceptions | Animate unconditionally |
| Test all text against WCAG AA minimum | Assume dark-on-dark is acceptable |
| Use JetBrains Mono for all numerical data | Mix fonts randomly within data tables |
| Give every empty state a brand voice | Write "No data found" |
| Make the grain overlay fixed and pointer-events:none | Let the grain layer intercept clicks |
| Use the 4px base grid for all spacing | Use arbitrary pixel values |
| Scale particle count down on mobile | Run 200 particles on a low-end phone |

---

*NEXUS Brand System v2.0 — Maintained by Design Systems.*
*Update this document with every component addition or token change.*
*Last revised: 2026.*
