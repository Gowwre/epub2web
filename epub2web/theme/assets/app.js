/* The Design of Everyday Things — browser edition */
(function () {
  "use strict";

  const root = document.documentElement;
  const body = document.body;

  /* ------------------------------------------------------------------
     Theme
     ------------------------------------------------------------------ */
  const themeButton = document.querySelector("[data-theme-toggle]");
  function currentTheme() {
    return root.dataset.theme === "dark" ? "dark" : "light";
  }
  function syncThemeLabel() {
    if (!themeButton) return;
    const next = currentTheme() === "dark" ? "light" : "dark";
    themeButton.setAttribute("aria-label", "Switch to " + next + " theme");
    themeButton.setAttribute("title", "Switch to " + next + " theme");
  }
  if (themeButton) {
    syncThemeLabel();
    themeButton.addEventListener("click", function () {
      const next = currentTheme() === "dark" ? "light" : "dark";
      root.dataset.theme = next;
      try { localStorage.setItem("doet-theme", next); } catch (e) {}
      syncThemeLabel();
    });
  }

  /* ------------------------------------------------------------------
     Dialogs
     ------------------------------------------------------------------ */
  const menuDialog = document.getElementById("menu-dialog");
  const searchDialog = document.getElementById("search-dialog");
  const lightbox = document.getElementById("lightbox");
  let lastFocus = null;

  function openDialog(dialog) {
    if (!dialog) return;
    if (menuDialog && menuDialog !== dialog && menuDialog.open) menuDialog.close();
    if (searchDialog && searchDialog !== dialog && searchDialog.open) searchDialog.close();
    lastFocus = document.activeElement;
    if (!dialog.open) dialog.showModal();
  }

  function closeDialog(dialog) {
    if (dialog && dialog.open) dialog.close();
  }

  document.querySelectorAll("[data-menu-open]").forEach(function (button) {
    button.addEventListener("click", function () { openDialog(menuDialog); });
  });
  document.querySelectorAll("[data-search-open]").forEach(function (button) {
    button.addEventListener("click", function () {
      openDialog(searchDialog);
      loadSearch();
    });
  });
  document.querySelectorAll("[data-close]").forEach(function (button) {
    button.addEventListener("click", function () {
      closeDialog(button.closest("dialog"));
    });
  });
  document.querySelectorAll("dialog").forEach(function (dialog) {
    dialog.addEventListener("click", function (event) {
      if (event.target === dialog) dialog.close();
    });
    dialog.addEventListener("close", function () {
      if (lastFocus && typeof lastFocus.focus === "function") lastFocus.focus();
      lastFocus = null;
    });
  });

  /* ------------------------------------------------------------------
     Search (Pagefind, loaded on first use)
     ------------------------------------------------------------------ */
  let searchPromise = null;

  function loadSearch() {
    if (window.PagefindUI) return Promise.resolve();
    if (searchPromise) return searchPromise;

    const mount = document.getElementById("search");
    if (mount) {
      mount.innerHTML = '<p class="search-loading">Loading the search index…</p>';
    }

    searchPromise = new Promise(function (resolve, reject) {
      if (!document.querySelector('link[href="/pagefind/pagefind-ui.css"]')) {
        const css = document.createElement("link");
        css.rel = "stylesheet";
        css.href = "/pagefind/pagefind-ui.css";
        document.head.appendChild(css);
      }
      const script = document.createElement("script");
      script.src = "/pagefind/pagefind-ui.js";
      script.onload = function () {
        try {
          if (!window.PagefindUI) throw new Error("PagefindUI missing");
          if (mount) mount.innerHTML = "";
          new window.PagefindUI({
            element: "#search",
            showSubResults: true,
            showImages: false,
            resetStyles: false,
            bundlePath: "/pagefind/"
          });
          window.setTimeout(function () {
            const input = document.querySelector("#search .pagefind-ui__search-input");
            if (input) input.focus();
          }, 40);
          resolve();
        } catch (error) {
          reject(error);
        }
      };
      script.onerror = function () { reject(new Error("Pagefind script failed")); };
      document.head.appendChild(script);
    }).catch(function () {
      const mountEl = document.getElementById("search");
      if (mountEl) {
        mountEl.innerHTML = '<p class="search-loading">The search index is not available yet. Run <code>npm run build</code> and try again.</p>';
      }
    });

    return searchPromise;
  }

  /* ------------------------------------------------------------------
     Lightbox
     ------------------------------------------------------------------ */
  const lightboxImage = lightbox ? lightbox.querySelector("img") : null;
  const lightboxCaption = lightbox ? lightbox.querySelector("figcaption") : null;

  function openLightbox(link) {
    if (!lightbox || !lightboxImage || !lightboxCaption) return;
    const figure = link.closest("figure");
    const caption = figure ? figure.querySelector("figcaption") : null;
    const img = link.querySelector("img");
    lightboxImage.src = link.getAttribute("href");
    lightboxImage.alt = img ? (img.alt || "") : "";
    lightboxCaption.innerHTML = caption ? caption.innerHTML : "";
    openDialog(lightbox);
    const close = lightbox.querySelector("[data-lightbox-close]");
    if (close) close.focus();
  }

  document.addEventListener("click", function (event) {
    const link = event.target.closest("a.lightbox-link");
    if (!link) return;
    event.preventDefault();
    openLightbox(link);
  });

  if (lightbox) {
    lightbox.querySelectorAll("[data-lightbox-close]").forEach(function (button) {
      button.addEventListener("click", function () { closeDialog(lightbox); });
    });
    lightbox.addEventListener("close", function () {
      if (lightboxImage) lightboxImage.removeAttribute("src");
      if (lightboxCaption) lightboxCaption.textContent = "";
    });
  }

  /* ------------------------------------------------------------------
     Note previews
     ------------------------------------------------------------------ */
  const popover = document.getElementById("note-popover");
  const popoverPage = popover ? popover.querySelector(".note-popover-page") : null;
  const popoverText = popover ? popover.querySelector(".note-popover-text") : null;
  const popoverLink = popover ? popover.querySelector(".note-popover-link") : null;
  let notesData = null;
  let notesPromise = null;
  let hideTimer = null;
  let activeRef = null;

  function loadNotes() {
    if (notesData) return Promise.resolve(notesData);
    if (notesPromise) return notesPromise;
    notesPromise = fetch("/notes.json", { credentials: "same-origin" })
      .then(function (response) {
        if (!response.ok) throw new Error("notes fetch failed");
        return response.json();
      })
      .then(function (data) { notesData = data; return data; })
      .catch(function () { notesData = null; return null; });
    return notesPromise;
  }

  function positionPopover() {
    if (!popover || !activeRef) return;
    const rect = activeRef.getBoundingClientRect();
    if (rect.bottom < 0 || rect.top > window.innerHeight) {
      popover.hidden = true;
      activeRef = null;
      return;
    }
    popover.style.visibility = "hidden";
    popover.hidden = false;
    const box = popover.getBoundingClientRect();
    const margin = 12;
    let left = rect.left + rect.width / 2 - box.width / 2;
    left = Math.max(margin, Math.min(left, window.innerWidth - box.width - margin));
    let top = rect.bottom + 10;
    if (top + box.height > window.innerHeight - margin) {
      top = Math.max(margin, rect.top - box.height - 10);
    }
    popover.style.left = left + "px";
    popover.style.top = top + "px";
    popover.style.visibility = "visible";
  }

  function showNote(ref) {
    if (!popover || !popoverPage || !popoverText || !popoverLink) return;
    const key = ref.getAttribute("data-note");
    const link = ref.querySelector("a");
    if (!key) return;
    window.clearTimeout(hideTimer);
    activeRef = ref;
    loadNotes().then(function (data) {
      const note = data ? data[key] : null;
      if (!note) return;
      popoverPage.textContent = note.page || "";
      popoverText.textContent = note.text || "";
      popoverLink.href = note.href || (link ? link.href : "/notes/");
      positionPopover();
    });
  }

  function hideNote(delay) {
    if (!popover) return;
    window.clearTimeout(hideTimer);
    hideTimer = window.setTimeout(function () {
      popover.hidden = true;
      activeRef = null;
    }, delay == null ? 180 : delay);
  }

  document.querySelectorAll("sup.note-ref").forEach(function (ref) {
    ref.addEventListener("mouseenter", function () { showNote(ref); });
    ref.addEventListener("focusin", function () { showNote(ref); });
    ref.addEventListener("mouseleave", function () { hideNote(); });
    ref.addEventListener("focusout", function (event) {
      if (popover && popover.contains(event.relatedTarget)) return;
      hideNote();
    });
  });

  if (popover) {
    popover.addEventListener("mouseenter", function () { window.clearTimeout(hideTimer); });
    popover.addEventListener("mouseleave", function () { hideNote(80); });
    popover.addEventListener("focusin", function () { window.clearTimeout(hideTimer); });
    popover.addEventListener("focusout", function (event) {
      if (activeRef && activeRef.contains(event.relatedTarget)) return;
      hideNote();
    });
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && !popover.hidden) hideNote(0);
    });
    window.addEventListener("scroll", function () {
      if (activeRef && popover && !popover.hidden) positionPopover();
    }, { passive: true });
    window.addEventListener("resize", function () {
      if (activeRef && popover && !popover.hidden) positionPopover();
    });
  }

  /* ------------------------------------------------------------------
     Reading progress
     ------------------------------------------------------------------ */
  const progressBar = document.querySelector(".progress span");
  if (progressBar && body.hasAttribute("data-reading")) {
    let ticking = false;
    function updateProgress() {
      const doc = document.documentElement;
      const max = doc.scrollHeight - doc.clientHeight;
      const ratio = max > 0 ? Math.min(1, Math.max(0, doc.scrollTop / max)) : 0;
      progressBar.style.width = (ratio * 100).toFixed(2) + "%";
      ticking = false;
    }
    window.addEventListener("scroll", function () {
      if (!ticking) {
        ticking = true;
        window.requestAnimationFrame(updateProgress);
      }
    }, { passive: true });
    window.addEventListener("resize", updateProgress);
    updateProgress();
  }

  /* ------------------------------------------------------------------
     Active sidebar section
     ------------------------------------------------------------------ */
  const sectionLinks = new Map();
  document.querySelectorAll("[data-section-link]").forEach(function (link) {
    const parts = (link.getAttribute("href") || "").split("#");
    if (parts.length === 2) sectionLinks.set(parts[1], link);
  });

  if (sectionLinks.size) {
    let currentId = null;
    let ticking = false;
    function setActive(id) {
      if (id === currentId) return;
      currentId = id;
      sectionLinks.forEach(function (link, key) {
        link.classList.toggle("is-active", key === id);
      });
    }
    const headings = Array.from(document.querySelectorAll(".book-page h2[id], .book-page h3[id]"))
      .filter(function (heading) { return sectionLinks.has(heading.id); });
    function updateActiveSection() {
      const headerHeight = parseInt(getComputedStyle(document.documentElement).getPropertyValue("--header-h"), 10) || 64;
      const offset = headerHeight + 40;
      let id = null;
      for (const heading of headings) {
        if (heading.getBoundingClientRect().top <= offset) id = heading.id;
        else break;
      }
      setActive(id);
      ticking = false;
    }
    window.addEventListener("scroll", function () {
      if (!ticking) { ticking = true; window.requestAnimationFrame(updateActiveSection); }
    }, { passive: true });
    window.addEventListener("resize", updateActiveSection);
    updateActiveSection();
    if (location.hash) setActive(location.hash.slice(1));
  }

  /* ------------------------------------------------------------------
     Index filter
     ------------------------------------------------------------------ */
  const indexFilter = document.getElementById("index-filter");
  if (indexFilter) {
    const entries = Array.from(document.querySelectorAll("[data-index-text]"));
    const groups = Array.from(document.querySelectorAll(".index-list"));
    const count = document.querySelector(".index-count");
    const total = entries.length;
    let noResults = null;

    function applyFilter() {
      const query = indexFilter.value.trim().toLowerCase();
      let visible = 0;
      entries.forEach(function (entry) {
        const match = !query || (entry.getAttribute("data-index-text") || "").toLowerCase().includes(query);
        entry.hidden = !match;
        if (match) visible += 1;
      });
      groups.forEach(function (group) {
        const hasVisible = Array.from(group.children).some(function (child) { return !child.hidden; });
        group.hidden = !hasVisible;
        const heading = group.previousElementSibling;
        if (heading && heading.classList.contains("index-letter")) heading.hidden = !hasVisible;
      });
      document.querySelectorAll(".index-letters a").forEach(function (link) {
        const id = (link.getAttribute("href") || "").slice(1);
        const heading = document.getElementById(id);
        link.hidden = !heading || heading.hidden;
      });
      if (count) {
        count.textContent = query
          ? visible + " of " + total + " entries match “" + indexFilter.value.trim() + "”"
          : total + " entries";
      }
      if (!noResults) {
        noResults = document.createElement("p");
        noResults.className = "index-empty";
        noResults.textContent = "No entries match. Try a shorter or different spelling.";
        const list = document.querySelector(".index-list");
        if (list) list.parentNode.insertBefore(noResults, list);
      }
      noResults.hidden = !query || visible > 0;
    }

    indexFilter.addEventListener("input", applyFilter);
    applyFilter();
    indexFilter.addEventListener("keydown", function (event) {
      if (event.key === "Escape") {
        indexFilter.value = "";
        applyFilter();
      }
    });
  }

  /* ------------------------------------------------------------------
     Keyboard shortcuts
     ------------------------------------------------------------------ */
  function isTyping(target) {
    if (!target) return false;
    const tag = target.tagName ? target.tagName.toLowerCase() : "";
    return tag === "input" || tag === "textarea" || tag === "select" || target.isContentEditable;
  }

  document.addEventListener("keydown", function (event) {
    if (event.defaultPrevented) return;
    if (event.key === "/" && !isTyping(event.target) && !event.metaKey && !event.ctrlKey && !event.altKey) {
      const openDialogEl = document.querySelector("dialog[open]");
      if (openDialogEl) return;
      event.preventDefault();
      openDialog(searchDialog);
      loadSearch();
      return;
    }
    if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
      if (isTyping(event.target) || document.querySelector("dialog[open]")) return;
      const href = event.key === "ArrowLeft" ? body.getAttribute("data-prev") : body.getAttribute("data-next");
      if (href) {
        event.preventDefault();
        window.location.href = href;
      }
    }
  });

  /* ------------------------------------------------------------------
     Back to top
     ------------------------------------------------------------------ */
  document.querySelectorAll("[data-top]").forEach(function (link) {
    link.addEventListener("click", function (event) {
      event.preventDefault();
      const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      window.scrollTo({ top: 0, behavior: reduce ? "auto" : "smooth" });
    });
  });
})();
