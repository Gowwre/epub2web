import json
import re
from pathlib import Path

from bs4 import BeautifulSoup
from epub2web.generic import GenericExtractor
from epub2web.i18n import MESSAGES, SUPPORTED_LANGUAGES, translate, ui_messages
from epub2web.render import render_site

TEMPLATES = Path(__file__).resolve().parents[1] / "epub2web" / "templates"
ASSETS = Path(__file__).resolve().parents[1] / "epub2web" / "theme" / "assets"


def _static_template_keys() -> set[str]:
    keys = set()
    pattern = re.compile(r'data-i18n(?:-(?:aria-label|title|placeholder|html))?="([^"]+)"')
    for path in TEMPLATES.glob("*.html"):
        for key in pattern.findall(path.read_text(encoding="utf-8")):
            if "{{" not in key and "{%" not in key:
                keys.add(key)
    return keys


def _script_keys() -> set[str]:
    keys = set()
    for name in ("app.js", "annotations.js", "i18n.js"):
        text = (ASSETS / name).read_text(encoding="utf-8")
        keys.update(re.findall(r'\bt\("([^"]+)"', text))
    return keys


def test_language_tables_have_matching_keys():
    assert set(MESSAGES) == set(SUPPORTED_LANGUAGES)
    english = set(MESSAGES["en"])
    vietnamese = set(MESSAGES["vi"])
    assert english == vietnamese
    assert all(MESSAGES["en"][key].strip() for key in english)
    assert all(MESSAGES["vi"][key].strip() for key in vietnamese)


def test_template_and_script_keys_are_translated():
    english = set(MESSAGES["en"])
    used = _static_template_keys() | _script_keys()
    missing = used - english
    assert not missing, f"missing interface translations: {sorted(missing)}"


def test_translate_and_normalize_language():
    assert translate("vi", "home.startReading") == "Bắt đầu đọc"
    assert translate("vi-VN", "reader.language") == "Ngôn ngữ giao diện"
    assert translate("fr", "home.startReading") == "Start reading"
    assert translate("vi", "contents.minutes", minutes=12) == "12 phút"
    assert translate("en", "contents.minutes", minutes=12) == "12 min"
    assert set(ui_messages()) == {"en", "vi"}


def test_rendered_site_embeds_both_languages(tiny_epub, tmp_path: Path):
    content = tmp_path / "content"
    images = tmp_path / "images"
    site = tmp_path / "site"
    GenericExtractor(tiny_epub, content, images).run()
    render_site(content, site, site_url="http://localhost:8000")

    home = (site / "index.html").read_text(encoding="utf-8")
    soup = BeautifulSoup(home, "lxml")

    payload = soup.find("script", id="epub2web-ui-i18n")
    assert payload is not None
    messages = json.loads(payload.get_text())
    assert set(messages) == {"en", "vi"}
    assert messages["vi"]["home.startReading"] == "Bắt đầu đọc"
    assert messages["vi"]["reader.language"] == "Ngôn ngữ giao diện"
    assert 'name="reader-language"' in home
    assert 'data-i18n="reader.language"' in home
    assert 'data-i18n="home.startReading"' in home
    assert "data-language-toggle" in home
    assert "data-language-code" in home
    assert 'data-book-title="A Tiny Book"' in home
    assert 'id="epub2web-reading-map"' in home

    reading_map = json.loads(soup.find("script", id="epub2web-reading-map").get_text())
    assert all(entry["labelVi"] for entry in reading_map)

    hero = soup.select_one(".hero-intro")
    assert hero is not None
    assert hero.get("data-i18n") == "home.heroIntro"
    assert hero.get("data-hero-chapters")
    assert hero.get("data-hero-length")

    contents = (site / "contents" / "index.html").read_text(encoding="utf-8")
    assert 'data-i18n="contents.title"' in contents
    assert 'data-i18n="contents.intro"' in contents

    reading = (site / "read" / "1" / "index.html").read_text(encoding="utf-8")
    assert 'data-i18n="readTime.chapter"' in reading
    assert "/assets/i18n.js" in reading
    assert (site / "assets" / "i18n.js").is_file()

    not_found = (site / "404.html").read_text(encoding="utf-8")
    assert 'data-i18n="notFound.title"' in not_found


def test_rendered_site_detects_the_system_language(tiny_epub, tmp_path: Path):
    content = tmp_path / "content"
    images = tmp_path / "images"
    site = tmp_path / "site"
    GenericExtractor(tiny_epub, content, images).run()
    render_site(content, site, site_url="http://localhost:8000")

    home = (site / "index.html").read_text(encoding="utf-8")
    assert "navigator.languages" in home
    assert "navigator.language" in home
    assert "Intl.DateTimeFormat" in home
    assert "dataset.uiLang" in home

    i18n_js = (site / "assets" / "i18n.js").read_text(encoding="utf-8")
    assert "navigator.languages" in i18n_js
    assert "navigator.language" in i18n_js
    assert "Intl.DateTimeFormat" in i18n_js
    assert "systemLanguage" in i18n_js


def test_vietnamese_font_subsets_are_always_available(tiny_epub, tmp_path: Path):
    content = tmp_path / "content"
    images = tmp_path / "images"
    site = tmp_path / "site"
    GenericExtractor(tiny_epub, content, images).run()
    render_site(content, site, site_url="http://localhost:8000")

    css = (site / "assets" / "fonts.css").read_text(encoding="utf-8")
    for name in (
        "fraunces-vietnamese.woff2",
        "inter-vietnamese.woff2",
        "literata-vietnamese.woff2",
    ):
        assert name in css
        assert (site / "assets" / "fonts" / name).is_file()
