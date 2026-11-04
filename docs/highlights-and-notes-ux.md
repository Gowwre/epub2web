# Highlights and notes: UI and interaction design

This is research and design, not an implemented feature. The goal is to make
highlighting and note-taking feel like a natural part of reading:

- one action to highlight;
- notes are optional and never block the highlight;
- no save button for highlights;
- review and migration stay out of the reading flow;
- the same mental model works on desktop, tablet, phone, keyboard, and screen
  reader.

See [`highlights-and-notes.md`](highlights-and-notes.md) for storage, anchoring,
persistence, and calibre migration.

## 1. What other readers teach us

| Reader | Creation | Notes | Review | Lesson |
|---|---|---|---|---|
| **Calibre** | Select text → small popup bar → Highlight | Add note or change color from the bar | Highlights panel, sorted by chapter; `Ctrl+H` | A small contextual bar is enough; the panel is for later. |
| **Apple Books** | Select → Highlight → color/underline palette | Add Note opens a composer; saved notes get a marker | Bookmarks & Highlights panel | Separate “make a highlight” from “choose a color”; notes need a visible marker. |
| **Kindle** | Select → compact menu → Highlight or Note | Note icon on the passage; notes appear in the notebook | Annotation Notebook with type filters | The note marker is essential; filtering by type matters once a book has many annotations. |
| **Thorium** | Select → annotate; quick mode skips the editor | Editor for note, color, style, tags | Annotations panel; margin indicators; keyboard shortcuts | “Quick” creation is a real user need. Power features must stay behind progressive disclosure. |
| **KOReader** | Long-press → select and highlight; tap highlight for menu | Add/edit note from the highlight menu | Bookmarks/highlights browser; book map | Touch users need a fast two-step path; tapping an existing highlight should expose edit/delete. |
| **Tome (web)** | Select → small color popover | Optional note in the same popover | Tap a highlight for a card with quote, chapter, date, note | A web reader can be both fast and reviewable with a compact popover and a highlight card. |

Common pattern: **selection → small action surface → immediate result**. The
annotation list is a separate, deliberate mode.

## 2. Design principles

1. **Selection is the entry point.** No permanent “highlight mode,” no toolbar
   that follows the reader around. Select text, act, return to reading.
2. **Highlight first; customize later.** The primary action applies the
   last-used color immediately. Color is a secondary control, not a required
   decision.
3. **Notes are optional.** A highlight must never require a note, and a note
   must not require a modal before the highlight exists.
4. **No save button for highlights.** Creation, color changes, and deletion are
   optimistic and auto-saved. Show a short Undo toast.
5. **Never cover the selected text.** The toolbar goes above the selection when
   there is room, below otherwise; on phones, use a bottom action bar.
6. **Review is a separate mode.** A header button opens the annotation panel.
   The reading page stays clean.
7. **Color is not the only signal.** Notes get a marker and appear in the panel;
   every action has a text label or accessible name.
8. **Migration is invisible.** Calibre annotations appear automatically with a
   one-time summary, not a setup wizard.
9. **Interruptions are recoverable.** Undo is available for create, edit, and
   delete; failed persistence is explained with an export path.
10. **Accessible by default.** The annotation panel is usable without a mouse
    and without relying on in-text color perception.

## 3. Core flows

### 3.1 Highlight a passage

Desktop:

```text
1. Select text.
   “The design of everyday things…”

2. A small toolbar appears above the selection.

   ┌──────────────────────────────────────┐
   │  ▍ Highlight     ✎ Note     ● yellow │
   └──────────────────────────────────────┘

3. Click Highlight.

4. The passage paints immediately.
   A toast appears: “Highlighted    Undo”
```

Mobile:

```text
1. Long-press and drag the native selection handles.

2. A bottom action bar appears above the safe area.

   ┌──────────────────────────────────────────┐
   │   Highlight      Add note      ● yellow  │
   └──────────────────────────────────────────┘

3. Tap Highlight.

4. The passage paints; the bar disappears; the page does not jump.
```

Rules:

- The primary button uses the last-used color. First use is yellow.
- Choosing a color from the swatch control creates the highlight in that color
  immediately if a selection is active; otherwise it changes the default.
