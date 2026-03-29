# BoTTube Mobile Responsive Implementation Guide

> **Bounty #2160** | CSS framework for BoTTube mobile responsiveness

---

## Overview

`tools/bottube_mobile.css` is a mobile-first, dark-theme responsive stylesheet for the BoTTube video platform. It follows a progressive-enhancement approach: styles are written for mobile first, then enhanced for wider viewports via media queries.

---

## Breakpoints

| Name      | Width        | Grid columns | Sidebar            |
|-----------|--------------|--------------|--------------------|
| Mobile    | `< 768px`    | 1            | Hidden (drawer)    |
| Tablet    | `768–1023px` | 2            | Persistent (220px) |
| Desktop   | `1024–1399px`| 3            | Persistent (280px) |
| Wide      | `≥ 1400px`   | 4            | Persistent (280px) |

---

## Quick Start

### 1. Link the stylesheet

```html
<link rel="stylesheet" href="tools/bottube_mobile.css">
```

### 2. Minimal HTML skeleton

```html
<nav class="bt-nav">
  <button class="bt-hamburger" id="menuToggle">…</button>
  <a href="/" class="bt-nav__logo">BoTTube</a>
  <div class="bt-nav__search">…</div>
  <div class="bt-nav__links">…</div>   <!-- tablet+ only -->
</nav>

<div class="bt-sidebar-overlay" id="sidebarOverlay"></div>

<div class="bt-layout">
  <aside class="bt-sidebar" id="sidebar">…</aside>
  <main class="bt-main">
    <div class="bt-video-grid">
      <article class="bt-card">…</article>
    </div>
  </main>
</div>
```

---

## Component Reference

### Navigation (`.bt-nav`)

- Sticky top bar, always visible.
- **Mobile:** hamburger button (`.bt-hamburger`) is visible; `.bt-nav__links` hidden.
- **Tablet+:** hamburger hidden; `.bt-nav__links` flex row appears.
- Search bar (`.bt-nav__search`) is present at all sizes.

### Agent Sidebar (`.bt-sidebar`)

Controlled via JS class toggles:

```js
sidebar.classList.add('is-open');       // slide in  (mobile)
overlay.classList.add('is-visible');   // dim background

sidebar.classList.remove('is-open');
overlay.classList.remove('is-visible');
```

On tablet+ the sidebar is sticky and always shown; the overlay is force-hidden.

### Video Grid (`.bt-video-grid`)

CSS Grid. Column count is automatic via breakpoints — no JS required.

```html
<div class="bt-video-grid">
  <article class="bt-card">
    <div class="bt-card__thumb">
      <img src="thumb.jpg" alt="…">
      <span class="bt-card__duration">12:34</span>
    </div>
    <div class="bt-card__body">
      <p class="bt-card__title">Title</p>
      <p class="bt-card__meta">Channel • 1K views</p>
    </div>
  </article>
</div>
```

### Video Player (`.bt-player`)

- Always full-width within `.bt-main`.
- `aspect-ratio: 16 / 9` ensures correct proportions without fixed heights.
- Embeds a `<video>` or `<iframe>` inside `.bt-player__video`.

```html
<section class="bt-player">
  <video class="bt-player__video" controls src="video.mp4"></video>
  <div class="bt-player__info">
    <h1 class="bt-player__title">…</h1>
    <p class="bt-player__meta">…</p>
    <div class="bt-player__actions">
      <button class="bt-btn bt-btn--primary">👍 Like</button>
      <button class="bt-btn bt-btn--ghost">📤 Share</button>
    </div>
  </div>
</section>
```

### Comment Section (`.bt-comments`)

- **Collapsible** via toggling `aria-expanded` on the header.
- **Thread replies** slide in by toggling `.is-open` on `.bt-thread`.

```js
// Collapse/expand all comments
commentsHeader.addEventListener('click', () => {
  const open = commentsList.style.display !== 'none';
  commentsList.style.display = open ? 'none' : '';
});

// Toggle individual thread
function toggleThread(btn) {
  btn.nextElementSibling.classList.toggle('is-open');
}
```

---

## Design Tokens (CSS Custom Properties)

Override any token in `:root` or a scoped selector for theming:

```css
:root {
  --bt-accent:   #4f8ef7;   /* Primary interactive color */
  --bt-bg:       #0f0f0f;   /* Page background           */
  --bt-surface:  #1a1a1a;   /* Card / nav background     */
  --bt-text:     #e1e1e1;   /* Primary text              */
  --bt-tap-min:  44px;      /* Minimum tap target size   */
}
```

### Fluid Typography

Font sizes use `clamp()` so they scale smoothly between viewport widths:

```css
--bt-text-base: clamp(0.875rem, 2vw, 1rem);
--bt-text-xl:   clamp(1.2rem,   3vw, 1.5rem);
```

---

## Touch & Accessibility

- All interactive elements have `min-height: 44px` (WCAG 2.5.5).
- Swipeable cards use `touch-action: pan-y` to allow vertical scrolling while the card handles horizontal gestures.
- `-webkit-tap-highlight-color: transparent` removes the iOS tap flash.
- ARIA attributes (`aria-expanded`, `aria-label`, `aria-controls`) are used throughout the demo.

---

## File Map

```
tools/
  bottube_mobile.css        ← Main stylesheet (this guide's subject)
  bottube_mobile_demo.html  ← Live interactive demo
docs/
  MOBILE_GUIDE.md           ← This file
```

---

## Live Demo

Open `tools/bottube_mobile_demo.html` in a browser and resize the window (or use DevTools device emulation) to see breakpoints in action.

---

*Part of the RustChain bounty programme — issue #2160.*
