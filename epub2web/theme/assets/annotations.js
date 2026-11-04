/* epub2web highlights and notes */
(function () {
  "use strict";

  const root = document.documentElement;
  const body = document.body;
  const bookPage = document.querySelector(".book-page");
  if (!body.hasAttribute("data-reading") || !bookPage) return;

  const contentId = (root.dataset.contentId || "").trim();
  const sourceSha256 = (root.dataset.readingId || "").trim();
  const pageKey = (body.dataset.pageKey || "").trim();
  if (!contentId || !pageKey) return;

  const basePath = root.dataset.base || "";
  const chapterKey = (body.dataset.chapterKey || "").trim();
  const progressStart = parseFloat(body.dataset.progressStart || "0");
  const progressEnd = parseFloat(body.dataset.progressEnd || "1");

  const SCHEMA = "epub2web.annotations";
  const VERSION = 1;
  const DB_NAME = "epub2web-annotations";
  const DB_VERSION = 1;
  const LOCAL_PREFIX = "epub2web:annotations:v1:";
  const COLOR_KEY = "epub2web:annotations:color";
  const COLORS = ["yellow", "green", "blue", "pink", "purple"];

  const toolbar = document.getElementById("epub2web-annotation-toolbar");
  const toolbarColors = document.querySelector("[data-annotation-colors]");
  const colorToggle = document.querySelector("[data-annotation-color-toggle]");
  const openButton = document.querySelector("[data-annotations-open]");
  const countBadge = document.querySelector("[data-annotations-count]");
  const noteDialog = document.getElementById("epub2web-note-dialog");
  const noteQuote = document.querySelector("[data-note-quote]");
  const noteText = document.getElementById("epub2web-note-text");
  const noteTitle = document.getElementById("epub2web-note-title");
  const noteSave = document.querySelector("[data-note-save]");
  const noteRemove = document.querySelector("[data-note-remove]");
  const noteError = document.querySelector("[data-note-error]");
  const card = document.getElementById("epub2web-highlight-card");
  const cardQuote = document.querySelector("[data-highlight-quote]");
  const cardNote = document.querySelector("[data-highlight-note]");
  const cardMeta = document.querySelector("[data-highlight-meta]");
  const cardEdit = document.querySelector("[data-highlight-edit]");
  const cardColors = document.querySelector("[data-highlight-colors]");
  const cardColorToggle = document.querySelector("[data-highlight-color-toggle]");
  const panel = document.getElementById("epub2web-annotations-dialog");
  const panelList = document.querySelector("[data-annotations-list]");
  const panelEmpty = document.querySelector("[data-annotations-empty]");
  const panelStatus = document.querySelector("[data-annotations-status]");
  const panelTotal = document.querySelector("[data-annotations-total]");
  const fileInput = document.querySelector("[data-annotations-file]");
  const storageDialog = document.getElementById("epub2web-storage-dialog");
  const storageState = document.querySelector("[data-storage-state]");
  const storageRequest = document.querySelector("[data-storage-request]");

  const bookMeta = readJsonScript("epub2web-book-meta", {});
  const readingMap = readJsonScript("epub2web-reading-map", []);

  const state = {
    annotations: new Map(),
    resolved: new Map(),
    markers: [],
    selection: null,
    note: null,
    cardId: "",
    cardPoint: null,
    filter: "all",
    lastColor: "yellow",
    db: null,
    mode: "",
    bookSaved: false,
    storageError: false,
    storageBusy: false,
    ready: false,
    channel: null,
    panelReturnFocus: null,
    cardReturnFocus: null,
    noteReturnFocus: null,
  };

  let saveChain = Promise.resolve();
  let toast = null;
  let toastAction = null;
  let toastTimer = null;
  let markerLayer = null;
  let markerFrame = null;

  /* ------------------------------------------------------------------
     Utilities
     ------------------------------------------------------------------ */

  function isPlainObject(value) {
    return Boolean(value) && typeof value === "object" && !Array.isArray(value);
  }

  function clamp(value, minimum, maximum) {
    return Math.min(Math.max(value, minimum), maximum);
  }

  function withBase(path) {
    if (!path) return basePath + "/";
    if (/^(?:[a-z][a-z0-9+.-]*:|\/\/)/i.test(path)) return path;
    if (path.charAt(0) !== "/") return path;
    if (basePath && (path === basePath || path.indexOf(basePath + "/") === 0)) return path;
    return basePath + path;
  }

  function debounce(fn, wait) {
    let timer = null;
    return function () {
      const args = arguments;
      window.clearTimeout(timer);
      timer = window.setTimeout(function () {
        fn.apply(null, args);
      }, wait);
    };
  }

  function nowIso() {
    return new Date().toISOString();
  }

  function newId() {
    if (window.crypto && typeof window.crypto.randomUUID === "function") {
      return window.crypto.randomUUID();
    }
    const bytes = new Uint8Array(16);
    if (window.crypto && window.crypto.getRandomValues) {
      window.crypto.getRandomValues(bytes);
    } else {
      for (let i = 0; i < bytes.length; i += 1) bytes[i] = Math.floor(Math.random() * 256);
    }
    bytes[6] = (bytes[6] & 0x0f) | 0x40;
    bytes[8] = (bytes[8] & 0x3f) | 0x80;
    const hex = Array.from(bytes)
      .map(function (byte) {
        return byte.toString(16).padStart(2, "0");
      })
      .join("");
    return (
      hex.slice(0, 8) +
      "-" +
      hex.slice(8, 12) +
      "-" +
      hex.slice(12, 16) +
      "-" +
      hex.slice(16, 20) +
      "-" +
      hex.slice(20)
    );
  }

  function validIso(value) {
    return typeof value === "string" && value.length > 0 && !Number.isNaN(Date.parse(value));
  }

  function formatDate(value) {
    if (!validIso(value)) return "";
    try {
      return new Intl.DateTimeFormat(undefined, {
        day: "numeric",
        month: "short",
        year: "numeric",
      }).format(new Date(value));
    } catch (error) {
      return "";
    }
  }

  function colorValue(color) {
    return "var(--hl-" + (COLORS.indexOf(color) === -1 ? "yellow" : color) + ")";
  }

  function readJsonScript(id, fallback) {
    const element = document.getElementById(id);
    if (!element) return fallback;
    try {
      const parsed = JSON.parse(element.textContent || "null");
      return parsed === null || parsed === undefined ? fallback : parsed;
    } catch (error) {
      return fallback;
    }
  }

  function isTyping(target) {
    if (!target) return false;
    const tag = target.tagName ? target.tagName.toLowerCase() : "";
    return tag === "input" || tag === "textarea" || tag === "select" || target.isContentEditable;
  }

  function headerHeight() {
    const value = parseInt(getComputedStyle(root).getPropertyValue("--header-h"), 10);
    return Number.isFinite(value) ? value : 64;
  }

  function focusElement(target) {
    if (target && target.isConnected && !target.closest("[hidden]")) {
      target.focus({ preventScroll: true });
      return;
    }
    if (bookPage) bookPage.focus({ preventScroll: true });
  }

  function normalizeWhitespace(value) {
    return String(value || "")
      .replace(/\s+/g, " ")
      .trim();
  }

  function normalizeWithMap(value) {
    const text = String(value || "");
    const output = [];
    const map = [];
    let pendingSpace = false;
    for (let i = 0; i < text.length; i += 1) {
      const character = text.charAt(i);
      if (/\s/.test(character)) {
        pendingSpace = output.length > 0;
        continue;
      }
      if (pendingSpace) {
        output.push(" ");
        map.push(i);
        pendingSpace = false;
      }
      output.push(character);
      map.push(i);
    }
    return { text: output.join(""), map: map };
  }

  function clone(value) {
    return JSON.parse(JSON.stringify(value));
  }

  function activeAnnotations() {
    return Array.from(state.annotations.values()).filter(function (annotation) {
      return !annotation.deleted;
    });
  }

  function colorButtons(container, attribute) {
    return Array.from(container.querySelectorAll("[" + attribute + "]"));
  }

  /* ------------------------------------------------------------------
     Annotation shape and merge
     ------------------------------------------------------------------ */

  function normalizePosition(raw) {
    if (!isPlainObject(raw)) return null;
    const position = {};
    if (typeof raw.dom_path === "string") position.dom_path = raw.dom_path;
    if (typeof raw.cfi === "string") position.cfi = raw.cfi;
    for (const key of ["offset", "char"]) {
      if (Number.isInteger(raw[key]) && raw[key] >= 0) position[key] = raw[key];
    }
    return Object.keys(position).length ? position : null;
  }

  function normalizeAnchor(raw) {
    if (!isPlainObject(raw)) return {};
    const anchor = {};
    for (const key of ["page_key", "chapter_key", "spine_href", "cfi", "prefix", "suffix"]) {
      if (typeof raw[key] === "string") anchor[key] = raw[key];
    }
    if (Number.isInteger(raw.spine_index) && raw.spine_index >= 0) {
      anchor.spine_index = raw.spine_index;
    }
    if (typeof raw.progression === "number" && raw.progression >= 0 && raw.progression <= 1) {
      anchor.progression = raw.progression;
    }
    for (const key of ["start", "end"]) {
      const position = normalizePosition(raw[key]);
      if (position) anchor[key] = position;
    }
    return anchor;
  }

  function validateAnnotation(raw) {
    if (!isPlainObject(raw)) return null;
    if (typeof raw.id !== "string" || !raw.id) return null;
    if (raw.type !== "highlight" && raw.type !== "bookmark") return null;
    const updated = validIso(raw.updated) ? raw.updated : raw.created;
    if (!validIso(updated)) return null;
    const created = validIso(raw.created) ? raw.created : updated;
    const style = isPlainObject(raw.style) ? raw.style : {};
    const color = typeof style.color === "string" ? style.color : "yellow";
    const annotation = {
      id: raw.id,
      type: raw.type,
      created: created,
      updated: updated,
      deleted: raw.deleted === true,
      note: typeof raw.note === "string" ? raw.note : "",
      quote: typeof raw.quote === "string" ? raw.quote : "",
      style: { color: COLORS.indexOf(color) === -1 ? "yellow" : color },
      anchor: normalizeAnchor(raw.anchor),
    };
    if (isPlainObject(raw.origin)) {
      annotation.origin = {};
      if (typeof raw.origin.app === "string") annotation.origin.app = raw.origin.app;
      if (typeof raw.origin.id === "string") annotation.origin.id = raw.origin.id;
      if (raw.origin.raw !== undefined) annotation.origin.raw = raw.origin.raw;
    }
    if (raw.needs_review === true) annotation.needs_review = true;
    if (typeof raw.review_reason === "string" && raw.review_reason) {
      annotation.review_reason = raw.review_reason;
    }
    return annotation;
  }

  function validateImportedDocument(raw) {
    if (!isPlainObject(raw)) return null;
    if (raw.schema !== SCHEMA || raw.version !== VERSION) return null;
    if (!isPlainObject(raw.book) || typeof raw.book.content_id !== "string") return null;
    if (!Array.isArray(raw.annotations)) return null;
    const annotations = [];
    const ids = new Set();
    const origins = new Set();
    for (const item of raw.annotations) {
      const record = validateAnnotation(item);
      if (!record || ids.has(record.id)) return null;
      ids.add(record.id);
      const origin = record.origin || {};
      if (origin.app && origin.id) {
        const key = origin.app + "\u0000" + origin.id;
        if (origins.has(key)) return null;
        origins.add(key);
      }
      annotations.push(record);
    }
    return { book: raw.book, annotations: annotations };
  }

  function hasAnchor(annotation) {
    const anchor = annotation.anchor || {};
    return Boolean(
      anchor.start || anchor.end || anchor.cfi || anchor.page_key || annotation.quote
    );
  }

  function findByOrigin(record) {
    const origin = record.origin || {};
    if (!origin.app || !origin.id) return null;
    for (const annotation of state.annotations.values()) {
      const candidate = annotation.origin || {};
      if (candidate.app === origin.app && candidate.id === origin.id) return annotation;
    }
    return null;
  }

  function mergeIntoState(record) {
    const current = state.annotations.get(record.id) || findByOrigin(record);
    if (!current) {
      state.annotations.set(record.id, record);
      return { changed: true, added: true, annotation: record };
    }
    const currentTime = Date.parse(current.updated);
    const incomingTime = Date.parse(record.updated);
    const replace =
      incomingTime > currentTime ||
      (incomingTime === currentTime && hasAnchor(record) && !hasAnchor(current));
    if (!replace) return { changed: false, added: false, annotation: current };
    const replacement = Object.assign({}, record, { id: current.id });
    state.annotations.set(replacement.id, replacement);
    return { changed: true, added: false, annotation: replacement };
  }

  /* ------------------------------------------------------------------
     Storage: IndexedDB first, localStorage fallback
     ------------------------------------------------------------------ */

  function localKey() {
    return LOCAL_PREFIX + contentId;
  }

  function bookRecord() {
    return {
      content_id: contentId,
      source_sha256: sourceSha256,
      title: typeof bookMeta.title === "string" ? bookMeta.title : "",
      author: typeof bookMeta.author === "string" ? bookMeta.author : "",
      isbn: typeof bookMeta.isbn === "string" ? bookMeta.isbn : "",
      aliases: [],
    };
  }

  function openDatabase() {
    return new Promise(function (resolve, reject) {
      if (!window.indexedDB) {
        reject(new Error("IndexedDB is unavailable"));
        return;
      }
      let request;
      try {
        request = window.indexedDB.open(DB_NAME, DB_VERSION);
      } catch (error) {
        reject(error);
        return;
      }
      request.onupgradeneeded = function () {
        const db = request.result;
        if (!db.objectStoreNames.contains("books")) {
          db.createObjectStore("books", { keyPath: "content_id" });
        }
        if (!db.objectStoreNames.contains("annotations")) {
          const store = db.createObjectStore("annotations", { keyPath: "id" });
          store.createIndex("content_id", "content_id", { unique: false });
          store.createIndex("updated", "updated", { unique: false });
        }
        if (!db.objectStoreNames.contains("meta")) {
          db.createObjectStore("meta", { keyPath: "key" });
        }
      };
      request.onsuccess = function () {
        resolve(request.result);
      };
      request.onerror = function () {
        reject(request.error || new Error("IndexedDB could not open"));
      };
      request.onblocked = function () {
        reject(new Error("IndexedDB is blocked"));
      };
    });
  }

  function idbGetAll(db, storeName, indexName, key) {
    return new Promise(function (resolve, reject) {
      let transaction;
      try {
        transaction = db.transaction(storeName, "readonly");
      } catch (error) {
        reject(error);
        return;
      }
      const request = transaction.objectStore(storeName).index(indexName).getAll(key);
      request.onsuccess = function () {
        resolve(request.result || []);
      };
      request.onerror = function () {
        reject(request.error || new Error("IndexedDB read failed"));
      };
    });
  }

  function idbPut(db, storeName, value) {
    return new Promise(function (resolve, reject) {
      let transaction;
      try {
        transaction = db.transaction(storeName, "readwrite");
      } catch (error) {
        reject(error);
        return;
      }
      transaction.objectStore(storeName).put(value);
      transaction.oncomplete = function () {
        resolve();
      };
      transaction.onerror = function () {
        reject(transaction.error || new Error("IndexedDB write failed"));
      };
      transaction.onabort = function () {
        reject(transaction.error || new Error("IndexedDB write aborted"));
      };
    });
  }

  function idbPutMany(db, storeName, values) {
    return new Promise(function (resolve, reject) {
      if (!values.length) {
        resolve();
        return;
      }
      let transaction;
      try {
        transaction = db.transaction(storeName, "readwrite");
      } catch (error) {
        reject(error);
        return;
      }
      const store = transaction.objectStore(storeName);
      values.forEach(function (value) {
        store.put(value);
      });
      transaction.oncomplete = function () {
        resolve();
      };
      transaction.onerror = function () {
        reject(transaction.error || new Error("IndexedDB write failed"));
      };
      transaction.onabort = function () {
        reject(transaction.error || new Error("IndexedDB write aborted"));
      };
    });
  }

  function readLocalAnnotations() {
    try {
      const raw = localStorage.getItem(localKey());
      if (!raw) return [];
      const data = JSON.parse(raw);
      if (
        !isPlainObject(data) ||
        data.schema !== SCHEMA ||
        data.version !== VERSION ||
        !Array.isArray(data.annotations)
      ) {
        return [];
      }
      return data.annotations.map(validateAnnotation).filter(Boolean);
    } catch (error) {
      return [];
    }
  }

  function writeLocalAnnotations() {
    const payload = {
      schema: SCHEMA,
      version: VERSION,
      book: bookRecord(),
      annotations: Array.from(state.annotations.values()),
    };
    localStorage.setItem(localKey(), JSON.stringify(payload));
  }

  function canPersistStorage() {
    return Boolean(navigator.storage && typeof navigator.storage.persist === "function");
  }

  async function storageIsPersisted() {
    try {
      if (navigator.storage && typeof navigator.storage.persisted === "function") {
        return await navigator.storage.persisted();
      }
    } catch (error) {}
    return false;
  }

  async function refreshStorageState() {
    if (!storageState || !storageRequest) return;
    if (!canPersistStorage()) {
      storageState.textContent =
        "This browser does not support persistent storage. Export a backup if you need a copy.";
      storageRequest.disabled = true;
      storageRequest.textContent = "Not supported";
      return;
    }
    storageRequest.disabled = false;
    storageRequest.textContent = "Ask browser to keep data";
    const persisted = await storageIsPersisted();
    if (persisted) {
      storageState.textContent =
        "This browser is already keeping this site’s data on this device.";
      storageRequest.disabled = true;
      storageRequest.textContent = "Already kept";
    } else {
      storageState.textContent = "Your browser may ask for permission when you continue.";
    }
  }

  function openStorageDialog() {
    if (!storageDialog) return;
    if (storageState) storageState.textContent = "Checking this browser…";
    if (storageRequest) storageRequest.disabled = true;
    if (!storageDialog.open) storageDialog.showModal();
    refreshStorageState();
  }

  async function requestPersistentStorage() {
    if (!storageRequest || !storageState || state.storageBusy) return;
    if (!canPersistStorage()) {
      refreshStorageState();
      return;
    }
    state.storageBusy = true;
    storageRequest.disabled = true;
    storageRequest.textContent = "Requesting…";
    storageState.textContent = "Waiting for your browser…";
    let granted = false;
    try {
      granted = await navigator.storage.persist();
    } catch (error) {
      granted = false;
    }
    state.storageBusy = false;
    if (granted) {
      storageState.textContent =
        "This browser will keep your highlights and notes on this device.";
      storageRequest.textContent = "Kept on this device";
      storageRequest.disabled = true;
    } else {
      storageState.textContent =
        "The browser did not grant persistent storage. Export a backup to keep a copy.";
      storageRequest.textContent = "Try again";
      storageRequest.disabled = false;
    }
  }

  async function persistRecord(record) {
    if (state.mode === "indexeddb" && state.db) {
      try {
        await idbPut(state.db, "annotations", record);
        if (!state.bookSaved) {
          await idbPut(state.db, "books", bookRecord());
          state.bookSaved = true;
        }
        return true;
      } catch (error) {
        state.mode = "local";
      }
    }
    try {
      writeLocalAnnotations();
      return true;
    } catch (error) {
      state.storageError = true;
      return false;
    }
  }

  function persist(annotation) {
    const record = Object.assign({}, annotation, { content_id: contentId });
    saveChain = saveChain
      .then(function () {
        return persistRecord(record);
      })
      .catch(function () {
        return false;
      });
    return saveChain;
  }

  function persistMany(annotations) {
    saveChain = saveChain
      .then(function () {
        return persistManyNow(annotations);
      })
      .catch(function () {
        return false;
      });
    return saveChain;
  }

  async function persistManyNow(annotations) {
    const payload = annotations.map(function (annotation) {
      return Object.assign({}, annotation, { content_id: contentId });
    });
    if (state.mode === "indexeddb" && state.db) {
      try {
        await idbPutMany(state.db, "annotations", payload);
        if (!state.bookSaved) {
          await idbPut(state.db, "books", bookRecord());
          state.bookSaved = true;
        }
        return true;
      } catch (error) {
        state.mode = "local";
      }
    }
    try {
      writeLocalAnnotations();
      return true;
    } catch (error) {
      state.storageError = true;
      return false;
    }
  }

  function broadcast(annotation) {
    if (!state.channel) return;
    try {
      state.channel.postMessage({ type: "annotation", annotation: annotation });
    } catch (error) {}
  }

  async function loadState() {
    let records = [];
    try {
      state.db = await openDatabase();
      state.mode = "indexeddb";
      records = await idbGetAll(state.db, "annotations", "content_id", contentId);
    } catch (error) {
      state.mode = "local";
    }

    const localRecords = readLocalAnnotations();
    if (localRecords.length) {
      if (!records.length) {
        records = localRecords;
      } else {
        const byId = new Map();
        records.forEach(function (record) {
          const valid = validateAnnotation(record);
          if (valid) byId.set(valid.id, valid);
        });
        localRecords.forEach(function (record) {
          const current = byId.get(record.id);
          if (!current || Date.parse(record.updated) > Date.parse(current.updated)) {
            byId.set(record.id, record);
          }
        });
        records = Array.from(byId.values());
      }
    }

    for (const raw of records) {
      const record = validateAnnotation(raw);
      if (!record) continue;
      const current = state.annotations.get(record.id);
      if (!current || Date.parse(record.updated) >= Date.parse(current.updated)) {
        state.annotations.set(record.id, record);
      }
    }

    if (state.mode === "indexeddb" && state.db && localRecords.length) {
      const payload = Array.from(state.annotations.values()).map(function (annotation) {
        return Object.assign({}, annotation, { content_id: contentId });
      });
      idbPutMany(state.db, "annotations", payload).catch(function () {});
    }

    state.ready = true;
    refresh();
  }

  function updateCount() {
    const count = activeAnnotations().length;
    if (countBadge) {
      countBadge.textContent = String(count);
      countBadge.hidden = count === 0;
    }
    if (panelTotal) panelTotal.textContent = count ? String(count) : "";
    if (openButton) {
      const label = count
        ? "Highlights and notes, " + count + (count === 1 ? " item" : " items")
        : "Highlights and notes";
      openButton.setAttribute("aria-label", label);
    }
  }

  /* ------------------------------------------------------------------
     DOM ranges and anchor resolution
     ------------------------------------------------------------------ */

  function resolveDomPath(container, path) {
    if (typeof path !== "string" || path.charAt(0) !== "/") return null;
    const parts = path.split("/").filter(Boolean);
    let node = container;
    for (const part of parts) {
      const textMatch = /^text\(\)\[(\d+)\]$/.exec(part);
      if (textMatch) {
        const wanted = parseInt(textMatch[1], 10);
        let index = 0;
        let found = null;
        for (const child of node.childNodes) {
          if (child.nodeType === 3) {
            index += 1;
            if (index === wanted) {
              found = child;
              break;
            }
          }
        }
        if (!found) return null;
        node = found;
        continue;
      }
      const elementMatch = /^([a-z0-9-]+)\[(\d+)\]$/i.exec(part);
      if (!elementMatch) return null;
      const tag = elementMatch[1].toLowerCase();
      const wanted = parseInt(elementMatch[2], 10);
      let index = 0;
      let found = null;
      for (const child of node.children) {
        if (child.tagName.toLowerCase() === tag) {
          index += 1;
          if (index === wanted) {
            found = child;
            break;
          }
        }
      }
      if (!found) return null;
      node = found;
    }
    return node;
  }

  function elementPath(container, element) {
    if (!element || element === container) return "";
    const parts = [];
    let current = element;
    while (current && current !== container) {
      if (current.nodeType !== 1 || !current.parentNode) return "";
      const tag = current.tagName.toLowerCase();
      let index = 0;
      for (const sibling of current.parentNode.children) {
        if (sibling.tagName.toLowerCase() === tag) {
          index += 1;
          if (sibling === current) break;
        }
      }
      parts.unshift(tag + "[" + index + "]");
      current = current.parentNode;
    }
    if (current !== container) return "";
    return "/" + parts.join("/");
  }

  function nodePath(container, node) {
    if (!node) return "";
    if (node.nodeType === 3) {
      const parent = node.parentNode;
      if (!parent || !container.contains(parent)) return "";
      const parentPath = elementPath(container, parent);
      if (!parentPath) return "";
      let index = 0;
      for (const child of parent.childNodes) {
        if (child.nodeType === 3) {
          index += 1;
          if (child === node) break;
        }
      }
      return parentPath + "/text()[" + index + "]";
    }
    if (node.nodeType === 1) return elementPath(container, node);
    return "";
  }

  function setRangePoint(range, which, node, offset) {
    if (!node) return false;
    const value = Number.isInteger(offset) ? offset : 0;
    const maximum = node.nodeType === 3 ? node.nodeValue.length : node.childNodes.length;
    const safe = clamp(value, 0, maximum);
    if (which === "start") range.setStart(node, safe);
    else range.setEnd(node, safe);
    return true;
  }

  function rangeMatchesQuote(range, quote) {
    if (!quote) return true;
    return normalizeWhitespace(range.toString()) === normalizeWhitespace(quote);
  }

  function rangeFromAnchor(annotation) {
    const anchor = annotation.anchor || {};
    const start = anchor.start;
    const end = anchor.end;
    if (!start || !start.dom_path) return null;
    const startNode = resolveDomPath(bookPage, start.dom_path);
    if (!startNode) return null;
    const endNode = end && end.dom_path ? resolveDomPath(bookPage, end.dom_path) : startNode;
    if (!endNode) return null;
    const range = document.createRange();
    try {
      setRangePoint(range, "start", startNode, start.offset);
      setRangePoint(range, "end", endNode, end.offset);
    } catch (error) {
      return null;
    }
    if (range.collapsed) return range;
    return rangeMatchesQuote(range, annotation.quote) ? range : null;
  }

  function rangeFromOffsets(container, start, end) {
    const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT, {
      acceptNode: function (node) {
        return node.nodeValue && node.nodeValue.length
          ? NodeFilter.FILTER_ACCEPT
          : NodeFilter.FILTER_REJECT;
      },
    });
    let node;
    let position = 0;
    let startNode = null;
    let startOffset = 0;
    let endNode = null;
    let endOffset = 0;
    while ((node = walker.nextNode())) {
      const length = node.nodeValue.length;
      if (startNode === null && start <= position + length) {
        startNode = node;
        startOffset = Math.max(0, start - position);
      }
      if (end <= position + length) {
        endNode = node;
        endOffset = Math.max(0, end - position);
        break;
      }
      position += length;
    }
    if (!startNode) {
      const last = document.createTreeWalker(container, NodeFilter.SHOW_TEXT).nextNode();
      if (!last) return null;
      startNode = last;
      startOffset = 0;
    }
    if (!endNode) {
      let last = null;
      const tail = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
      while ((node = tail.nextNode())) last = node;
      if (!last) return null;
      endNode = last;
      endOffset = last.nodeValue.length;
    }
    const range = document.createRange();
    try {
      range.setStart(startNode, startOffset);
      range.setEnd(endNode, endOffset);
    } catch (error) {
      return null;
    }
    return range;
  }

  function rangeFromQuote(quote, prefix, suffix) {
    const target = normalizeWithMap(quote);
    if (!target.text) return null;
    const page = normalizeWithMap(bookPage.textContent || "");
    if (!page.text) return null;
    const wantedPrefix = normalizeWithMap(prefix || "").text;
    const wantedSuffix = normalizeWithMap(suffix || "").text;

    let best = null;
    let bestScore = -1;
    let ties = 0;
    let index = page.text.indexOf(target.text);
    while (index !== -1) {
      let score = 0;
      if (wantedPrefix) {
        const start = Math.max(0, index - wantedPrefix.length);
        if (page.text.slice(start, index) === wantedPrefix) score += 2;
      }
      if (wantedSuffix) {
        const start = index + target.text.length;
        if (page.text.slice(start, start + wantedSuffix.length) === wantedSuffix) score += 2;
      }
      if (score > bestScore) {
        bestScore = score;
        best = index;
        ties = 1;
      } else if (score === bestScore) {
        ties += 1;
      }
      index = page.text.indexOf(target.text, index + 1);
    }
    if (best === null) return null;
    if (bestScore === 0 && ties > 1) return null;
    const start = page.map[best];
    const end = page.map[best + target.text.length - 1] + 1;
    return rangeFromOffsets(bookPage, start, end);
  }

  function resolveAnnotationRange(annotation) {
    const anchor = annotation.anchor || {};
    if (anchor.page_key && anchor.page_key !== pageKey) return null;
    if (!anchor.page_key && anchor.chapter_key && chapterKey && anchor.chapter_key !== chapterKey) {
      return null;
    }
    let range = rangeFromAnchor(annotation);
    if (!range && annotation.quote) {
      range = rangeFromQuote(annotation.quote, anchor.prefix, anchor.suffix);
    }
    return range;
  }

  /* ------------------------------------------------------------------
     Rendering
     ------------------------------------------------------------------ */

  function unwrapMarks() {
    document.querySelectorAll("mark.annotation-mark[data-annotation-id]").forEach(function (mark) {
      const parent = mark.parentNode;
      if (!parent) return;
      while (mark.firstChild) parent.insertBefore(mark.firstChild, mark);
      parent.removeChild(mark);
      if (parent.normalize) parent.normalize();
    });
  }

  function supportsHighlightApi() {
    return Boolean(window.CSS && CSS.highlights && typeof window.Highlight === "function");
  }

  function clearHighlightApi() {
    if (!supportsHighlightApi()) return;
    try {
      Array.from(CSS.highlights.keys()).forEach(function (name) {
        if (name.indexOf("epub2web-") === 0) CSS.highlights.delete(name);
      });
    } catch (error) {}
  }

  function paintHighlights() {
    clearHighlightApi();
    if (supportsHighlightApi()) {
      const groups = new Map();
      state.resolved.forEach(function (item) {
        if (!item.range || item.range.collapsed) return;
        const color = item.annotation.style.color || "yellow";
        if (!groups.has(color)) groups.set(color, []);
        groups.get(color).push(item.range);
      });
      groups.forEach(function (ranges, color) {
        try {
          CSS.highlights.set("epub2web-" + color, new Highlight(...ranges));
        } catch (error) {}
      });
      return;
    }

    state.resolved.forEach(function (item) {
      if (!item.range || item.range.collapsed) return;
      const mark = document.createElement("mark");
      mark.className = "annotation-mark";
      mark.dataset.annotationId = item.annotation.id;
      mark.style.setProperty("--annotation-color", colorValue(item.annotation.style.color));
      try {
        item.range.surroundContents(mark);
        item.element = mark;
      } catch (error) {
        try {
          const fragment = item.range.extractContents();
          mark.appendChild(fragment);
          item.range.insertNode(mark);
          item.element = mark;
        } catch (fallbackError) {}
      }
    });
  }

  function renderHighlights() {
    unwrapMarks();
    state.resolved = new Map();
    activeAnnotations().forEach(function (annotation) {
      const range = resolveAnnotationRange(annotation);
      if (!range) return;
      state.resolved.set(annotation.id, { annotation: annotation, range: range, element: null });
    });
    paintHighlights();
    renderMarkers();
    updateCount();
    if (state.cardId) {
      const current = state.annotations.get(state.cardId);
      if (!current || current.deleted) closeCard(false);
    }
  }

  function markerLayerElement() {
    if (!markerLayer) {
      markerLayer = document.createElement("div");
      markerLayer.className = "annotation-markers";
      document.body.appendChild(markerLayer);
    }
    return markerLayer;
  }

  function renderMarkers() {
    const layer = markerLayerElement();
    layer.replaceChildren();
    state.markers = [];
    state.resolved.forEach(function (item) {
      if (!item.annotation.note) return;
      const button = document.createElement("button");
      button.type = "button";
      button.className = "annotation-note-marker";
      button.textContent = "✎";
      button.setAttribute(
        "aria-label",
        "Note: " + (item.annotation.quote || item.annotation.note || "annotation")
      );
      button.addEventListener("click", function (event) {
        event.preventDefault();
        event.stopPropagation();
        const rect = button.getBoundingClientRect();
        openCard(item.annotation, rect.left, rect.top);
      });
      layer.appendChild(button);
      state.markers.push({ annotation: item.annotation, range: item.range, element: item.element, button: button });
    });
    scheduleMarkerUpdate();
  }

  function scheduleMarkerUpdate() {
    if (markerFrame !== null) return;
    markerFrame = window.requestAnimationFrame(function () {
      markerFrame = null;
      updateMarkerPositions();
    });
  }

  function updateMarkerPositions() {
    state.markers.forEach(function (item) {
      if (!item.button || !item.button.isConnected) return;
      let rect = null;
      if (item.element && item.element.isConnected) {
        rect = item.element.getBoundingClientRect();
      } else if (item.range) {
        const rects = item.range.getClientRects();
        rect = rects.length ? rects[rects.length - 1] : item.range.getBoundingClientRect();
      }
      if (!rect || (rect.width === 0 && rect.height === 0)) {
        item.button.hidden = true;
        return;
      }
      if (rect.bottom < 0 || rect.top > window.innerHeight) {
        item.button.hidden = true;
        return;
      }
      item.button.hidden = false;
      const left = clamp(rect.right - 9, 4, window.innerWidth - 22);
      const top = clamp(rect.top + rect.height / 2 - 9, 4, window.innerHeight - 22);
      item.button.style.left = left + "px";
      item.button.style.top = top + "px";
    });
  }

  /* ------------------------------------------------------------------
     Toast
     ------------------------------------------------------------------ */

  function ensureToast() {
    if (toast) return toast;
    toast = document.createElement("div");
    toast.className = "annotation-toast";
    toast.setAttribute("role", "status");
    toast.setAttribute("aria-live", "polite");
    toast.setAttribute("aria-atomic", "true");
    toast.hidden = true;
    const text = document.createElement("span");
    text.setAttribute("data-annotation-toast-text", "");
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = "Undo";
    button.setAttribute("data-annotation-toast-undo", "");
    button.hidden = true;
    button.addEventListener("click", function () {
      const action = toastAction;
      hideToast();
      if (action) action();
    });
    toast.append(text, button);
    document.body.appendChild(toast);
    return toast;
  }

  function showToast(message, undo) {
    const element = ensureToast();
    element.querySelector("[data-annotation-toast-text]").textContent = message;
    const button = element.querySelector("[data-annotation-toast-undo]");
    button.hidden = typeof undo !== "function";
    toastAction = typeof undo === "function" ? undo : null;
    element.hidden = false;
    window.clearTimeout(toastTimer);
    toastTimer = window.setTimeout(hideToast, 6000);
  }

  function hideToast() {
    window.clearTimeout(toastTimer);
    toastTimer = null;
    toastAction = null;
    if (toast) toast.hidden = true;
  }

  /* ------------------------------------------------------------------
     Selection toolbar
     ------------------------------------------------------------------ */

  function readLastColor() {
    try {
      const stored = localStorage.getItem(COLOR_KEY);
      return COLORS.indexOf(stored) === -1 ? "yellow" : stored;
    } catch (error) {
      return "yellow";
    }
  }

  function setLastColor(color) {
    state.lastColor = COLORS.indexOf(color) === -1 ? "yellow" : color;
    try {
      localStorage.setItem(COLOR_KEY, state.lastColor);
    } catch (error) {}
    updateToolbarColors();
  }

  function updateToolbarColors() {
    if (!toolbar) return;
    toolbar.querySelectorAll("[data-annotation-color-dot]").forEach(function (dot) {
      dot.style.setProperty("--annotation-color", colorValue(state.lastColor));
    });
    toolbar.querySelectorAll("[data-annotation-color-choice]").forEach(function (button) {
      button.setAttribute(
        "aria-pressed",
        button.dataset.annotationColorChoice === state.lastColor ? "true" : "false"
      );
    });
  }

  function captureSelection() {
    if (!state.ready) return null;
    const selection = window.getSelection ? window.getSelection() : null;
    if (!selection || selection.isCollapsed || selection.rangeCount === 0) return null;
    const range = selection.getRangeAt(0);
    if (!bookPage.contains(range.startContainer) || !bookPage.contains(range.endContainer)) {
      return null;
    }
    const quote = range.toString();
    if (!quote.trim()) return null;
    const startPath = nodePath(bookPage, range.startContainer);
    const endPath = nodePath(bookPage, range.endContainer);
    if (!startPath || !endPath) return null;

    const before = document.createRange();
    before.selectNodeContents(bookPage);
    before.setEnd(range.startContainer, range.startOffset);
    const after = document.createRange();
    after.selectNodeContents(bookPage);
    after.setStart(range.endContainer, range.endOffset);
    const beforeText = before.toString();
    const afterText = after.toString();

    const rect = range.getBoundingClientRect();
    const pageRect = bookPage.getBoundingClientRect();
    const pageHeight = Math.max(1, bookPage.scrollHeight);
    const within = clamp((rect.top - pageRect.top) / pageHeight, 0, 1);
    const startProgress = Number.isFinite(progressStart) ? progressStart : 0;
    const endProgress = Number.isFinite(progressEnd) ? progressEnd : 1;

    return {
      range: range.cloneRange(),
      quote: quote.trim(),
      prefix: beforeText.slice(-40),
      suffix: afterText.slice(0, 40),
      startPath: startPath,
      endPath: endPath,
      startOffset: range.startOffset,
      endOffset: range.endOffset,
      charStart: beforeText.length,
      charEnd: beforeText.length + quote.length,
      progression: startProgress + (endProgress - startProgress) * within,
    };
  }

  function positionToolbar() {
    if (!toolbar || toolbar.hidden || !state.selection) return;
    if (window.innerWidth <= 700) {
      toolbar.style.left = "";
      toolbar.style.top = "";
      return;
    }
    const selectionRect = state.selection.range.getBoundingClientRect();
    if (!selectionRect || (selectionRect.width === 0 && selectionRect.height === 0)) return;
    const toolbarRect = toolbar.getBoundingClientRect();
    let left = selectionRect.left + selectionRect.width / 2 - toolbarRect.width / 2;
    left = clamp(left, 10, Math.max(10, window.innerWidth - toolbarRect.width - 10));
    let top = selectionRect.top - toolbarRect.height - 10;
    if (top < headerHeight() + 8) top = selectionRect.bottom + 10;
    top = clamp(top, 8, Math.max(8, window.innerHeight - toolbarRect.height - 8));
    toolbar.style.left = left + "px";
    toolbar.style.top = top + "px";
  }

  function showToolbar(selection) {
    if (!toolbar || state.note || state.cardId) return;
    state.selection = selection;
    toolbar.hidden = false;
    if (toolbarColors) toolbarColors.hidden = true;
    if (colorToggle) colorToggle.setAttribute("aria-expanded", "false");
    updateToolbarColors();
    window.requestAnimationFrame(positionToolbar);
  }

  function hideToolbar(clearSelection) {
    if (!toolbar) return;
    toolbar.hidden = true;
    if (toolbarColors) toolbarColors.hidden = true;
    if (colorToggle) colorToggle.setAttribute("aria-expanded", "false");
    if (clearSelection !== false) state.selection = null;
  }

  function clearNativeSelection() {
    const selection = window.getSelection ? window.getSelection() : null;
    if (selection) selection.removeAllRanges();
  }

  function buildAnnotation(selection, color, note) {
    const updated = nowIso();
    return {
      id: newId(),
      type: "highlight",
      created: updated,
      updated: updated,
      deleted: false,
      note: note || "",
      quote: selection.quote,
      style: { color: COLORS.indexOf(color) === -1 ? state.lastColor : color },
      anchor: {
        page_key: pageKey,
        chapter_key: chapterKey,
        start: {
          dom_path: selection.startPath,
          offset: selection.startOffset,
          char: selection.charStart,
        },
        end: {
          dom_path: selection.endPath,
          offset: selection.endOffset,
          char: selection.charEnd,
        },
        prefix: selection.prefix,
        suffix: selection.suffix,
        progression: selection.progression,
      },
    };
  }

  function createHighlight(selection, color) {
    if (!selection || !state.ready) return;
    const annotation = buildAnnotation(selection, color || state.lastColor, "");
    state.annotations.set(annotation.id, annotation);
    setLastColor(annotation.style.color);
    hideToolbar();
    clearNativeSelection();
    refresh();
    persist(annotation).then(function (ok) {
      if (!ok) {
        showToast("Highlight saved in this tab only. Export to keep it.", function () {
          undoCreate(annotation.id);
        });
      }
    });
    broadcast(annotation);
    showToast("Highlighted", function () {
      undoCreate(annotation.id);
    });
  }

  function undoCreate(id) {
    const annotation = state.annotations.get(id);
    if (!annotation) return;
    annotation.deleted = true;
    annotation.updated = nowIso();
    refresh();
    persist(annotation);
    broadcast(annotation);
    hideToast();
  }

  function deleteAnnotation(id) {
    const annotation = state.annotations.get(id);
    if (!annotation || annotation.deleted) return;
    const before = clone(annotation);
    annotation.deleted = true;
    annotation.updated = nowIso();
    refresh();
    persist(annotation);
    broadcast(annotation);
    showToast(annotation.quote ? "Highlight removed" : "Note removed", function () {
      restoreAnnotation(before);
    });
  }

  function restoreAnnotation(before) {
    const restored = clone(before);
    restored.deleted = false;
    restored.updated = nowIso();
    state.annotations.set(restored.id, restored);
    refresh();
    persist(restored);
    broadcast(restored);
    hideToast();
  }

  function setColor(id, color) {
    const annotation = state.annotations.get(id);
    if (!annotation || annotation.deleted) return;
    annotation.style = { color: COLORS.indexOf(color) === -1 ? "yellow" : color };
    annotation.updated = nowIso();
    setLastColor(annotation.style.color);
    refresh();
    persist(annotation);
    broadcast(annotation);
    if (state.cardId === id) updateCard(annotation);
  }

  /* ------------------------------------------------------------------
     Note composer
     ------------------------------------------------------------------ */

  function refreshNoteSave() {
    if (!noteSave || !noteText) return;
    noteSave.disabled = !noteText.value.trim();
  }

  function openNoteComposer(selection, annotation) {
    if (!noteDialog) return;
    hideToolbar();
    closeCard(false);
    state.noteReturnFocus = document.activeElement;
    state.note = { selection: selection, annotation: annotation, created: null };
    const quote = annotation ? annotation.quote : selection ? selection.quote : "";
    noteQuote.textContent = quote || "Note at this location";
    noteQuote.style.setProperty(
      "--annotation-color",
      colorValue(annotation ? annotation.style.color : selection ? state.lastColor : "yellow")
    );
    noteText.value = annotation ? annotation.note : "";
    noteText.placeholder = annotation ? "Add a note (optional)" : "Write a note…";
    noteTitle.textContent = annotation ? "Edit note" : "Add a note";
    noteRemove.hidden = !(annotation && annotation.note);
    noteError.hidden = true;
    noteError.textContent = "";
    refreshNoteSave();
    if (!noteDialog.open) noteDialog.showModal();
    window.requestAnimationFrame(function () {
      noteText.focus();
      const length = noteText.value.length;
      try {
        noteText.setSelectionRange(length, length);
      } catch (error) {}
    });
  }

  function showNoteError(message) {
    noteError.textContent =
      message ||
      "This browser could not save the note. Export your annotations to keep them.";
    noteError.hidden = false;
  }

  async function saveNote() {
    const text = noteText.value.trim();
    if (!text || !state.note) return;
    noteSave.disabled = true;
    const target = state.note;
    let saved = false;

    if (target.annotation) {
      const before = clone(target.annotation);
      const annotation = state.annotations.get(target.annotation.id) || clone(target.annotation);
      annotation.note = text;
      annotation.updated = nowIso();
      state.annotations.set(annotation.id, annotation);
      refresh();
      saved = await persist(annotation);
      if (saved) {
        broadcast(annotation);
        noteDialog.close();
        showToast("Note saved", function () {
          const current = state.annotations.get(annotation.id);
          if (!current) return;
          current.note = before.note;
          current.updated = nowIso();
          refresh();
          persist(current);
          broadcast(current);
          hideToast();
        });
      }
    } else if (target.selection) {
      let annotation = target.created;
      if (!annotation) {
        annotation = buildAnnotation(target.selection, state.lastColor, text);
        target.created = annotation;
      } else {
        annotation.note = text;
        annotation.updated = nowIso();
      }
      state.annotations.set(annotation.id, annotation);
      refresh();
      saved = await persist(annotation);
      if (saved) {
        clearNativeSelection();
        broadcast(annotation);
        noteDialog.close();
        showToast("Note saved", function () {
          undoCreate(annotation.id);
        });
      }
    }

    noteSave.disabled = false;
    if (!saved) showNoteError();
  }

  async function removeNote() {
    if (!state.note || !state.note.annotation) return;
    const annotation = state.annotations.get(state.note.annotation.id);
    if (!annotation) return;
    const before = annotation.note;
    annotation.note = "";
    annotation.updated = nowIso();
    state.annotations.set(annotation.id, annotation);
    refresh();
    const saved = await persist(annotation);
    broadcast(annotation);
    noteDialog.close();
    if (saved) {
      showToast("Note removed", function () {
        const current = state.annotations.get(annotation.id);
        if (!current) return;
        current.note = before;
        current.updated = nowIso();
        refresh();
        persist(current);
        broadcast(current);
        hideToast();
      });
    } else {
      showToast("Note removed in this tab only. Export to keep it.", null);
    }
  }

  /* ------------------------------------------------------------------
     Highlight card
     ------------------------------------------------------------------ */

  function updateCard(annotation) {
    if (!card || !annotation) return;
    card.dataset.annotationId = annotation.id;
    card.style.setProperty("--annotation-color", colorValue(annotation.style.color));
    cardQuote.textContent = annotation.quote || "Note at this location";
    cardNote.textContent = annotation.note;
    cardNote.hidden = !annotation.note;
    cardEdit.querySelector("span").textContent = annotation.note ? "Edit note" : "Add note";
    cardMeta.textContent = [chapterLabel(annotation), formatDate(annotation.updated)]
      .filter(Boolean)
      .join(" · ");
    card.querySelectorAll("[data-highlight-color-choice]").forEach(function (button) {
      button.setAttribute(
        "aria-pressed",
        button.dataset.highlightColorChoice === annotation.style.color ? "true" : "false"
      );
    });
  }

  function positionCard(x, y) {
    if (!card || card.hidden || window.innerWidth <= 700) return;
    const width = card.offsetWidth;
    const height = card.offsetHeight;
    const pointX = Number.isFinite(x) ? x : window.innerWidth / 2;
    const pointY = Number.isFinite(y) ? y : window.innerHeight / 3;
    let left = clamp(pointX - width / 2, 12, Math.max(12, window.innerWidth - width - 12));
    let top = pointY - height - 14;
    if (top < headerHeight() + 8) top = pointY + 18;
    top = clamp(top, 8, Math.max(8, window.innerHeight - height - 8));
    card.style.left = left + "px";
    card.style.top = top + "px";
  }

  function openCard(annotation, x, y) {
    if (!card || !annotation) return;
    state.cardReturnFocus = document.activeElement;
    state.cardPoint = { x: x, y: y };
    state.cardId = annotation.id;
    updateCard(annotation);
    cardColors.hidden = true;
    cardColorToggle.setAttribute("aria-expanded", "false");
    card.hidden = false;
    positionCard(x, y);
    card.focus({ preventScroll: true });
  }

  function closeCard(restoreFocus) {
    if (!card) return;
    card.hidden = true;
    cardColors.hidden = true;
    cardColorToggle.setAttribute("aria-expanded", "false");
    state.cardId = "";
    state.cardPoint = null;
    if (restoreFocus !== false && state.cardReturnFocus) {
      const target = state.cardReturnFocus;
      state.cardReturnFocus = null;
      focusElement(target);
    }
  }

  function copyText(text, label) {
    if (!text) return;
    const done = function () {
      showToast(label || "Copied", null);
    };
    if (navigator.clipboard && typeof navigator.clipboard.writeText === "function") {
      navigator.clipboard.writeText(text).then(done).catch(function () {
        fallbackCopy(text, done);
      });
    } else {
      fallbackCopy(text, done);
    }
  }

  function fallbackCopy(text, done) {
    const area = document.createElement("textarea");
    area.value = text;
    area.setAttribute("readonly", "");
    area.style.position = "fixed";
    area.style.opacity = "0";
    document.body.appendChild(area);
    area.select();
    try {
      document.execCommand("copy");
      done();
    } catch (error) {}
    area.remove();
  }

  function chapterLabel(annotation) {
    const anchor = annotation.anchor || {};
    if (anchor.chapter_key && anchor.chapter_key === chapterKey) {
      const title = bookPage.querySelector(".chapter-title");
      if (title && title.textContent.trim()) return title.textContent.trim();
    }
    const chapterEntry = readingMap.find(function (entry) {
      return entry.chapterKey && entry.chapterKey === anchor.chapter_key;
    });
    if (chapterEntry && chapterEntry.label) return chapterEntry.label;
    const pageEntry = readingMap.find(function (entry) {
      return entry.key === anchor.page_key;
    });
    return pageEntry && pageEntry.label ? pageEntry.label : "";
  }

  /* ------------------------------------------------------------------
     Annotation panel
     ------------------------------------------------------------------ */

  function setStatus(message) {
    if (panelStatus) panelStatus.textContent = message || "";
  }

  function pageOrder(key) {
    const index = readingMap.findIndex(function (entry) {
      return entry.key === key;
    });
    return index === -1 ? Number.MAX_SAFE_INTEGER : index;
  }

  function sortAnnotations(annotations) {
    return annotations.slice().sort(function (left, right) {
      const leftOrder = pageOrder(left.anchor.page_key);
      const rightOrder = pageOrder(right.anchor.page_key);
      if (leftOrder !== rightOrder) return leftOrder - rightOrder;
      const leftChar = left.anchor.start ? left.anchor.start.char || 0 : 0;
      const rightChar = right.anchor.start ? right.anchor.start.char || 0 : 0;
      if (leftChar !== rightChar) return leftChar - rightChar;
      return Date.parse(left.created) - Date.parse(right.created);
    });
  }

  function menuButton(label, action) {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = label;
    button.dataset.annotationAction = action;
    return button;
  }

  function colorChoices(annotation) {
    const wrapper = document.createElement("div");
    wrapper.className = "annotation-item-colors";
    COLORS.forEach(function (color) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "annotation-color";
      button.dataset.annotationColorChoice = color;
      button.setAttribute("aria-label", color.charAt(0).toUpperCase() + color.slice(1) + " highlight");
      button.setAttribute("aria-pressed", annotation.style.color === color ? "true" : "false");
      button.style.setProperty("--annotation-color", colorValue(color));
      wrapper.appendChild(button);
    });
    return wrapper;
  }

  function renderPanel() {
    if (!panelList) return;
    panelList.replaceChildren();
    const all = sortAnnotations(activeAnnotations());
    const filtered = all.filter(function (annotation) {
      if (state.filter === "note") return Boolean(annotation.note);
      if (state.filter === "highlight") return !annotation.note;
      return true;
    });

    panelEmpty.hidden = filtered.length > 0;
    if (!filtered.length) {
      panelEmpty.textContent = all.length
        ? "No annotations match this filter."
        : "No highlights or notes yet. Select text and press H to highlight, or use the selection toolbar.";
    }

    const groups = new Map();
    filtered.forEach(function (annotation) {
      const key = annotation.anchor.chapter_key || annotation.anchor.page_key || "book";
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key).push(annotation);
    });

    groups.forEach(function (annotations, key) {
      const section = document.createElement("section");
      section.className = "annotation-group";
      const heading = document.createElement("h3");
      heading.className = "annotation-group-title";
      const first = annotations[0];
      heading.textContent = chapterLabel(first) || "Book";
      section.appendChild(heading);

      annotations.forEach(function (annotation) {
        const item = document.createElement("article");
        item.className = "annotation-item";
        item.dataset.annotationId = annotation.id;
        item.style.setProperty("--annotation-color", colorValue(annotation.style.color));

        const main = document.createElement("button");
        main.type = "button";
        main.className = "annotation-item-main";
        main.dataset.annotationAction = "jump";
        const bar = document.createElement("span");
        bar.className = "annotation-item-bar";
        const text = document.createElement("span");
        text.className = "annotation-item-text";
        const quote = document.createElement("span");
        quote.className = "annotation-item-quote";
        quote.textContent = annotation.quote || "Note at this location";
        text.appendChild(quote);
        if (annotation.note && annotation.quote) {
          const note = document.createElement("span");
          note.className = "annotation-item-note";
          note.textContent = annotation.note;
          text.appendChild(note);
        }
        const meta = document.createElement("span");
        meta.className = "annotation-item-meta";
        const bits = [];
        if (annotation.note) bits.push("Note");
        const date = formatDate(annotation.updated);
        if (date) bits.push(date);
        if (annotation.needs_review) bits.push("Needs review");
        meta.textContent = bits.join(" · ");
        text.appendChild(meta);
        main.append(bar, text);

        const details = document.createElement("details");
        details.className = "annotation-item-menu";
        const summary = document.createElement("summary");
        summary.setAttribute("aria-label", "Actions for this annotation");
        summary.textContent = "⋯";
        const actions = document.createElement("div");
        actions.className = "annotation-item-actions";
        actions.appendChild(menuButton(annotation.note ? "Edit note" : "Add note", "edit-note"));
        actions.appendChild(menuButton("Copy quote", "copy"));
        actions.appendChild(menuButton("Remove", "remove"));
        actions.appendChild(colorChoices(annotation));
        details.append(summary, actions);
        item.append(main, details);
        section.appendChild(item);
      });
      panelList.appendChild(section);
    });
  }

  function openPanel() {
    if (!panel) return;
    closeCard(false);
    state.panelReturnFocus = document.activeElement;
    renderPanel();
    if (!panel.open) panel.showModal();
  }

  function closePanel() {
    if (panel && panel.open) panel.close();
  }

  function togglePanel() {
    if (!panel) return;
    if (panel.open) closePanel();
    else openPanel();
  }

  function scrollToAnnotation(annotation) {
    const item = state.resolved.get(annotation.id);
    if (!item) {
      showToast("Could not find this annotation on this page.", null);
      return;
    }
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const behavior = reduce ? "auto" : "smooth";
    if (item.element && item.element.isConnected) {
      item.element.scrollIntoView({ block: "center", behavior: behavior });
    } else {
      const rect = item.range.getBoundingClientRect();
      const top = window.scrollY + rect.top - headerHeight() - 70;
      window.scrollTo({ top: Math.max(0, top), behavior: behavior });
    }
    window.setTimeout(function () {
      flashItem(item);
    }, reduce ? 0 : 360);
  }

  function flashItem(item) {
    let rect = null;
    if (item.element && item.element.isConnected) {
      rect = item.element.getBoundingClientRect();
    } else if (item.range) {
      rect = item.range.getBoundingClientRect();
    }
    if (!rect) return;
    const flash = document.createElement("div");
    flash.className = "annotation-flash";
    flash.style.left = rect.left + "px";
    flash.style.top = rect.top + "px";
    flash.style.width = Math.max(4, rect.width) + "px";
    flash.style.height = Math.max(4, rect.height) + "px";
    document.body.appendChild(flash);
    window.setTimeout(function () {
      flash.remove();
    }, 1300);
  }

  function jumpToAnnotation(annotation) {
    const targetKey = annotation.anchor ? annotation.anchor.page_key : "";
    if (targetKey && targetKey !== pageKey) {
      const entry = readingMap.find(function (item) {
        return item.key === targetKey;
      });
      if (!entry) {
        showToast("This annotation is on another page.", null);
        return;
      }
      const separator = entry.route.indexOf("?") === -1 ? "?" : "&";
      window.location.href =
        withBase(entry.route) + separator + "annotation=" + encodeURIComponent(annotation.id);
      return;
    }
    closePanel();
    scrollToAnnotation(annotation);
  }

  async function importAnnotations(file) {
    if (file.size > 10 * 1024 * 1024) {
      setStatus("That annotation file is too large.");
      return;
    }
    let raw;
    try {
      raw = JSON.parse(await file.text());
    } catch (error) {
      setStatus("That file is not valid JSON.");
      return;
    }
    const imported = validateImportedDocument(raw);
    if (!imported) {
      setStatus("That file is not a valid epub2web annotation file.");
      return;
    }
    const sameBook =
      imported.book.content_id === contentId ||
      (sourceSha256 && imported.book.source_sha256 === sourceSha256);
    if (!sameBook) {
      setStatus("That file belongs to a different book.");
      return;
    }

    let added = 0;
    let updated = 0;
    const changed = [];
    imported.annotations.forEach(function (record) {      const result = mergeIntoState(record);
      if (!result.changed) return;
      if (result.added) added += 1;
      else updated += 1;
      changed.push(result.annotation);
    });

    if (!changed.length) {
      setStatus("No new annotations.");
      return;
    }

    const saved = await persistMany(changed);
    refresh();
    renderPanel();
    if (saved) {
      const total = added + updated;
      const detail = updated ? " (" + added + " new, " + updated + " updated)" : "";
      setStatus(
        "Imported " +
          total +
          (total === 1 ? " annotation" : " annotations") +
          detail +
          "."
      );
    } else {
      setStatus("Imported annotations, but this browser could not save them. Export to keep them.");
    }
    changed.forEach(broadcast);
  }

  function exportAnnotations() {
    const payload = {
      schema: SCHEMA,
      version: VERSION,
      book: bookRecord(),
      annotations: sortAnnotations(Array.from(state.annotations.values())),
    };
    const text = JSON.stringify(payload, null, 2) + "\n";
    const blob = new Blob([text], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    const title = (bookMeta.title || "book").toString();
    const slug =
      title
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-+|-+$/g, "")
        .slice(0, 60) || "book";
    link.href = url;
    link.download = slug + ".annotations.json";
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(function () {
      URL.revokeObjectURL(url);
    }, 1000);
    setStatus("Exported " + activeAnnotations().length + " annotations.");
  }

  function firstTextNode(container) {
    const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT, null);
    let node;
    while ((node = walker.nextNode())) {
      if (node.nodeValue.trim()) return node;
    }
    return null;
  }

  function startLocationNote() {
    if (!noteDialog) return;
    closePanel();
    const candidates = Array.from(bookPage.querySelectorAll("p, blockquote, li")).filter(
      function (element) {
        return element.textContent.trim() && !element.closest("[data-chrome]");
      }
    );
    const headings = Array.from(bookPage.querySelectorAll("h1, h2, h3")).filter(function (element) {
      return element.textContent.trim() && !element.closest("[data-chrome]");
    });
    const header = headerHeight();
    const visible = function (element) {
      const rect = element.getBoundingClientRect();
      return rect.bottom > header && rect.top < window.innerHeight;
    };
    const target =
      candidates.find(visible) ||
      candidates[0] ||
      headings.find(visible) ||
      headings[0] ||
      bookPage;

    const textNode = firstTextNode(target) || target;
    const range = document.createRange();
    try {
      range.setStart(textNode, 0);
      range.collapse(true);
    } catch (error) {
      range.selectNodeContents(target);
      range.collapse(true);
    }
    const startPath = nodePath(bookPage, textNode);
    const endPath = startPath;
    if (!startPath) {
      showToast("Could not find a place for the note on this page.", null);
      return;
    }
    const before = document.createRange();
    before.selectNodeContents(bookPage);
    before.setEnd(textNode, 0);
    const charStart = before.toString().length;
    const quote = target.textContent.trim().replace(/\s+/g, " ").slice(0, 160);
    const rect = target.getBoundingClientRect();
    const pageRect = bookPage.getBoundingClientRect();
    const pageHeight = Math.max(1, bookPage.scrollHeight);
    const within = clamp((rect.top - pageRect.top) / pageHeight, 0, 1);
    const start = Number.isFinite(progressStart) ? progressStart : 0;
    const end = Number.isFinite(progressEnd) ? progressEnd : 1;
    openNoteComposer(
      {
        range: range.cloneRange(),
        quote: quote,
        prefix: "",
        suffix: "",
        startPath: startPath,
        endPath: endPath,
        startOffset: 0,
        endOffset: 0,
        charStart: charStart,
        charEnd: charStart,
        progression: start + (end - start) * within,
      },
      null
    );
  }

  /* ------------------------------------------------------------------
     Event wiring
     ------------------------------------------------------------------ */

  function bindToolbar() {
    if (!toolbar) return;
    toolbar.addEventListener("pointerdown", function (event) {
      event.preventDefault();
    });
    toolbar.querySelector("[data-annotation-highlight]").addEventListener("click", function () {
      if (state.selection) createHighlight(state.selection, state.lastColor);
    });
    toolbar.querySelector("[data-annotation-note]").addEventListener("click", function () {
      if (state.selection) {
        const selection = state.selection;
        hideToolbar(false);
        openNoteComposer(selection, null);
      }
    });
    if (colorToggle) {
      colorToggle.addEventListener("click", function () {
        const opening = toolbarColors.hidden;
        toolbarColors.hidden = !opening;
        colorToggle.setAttribute("aria-expanded", opening ? "true" : "false");
      });
    }
    toolbar.querySelectorAll("[data-annotation-color-choice]").forEach(function (button) {
      button.addEventListener("click", function () {
        const color = button.dataset.annotationColorChoice;
        if (state.selection) createHighlight(state.selection, color);
        else {
          setLastColor(color);
          hideToolbar();
        }
      });
    });
  }

  function bindCard() {
    if (!card) return;
    card.querySelector("[data-highlight-close]").addEventListener("click", function () {
      closeCard();
    });
    cardEdit.addEventListener("click", function () {
      const annotation = state.annotations.get(state.cardId);
      if (!annotation) return;
      closeCard(false);
      openNoteComposer(null, annotation);
    });
    cardColorToggle.addEventListener("click", function () {
      const opening = cardColors.hidden;
      cardColors.hidden = !opening;
      cardColorToggle.setAttribute("aria-expanded", opening ? "true" : "false");
    });
    card.querySelector("[data-highlight-copy]").addEventListener("click", function () {
      const annotation = state.annotations.get(state.cardId);
      if (!annotation) return;
      copyText(annotation.quote || annotation.note, annotation.quote ? "Quote copied" : "Note copied");
    });
    card.querySelector("[data-highlight-remove]").addEventListener("click", function () {
      const id = state.cardId;
      closeCard(false);
      deleteAnnotation(id);
    });
    card.querySelectorAll("[data-highlight-color-choice]").forEach(function (button) {
      button.addEventListener("click", function () {
        if (state.cardId) setColor(state.cardId, button.dataset.highlightColorChoice);
      });
    });
  }

  function bindPanel() {
    if (!panel) return;
    if (openButton) {
      openButton.addEventListener("click", function () {
        openPanel();
      });
    }
    panel.querySelectorAll("[data-annotations-filter]").forEach(function (button) {
      button.addEventListener("click", function () {
        state.filter = button.dataset.annotationsFilter;
        panel.querySelectorAll("[data-annotations-filter]").forEach(function (candidate) {
          const active = candidate === button;
          candidate.classList.toggle("is-active", active);
          candidate.setAttribute("aria-pressed", active ? "true" : "false");
        });
        renderPanel();
      });
    });
    panel.querySelector("[data-annotations-location]").addEventListener("click", function () {
      startLocationNote();
    });
    panel.querySelector("[data-annotations-export]").addEventListener("click", function () {
      exportAnnotations();
    });
    panel.querySelector("[data-annotations-import]").addEventListener("click", function () {
      fileInput.click();
    });
    fileInput.addEventListener("change", function () {
      const file = fileInput.files && fileInput.files[0];
      fileInput.value = "";
      if (file) importAnnotations(file);
    });
    panelList.addEventListener("click", function (event) {
      const item = event.target.closest("[data-annotation-id]");
      if (!item) return;
      const id = item.dataset.annotationId;
      const annotation = state.annotations.get(id);
      if (!annotation) return;
      const color = event.target.closest("[data-annotation-color-choice]");
      if (color) {
        setColor(id, color.dataset.annotationColorChoice);
        renderPanel();
        return;
      }
      const action = event.target.closest("[data-annotation-action]");
      if (!action) return;
      event.preventDefault();
      if (action.dataset.annotationAction === "jump") {
        jumpToAnnotation(annotation);
      } else if (action.dataset.annotationAction === "edit-note") {
        closePanel();
        openNoteComposer(null, annotation);
      } else if (action.dataset.annotationAction === "copy") {
        copyText(annotation.quote || annotation.note, "Copied");
        setStatus("Copied.");
      } else if (action.dataset.annotationAction === "remove") {
        closePanel();
        deleteAnnotation(id);
      }
    });
    panel.addEventListener("close", function () {
      if (state.panelReturnFocus) {
        const target = state.panelReturnFocus;
        state.panelReturnFocus = null;
        focusElement(target);
      }
    });
  }

  function bindStorageDialog() {
    if (!storageDialog) return;
    document.querySelectorAll("[data-storage-open]").forEach(function (button) {
      button.addEventListener("click", function () {
        openStorageDialog();
      });
    });
    if (storageRequest) {
      storageRequest.addEventListener("click", requestPersistentStorage);
    }
    storageDialog.addEventListener("close", function () {
      const trigger = document.querySelector("[data-storage-open]");
      if (trigger && trigger.getClientRects().length) {
        trigger.focus({ preventScroll: true });
      }
    });
  }

  function bindNoteDialog() {
    if (!noteDialog) return;
    noteDialog.querySelectorAll("[data-note-cancel]").forEach(function (button) {
      button.addEventListener("click", function () {
        noteDialog.close();
      });
    });
    noteText.addEventListener("input", refreshNoteSave);
    noteSave.addEventListener("click", saveNote);
    noteRemove.addEventListener("click", removeNote);
    noteDialog.addEventListener("keydown", function (event) {
      if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
        event.preventDefault();
        saveNote();
      }
    });
    noteDialog.addEventListener("close", function () {
      state.note = null;
      noteText.value = "";
      noteError.hidden = true;
      if (state.noteReturnFocus) {
        const target = state.noteReturnFocus;
        state.noteReturnFocus = null;
        focusElement(target);
      }
    });
  }

  function bindSelection() {
    const handleSelectionChange = debounce(function () {
      if (document.querySelector("dialog[open]")) return;
      if (state.note) return;
      if (isTyping(document.activeElement)) return;
      const selection = captureSelection();
      if (selection) showToolbar(selection);
      else hideToolbar();
    }, 130);
    document.addEventListener("selectionchange", handleSelectionChange);

    document.addEventListener("pointerdown", function (event) {
      if (!toolbar || toolbar.hidden) return;
      if (toolbar.contains(event.target)) return;
      hideToolbar();
    });

    document.addEventListener("pointerdown", function (event) {
      if (!card || card.hidden) return;
      if (card.contains(event.target)) return;
      if (event.target.closest && event.target.closest(".annotation-note-marker")) return;
      if (event.target.closest && event.target.closest("mark.annotation-mark")) return;
      if (bookPage.contains(event.target) && annotationAtPoint(event.clientX, event.clientY)) {
        return;
      }
      closeCard();
    });

    window.addEventListener(
      "scroll",
      function () {
        if (toolbar && !toolbar.hidden) hideToolbar();
        scheduleMarkerUpdate();
      },
      { passive: true }
    );
    window.addEventListener("resize", function () {
      positionToolbar();
      scheduleMarkerUpdate();
      if (state.cardId && state.cardPoint) {
        positionCard(state.cardPoint.x, state.cardPoint.y);
      }
    });
    if (window.MutationObserver) {
      new MutationObserver(scheduleMarkerUpdate).observe(root, {
        attributes: true,
        attributeFilter: ["data-theme", "data-reader-size", "data-reader-spacing", "data-reader-width"],
      });
    }
  }

  function annotationAtPoint(x, y) {
    let node = null;
    let offset = 0;
    if (document.caretRangeFromPoint) {
      const range = document.caretRangeFromPoint(x, y);
      if (!range) return null;
      node = range.startContainer;
      offset = range.startOffset;
    } else if (document.caretPositionFromPoint) {
      const position = document.caretPositionFromPoint(x, y);
      if (!position) return null;
      node = position.offsetNode;
      offset = position.offset;
    } else {
      return null;
    }
    let found = null;
    state.resolved.forEach(function (item) {
      if (!item.range) return;
      try {
        if (item.range.isPointInRange(node, offset)) found = item.annotation;
      } catch (error) {}
    });
    return found;
  }

  function bindPageClicks() {
    bookPage.addEventListener("click", function (event) {
      if (event.defaultPrevented || event.button !== 0) return;
      const selection = window.getSelection ? window.getSelection() : null;
      if (selection && !selection.isCollapsed) return;
      const mark = event.target.closest && event.target.closest("mark.annotation-mark");
      let annotation = null;
      if (mark && mark.dataset.annotationId) {
        annotation = state.annotations.get(mark.dataset.annotationId) || null;
      } else {
        annotation = annotationAtPoint(event.clientX, event.clientY);
      }
      if (annotation && annotation.deleted) annotation = null;
      if (!annotation) return;
      event.preventDefault();
      event.stopPropagation();
      openCard(annotation, event.clientX, event.clientY);
    });
  }

  function bindKeyboard() {
    document.addEventListener("keydown", function (event) {
      if (event.defaultPrevented) return;
      if (event.metaKey || event.ctrlKey || event.altKey) return;
      if (isTyping(event.target)) return;
      if (event.key === "Escape") {
        hideToolbar();
        if (card && !card.hidden) closeCard();
        return;
      }
      if (event.shiftKey) {
        if (event.key === "A" || event.key === "a") {
          const openDialogEl = document.querySelector("dialog[open]");
          if (openDialogEl && openDialogEl !== panel) return;
          event.preventDefault();
          togglePanel();
        }
        return;
      }
      if (document.querySelector("dialog[open]")) return;
      if ((event.key === "h" || event.key === "H") && state.selection) {
        event.preventDefault();
        createHighlight(state.selection, state.lastColor);
      } else if ((event.key === "n" || event.key === "N") && state.selection) {
        event.preventDefault();
        const selection = state.selection;
        hideToolbar(false);
        openNoteComposer(selection, null);
      }
    });
  }

  function handleDeepLink() {
    const url = new URL(window.location.href);
    const id = url.searchParams.get("annotation");
    if (!id) return;
    url.searchParams.delete("annotation");
    const clean = url.pathname + (url.search || "") + url.hash;
    try {
      window.history.replaceState(null, "", clean);
    } catch (error) {}
    const annotation = state.annotations.get(id);
    if (!annotation || annotation.deleted) return;
    window.setTimeout(function () {
      if (!annotation.anchor.page_key || annotation.anchor.page_key === pageKey) {
        scrollToAnnotation(annotation);
      }
    }, 180);
  }

  function bindStorageSync() {
    if (window.BroadcastChannel) {
      try {
        state.channel = new BroadcastChannel("epub2web-annotations:" + contentId);
        state.channel.addEventListener("message", function (event) {
          const message = event.data;
          if (!message || message.type !== "annotation") return;
          const record = validateAnnotation(message.annotation);
          if (!record) return;
          const current = state.annotations.get(record.id);
          if (!current || Date.parse(record.updated) > Date.parse(current.updated)) {
            state.annotations.set(record.id, record);
            refresh();
            if (panel && panel.open) renderPanel();
          }
        });
      } catch (error) {
        state.channel = null;
      }
    }
    window.addEventListener("storage", function (event) {
      if (event.key !== localKey()) return;
      readLocalAnnotations().forEach(function (record) {
        const current = state.annotations.get(record.id);
        if (!current || Date.parse(record.updated) > Date.parse(current.updated)) {
          state.annotations.set(record.id, record);
        }
      });
      refresh();
      if (panel && panel.open) renderPanel();
    });
  }

  function refresh() {
    renderHighlights();
    if (panel && panel.open) renderPanel();
  }

  function init() {
    state.lastColor = readLastColor();
    updateToolbarColors();
    bookPage.setAttribute("tabindex", "-1");
    bindToolbar();
    bindCard();
    bindPanel();
    bindStorageDialog();
    bindNoteDialog();
    bindSelection();
    bindPageClicks();
    bindKeyboard();
    bindStorageSync();
    loadState()
      .then(handleDeepLink)
      .catch(function () {
        refresh();
      });
  }

  init();
})();
