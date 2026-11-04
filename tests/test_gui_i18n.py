import json
import re
from pathlib import Path

from epub2web import gui_i18n, tk_app


def _used_keys() -> set[str]:
    source = Path(tk_app.__file__).read_text(encoding="utf-8")
    keys = set(
        re.findall(
            r'(?:_t|_set_status_key|_set_log_hint_key)\(\s*"([^"]+)"',
            source,
        )
    )
    keys.update(gui_i18n.PROGRESS_LABELS.values())
    return keys


def test_gui_language_tables_have_matching_keys():
    assert set(gui_i18n.MESSAGES) == set(gui_i18n.SUPPORTED_LANGUAGES)
    english = set(gui_i18n.MESSAGES["en"])
    vietnamese = set(gui_i18n.MESSAGES["vi"])
    assert english == vietnamese
    assert all(gui_i18n.MESSAGES["en"][key].strip() for key in english)
    assert all(gui_i18n.MESSAGES["vi"][key].strip() for key in vietnamese)


def test_gui_keys_used_by_the_view_are_translated():
    missing = _used_keys() - set(gui_i18n.MESSAGES["en"])
    assert not missing, f"missing GUI translations: {sorted(missing)}"


def test_gui_translate_and_language_names():
    assert gui_i18n.normalize_language("vi-VN") == "vi"
    assert gui_i18n.normalize_language("fr") == "en"
    assert gui_i18n.translate("vi", "actions.convert") == "Chuyển đổi"
    assert gui_i18n.translate("vi", "status.previewRunning", url="http://x") == (
        "Bản xem trước đang chạy tại http://x"
    )
    assert gui_i18n.translate("vi", "progress.countedLog", label="X", current="1", total="2") == (
        "X: 1/2"
    )
    assert gui_i18n.progress_label("vi", "Building pages") == "Đang dựng trang"
    assert gui_i18n.progress_label("vi", "Unknown label") == "Unknown label"


def test_gui_settings_round_trip(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("EPUB2WEB_LANGUAGE", raising=False)
    settings = tmp_path / "settings.json"
    assert gui_i18n.load_language(settings) == "en"

    gui_i18n.save_language("vi-VN", settings)
    assert gui_i18n.load_language(settings) == "vi"
    data = json.loads(settings.read_text(encoding="utf-8"))
    assert data == {"language": "vi"}

    data["other"] = "keep me"
    settings.write_text(json.dumps(data), encoding="utf-8")
    gui_i18n.save_language("en", settings)
    assert json.loads(settings.read_text(encoding="utf-8"))["other"] == "keep me"


def test_gui_language_environment_override(tmp_path: Path, monkeypatch):
    settings = tmp_path / "settings.json"
    gui_i18n.save_language("en", settings)
    monkeypatch.setenv("EPUB2WEB_LANGUAGE", "vi")
    assert gui_i18n.load_language(settings) == "vi"


def test_tk_app_uses_translated_language_button():
    app = object.__new__(tk_app.Epub2WebApp)
    app.language = "en"
    assert app._t("actions.convert") == "Convert"
    assert app._language_code() == "VI"

    app.language = "vi"
    assert app._t("actions.convert") == "Chuyển đổi"
    assert app._language_code() == "EN"
    assert app._format_count(12345) == "12.345"

    app.language = "en"
    assert app._format_count(12345) == "12,345"


def test_dnd_unavailable_message_is_localized(monkeypatch):
    monkeypatch.setattr(tk_app, "TkinterDnD", None)
    assert "tkinterdnd2" in tk_app._dnd_unavailable_message("en")
    assert "tkinterdnd2" in tk_app._dnd_unavailable_message("vi")
    assert "cài đặt" in tk_app._dnd_unavailable_message("vi")