- Do not open a dialog, ask for confirmation, or require a note.
- Clear the native selection after the highlight is created so the browser’s
  selection menu does not linger.
- Keep the viewport exactly where it was. No scroll-to-highlight after creation.

### 3.2 Add a note

```text
Select text → Note → composer → Done
```

Desktop popover:

```text
┌──────────────────────────────────────────┐
│  “The design of everyday things…”        │
│  ┌────────────────────────────────────┐  │
│  │ Add a note…                        │  │
│  │                                    │  │
│  └────────────────────────────────────┘  │
│  Cancel                         Done     │
└──────────────────────────────────────────┘
```

Mobile: the composer becomes a bottom sheet with the quote pinned above the
textarea and the keyboard-safe Done button.

Rules:

- The composer opens with the textarea focused on desktop; on mobile, focus it
  after the sheet animation to avoid keyboard jank.
- **Done** is disabled until the note is non-empty. Cancel creates nothing.
- Saving creates the highlight and the note together, then closes the composer.
- The quote stays visible in the composer; the user should never wonder what
  they are annotating.
- `Cmd/Ctrl+Enter` saves; `Esc` cancels.
- Adding a note to an existing highlight reuses the same composer, with the
  existing note prefilled and a “Remove note” action.

### 3.3 Open an existing highlight

Tap or click a highlighted passage:

```text
┌──────────────────────────────────────────┐
│  ▍ “The design of everyday things…”      │
│                                          │
│  This is the note text.                  │
│  Chapter 3 · 4 Nov 2026                  │
│                                          │
│  [Edit note]  [Color]  [Copy]  [Remove]  │
└──────────────────────────────────────────┘
```

Rules:

- Desktop: a popover near the highlight, clamped to the viewport.
- Mobile: a bottom sheet; do not cover the highlight if it can be avoided.
- If there is no note, show “Add note” as the primary action.
- Color opens the same five swatches and applies immediately.
- Remove applies immediately and shows “Highlight removed · Undo.” No confirm
  dialog for a single highlight.
- Clicking outside or pressing `Esc` closes the card and returns focus to the
  reading page.

### 3.4 Review all annotations

Header button: highlighter icon with a count badge.

```text
┌──────────────────────────────────────────────┐
│  Highlights & notes                      42  │
│  [All] [Highlights] [Notes]                  │
│                                              │
│  Chapter 3                                   │
│  ▍ “The design of everyday things…”          │
│    This is the note text.        4 Nov 2026  │
│  ▍ “Affordances…”                            │
│                                              │
│  Chapter 4                                   │
│  ▍ “A signifier is…”                         │
│                                              │
│  [Export]                          [Import]  │
└──────────────────────────────────────────────┘
```

Rules:

- Use the existing `dialog.sheet` visual language; desktop width around 520–600
  px, full-height sheet on phones.
- Default sort is reading order, grouped by chapter.
- Filters: All, Highlights, Notes. Do not add color/style filters until users
  have enough annotations to need them.
- Each item shows a color bar, a short quote, an optional note preview, and a
  date. The whole row is clickable.
- Clicking an item closes the panel, scrolls to the passage, and flashes it for
  about 1 second.
- Overflow menu per item: Edit note, Change color, Copy quote, Remove.
- Empty state: “No highlights or notes yet. Select text while reading to add
  one.”
- “Needs review” section appears only for annotations that could not be
  re-anchored or imported confidently.
- Export/import live at the bottom, not as primary reading actions.

### 3.5 Undo

- Create: “Highlighted · Undo” for about 6 seconds.
- Note: “Note saved · Undo.” If the same action created the highlight, Undo
  removes both; if the note was added to an existing highlight, Undo removes
  only the note.
- Delete: “Highlight removed · Undo,” restoring the same record and position.
- Color change: no toast; the visual change is immediate and reversible from the
  card.
- Use `role="status"` for the live message and place the toast above the mobile
  safe area.

### 3.6 Migration

Calibre import should not look like migration:

```text
┌────────────────────────────────────────────────────┐
│  42 highlights and 7 notes imported from calibre.  │
│  [View]                                      [Undo]│
└────────────────────────────────────────────────────┘
```

