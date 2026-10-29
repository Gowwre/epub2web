/* epub2web reader */
(function () {
  "use strict";

  const root = document.documentElement;
  const body = document.body;
  const basePath = root.dataset.base || "";
  const readingId = (root.dataset.readingId || "").trim();
  const progressKey = readingId ? "epub2web:progress:v1:" + readingId : "";
  const isReading = body.hasAttribute("data-reading");
  const pageKey = isReading ? (body.dataset.pageKey || "").trim() : "";
  const chapterKey = isReading ? (body.dataset.chapterKey || "").trim() : "";
  const progressStart = isReading ? parseFloat(body.dataset.progressStart || "0") : 0;
  const progressEnd = isReading ? parseFloat(body.dataset.progressEnd || "1") : 1;

  function withBase(path) {
    if (!path) return basePath + "/";
    if (/^(?:[a-z][a-z0-9+.-]*:|\/\/)/i.test(path)) return path;
    if (path.charAt(0) !== "/") return path;
    if (basePath && (path === basePath || path.indexOf(basePath + "/") === 0)) return path;
    return basePath + path;
  }

  function readProgress() {
    if (!progressKey) return null;
    let raw;
    try {
      raw = localStorage.getItem(progressKey);
    } catch (e) {
      return null;
    }
    if (!raw) return null;
    try {
      const data = JSON.parse(raw);
      if (!data || data.v !== 1) return null;
      if (typeof data.pageKey !== "string" || !data.pageKey) return null;
      if (typeof data.ratio !== "number" || !isFinite(data.ratio)) return null;
      return data;
    } catch (e) {
      try { localStorage.removeItem(progressKey); } catch (e2) {}
      return null;
    }
  }

  function writeProgress(data) {
    if (!progressKey) return;
    try { localStorage.setItem(progressKey, JSON.stringify(data)); } catch (e) {}
  }

  function clearProgress() {
    if (!progressKey) return;
    try { localStorage.removeItem(progressKey); } catch (e) {}
  }

  function currentScrollRatio() {
    const doc = document.documentElement;
    const max = doc.scrollHeight - doc.clientHeight;
    return max > 0 ? Math.min(1, Math.max(0, doc.scrollTop / max)) : 0;
  }

  function currentBookRatio() {
    const start = isFinite(progressStart) ? Math.min(1, Math.max(0, progressStart)) : 0;
    const end = isFinite(progressEnd) ? Math.min(1, Math.max(start, progressEnd)) : 1;
    return start + (end - start) * currentScrollRatio();
  }

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
      try { localStorage.setItem("epub2web-theme", next); } catch (e) {}
      syncThemeLabel();
    });
  }

  /* ------------------------------------------------------------------
     Dialogs
     ------------------------------------------------------------------ */
  const menuDialog = document.getElementById("epub2web-menu-dialog");
  const searchDialog = document.getElementById("epub2web-search-dialog");
  const readerDialog = document.getElementById("epub2web-reader-dialog");
  const lightbox = document.getElementById("epub2web-lightbox");
  let lastFocus = null;

  function openDialog(dialog) {
    if (!dialog) return;
    document.querySelectorAll("dialog[open]").forEach(function (open) {
      if (open !== dialog) open.close();
    });
    lastFocus = document.activeElement;
    if (!dialog.open) dialog.showModal();
  }

  function closeDialog(dialog) {
    if (dialog && dialog.open) dialog.close();
  }

  function scrollMenuToCurrent() {
    if (!menuDialog) return;
    const current = menuDialog.querySelector("[data-menu-current]");
    const sheetBody = menuDialog.querySelector(".sheet-body");
    if (!current || !sheetBody) return;
    const bodyRect = sheetBody.getBoundingClientRect();
    const currentRect = current.getBoundingClientRect();
    const target =
      sheetBody.scrollTop +
      currentRect.top -
      bodyRect.top -
      (sheetBody.clientHeight - currentRect.height) / 2;
    sheetBody.scrollTop = Math.max(0, target);
  }

  document.querySelectorAll("[data-menu-open]").forEach(function (button) {
    button.addEventListener("click", function () {
      openDialog(menuDialog);
      window.requestAnimationFrame(scrollMenuToCurrent);
    });
  });
  document.querySelectorAll("[data-search-open]").forEach(function (button) {
    button.addEventListener("click", function () {
      openSearch();
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
     Reading settings
     ------------------------------------------------------------------ */
  const readerKey = "epub2web-reader:v1";
  const readerSizes = ["small", "default", "large", "x-large"];
  const readerSpacings = ["compact", "default", "relaxed"];
  const readerInputs = readerDialog
    ? readerDialog.querySelectorAll('input[name="reader-size"], input[name="reader-spacing"]')
    : [];
  const readerReset = readerDialog ? readerDialog.querySelector("[data-reader-reset]") : null;

  function defaultReaderSettings() {
    return { size: "default", spacing: "default" };
  }

  function readReaderSettings() {
    const settings = defaultReaderSettings();
    let raw;
    try {
      raw = localStorage.getItem(readerKey);
    } catch (e) {
      return settings;
    }
    if (!raw) return settings;
    try {
      const saved = JSON.parse(raw);
      if (!saved || typeof saved !== "object") return settings;
      if (readerSizes.indexOf(saved.size) !== -1) settings.size = saved.size;
      if (readerSpacings.indexOf(saved.spacing) !== -1) settings.spacing = saved.spacing;
    } catch (e) {
      try { localStorage.removeItem(readerKey); } catch (e2) {}
    }
    return settings;
  }

  function applyReaderSettings(settings) {
    if (settings.size === "default") root.removeAttribute("data-reader-size");
    else root.setAttribute("data-reader-size", settings.size);
    if (settings.spacing === "default") root.removeAttribute("data-reader-spacing");
    else root.setAttribute("data-reader-spacing", settings.spacing);
  }

  function writeReaderSettings(settings) {
    try { localStorage.setItem(readerKey, JSON.stringify(settings)); } catch (e) {}
  }

  function syncReaderInputs(settings) {
    if (!readerDialog) return;
    readerDialog.querySelectorAll('input[name="reader-size"]').forEach(function (input) {
      input.checked = input.value === settings.size;
    });
    readerDialog.querySelectorAll('input[name="reader-spacing"]').forEach(function (input) {
      input.checked = input.value === settings.spacing;
    });
  }

  function currentReaderSettings() {
    const settings = defaultReaderSettings();
    if (!readerDialog) return settings;
    const size = readerDialog.querySelector('input[name="reader-size"]:checked');
    const spacing = readerDialog.querySelector('input[name="reader-spacing"]:checked');
    if (size && readerSizes.indexOf(size.value) !== -1) settings.size = size.value;
    if (spacing && readerSpacings.indexOf(spacing.value) !== -1) settings.spacing = spacing.value;
    return settings;
  }

  applyReaderSettings(readReaderSettings());

  document.querySelectorAll("[data-reader-open]").forEach(function (button) {
    button.addEventListener("click", function () {
      syncReaderInputs(readReaderSettings());
      openDialog(readerDialog);
    });
  });

  readerInputs.forEach(function (input) {
    input.addEventListener("change", function () {
      const settings = currentReaderSettings();
      writeReaderSettings(settings);
      applyReaderSettings(settings);
    });
  });

  if (readerReset) {
    readerReset.addEventListener("click", function () {
      try { localStorage.removeItem(readerKey); } catch (e) {}
      const settings = defaultReaderSettings();
      applyReaderSettings(settings);
      syncReaderInputs(settings);
    });
  }

  window.addEventListener("storage", function (event) {
    if (event.key !== readerKey && event.key !== null) return;
    const settings = readReaderSettings();
    applyReaderSettings(settings);
    if (readerDialog && readerDialog.open) syncReaderInputs(settings);
  });

  /* ------------------------------------------------------------------
     Search (built-in index, loaded on first use)
     ------------------------------------------------------------------ */
  const searchInput = document.getElementById("epub2web-book-search");
  const searchResults = document.getElementById("epub2web-search-results");
  const searchStatus = document.getElementById("epub2web-search-status");
  let searchIndex = null;
  let searchPromise = null;
  let searchTimer = null;

  function highlight(text, query) {
    const fragment = document.createDocumentFragment();
    if (!query) {
      fragment.append(document.createTextNode(text));
      return fragment;
    }
    const lower = text.toLowerCase();
    const needle = query.toLowerCase();
    let index = 0;
    while (true) {
      const found = lower.indexOf(needle, index);
      if (found === -1) {
        fragment.append(document.createTextNode(text.slice(index)));
        break;
      }
      if (found > index) fragment.append(document.createTextNode(text.slice(index, found)));
      const mark = document.createElement("mark");
      mark.textContent = text.slice(found, found + needle.length);
      fragment.append(mark);
      index = found + needle.length;
    }
    return fragment;
  }

  function snippet(text, query) {
    const lower = text.toLowerCase();
    const needle = query.toLowerCase();
    const pos = lower.indexOf(needle);
    if (pos < 0) return text.slice(0, 160) + (text.length > 160 ? "…" : "");
    const start = Math.max(0, pos - 50);
    const end = Math.min(text.length, pos + needle.length + 110);
    return (start > 0 ? "…" : "") + text.slice(start, end) + (end < text.length ? "…" : "");
  }

  function renderSearch() {
    if (!searchResults || !searchStatus) return;
    const query = (searchInput ? searchInput.value : "").trim();
    searchResults.replaceChildren();
    if (!query) {
      searchStatus.textContent = searchIndex
        ? searchIndex.length.toLocaleString() + " sections indexed. Type to search."
        : "Type a word or phrase.";
      return;
    }
    if (!searchIndex) {
      searchStatus.textContent = "Loading the search index…";
      return;
    }
    const needle = query.toLowerCase();
    const allMatches = searchIndex
      .map(function (entry) {
        const titleMatch = entry.title.toLowerCase().includes(needle);
        const textMatch = entry.text.toLowerCase().includes(needle);
        if (!titleMatch && !textMatch) return null;
        return { entry: entry, score: (titleMatch ? 3 : 0) + (textMatch ? 1 : 0) };
      })
      .filter(Boolean)
      .sort(function (a, b) { return b.score - a.score; });
    const matches = allMatches.slice(0, 20);
    if (!matches.length) {
      searchStatus.textContent = "No matches for “" + query + "”.";
      return;
    }
    searchStatus.textContent =
      allMatches.length +
      " result" +
      (allMatches.length === 1 ? "" : "s") +
      " for “" +
      query +
      "”" +
      (allMatches.length > matches.length ? " · showing the first 20" : "") +
      ".";
    matches.forEach(function (match) {
      const entry = match.entry;
      const link = document.createElement("a");
      link.className = "search-result";
      link.href = withBase(entry.href);
      const meta = document.createElement("span");
      meta.className = "search-result-meta";
      meta.textContent = entry.chapter;
      const title = document.createElement("span");
      title.className = "search-result-title";
      title.append(highlight(entry.title, query));
      const body = document.createElement("span");
      body.className = "search-result-snippet";
      body.append(highlight(snippet(entry.text, query), query));
      link.append(meta, title, body);
      searchResults.append(link);
    });
  }

  function searchResultLinks() {
    if (!searchResults) return [];
    return Array.from(searchResults.querySelectorAll("a.search-result"));
  }

  function loadSearch() {
    if (searchIndex) return Promise.resolve(searchIndex);
    if (searchPromise) return searchPromise;
    if (searchStatus) searchStatus.textContent = "Loading the search index…";
    searchPromise = fetch(withBase("/search-index.json"), { credentials: "same-origin" })
      .then(function (response) {
        if (!response.ok) throw new Error("search index missing");
        return response.json();
      })
      .then(function (data) {
        searchIndex = data;
        renderSearch();
        return data;
      })
      .catch(function () {
        searchIndex = null;
        if (searchStatus) {
          searchStatus.textContent =
            "Search index unavailable. Serve the site with `epub2web --serve`.";
        }
        return null;
      });
    return searchPromise;
  }

  function openSearch() {
    openDialog(searchDialog);
    loadSearch().then(function () {
      if (searchInput) {
        searchInput.focus();
        searchInput.select();
      }
      renderSearch();
    });
  }

  if (searchInput) {
    searchInput.addEventListener("input", function () {
      window.clearTimeout(searchTimer);
      searchTimer = window.setTimeout(renderSearch, 80);
    });
    searchInput.addEventListener("keydown", function (event) {
      if (event.key !== "ArrowDown" && event.key !== "Enter") return;
      window.clearTimeout(searchTimer);
      renderSearch();
      const links = searchResultLinks();
      if (!links.length) return;
      event.preventDefault();
      if (event.key === "Enter") links[0].click();
      else links[0].focus();
    });
  }
  if (searchResults) {
    searchResults.addEventListener("click", function (event) {
      if (event.target.closest("a") && searchDialog) searchDialog.close();
    });
    searchResults.addEventListener("keydown", function (event) {
      if (event.key !== "ArrowDown" && event.key !== "ArrowUp") return;
      const link = event.target.closest("a.search-result");
      if (!link) return;
      const links = searchResultLinks();
      const index = links.indexOf(link);
      if (index === -1) return;
      event.preventDefault();
      if (event.key === "ArrowUp" && index === 0) {
        if (searchInput) searchInput.focus();
        return;
      }
      const next = links[index + (event.key === "ArrowDown" ? 1 : -1)];
      if (next) next.focus();
    });
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
     Reading progress
     ------------------------------------------------------------------ */
  const progressBar = document.querySelector(".progress span");
  let saveTimer = null;
  let userMoved = false;
  const storedAtLoad = isReading ? readProgress() : null;

  function savePosition() {
    if (!isReading || !pageKey || !progressKey) return;
    const ratio = currentScrollRatio();
    if (!userMoved && ratio <= 0) return;
    const data = {
      v: 1,
      pageKey: pageKey,
      ratio: Math.round(ratio * 10000) / 10000,
      updatedAt: Date.now(),
    };
    if (chapterKey) data.chapterKey = chapterKey;
    writeProgress(data);
  }

  function scheduleSave() {
    if (!isReading || !pageKey || !progressKey || saveTimer !== null) return;
    saveTimer = window.setTimeout(function () {
      saveTimer = null;
      savePosition();
    }, 500);
  }

  if (isReading && pageKey && progressKey) {
    window.addEventListener("scroll", scheduleSave, { passive: true });
    window.addEventListener("pagehide", savePosition);
    document.addEventListener("visibilitychange", function () {
      if (document.visibilityState === "hidden") savePosition();
    });
    ["wheel", "touchstart", "keydown", "mousedown"].forEach(function (type) {
      window.addEventListener(type, function () { userMoved = true; }, { passive: true, once: true });
    });
  }

  if (progressBar && isReading) {
    let ticking = false;
    function updateProgress() {
      progressBar.style.width = (currentBookRatio() * 100).toFixed(2) + "%";
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

  function removeContinueParam() {
    try {
      const url = new URL(window.location.href);
      if (url.searchParams.get("continue") !== "1") return;
      url.searchParams.delete("continue");
      const query = url.searchParams.toString();
      history.replaceState(null, "", url.pathname + (query ? "?" + query : "") + url.hash);
    } catch (e) {}
  }

  function navigationType() {
    try {
      const perf = window.performance;
      if (!perf) return "navigate";
      const entries = perf.getEntriesByType ? perf.getEntriesByType("navigation") : [];
      if (entries && entries.length && entries[0].type) return entries[0].type;
      if (perf.navigation) {
        if (perf.navigation.type === 1) return "reload";
        if (perf.navigation.type === 2) return "back_forward";
      }
    } catch (e) {}
    return "navigate";
  }

  function applyScrollRatio(ratio) {
    function apply() {
      if (userMoved) return;
      const doc = document.documentElement;
      const max = doc.scrollHeight - doc.clientHeight;
      if (max <= 0) return;
      const top = Math.min(max, Math.max(0, ratio * max));
      const previous = doc.style.scrollBehavior;
      doc.style.scrollBehavior = "auto";
      window.scrollTo(0, top);
      window.requestAnimationFrame(function () {
        if (previous) doc.style.scrollBehavior = previous;
        else doc.style.removeProperty("scroll-behavior");
      });
    }
    apply();
    if (document.readyState === "complete") apply();
    else window.addEventListener("load", apply, { once: true });
    if (document.fonts && document.fonts.ready) {
      document.fonts.ready.then(function () { window.requestAnimationFrame(apply); });
    }
  }

  if (isReading && pageKey && progressKey && storedAtLoad) {
    const wantsContinue = new URLSearchParams(window.location.search).get("continue") === "1";
    if (wantsContinue) removeContinueParam();
    const navType = navigationType();
    const shouldRestore = !window.location.hash
      && (wantsContinue || navType === "reload" || navType === "back_forward");
    if (shouldRestore && storedAtLoad.pageKey === pageKey) {
      if ("scrollRestoration" in history) history.scrollRestoration = "manual";
      applyScrollRatio(Math.min(1, Math.max(0, storedAtLoad.ratio)));
    }
  } else if (isReading) {
    removeContinueParam();
  }

  /* ------------------------------------------------------------------
     Continue reading
     ------------------------------------------------------------------ */
  if (!isReading && readingId && progressKey) {
    const startLink = document.querySelector("[data-reading-start]");
    const startLabel = document.querySelector("[data-reading-label]");
    const restart = document.querySelector("[data-reading-restart]");
    const mapElement = document.getElementById("epub2web-reading-map");
    const defaultHref = startLink ? startLink.getAttribute("href") : "";
    const defaultLabel = startLabel ? startLabel.textContent : "";

    function resetHomeContinue() {
      if (!startLink || !startLabel) return;
      if (defaultHref) startLink.setAttribute("href", defaultHref);
      startLink.removeAttribute("aria-label");
      startLink.removeAttribute("title");
      startLabel.textContent = defaultLabel || "Start reading";
      if (restart) restart.hidden = true;
    }

    function enhanceHomeContinue() {
      if (!startLink || !startLabel) return;
      const stored = readProgress();
      if (!stored) {
        resetHomeContinue();
        return;
      }
      let map = [];
      if (mapElement) {
        try {
          map = JSON.parse(mapElement.textContent || "[]");
        } catch (e) {
          map = [];
        }
      }
      let entry = null;
      if (map.length) {
        entry = map.find(function (item) { return item.key === stored.pageKey; }) || null;
        if (!entry && stored.chapterKey) {
          entry = map.find(function (item) { return item.chapterKey === stored.chapterKey; }) || null;
        }
      }
      if (!entry) {
        resetHomeContinue();
        return;
      }
      const continueHref = withBase(entry.route);
      startLink.href = continueHref + (continueHref.indexOf("?") === -1 ? "?continue=1" : "&continue=1");
      const description = entry.label ? "Continue reading: " + entry.label : "Continue reading";
      startLink.setAttribute("aria-label", description);
      startLink.title = description;
      startLabel.textContent = description.length <= 42 ? description : "Continue reading";
      if (restart) restart.hidden = false;
    }

    if (startLink && startLabel) {
      enhanceHomeContinue();
      window.addEventListener("pageshow", function (event) {
        if (event.persisted) enhanceHomeContinue();
      });
      document.addEventListener("visibilitychange", function () {
        if (document.visibilityState === "visible") enhanceHomeContinue();
      });
      window.addEventListener("storage", function (event) {
        if (event.key === progressKey) enhanceHomeContinue();
      });
    }

    if (restart) {
      restart.addEventListener("click", function () { clearProgress(); });
    }
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
      openSearch();
      return;
    }
    if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
      if (isTyping(event.target) || document.querySelector("dialog[open]")) return;
      const href = event.key === "ArrowLeft" ? body.getAttribute("data-prev") : body.getAttribute("data-next");
      if (href) {
        event.preventDefault();
        window.location.href = withBase(href);
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
