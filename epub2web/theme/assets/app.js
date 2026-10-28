/* epub2web reader */
(function () {
  "use strict";

  const root = document.documentElement;
  const body = document.body;
  const basePath = root.dataset.base || "";

  function withBase(path) {
    if (!path) return basePath + "/";
    if (/^(?:[a-z][a-z0-9+.-]*:|\/\/)/i.test(path)) return path;
    if (path.charAt(0) !== "/") return path;
    if (basePath && (path === basePath || path.indexOf(basePath + "/") === 0)) return path;
    return basePath + path;
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
  const lightbox = document.getElementById("epub2web-lightbox");
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
  }
  if (searchResults) {
    searchResults.addEventListener("click", function (event) {
      if (event.target.closest("a") && searchDialog) searchDialog.close();
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