- Show once, as a non-blocking banner or toast. Never a setup wizard.
- “View” opens the annotation panel; “Undo” removes the imported batch.
- If nothing is found, show nothing.
- If the match is ambiguous, show a small review sheet; do not block the book.
- Unresolved items go to the panel’s “Needs review” section.

## 4. Selection toolbar specification

### 4.1 When it appears

- Only for a non-collapsed text selection inside `.book-page`.
- Only when the selection contains at least one non-whitespace character.
- Not while a dialog is open, while composing a note, or while the annotation
  panel is open.
- Not for selections inside inputs, textareas, or the annotation UI.
- Hide on scroll, resize, `Esc`, selection collapse, or click outside.
- Debounce `selectionchange` by about 100–150 ms so the toolbar does not flicker
  while the user drags a selection.

### 4.2 Placement

- Desktop/tablet: floating above the selection; flip below if the viewport top
  is too close. Clamp horizontally to an 8–12 px margin.
- Phone: fixed bottom action bar above `env(safe-area-inset-bottom)`. This keeps
  the toolbar away from the native selection handles and within thumb reach.
- Never cover the selection’s bounding box. If neither above nor below fits,
  prefer the bottom bar.
- Use logical properties for RTL.

### 4.3 Controls

| Control | Behavior |
|---|---|
| **Highlight** | Apply last-used color immediately. |
| **Note** | Open the note composer for the current selection. |
| **Color swatch** | Open five color choices. Choosing one creates the highlight in that color or changes the default if there is no selection. |
| **Close** | Dismiss without changing anything. |

Do not add Copy, Search, Translate, Share, or Read Aloud in the first version.
The browser’s native menu and the existing reader features already cover those.
Keep the annotation toolbar focused.

### 4.4 Colors

Start with five named colors:

- Yellow (default)
- Green
- Blue
- Pink
- Purple

Each swatch has an accessible name (“Yellow highlight”), a visible selected
state, and a checkmark or ring, not color alone. The last-used color is stored
with the reader settings.

Use a background wash rather than a saturated block. In dark mode, use a darker,
desaturated wash so body text keeps contrast.

Do not add underline/strikethrough styles in the first version. They are useful,
but they add a style decision to the core flow. Add them later behind the color
control if users ask.

## 5. Note composer specification

- Quote preview: up to three lines, with the full quote available to screen
  readers and in the annotation card.
- Textarea: plain text, auto-growing up to about 40% of the viewport; then
  scroll.
- Placeholder: “Add a note (optional)” only when editing an existing highlight;
  for a new note action, “Write a note…”.
- Buttons: Cancel and Done. Done is disabled when the note is empty.
- `Cmd/Ctrl+Enter` saves; `Esc` cancels.
- No rich text, Markdown preview, tags, or sharing in the first version.
- Preserve line breaks. Do not trim internal whitespace; trim leading/trailing
  whitespace on save.
- On mobile, keep the quote visible above the textarea but let it scroll away
  when the keyboard is open if space is tight.
- If the note cannot be saved, keep the composer open and show an inline error
  with a retry action. Never lose the typed text.

## 6. Annotation panel specification

### 6.1 Entry point

- Header highlighter icon with a count badge.
- `Shift+A` opens the panel when the user is not typing.
- The icon is visible on reading pages, not on the home or contents pages.
- On phones, keep the icon in the header; do not bury it in the menu.

### 6.2 Layout

- Reuse `dialog.sheet` so it feels native to epub2web.
- Header: “Highlights & notes” and total count.
- Filter chips: All, Highlights, Notes. One active filter at a time.
- Optional “This chapter” toggle can come later; default is whole book.
- Group headings are chapter titles, sticky inside the scrolling body.
- Each row:
  - 4 px color bar;
  - quote in body text, clamped to two lines;
  - note preview in UI text, clamped to one line;
  - date in muted UI text;
  - overflow button with a text label for screen readers.
- Row activation: jump and flash.
- Footer: Export and Import, separated from the list.

### 6.3 Empty and error states

- Empty: short explanation plus a “Select text to highlight” hint. No tour.
- Needs review: “3 annotations need review” with a short reason on each item.
- Storage failure: an inline banner with “Export annotations” and a retry.
- No annotations but import available: do not show an import prompt until the
  user opens the panel.

