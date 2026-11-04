"""Interface translations for the Tkinter desktop app.

The desktop GUI keeps its language preference in the platform application-data
folder. Build logs from the worker stay in English because they mirror the
command-line output; everything the GUI itself writes is translated.
"""

from __future__ import annotations

import json
import locale
import os
import re
from pathlib import Path
from typing import Any

from .paths import app_data_dir

DEFAULT_LANGUAGE = "en"
SUPPORTED_LANGUAGES = ("en", "vi")

_PLACEHOLDER = re.compile(r"\{(\w+)\}")

MESSAGES: dict[str, dict[str, str]] = {
    "en": {
        # Header
        "header.update": "Update",
        "header.website": "Website",
        "header.github": "GitHub",
        "header.checkUpdates": "Check for updates",
        "header.checking": "Checking…",
        "header.switchToVietnamese": "Switch to Vietnamese",
        "header.switchToEnglish": "Switch to English",
        "brand.title": "Turn an EPUB into a website",
        "brand.subtitle": "A readable web edition, verified against the source.",
        # Source card
        "source.eyebrow": "SOURCE",
        "source.badge": "EPUB 2 / 3",
        "source.emptyTitle": "No EPUB selected",
        "source.emptyHint": "Choose a reflowable EPUB 2/3 file to begin.",
        "source.emptyHintDrop": ("Choose a reflowable EPUB 2/3 file, or drag and drop it here."),
        "source.choose": "Choose EPUB…",
        "source.useChoose": "Use Choose EPUB… instead.",
        "source.dndMissing": ("Drag and drop is unavailable because tkinterdnd2 is not installed."),
        "source.dndLoadFailed": (
            "Drag and drop is unavailable because TkDND could not load on this system."
        ),
        "source.dropLocked": "Stop the current preview before choosing another EPUB.",
        "source.dropOne": "Drop one EPUB 2 or 3 file to select it.",
        "source.dropTooMany": "Drop one EPUB at a time.",
        "source.dropFolder": "Drop an EPUB file, not a folder.",
        "source.dropNotEpub": "That file is not an EPUB. Drop a .epub file.",
        "source.notFoundTitle": "File not found",
        "source.notFoundMessage": "The selected EPUB is no longer available.",
        "source.notEpubTitle": "Not an EPUB",
        "source.notEpubMessage": "Choose a reflowable EPUB 2 or 3 file.",
        # Output and actions
        "output.eyebrow": "OUTPUT",
        "output.placeholder": "The generated site will appear here.",
        "output.change": "Change…",
        "output.folderLog": "Output folder: {path}",
        "actions.convert": "Convert",
        "actions.stop": "Stop",
        "actions.openPreview": "Open preview",
        # Status line and log hint
        "status.choose": "Choose an EPUB to begin.",
        "status.chooseOrDrop": "Choose or drop an EPUB to begin.",
        "status.ready": "Ready to convert.",
        "status.converting": "Converting…",
        "status.runningChecks": "Running fidelity and link checks…",
        "status.stopping": "Stopping…",
        "status.stoppingServer": "Stopping the preview server…",
        "status.siteBuilt": "Site built. Starting preview…",
        "status.startingPreview": "Starting the local preview server…",
        "status.previewRunning": "Preview running at {url}",
        "status.previewHint": ("Preview running. Use Stop to close the local server."),
        "status.previewUnavailable": "Preview unavailable.",
        "status.complete": "Conversion complete.",
        "status.checksPassed": "All checks passed.",
        "status.failed": "Conversion failed.",
        "status.buildFailedHint": "Build failed. The support report is ready.",
        "status.stopped": "Stopped.",
        "status.startFailed": "Could not start conversion.",
        "status.startFailedHint": "Build failed. See the error below.",
        "log.eyebrow": "BUILD LOG",
        "log.hint": "Fidelity and link checks appear here.",
        "log.selected": "Selected {name}",
        "log.converting": "Converting {name} …",
        "log.conversionComplete": "Conversion complete.",
        "log.conversionCompleteSite": "Conversion complete. Site: {site}",
        "log.previewStarted": "Preview server started.",
        # Progress
        "progress.working": "Working",
        "progress.counted": "{label} — {current} of {total} · {percent}%",
        "progress.simple": "{label}… {percent}%",
        "progress.hint": "{label} · {percent}% complete",
        "progress.start": "{label}…",
        "progress.countedLog": "{label}: {current} of {total}",
        "progress.done": "{label}: done",
        "progress.openingBook": "Opening book",
        "progress.layingOut": "Laying out pages",
        "progress.savingData": "Saving book data",
        "progress.preparingImages": "Preparing images",
        "progress.noImages": "No images to prepare",
        "progress.buildingPages": "Building pages",
        "progress.finishingSite": "Finishing site",
        "progress.checkingWords": "Checking every word",
        "progress.checkingLinks": "Checking links",
        # Dialogs and file pickers
        "dialog.details": "DETAILS",
        "dialog.supportReport": "SUPPORT REPORT",
        "dialog.supportReportDetail": "Support report:\n{report}",
        "dialog.ok": "OK",
        "dialog.openPreviewTitle": "Open preview",
        "dialog.previewAddress": "PREVIEW ADDRESS",
        "dialog.openGithubTitle": "Open GitHub",
        "dialog.openWebsiteTitle": "Open website",
        "dialog.openDownloadTitle": "Open download page",
        "dialog.address": "ADDRESS",
        "dialog.openAddress": "Open this address in your browser:",
        "dialog.openBrowserFailed": "Could not open the browser",
        "dialog.outputCreateTitle": "Could not create the output folder",
        "dialog.startFailedTitle": "Could not start conversion",
        "dialog.buildFailedTitle": "Build failed",
        "dialog.updateCheckTitle": "Could not check for updates",
        "dialog.updateCheckMessage": (
            "The update server could not be reached. Check your internet connection and try again."
        ),
        "dialog.noUpdateTitle": "No updates available",
        "dialog.noUpdateMessage": ("You are running epub2web {version}, the latest version."),
        "dialog.selectEpubTitle": "Choose an EPUB",
        "dialog.epubFiles": "EPUB books",
        "dialog.allFiles": "All files",
        "dialog.chooseOutputTitle": "Choose where to save the generated site",
        # Update dialog
        "update.titleSuffix": "Update available",
        "update.available": ("epub2web {version} is available. You are running {current}."),
        "update.whatsNew": "WHAT'S NEW",
        "update.notesFallback": "See the download page for details.",
        "update.notesLanguage": "Release notes are published in English.",
        "update.openDownload": "Open download page",
        "update.later": "Later",
        # Startup errors
        "error.startGui": "error: could not start the desktop GUI: {error}",
        "error.noDisplay": "This machine may not have a graphical display.",
    },
    "vi": {
        # Thanh đầu trang
        "header.update": "Cập nhật",
        "header.website": "Trang web",
        "header.github": "GitHub",
        "header.checkUpdates": "Kiểm tra cập nhật",
        "header.checking": "Đang kiểm tra…",
        "header.switchToVietnamese": "Chuyển sang tiếng Việt",
        "header.switchToEnglish": "Chuyển sang tiếng Anh",
        "brand.title": "Biến EPUB thành trang web",
        "brand.subtitle": "Bản đọc trên web dễ đọc, được đối chiếu với bản gốc.",
        # Thẻ nguồn
        "source.eyebrow": "NGUỒN",
        "source.badge": "EPUB 2 / 3",
        "source.emptyTitle": "Chưa chọn EPUB",
        "source.emptyHint": "Chọn tệp EPUB 2/3 có bố cục linh hoạt để bắt đầu.",
        "source.emptyHintDrop": (
            "Chọn tệp EPUB 2/3 có bố cục linh hoạt, hoặc kéo thả tệp vào đây."
        ),
        "source.choose": "Chọn EPUB…",
        "source.useChoose": "Hãy dùng Chọn EPUB… để chọn tệp.",
        "source.dndMissing": ("Không thể kéo thả vì tkinterdnd2 chưa được cài đặt."),
        "source.dndLoadFailed": ("Không thể kéo thả vì TkDND không tải được trên hệ thống này."),
        "source.dropLocked": ("Hãy dừng bản xem trước hiện tại trước khi chọn EPUB khác."),
        "source.dropOne": "Kéo thả một tệp EPUB 2 hoặc 3 để chọn.",
        "source.dropTooMany": "Mỗi lần chỉ kéo thả một tệp EPUB.",
        "source.dropFolder": "Hãy kéo thả tệp EPUB, không phải thư mục.",
        "source.dropNotEpub": "Tệp này không phải EPUB. Hãy kéo thả tệp .epub.",
        "source.notFoundTitle": "Không tìm thấy tệp",
        "source.notFoundMessage": "Tệp EPUB đã chọn không còn tồn tại.",
        "source.notEpubTitle": "Không phải EPUB",
        "source.notEpubMessage": "Chọn tệp EPUB 2 hoặc 3 có bố cục linh hoạt.",
        # Đầu ra và hành động
        "output.eyebrow": "ĐẦU RA",
        "output.placeholder": "Trang web được tạo sẽ hiện ở đây.",
        "output.change": "Thay đổi…",
        "output.folderLog": "Thư mục đầu ra: {path}",
        "actions.convert": "Chuyển đổi",
        "actions.stop": "Dừng",
        "actions.openPreview": "Mở bản xem trước",
        # Dòng trạng thái và gợi ý nhật ký
        "status.choose": "Chọn một tệp EPUB để bắt đầu.",
        "status.chooseOrDrop": "Chọn hoặc kéo thả một tệp EPUB để bắt đầu.",
        "status.ready": "Sẵn sàng chuyển đổi.",
        "status.converting": "Đang chuyển đổi…",
        "status.runningChecks": "Đang chạy kiểm tra độ trung thực và liên kết…",
        "status.stopping": "Đang dừng…",
        "status.stoppingServer": "Đang dừng máy chủ xem trước…",
        "status.siteBuilt": "Đã dựng xong trang. Đang khởi động bản xem trước…",
        "status.startingPreview": "Đang khởi động máy chủ xem trước cục bộ…",
        "status.previewRunning": "Bản xem trước đang chạy tại {url}",
        "status.previewHint": ("Bản xem trước đang chạy. Dùng Dừng để tắt máy chủ cục bộ."),
        "status.previewUnavailable": "Không thể mở bản xem trước.",
        "status.complete": "Chuyển đổi hoàn tất.",
        "status.checksPassed": "Mọi bước kiểm tra đều đạt.",
        "status.failed": "Chuyển đổi thất bại.",
        "status.buildFailedHint": "Quá trình dựng thất bại. Báo cáo hỗ trợ đã sẵn sàng.",
        "status.stopped": "Đã dừng.",
        "status.startFailed": "Không thể bắt đầu chuyển đổi.",
        "status.startFailedHint": "Quá trình dựng thất bại. Xem lỗi bên dưới.",
        "log.eyebrow": "NHẬT KÝ DỰNG",
        "log.hint": ("Các bước kiểm tra độ trung thực và liên kết sẽ hiện ở đây."),
        "log.selected": "Đã chọn {name}",
        "log.converting": "Đang chuyển đổi {name} …",
        "log.conversionComplete": "Chuyển đổi hoàn tất.",
        "log.conversionCompleteSite": "Chuyển đổi hoàn tất. Trang: {site}",
        "log.previewStarted": "Máy chủ xem trước đã khởi động.",
        # Tiến trình
        "progress.working": "Đang xử lý",
        "progress.counted": "{label} — {current}/{total} · {percent}%",
        "progress.simple": "{label}… {percent}%",
        "progress.hint": "{label} · đã xong {percent}%",
        "progress.start": "{label}…",
        "progress.countedLog": "{label}: {current}/{total}",
        "progress.done": "{label}: xong",
        "progress.openingBook": "Đang mở sách",
        "progress.layingOut": "Đang dàn trang",
        "progress.savingData": "Đang lưu dữ liệu sách",
        "progress.preparingImages": "Đang chuẩn bị hình ảnh",
        "progress.noImages": "Không có hình ảnh cần chuẩn bị",
        "progress.buildingPages": "Đang dựng trang",
        "progress.finishingSite": "Đang hoàn thiện trang",
        "progress.checkingWords": "Đang kiểm tra từng từ",
        "progress.checkingLinks": "Đang kiểm tra liên kết",
        # Hộp thoại và chọn tệp
        "dialog.details": "CHI TIẾT",
        "dialog.supportReport": "BÁO CÁO HỖ TRỢ",
        "dialog.supportReportDetail": "Báo cáo hỗ trợ:\n{report}",
        "dialog.ok": "OK",
        "dialog.openPreviewTitle": "Mở bản xem trước",
        "dialog.previewAddress": "ĐỊA CHỈ XEM TRƯỚC",
        "dialog.openGithubTitle": "Mở GitHub",
        "dialog.openWebsiteTitle": "Mở trang web",
        "dialog.openDownloadTitle": "Mở trang tải xuống",
        "dialog.address": "ĐỊA CHỈ",
        "dialog.openAddress": "Mở địa chỉ này trong trình duyệt:",
        "dialog.openBrowserFailed": "Không thể mở trình duyệt",
        "dialog.outputCreateTitle": "Không thể tạo thư mục đầu ra",
        "dialog.startFailedTitle": "Không thể bắt đầu chuyển đổi",
        "dialog.buildFailedTitle": "Dựng trang thất bại",
        "dialog.updateCheckTitle": "Không thể kiểm tra cập nhật",
        "dialog.updateCheckMessage": (
            "Không kết nối được máy chủ cập nhật. Hãy kiểm tra kết nối mạng và thử lại."
        ),
        "dialog.noUpdateTitle": "Không có bản cập nhật mới",
        "dialog.noUpdateMessage": ("Bạn đang dùng epub2web {version}, phiên bản mới nhất."),
        "dialog.selectEpubTitle": "Chọn EPUB",
        "dialog.epubFiles": "Sách EPUB",
        "dialog.allFiles": "Tất cả tệp",
        "dialog.chooseOutputTitle": "Chọn nơi lưu trang web được tạo",
        # Hộp thoại cập nhật
        "update.titleSuffix": "Có bản cập nhật",
        "update.available": ("epub2web {version} đã có. Bạn đang dùng {current}."),
        "update.whatsNew": "CÓ GÌ MỚI",
        "update.notesFallback": "Xem trang tải xuống để biết chi tiết.",
        "update.notesLanguage": "Ghi chú phát hành được công bố bằng tiếng Anh.",
        "update.openDownload": "Mở trang tải xuống",
        "update.later": "Để sau",
        # Lỗi khởi động
        "error.startGui": "lỗi: không thể khởi động giao diện desktop: {error}",
        "error.noDisplay": "Máy này có thể không có màn hình đồ họa.",
    },
}

