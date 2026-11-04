from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAYOUT = ROOT / "site" / "src" / "layouts" / "BaseLayout.astro"
HEADER = ROOT / "site" / "src" / "components" / "SiteHeader.astro"


def test_landing_layout_detects_vietnamese_system_locale():
    layout = LAYOUT.read_text(encoding="utf-8")

    assert "data-locale-href-en={englishPath}" in layout
    assert "data-locale-href-vi={vietnamesePath}" in layout
    assert 'localStorage.getItem("epub2web-ui-lang")' in layout
    assert "navigator.languages" in layout
    assert "navigator.language" in layout
    assert "Intl.DateTimeFormat" in layout
    assert 'preferred !== "vi" || current !== "en"' in layout
    assert "window.location.replace" in layout
    assert "window.location.search" in layout
    assert "window.location.hash" in layout


def test_landing_language_switch_remembers_the_choice():
    header = HEADER.read_text(encoding="utf-8")

    assert "data-language-switch={otherLocale}" in header
    assert 'const languageKey = "epub2web-ui-lang"' in header
    assert "localStorage.setItem(languageKey, language)" in header
    assert 'link.addEventListener("click", rememberLanguage)' in header
    assert 'link.addEventListener("auxclick", rememberLanguage)' in header