## 7. Keyboard and screen reader behavior

### 7.1 Shortcuts

| Key | Action |
|---|---|
| `H` | Highlight the current selection with the last-used color. |
| `N` | Add a note to the current selection. |
| `Shift+A` | Open or close the annotation panel. |
| `Esc` | Close toolbar, card, composer, or panel. |
| `Cmd/Ctrl+Enter` | Save the note composer. |
| `Tab` / `Shift+Tab` | Move through toolbar, card, and panel controls. |

Do not use `Ctrl+H` (browser history) or `Ctrl+N` (new window). Do not trigger
single-letter shortcuts while typing.

### 7.2 Focus management

- When the selection toolbar opens from a keyboard selection, keep focus in the
  document but make the toolbar reachable with `Tab`; `H`/`N` should work
  immediately.
- Opening the note composer moves focus to the textarea; closing returns focus
  to the reading page near the highlight.
- Opening the annotation panel traps focus inside the dialog and returns focus
  to the header button on close.
- Row actions use buttons with accessible names, not icon-only controls without
  labels.
- Announce creation, edit, deletion, and undo with an `aria-live="polite"`
  status region.

### 7.3 Screen reader fallback

Native DOM text selection is difficult or impossible in some screen reader and
browser combinations. Do not make annotation creation depend on it.

Provide an **“Add note at current location”** action in the annotation panel.
It anchors to the first visible paragraph, opens the same composer, and labels
the annotation with the chapter and a short quote. This gives screen reader
users a usable note-taking path even when selecting a range is unreliable.

In-text highlights are visual. The annotation panel is the accessible source of
truth: every highlight and note must be reachable, labeled, and editable there.

### 7.4 Color and perception

- Never use color alone to distinguish a note. Use a note marker and text in the
  panel.
- Ensure highlight washes keep at least WCAG AA contrast for body text.
- Color swatches have names and selected states.
- Support Windows High Contrast and forced-colors mode where possible; at
  minimum, do not let highlights disappear entirely.

## 8. Visual specification

### 8.1 Highlight styles

- Background wash with a subtle edge; no heavy border.
- Current highlight hover: slightly stronger wash and a pointer cursor.
- Note marker: small rounded square with a pencil glyph at the end of the
  highlighted range, or in the trailing margin if the range is long. It must be
  a real button with an accessible label.
- Dark mode: desaturated background washes; keep text color inherited.
- Reduce motion users get an instant flash instead of an animated pulse.

Suggested tokens:

```css
--hl-yellow: #f3d36a;
--hl-green:  #bfe3a2;
--hl-blue:   #b9d9f2;
--hl-pink:   #f3c2d4;
--hl-purple: #d9c5f0;
```

Dark-mode variants should be darker and less saturated; verify contrast rather
than reusing the light values.

### 8.2 Toolbar

- Surface: `--paper-2`.
- Border: `--rule-strong`.
- Shadow: `--shadow-soft`.
- Radius: 6 px.
- Height: 44–48 px desktop, 52–56 px mobile.
- Buttons: icon plus label on desktop; on mobile, label plus icon where space
  allows. Minimum target 44×44 px on touch.
- Focus ring: 2 px accent, visible on keyboard focus.
- The toolbar is not a dialog; it should not trap focus or create a backdrop.

### 8.3 Panel

- Reuse the existing sheet header, body, and close button.
- List rows use a 4 px color bar, a two-line quote, a one-line note preview, and
  a muted date.
- Hover state: `--accent-soft`.
- Focus state: visible outline on the row and overflow button.
- Sticky chapter headings with a subtle bottom rule.
- On phones, the sheet is full-width and nearly full-height; the header stays
  fixed and the footer stays reachable.

### 8.4 RTL and scripts

- Use `inset-inline-start/end`, `margin-inline`, and logical text alignment.
- The toolbar’s arrow/flip logic is geometric, not directional.
- Highlight ranges and note markers use Range rectangles, which already follow
  the writing direction.
- Test at least one RTL book and one CJK book with vertical-ish punctuation.

## 9. State and edge cases

- **Selection spans paragraphs:** allow it. Store the full range; the quote may
  be long but the card clamps it.
- **Selection includes an image or figure:** only text ranges can be
  highlighted. If there is no text, hide the toolbar.