PROGRESS_LABELS = {
    "Opening book": "progress.openingBook",
    "Laying out pages": "progress.layingOut",
    "Saving book data": "progress.savingData",
    "Preparing images": "progress.preparingImages",
    "No images to prepare": "progress.noImages",
    "Building pages": "progress.buildingPages",
    "Finishing site": "progress.finishingSite",
    "Checking every word": "progress.checkingWords",
    "Checking links": "progress.checkingLinks",
}


def normalize_language(value: str | None) -> str:
    key = (value or "").strip().lower().replace("_", "-")
    base = key.split("-", 1)[0]
    return base if base in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE


def _stored_language(value: object) -> str:
    if not isinstance(value, str):
        return ""
    key = value.strip().lower().replace("_", "-").split("-", 1)[0]
    return key if key in SUPPORTED_LANGUAGES else ""


def _language_from_locale(value: str) -> str:
    key = (value or "").strip().lower().replace("_", "-")
    token = key.split("-", 1)[0].split(".", 1)[0].split("@", 1)[0]
    if token in {"vi", "vietnamese"}:
        return "vi"
    if token in {"en", "english", "c", "posix"}:
        return "en"
    return ""


def _locale_values() -> list[str]:
    values: list[str] = []
    for name in ("LC_ALL", "LANGUAGE", "LC_MESSAGES", "LANG"):
        raw = os.environ.get(name, "").strip()
        if not raw:
            continue
        if name == "LANGUAGE":
            values.extend(part.strip() for part in raw.split(":") if part.strip())
        else:
            values.append(raw)

    for category_name in ("LC_MESSAGES", "LC_CTYPE"):
        category = getattr(locale, category_name, None)
        if category is None:
            continue
        try:
            language, _encoding = locale.getlocale(category)
        except (TypeError, ValueError, locale.Error):
            continue
        if language:
            values.append(language)
    return values


