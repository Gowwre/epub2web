# ruff: noqa: RUF001

from epub2web.fonts import (
    cjk_region,
    cjk_regions,
    detect_scripts,
    is_rtl_language,
    render_font_css,
    select_font_faces,
    uses_character_metrics,
)


def test_detect_scripts_finds_multiple_writing_systems():
    text = "Ελληνικά Кириллица العربية עברית देवनागरी ไทย 你好 こんにちは 안녕하세요"
    assert detect_scripts(text) == {
        "greek",
        "cyrillic",
        "arabic",
        "hebrew",
        "devanagari",
        "thai",
        "cjk",
    }


def test_rtl_and_character_metric_languages():
    assert is_rtl_language("ar-SA")
    assert is_rtl_language("he")
    assert is_rtl_language("az-Arab")
    assert not is_rtl_language("en")
    assert uses_character_metrics("zh-Hant")
    assert uses_character_metrics("ja")
    assert uses_character_metrics("th")
    assert not uses_character_metrics("fr")


def test_cjk_region_uses_script_and_language():
    assert cjk_region("en", {ord("你")}) == "sc"
    assert cjk_region("en", {ord("あ")}) == "jp"
    assert cjk_region("en", {ord("한")}) == "kr"
    assert cjk_region("zh-TW", {ord("你")}) == "tc"
    assert cjk_region("zh-Hant-TW", {ord("你")}) == "tc"
    assert cjk_region("ja", set()) == "jp"


def test_cjk_regions_cover_mixed_scripts():
    assert cjk_regions("ja", {ord("漢"), ord("あ")}) == ["jp"]
    assert cjk_regions("zh-Hant", {ord("漢")}) == ["tc"]
    assert cjk_regions("en", {ord("漢"), ord("あ")}) == ["jp", "sc"]
    assert cjk_regions("en", {ord("漢"), ord("あ"), ord("한")}) == ["jp", "kr", "sc"]
    assert cjk_regions("zh", {ord("漢"), ord("あ")}) == ["sc", "jp"]


def test_font_selection_includes_only_used_scripts():
    text = "Γειά σου. مرحبا. 你好世界"
    scripts = detect_scripts(text)
    codepoints = {ord(character) for character in text if ord(character) >= 0x0300}
    faces, regions = select_font_faces(scripts, "en", codepoints)

    files = {face["file"] for face in faces}
    assert "literata-greek.woff2" in files
    assert "noto-naskh-arabic-arabic.woff2" in files
    assert "noto-serif-hebrew-hebrew.woff2" not in files
    assert "noto-serif-thai-thai.woff2" not in files
    assert regions == ["sc"]
    assert any(path.startswith("cjk/sc/") for path in files)
    assert not any(path.startswith("cjk/jp/") for path in files)


def test_font_css_is_self_contained():
    scripts = detect_scripts("Γειά σου. مرحبا.")
    codepoints = {ord(character) for character in "Γειά σου. مرحبا." if ord(character) >= 0x0300}
    faces, _ = select_font_faces(scripts, "en", codepoints)
    css = render_font_css(faces)
    assert "http://" not in css
    assert "https://" not in css
    assert 'font-family: "Literata"' in css
    assert 'font-family: "Noto Naskh Arabic"' in css
    assert 'url("fonts/literata-greek.woff2")' in css