- **Selection inside a link:** allow highlight; do not prevent the link from
  being clickable when no annotation action is active.
- **Overlapping highlights:** allow them. A click inside an overlap opens a small
  chooser listing the overlapping annotations; the panel remains the
  disambiguating surface.
- **Accidental selection on touch:** require a non-empty selection and a
  deliberate tap on Highlight. Do not highlight on selection alone.
- **Page scroll while the toolbar is open:** hide the toolbar rather than
  chasing the selection.
- **Browser selection menu:** native long-press menus may appear alongside the
  custom bar on some mobile browsers. Test iOS Safari and Android Chrome; delay
  showing the bar until selection settles.
- **Storage unavailable:** create the highlight optimistically, then show an
  inline error and keep the annotation in memory for export. Do not silently
  lose it.
- **Reload before save:** autosave immediately after the action; do not rely on
  `pagehide` alone.
- **Deleted book or changed edition:** unresolved annotations appear in “Needs
  review,” never attached to a random passage.
- **Print:** hide interactive chrome; if highlights print, ensure the wash is
  light enough. Printing annotations is a later feature.

## 10. Microcopy

| Situation | Copy |
|---|---|
| Toolbar primary | **Highlight** |
| Toolbar note | **Note** |
| New note placeholder | **Write a note…** |
| Existing note placeholder | **Add a note (optional)** |
| Note save | **Done** |
| Note cancel | **Cancel** |
| Created | **Highlighted** · Undo |
| Note saved | **Note saved** · Undo |
| Removed | **Highlight removed** · Undo |
| Panel title | **Highlights & notes** |
| Empty state | **No highlights or notes yet. Select text while reading to add one.** |
| Import summary | **42 highlights and 7 notes imported from calibre.** View · Undo |
| Needs review | **3 annotations need review** |
| Storage error | **Highlights can’t be saved in this browser. Export them to keep them.** |

Use sentence case. Avoid “annotation” in the primary UI; use “highlight” and
“note.” Use “annotations” only in the panel title or technical settings.

## 11. Acceptance criteria

A first implementation is successful when:

- Selecting a passage and choosing Highlight takes one action after selection
  and paints immediately.
- Adding a note takes one action to open the composer and one to finish; no
  modal appears before the highlight exists.
- No save button is required for a highlight, color change, or deletion.
- An accidental highlight can be undone for at least 6 seconds.
- Clicking a highlight opens a card with edit note, color, copy, and remove.
- The annotation panel opens in one action, groups by chapter, and jumps to a
  highlight in one action.
- Keyboard-only users can select text, press `H`, open the panel with `Shift+A`,
  edit a note, and delete with Undo.
- Screen reader users can reach every annotation through the panel and can add a
  note at the current location without a DOM range selection.
- Mobile targets are at least 44×44 px; the toolbar does not cover the selection
  or the native selection handles.
- The annotation panel clearly distinguishes notes from plain highlights without
  relying on color alone.
- Calibre annotations appear automatically with a one-time summary and Undo; no
  migration wizard is required.
- Highlights and notes survive reload, rebuild, and the documented origin/path
  changes described in the storage design.

## 12. What not to do

- Do not require a color choice before creating a highlight.
- Do not require a note before creating a highlight.
- Do not open a modal for the basic highlight action.
- Do not add a permanent highlighter mode that must be turned off.
- Do not put the annotation panel behind a settings menu.
- Do not use color as the only indication that a note exists.
- Do not auto-scroll or jump after saving a highlight.
- Do not show a confirmation dialog for deleting a single highlight; use Undo.
- Do not add tags, sharing, rich text, or export formats to the first version.
- Do not let a failed save silently discard the user’s text.

## 13. Implementation notes

### 13.1 Selection capture

- Capture the `Range` before showing the toolbar; DOM changes can invalidate it.
- Store the quote, prefix, suffix, and a fallback DOM path immediately.
- Clear the native selection after a successful action.
- On toolbar `pointerdown`/`mousedown`, call `preventDefault()` so the selection
  is not lost before the click handler runs.

### 13.2 Rendering

- Prefer the CSS Custom Highlight API for painting: ranges stay in the DOM, text
  is not wrapped, and multiple highlights can overlap.