def system_language() -> str:
    """Return the interface language for the current system locale.

    The highest-priority locale decides the result: Vietnamese selects
    Vietnamese, and every other locale falls back to English. This mirrors the
    browser and landing-site detection so the desktop app opens in the same
    language as the rest of the product.
    """
    values = _locale_values()
    if not values:
        return DEFAULT_LANGUAGE
    return _language_from_locale(values[0]) or DEFAULT_LANGUAGE


def translate(language: str | None, key: str, **values: Any) -> str:
    table = MESSAGES[normalize_language(language)]
    template = table.get(key)
    if template is None:
        template = MESSAGES[DEFAULT_LANGUAGE].get(key, key)

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        return str(values[name]) if name in values else match.group(0)

    return _PLACEHOLDER.sub(replace, template)


def progress_label(language: str | None, label: str) -> str:
    key = PROGRESS_LABELS.get(label)
    return translate(language, key) if key else label


def settings_path() -> Path:
    return app_data_dir() / "settings.json"


def load_language(path: Path | None = None) -> str:
    override = os.environ.get("EPUB2WEB_LANGUAGE")
    if override:
        return normalize_language(override)
    destination = path or settings_path()
    try:
        data = json.loads(destination.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return system_language()
    if not isinstance(data, dict):
        return system_language()
    return _stored_language(data.get("language")) or system_language()


def save_language(language: str, path: Path | None = None) -> None:
    destination = path or settings_path()
    try:
        data: dict[str, Any] = {}
        if destination.is_file():
            try:
                existing = json.loads(destination.read_text(encoding="utf-8"))
                if isinstance(existing, dict):
                    data.update(existing)
            except (OSError, ValueError):
                pass
        data["language"] = normalize_language(language)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(destination.name + ".tmp")
        temporary.write_text(
            json.dumps(data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.replace(destination)
    except OSError:
        # A language preference is not worth interrupting a conversion.
        pass
