/* epub2web interface language */
(function () {
  "use strict";

  const root = document.documentElement;
  const STORAGE_KEY = "epub2web-ui-lang";
  const SOURCE_ID = "epub2web-ui-i18n";
  const FALLBACK = "en";

  let messages = {};
  try {
    const element = document.getElementById(SOURCE_ID);
    if (element) messages = JSON.parse(element.textContent || "{}");
  } catch (error) {
    messages = {};
  }

  const supported = Object.keys(messages).filter(function (language) {
    return messages[language] && typeof messages[language] === "object";
  });
  if (!supported.length) {
    window.epub2webI18n = {
      t: function (key) {
        return key;
      },
      apply: function () {},
      setLanguage: function () {},
      language: function () {
        return FALLBACK;
      },
      locale: function () {
        return "en-US";
      },
      formatNumber: function (value) {
        return String(value);
      },
      supported: [],
    };
    return;
  }

  function normalize(value) {
    const key = String(value || "")
      .trim()
      .toLowerCase()
      .replace("_", "-");
    if (key.indexOf("vi") === 0 && supported.indexOf("vi") !== -1) return "vi";
    if (key.indexOf("en") === 0 && supported.indexOf("en") !== -1) return "en";
    return "";
  }

  function storedLanguage() {
    try {
      const value = localStorage.getItem(STORAGE_KEY);
      return supported.indexOf(value) !== -1 ? value : "";
    } catch (error) {
      return "";
    }
  }

  function systemLanguage() {
    let candidate = "";
    try {
      if (navigator.languages && navigator.languages.length) {
        candidate = navigator.languages[0];
      }
    } catch (error) {}
    if (!candidate) {
      try {
        candidate = navigator.language || "";
      } catch (error) {}
    }
    if (!candidate) {
      try {
        candidate = Intl.DateTimeFormat().resolvedOptions().locale || "";
      } catch (error) {}
    }
    const tag = String(candidate).trim().toLowerCase().replace(/_/g, "-");
    return tag === "vi" || tag.indexOf("vi-") === 0 ? "vi" : "en";
  }

  function preferredLanguage() {
    const stored = storedLanguage();
    if (stored) return stored;
    const system = systemLanguage();
    if (supported.indexOf(system) !== -1) return system;
    return supported.indexOf(FALLBACK) !== -1 ? FALLBACK : supported[0];
  }

  let language = preferredLanguage();

  function locale() {
    return language === "vi" ? "vi-VN" : "en-US";
  }

  function formatNumber(value) {
    const number = Number(value);
    if (!isFinite(number)) return String(value);
    try {
      return new Intl.NumberFormat(locale()).format(number);
    } catch (error) {
      return String(number);
    }
  }

  function t(key, values) {
    const table = messages[language] || {};
    const fallback = messages[FALLBACK] || {};
    let template = table[key];
    if (typeof template !== "string") template = fallback[key];
    if (typeof template !== "string") return key;
    if (!values) return template;
    return template.replace(/\{(\w+)\}/g, function (match, name) {
      return Object.prototype.hasOwnProperty.call(values, name)
        ? String(values[name])
        : match;
    });
  }

  function readValues(element) {
    const values = {};
    const raw = element.getAttribute("data-i18n-vars");
    if (raw) {
      try {
        const parsed = JSON.parse(raw);
        if (parsed && typeof parsed === "object") Object.assign(values, parsed);
      } catch (error) {}
    }
    Array.from(element.attributes).forEach(function (attribute) {
      if (attribute.name.indexOf("data-var-") !== 0) return;
      const name = attribute.name
        .slice("data-var-".length)
        .replace(/-([a-z])/g, function (_, letter) {
          return letter.toUpperCase();
        });
      values[name] = attribute.value;
    });
    return values;
  }

  function heroSummary(element) {
    const parts = [];
    const chapters = element.getAttribute("data-hero-chapters");
    const figures = element.getAttribute("data-hero-figures");
    const length = element.getAttribute("data-hero-length");
    const unit = element.getAttribute("data-hero-unit");
    if (chapters) {
      const key =
        Number(chapters) === 1 ? "home.heroChaptersOne" : "home.heroChapters";
      parts.push(t(key, { count: formatNumber(chapters) }));
    }
    if (figures) {
      const key =
        Number(figures) === 1 ? "home.heroFiguresOne" : "home.heroFigures";
      parts.push(t(key, { count: formatNumber(figures) }));
    }
    if (length) {
      let key;
      if (unit === "characters") {
        key = Number(length) === 1 ? "home.heroCharactersOne" : "home.heroCharacters";
      } else {
        key = Number(length) === 1 ? "home.heroWordsOne" : "home.heroWords";
      }
      parts.push(t(key, { count: formatNumber(length) }));
    }
    return parts.join(", ");
  }

  function valuesFor(element, key) {
    const values = readValues(element);
    if (key === "home.heroIntro") values.summary = heroSummary(element);
    return values;
  }

  function markLanguage(element) {
    if (language === FALLBACK) element.removeAttribute("lang");
    else element.setAttribute("lang", language);
  }

  function translateText(element) {
    const key = element.getAttribute("data-i18n");
    if (!key) return;
    element.textContent = t(key, valuesFor(element, key));
    markLanguage(element);
  }

  function translateHtml(element) {
    const key = element.getAttribute("data-i18n-html");
    if (!key) return;
    element.innerHTML = t(key, valuesFor(element, key));
    markLanguage(element);
  }

  function translateAttribute(element, attribute) {
    const key = element.getAttribute("data-i18n-" + attribute);
    if (!key) return;
    element.setAttribute(attribute, t(key, valuesFor(element, key)));
  }

  function apply(scope) {
    const container = scope || document;
    root.dataset.uiLang = language;
    container.querySelectorAll("[data-i18n]").forEach(translateText);
    container.querySelectorAll("[data-i18n-html]").forEach(translateHtml);
    ["aria-label", "title", "placeholder"].forEach(function (attribute) {
      container
        .querySelectorAll("[data-i18n-" + attribute + "]")
        .forEach(function (element) {
          translateAttribute(element, attribute);
        });
    });
    syncControls(container);
    syncTitle();
    syncLanguageButton();
  }

  function syncControls(scope) {
    const container = scope || document;
    container
      .querySelectorAll('input[name="reader-language"]')
      .forEach(function (input) {
        input.checked = input.value === language;
      });
  }

  function syncTitle() {
    const body = document.body;
    if (!body) return;
    const book = body.getAttribute("data-book-title") || "";
    if (body.classList.contains("page-contents")) {
      document.title = t("document.contents", { book: book });
    } else if (body.classList.contains("page-404")) {
      document.title = t("document.notFound", { book: book });
    }
  }

  function syncLanguageButton() {
    document.querySelectorAll("[data-language-toggle]").forEach(function (button) {
      const code = button.querySelector("[data-language-code]");
      if (code) code.textContent = language === "vi" ? "VI" : "EN";
      const label = t(
        language === "vi" ? "language.switchToEnglish" : "language.switchToVietnamese"
      );
      button.setAttribute("aria-label", label);
      button.setAttribute("title", label);
    });
  }

  function announce() {
    const event = new CustomEvent("epub2web:languagechange", {
      detail: { language: language, locale: locale() },
    });
    document.dispatchEvent(event);
  }

  function setLanguage(next, options) {
    const normalized = normalize(next) || FALLBACK;
    const previous = language;
    language = normalized;
    try {
      localStorage.setItem(STORAGE_KEY, language);
    } catch (error) {}
    apply(document);
    if (!options || !options.silent) {
      if (previous !== language || (options && options.force)) announce();
    }
  }

  function handleInput(event) {
    const input = event.target;
    if (!input || input.name !== "reader-language") return;
    if (input.value !== language) setLanguage(input.value);
  }

  function handleLanguageToggle(event) {
    const button = event.target.closest
      ? event.target.closest("[data-language-toggle]")
      : null;
    if (!button) return;
    setLanguage(language === "vi" ? "en" : "vi");
  }

  document.addEventListener("change", handleInput);
  document.addEventListener("click", handleLanguageToggle);
  window.addEventListener("storage", function (event) {
    if (event.key !== STORAGE_KEY) return;
    const next = storedLanguage() || preferredLanguage();
    if (next !== language) {
      language = next;
      apply(document);
      announce();
    }
  });

  window.epub2webI18n = {
    t: t,
    apply: apply,
    setLanguage: setLanguage,
    language: function () {
      return language;
    },
    locale: locale,
    formatNumber: formatNumber,
    supported: supported.slice(),
  };

  apply(document);
})();