- Maintain a map from highlight name to ranges, and hit-test clicks with
  `caretRangeFromPoint` or `Range.intersectsNode`.
- If the browser lacks the API, fall back to `<mark>` wrapping after resolving
  all ranges. Do not wrap before resolving, or paths will shift.
- Draw note markers in an overlay positioned from `Range.getClientRects()`;
  update on resize, font change, and theme change.
- Only resolve and paint annotations for the current page; lazy-load the panel
  data.

### 13.3 State machine

```text
idle
  → selected (toolbar visible)
  → highlighting → idle
  → composing-note → saving → idle
  → card-open → editing-note → saving → idle
  → card-open → changing-color → idle
  → card-open → removing → toast → idle
  → panel-open → jumping → idle
```

Keep the state per page, not global. Opening the panel should not destroy an
in-progress selection unless the user chooses an action.

### 13.4 Persistence

- Save optimistically, then reconcile with IndexedDB.
- Keep a per-page in-memory copy so a failed write can be retried without
  losing the annotation.
- Broadcast changes to other tabs; update the panel count without a reload.
- Do not block the UI on storage; show a small “Saving…” state only if the write
  takes longer than about 300 ms.

### 13.5 Test matrix

- Desktop Chrome/Firefox/Safari, keyboard and mouse.
- iOS Safari and Android Chrome, touch selection.
- 320 px wide through wide desktop.
- Light, dark, high-contrast, reduced motion.
- LTR and RTL books; CJK text.
- Empty book, one highlight, hundreds of highlights.
- Storage failure, quota exceeded, private browsing.
- Imported calibre highlights, unresolved imports, changed edition.

## 14. Open questions

- **Default color vs palette:** should the toolbar always show five swatches, or
  keep one Highlight button plus a color control? The recommendation is the
  latter for speed and visual calm; test both with users.
- **Mobile placement:** bottom action bar vs floating above selection. The
  recommendation is bottom bar on phones; test on small screens and with the
  native selection menu.
- **Note marker:** pencil glyph at the end of the range vs margin dot. Test
  overlap with punctuation and RTL text.
- **Standalone notes:** should users be able to create a note without a
  highlight? Calibre couples them; a standalone note needs a point anchor and a
  different list treatment.
- **Overlap interaction:** chooser popover vs cycling through highlights. A
  chooser is more predictable.
- **Panel entry point:** header icon vs sidebar tab. Header icon is more
  discoverable; monitor mobile header crowding.
- **Printing:** whether to print highlights and notes, and in what layout.
- **Tags and search:** defer until there is evidence users need them.

## 15. References

### Reader behavior

- [Calibre E-book viewer: highlighting text](https://manual.calibre-ebook.com/viewer.html)
- [Apple Books: highlight and add notes](https://support.apple.com/guide/ipad/annotate-books-ipade2f8027b/ipados)
- [Kindle: highlights, notes, and notebook](https://www.clippings.io/kindle-highlights)
- [Thorium Reader: highlights](https://support.thoriumreader.com/hc/en-us/articles/26763214733852-Highlights-Desktop)
- [KOReader user guide: highlights](https://koreader.rocks/user_guide/)
- [Tome reader: highlights & notes](https://tome.bndct.sh/docs/reader)

### Interaction and accessibility

- [Text annotation UX: keep notes anchored](https://screensdesign.com/articles/mobile-text-highlighting-annotation-ux)
- [W3C Web Annotation Data Model](https://www.w3.org/TR/annotation-model/)
- [WCAG 2.2: target size and focus appearance](https://www.w3.org/TR/WCAG22/)
- [CSS Custom Highlight API](https://developer.mozilla.org/en-US/docs/Web/API/CSS_Custom_Highlight_API)

### This repository

- `docs/highlights-and-notes.md` — storage, anchoring, migration, and adapters.
- `epub2web/theme/assets/styles.css` — existing reader, sheet, and responsive
  design tokens.
- `epub2web/theme/assets/app.js` — existing keyboard, dialog, selection, and
  progress behavior.
- `epub2web/templates/base.html` — header actions and reading-page data.
- `epub2web/templates/dialogs.html` — sheet and lightbox patterns.
