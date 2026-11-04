# ruff: noqa: RUF001

"""Interface translations for the generated reader.

The reader ships English and Vietnamese labels. Book text and book metadata are
never translated: only the interface chrome (navigation, settings, search,
highlights, notes, and accessibility labels) changes with the selected language.

The dictionaries are embedded in each generated page as JSON and applied by
``theme/assets/i18n.js``. Keeping the strings here gives the templates and the
tests one source of truth.
"""

from __future__ import annotations

import re
from typing import Any

DEFAULT_LANGUAGE = "en"
SUPPORTED_LANGUAGES = ("en", "vi")

_PLACEHOLDER = re.compile(r"\{(\w+)\}")

MESSAGES: dict[str, dict[str, str]] = {
    "en": {
        # Chrome, navigation, footer
        "chrome.skipToContent": "Skip to content",
        "chrome.brandHome": "{initial} — {title} — home",
        "chrome.primaryNav": "Primary",
        "chrome.secondaryNav": "Secondary",
        "nav.contents": "Contents",
        "nav.read": "Read",
        "footer.browserEdition": "A browser edition.",
        "footer.browserEditionOf": "A browser edition of the {subtitle}.",
        "footer.unabridged": "This browser edition is unabridged.",
        "footer.rightsFallback": "Text rights belong to the respective rights holder.",
        "footer.colophon": "Colophon",
        "footer.builtWith": (
            "Built with a deterministic extraction pipeline and a text-fidelity gate."
        ),
        "footer.frontMatter": "Front matter",
        # Search
        "search.open": "Search the book",
        "search.openTitle": "Search the book (/)",
        "search.eyebrow": "Full text",
        "search.title": "Search the book",
        "search.close": "Close search",
        "search.inputLabel": "Search the book",
        "search.placeholder": "Search the book…",
        "search.prompt": "Type a word or phrase.",
        "search.indexed": "{count} sections indexed. Type to search.",
        "search.loading": "Loading the search index…",
        "search.noMatches": "No matches for “{query}”.",
        "search.oneResult": "1 result for “{query}”",
        "search.manyResults": "{count} results for “{query}”",
        "search.showingFirst": " · showing the first {count}",
        "search.unavailable": ("Search index unavailable. Serve the site with `epub2web --serve`."),
        "search.hint": (
            "Press <kbd>/</kbd> anywhere to open search, <kbd>↑</kbd><kbd>↓</kbd> "
            "to choose a result, <kbd>Enter</kbd> to open it, <kbd>Esc</kbd> to close."
        ),
        # Theme and reading settings
        "language.switch": "Switch language",
        "language.switchToEnglish": "Switch to English",
        "language.switchToVietnamese": "Switch to Vietnamese",
        "theme.switch": "Switch color theme",
        "theme.switchTo": "Switch to {mode} theme",
        "theme.light": "light",
        "theme.dark": "dark",
        "reader.open": "Reading settings",
        "reader.eyebrow": "Reading",
        "reader.title": "Reading settings",
        "reader.close": "Close reading settings",
        "reader.textSize": "Text size",
        "reader.small": "Small",
        "reader.default": "Default",
        "reader.large": "Large",
        "reader.extraLarge": "Extra large",
        "reader.lineSpacing": "Line spacing",
        "reader.compact": "Compact",
        "reader.relaxed": "Relaxed",
        "reader.paragraphs": "Paragraphs",
        "reader.spaced": "Spaced",
        "reader.indented": "Indented",
        "reader.pageWidth": "Page width",
        "reader.narrow": "Narrow",
        "reader.standard": "Standard",
        "reader.wide": "Wide",
        "reader.theme": "Theme",
        "reader.auto": "Auto",
        "reader.light": "Light",
        "reader.dark": "Dark",
        "reader.language": "Interface language",
        "reader.note": (
            "These settings apply only to this browser. Auto follows your device "
            "theme. Your book is unchanged."
        ),
        "reader.reset": "Reset to defaults",
        # Keyboard shortcuts
        "shortcuts.open": "Keyboard shortcuts",
        "shortcuts.openTitle": "Keyboard shortcuts (?)",
        "shortcuts.title": "Keyboard shortcuts",
        "shortcuts.close": "Close keyboard shortcuts",
        "shortcuts.eyebrow": "Reader",
        "shortcuts.reading": "Reading",
        "shortcuts.anywhere": "Anywhere",
        "shortcuts.searchResults": "Search results",
        "shortcuts.noteComposer": "Note composer",
        "shortcuts.h": "Highlight the selected text",
        "shortcuts.n": "Add a note to the selected text",
        "shortcuts.shiftA": "Open or close highlights and notes",
        "shortcuts.arrows": "Previous or next chapter",
        "shortcuts.slash": "Search the book",
        "shortcuts.question": "Show this shortcut list",
        "shortcuts.escape": "Close a toolbar, card, composer, or panel",
        "shortcuts.upDown": "Choose a result",
        "shortcuts.enter": "Open the chosen result",
        "shortcuts.ctrlEnter": "Save the note",
        "shortcuts.escapeCancel": "Cancel and close",
        "shortcuts.note": (
            "Shortcuts are ignored while you are typing in a field. On a touch "
            "device, use the header buttons and the selection toolbar."
        ),
        "shortcuts.srH": "Shortcut H: ",
        "shortcuts.srN": "Shortcut N: ",
        "shortcuts.srShiftA": "Shortcut Shift plus A: ",
        "shortcuts.srArrows": "Shortcut Left arrow or Right arrow: ",
        "shortcuts.srSlash": "Shortcut slash: ",
        "shortcuts.srQuestion": "Shortcut question mark: ",
        "shortcuts.srEscape": "Shortcut Escape: ",
        "shortcuts.srUpDown": "Shortcut Up arrow or Down arrow: ",
        "shortcuts.srEnter": "Shortcut Enter: ",
        "shortcuts.srCtrlEnter": "Shortcut Control or Command plus Enter: ",
        # Contents menu and sidebar
        "menu.open": "Open contents",
        "menu.close": "Close contents",
        "menu.sections": "Sections",
        "sidebar.contents": "Contents",
        "sidebar.allChapters": "All chapters",
        "sidebar.about": "About this edition",
        "sidebar.search": "Search the book",
        "sidebar.label": "Book contents",
        # Chapter navigation
        "pagination.previous": "Previous",
        "pagination.next": "Next",
        "pagination.label": "Chapter navigation",
        "pagination.contents": "Contents",
        "pagination.about": "About this edition",
        "pagination.top": "Back to top",
        # Home page
        "home.browserEdition": "A browser edition",
        "home.startReading": "Start reading",
        "home.continueReading": "Continue reading",
        "home.continueReadingLabel": "Continue reading: {label}",
        "home.startOver": "Start over",
        "home.startOverTitle": "Clear the saved reading position",
        "home.read": "Read",
        "home.headingChapters": "The chapters",
        "home.fullContents": "Full contents",
        "home.chapterMeta": "{sections} sections · {minutes} min read",
        "home.chapterMetaOneSection": "1 section · {minutes} min read",
        "home.chapterMetaNoSections": "{minutes} min read",
        "home.alsoInEdition": "Also in this edition",
        "home.colophonEyebrow": "Colophon",
        "home.aboutEdition": "About this edition",
        "home.colophonText": (
            "This is the complete text of {title}{subtitle}, built from {source} as a "
            "static website. Navigation, scripts, and hidden layers are omitted; the "
            "words, headings, figures, captions, notes, references, and index remain."
        ),
        "home.fidelityText": (
            "Every paragraph is checked against the source by a text-fidelity gate. A "
            "build fails if a word is added, dropped, or moved. The design is the only "
            "thing that changes."
        ),
        "home.unabridgedPublisher": (
            "This browser edition is unabridged and is not affiliated with the publisher."
        ),
        "home.typography": "Typography",
        "home.build": "Build",
        "home.search": "Search",
        "home.source": "Source",
        "home.searchValue": "Built-in full-text index",
        "home.heroIntro": (
            "The complete text, set for the browser. {summary} — with nothing abridged."
        ),
        "home.heroIntroBare": ("The complete text, set for the browser, with nothing abridged."),
        "home.heroChapters": "{count} chapters",
        "home.heroChaptersOne": "1 chapter",
        "home.heroFigures": "{count} figures",
        "home.heroFiguresOne": "1 figure",
        "home.heroWords": "{count} words",
        "home.heroWordsOne": "1 word",
        "home.heroCharacters": "{count} characters",
        "home.heroCharactersOne": "1 character",
        "stats.chapters": "Chapters",
        "stats.words": "Words",
        "stats.characters": "Characters",
        "stats.figures": "Figures",
        # Contents page
        "contents.title": "CONTENTS",
        "contents.intro": (
            "Every chapter and section, plus the front and back matter. Every section is linked."
        ),
        "contents.quickLinks": "Quick links",
        "contents.minutes": "{minutes} min",
        # Page metadata
        "readTime.minutes": "{minutes} min read",
        "readTime.chapter": "Chapter {current} of {total} · {minutes} min read",
        # Highlight and note tools
        "toolbar.label": "Highlight or note this selection",
        "toolbar.highlight": "Highlight",
        "toolbar.highlightTitle": "Highlight (H)",
        "toolbar.note": "Note",
        "toolbar.noteTitle": "Add a note (N)",
        "toolbar.chooseColor": "Choose highlight color",
        "toolbar.colorGroup": "Highlight color",
        "toolbar.cardLabel": "Highlight",
        "toolbar.closeCard": "Close highlight",
        "toolbar.addNote": "Add note",
        "toolbar.color": "Color",
        "toolbar.copy": "Copy",
        "toolbar.remove": "Remove",
        "color.yellow": "Yellow highlight",
        "color.green": "Green highlight",
        "color.blue": "Blue highlight",
        "color.pink": "Pink highlight",
        "color.purple": "Purple highlight",
        # Note composer
        "note.addTitle": "Add a note",
        "note.editTitle": "Edit note",
        "note.close": "Close note",
        "note.label": "Your note",
        "note.placeholder": "Write a note…",
        "note.placeholderOptional": "Add a note (optional)",
        "note.hint": (
            "Press <kbd>Ctrl</kbd>/<kbd>⌘</kbd> + <kbd>Enter</kbd> to save. "
            "<kbd>Esc</kbd> to cancel."
        ),
        "note.hintLabel": "Press Control or Command plus Enter to save. Escape to cancel.",
        "note.remove": "Remove note",
        "note.cancel": "Cancel",
        "note.save": "Done",
        # Highlights and notes panel
        "annotations.open": "Highlights and notes",
        "annotations.openCountOne": "Highlights and notes, 1 item",
        "annotations.openCount": "Highlights and notes, {count} items",
        "annotations.title": "Highlights & notes",
        "annotations.close": "Close highlights and notes",
        "annotations.eyebrow": "Reading",
        "annotations.filter": "Filter annotations",
        "annotations.all": "All",
        "annotations.highlights": "Highlights",
        "annotations.notes": "Notes",
        "annotations.locationNote": "Note at current page",
        "annotations.searchLabel": "Search highlights and notes",
        "annotations.searchPlaceholder": "Search highlights and notes…",
        "annotations.shortcuts": (
            "<kbd>H</kbd> highlight · <kbd>N</kbd> note · <kbd>?</kbd> all shortcuts"
        ),
        "annotations.empty": (
            "No highlights or notes yet. Select text and press H to highlight, or use "
            "the selection toolbar."
        ),
        "annotations.privacy": (
            "Highlights and notes stay in this browser and are never uploaded."
        ),
        "annotations.keep": "Keep on this device",
        "annotations.copyAll": "Copy all",
        "annotations.export": "Export",
        "annotations.exportMarkdown": "Markdown (.md)",
        "annotations.exportJson": "JSON backup (.json)",
        "annotations.import": "Import",
        "annotations.note": "Note",
        "annotations.needsReview": "Needs review",
        "annotations.book": "Book",
        "annotations.actions": "Actions for this annotation",
        "annotations.editNote": "Edit note",
        "annotations.addNote": "Add note",
        "annotations.copyQuote": "Copy quote",
        "annotations.remove": "Remove",
        "annotations.highlightRemoved": "Highlight removed",
        "annotations.noteRemoved": "Note removed",
        "annotations.noteSaved": "Note saved",
        "annotations.highlighted": "Highlighted",
        "annotations.highlightTabOnly": ("Highlight saved in this tab only. Export to keep it."),
        "annotations.noteTabOnly": "Note removed in this tab only. Export to keep it.",
        "annotations.copied": "Copied",
        "annotations.copiedSentence": "Copied.",
        "annotations.quoteCopied": "Quote copied",
        "annotations.noteCopied": "Note copied",
        "annotations.undo": "Undo",
        "annotations.noteAtLocation": "Note at this location",
        "annotations.couldNotFind": "Could not find this annotation on this page.",
        "annotations.otherPage": "This annotation is on another page.",
        "annotations.noNoteSpot": "Could not find a place for the note on this page.",
        "annotations.matchOne": "1 match for “{query}”",
        "annotations.matches": "{count} matches for “{query}”",
        "annotations.noMatches": "No matches for “{query}”",
        "annotations.noFilterMatch": "No annotations match this filter.",
        "annotations.noQueryMatch": "No annotations match “{query}”.",
        "annotations.importTooLarge": "That annotation file is too large.",
        "annotations.importInvalidJson": "That file is not valid JSON.",
        "annotations.importInvalid": "That file is not a valid epub2web annotation file.",
        "annotations.importOtherBook": "That file belongs to a different book.",
        "annotations.importNone": "No new annotations.",
        "annotations.importOne": "Imported 1 annotation{detail}.",
        "annotations.importMany": "Imported {count} annotations{detail}.",
        "annotations.importDetail": " ({added} new, {updated} updated)",
        "annotations.importUnsaved": (
            "Imported annotations, but this browser could not save them. Export to keep them."
        ),
        "annotations.copyNone": "No annotations to copy.",
        "annotations.copiedCount": "Copied {count} to the clipboard.",
        "annotations.copyFailed": "Could not copy. Use Export instead.",
        "annotations.exportNone": "No annotations to export.",
        "annotations.exportedMarkdown": "Exported {count} as Markdown.",
        "annotations.exportedJson": "Exported {count} as JSON.",
        "annotations.countOne": "1 annotation",
        "annotations.count": "{count} annotations",
        "annotations.markdownTitle": "Highlights and notes",
        "annotations.noteError": (
            "This browser could not save the note. Export your annotations to keep them."
        ),
        "annotations.noteMarker": "Note: {text}",
        # Storage
        "storage.eyebrow": "Privacy",
        "storage.title": "Keep highlights on this device",
        "storage.close": "Close storage settings",
        "storage.intro": (
            "Highlights and notes are stored only in this browser. They are never "
            "uploaded and never added to the published site."
        ),
        "storage.risk": (
            "Browsers can remove site data when storage is low. Your browser can keep "
            "this site’s data on this device, but it may ask for permission first."
        ),
        "storage.note": (
            "epub2web does not receive your book text or notes. Export a backup if you "
            "need a copy you can move elsewhere."
        ),
        "storage.notNow": "Not now",
        "storage.request": "Ask browser to keep data",
        "storage.unsupported": (
            "This browser does not support persistent storage. Export a backup if you need a copy."
        ),
        "storage.notSupported": "Not supported",
        "storage.alreadyKept": ("This browser is already keeping this site’s data on this device."),
        "storage.alreadyKeptButton": "Already kept",
        "storage.permissionMaybe": ("Your browser may ask for permission when you continue."),
        "storage.checking": "Checking this browser…",
        "storage.requesting": "Requesting…",
        "storage.waiting": "Waiting for your browser…",
        "storage.granted": ("This browser will keep your highlights and notes on this device."),
        "storage.keptButton": "Kept on this device",
        "storage.denied": (
            "The browser did not grant persistent storage. Export a backup to keep a copy."
        ),
        "storage.tryAgain": "Try again",
        # Figure viewer
        "lightbox.label": "Figure viewer",
        "lightbox.close": "Close figure",
        "lightbox.previous": "Previous figure",
        "lightbox.next": "Next figure",
        "lightbox.position": "{current} of {total}",
        # Not found
        "notFound.title": "This page is not in the book.",
        "notFound.body": ("The address may be wrong, or the section may have moved."),
        "notFound.cover": "Back to the cover",
        # Document titles for generated utility pages
        "document.contents": "Contents — {book}",
        "document.notFound": "Page not found — {book}",
    },
    "vi": {
        # Khung trang, điều hướng, chân trang
        "chrome.skipToContent": "Bỏ qua, đến nội dung",
        "chrome.brandHome": "{initial} — {title} — trang chủ",
        "chrome.primaryNav": "Điều hướng chính",
        "chrome.secondaryNav": "Điều hướng phụ",
        "nav.contents": "Mục lục",
        "nav.read": "Đọc",
        "footer.browserEdition": "Bản đọc trên trình duyệt.",
        "footer.browserEditionOf": "Bản đọc trên trình duyệt của {subtitle}.",
        "footer.unabridged": "Bản đọc trên trình duyệt này giữ nguyên toàn văn.",
        "footer.rightsFallback": "Bản quyền văn bản thuộc về chủ sở hữu tương ứng.",
        "footer.colophon": "Thông tin ấn bản",
        "footer.builtWith": (
            "Được tạo bằng quy trình trích xuất tất định và bước kiểm tra độ trung thực văn bản."
        ),
        "footer.frontMatter": "Phần đầu sách",
        # Tìm kiếm
        "search.open": "Tìm trong sách",
        "search.openTitle": "Tìm trong sách (/)",
        "search.eyebrow": "Toàn văn",
        "search.title": "Tìm trong sách",
        "search.close": "Đóng tìm kiếm",
        "search.inputLabel": "Tìm trong sách",
        "search.placeholder": "Tìm trong sách…",
        "search.prompt": "Nhập một từ hoặc cụm từ.",
        "search.indexed": "Đã lập chỉ mục {count} mục. Nhập để tìm kiếm.",
        "search.loading": "Đang tải chỉ mục tìm kiếm…",
        "search.noMatches": "Không tìm thấy kết quả cho “{query}”.",
        "search.oneResult": "1 kết quả cho “{query}”",
        "search.manyResults": "{count} kết quả cho “{query}”",
        "search.showingFirst": " · hiển thị {count} kết quả đầu tiên",
        "search.unavailable": (
            "Không tải được chỉ mục tìm kiếm. Hãy chạy trang bằng `epub2web --serve`."
        ),
        "search.hint": (
            "Nhấn <kbd>/</kbd> ở bất kỳ đâu để mở tìm kiếm, <kbd>↑</kbd><kbd>↓</kbd> "
            "để chọn kết quả, <kbd>Enter</kbd> để mở, <kbd>Esc</kbd> để đóng."
        ),
        # Giao diện và cài đặt đọc
        "language.switch": "Đổi ngôn ngữ",
        "language.switchToEnglish": "Chuyển sang tiếng Anh",
        "language.switchToVietnamese": "Chuyển sang tiếng Việt",
        "theme.switch": "Đổi giao diện màu",
        "theme.switchTo": "Chuyển sang giao diện {mode}",
        "theme.light": "sáng",
        "theme.dark": "tối",
        "reader.open": "Cài đặt đọc",
        "reader.eyebrow": "Đọc sách",
        "reader.title": "Cài đặt đọc",
        "reader.close": "Đóng cài đặt đọc",
        "reader.textSize": "Cỡ chữ",
        "reader.small": "Nhỏ",
        "reader.default": "Mặc định",
        "reader.large": "Lớn",
        "reader.extraLarge": "Rất lớn",
        "reader.lineSpacing": "Giãn dòng",
        "reader.compact": "Sát nhau",
        "reader.relaxed": "Thoáng",
        "reader.paragraphs": "Đoạn văn",
        "reader.spaced": "Tách đoạn",
        "reader.indented": "Thụt lề",
        "reader.pageWidth": "Độ rộng trang",
        "reader.narrow": "Hẹp",
        "reader.standard": "Tiêu chuẩn",
        "reader.wide": "Rộng",
        "reader.theme": "Giao diện",
        "reader.auto": "Tự động",
        "reader.light": "Sáng",
        "reader.dark": "Tối",
        "reader.language": "Ngôn ngữ giao diện",
        "reader.note": (
            "Các cài đặt này chỉ áp dụng cho trình duyệt này. Tự động sẽ theo giao diện "
            "của thiết bị. Nội dung sách không thay đổi."
        ),
        "reader.reset": "Khôi phục mặc định",
        # Phím tắt
        "shortcuts.open": "Phím tắt",
        "shortcuts.openTitle": "Phím tắt (?)",
        "shortcuts.title": "Phím tắt",
        "shortcuts.close": "Đóng phím tắt",
        "shortcuts.eyebrow": "Trình đọc",
        "shortcuts.reading": "Đọc sách",
        "shortcuts.anywhere": "Ở mọi nơi",
        "shortcuts.searchResults": "Kết quả tìm kiếm",
        "shortcuts.noteComposer": "Khung soạn ghi chú",
        "shortcuts.h": "Đánh dấu đoạn văn đã chọn",
        "shortcuts.n": "Thêm ghi chú cho đoạn văn đã chọn",
        "shortcuts.shiftA": "Mở hoặc đóng đánh dấu và ghi chú",
        "shortcuts.arrows": "Chương trước hoặc chương sau",
        "shortcuts.slash": "Tìm trong sách",
        "shortcuts.question": "Mở danh sách phím tắt này",
        "shortcuts.escape": "Đóng thanh công cụ, thẻ, khung soạn hoặc bảng điều khiển",
        "shortcuts.upDown": "Chọn một kết quả",
        "shortcuts.enter": "Mở kết quả đã chọn",
        "shortcuts.ctrlEnter": "Lưu ghi chú",
        "shortcuts.escapeCancel": "Hủy và đóng",
        "shortcuts.note": (
            "Phím tắt sẽ không hoạt động khi bạn đang gõ trong ô nhập liệu. Trên thiết bị "
            "cảm ứng, hãy dùng các nút trên thanh đầu trang và thanh công cụ khi chọn văn bản."
        ),
        "shortcuts.srH": "Phím tắt H: ",
        "shortcuts.srN": "Phím tắt N: ",
        "shortcuts.srShiftA": "Phím tắt Shift cộng A: ",
        "shortcuts.srArrows": "Phím tắt mũi tên trái hoặc phải: ",
        "shortcuts.srSlash": "Phím tắt dấu gạch chéo: ",
        "shortcuts.srQuestion": "Phím tắt dấu hỏi: ",
        "shortcuts.srEscape": "Phím tắt Escape: ",
        "shortcuts.srUpDown": "Phím tắt mũi tên lên hoặc xuống: ",
        "shortcuts.srEnter": "Phím tắt Enter: ",
        "shortcuts.srCtrlEnter": "Phím tắt Control hoặc Command cộng Enter: ",
        # Mục lục và thanh bên
        "menu.open": "Mở mục lục",
        "menu.close": "Đóng mục lục",
        "menu.sections": "Các mục",
        "sidebar.contents": "Mục lục",
        "sidebar.allChapters": "Tất cả các chương",
        "sidebar.about": "Về bản sách này",
        "sidebar.search": "Tìm trong sách",
        "sidebar.label": "Mục lục sách",
        # Điều hướng chương
        "pagination.previous": "Trước",
        "pagination.next": "Tiếp",
        "pagination.label": "Điều hướng chương",
        "pagination.contents": "Mục lục",
        "pagination.about": "Về bản sách này",
        "pagination.top": "Lên đầu trang",
        # Trang chủ
        "home.browserEdition": "Bản đọc trên trình duyệt",
        "home.startReading": "Bắt đầu đọc",
        "home.continueReading": "Đọc tiếp",
        "home.continueReadingLabel": "Đọc tiếp: {label}",
        "home.startOver": "Đọc lại từ đầu",
        "home.startOverTitle": "Xóa vị trí đọc đã lưu",
        "home.read": "Đọc",
        "home.headingChapters": "Các chương",
        "home.fullContents": "Toàn bộ mục lục",
        "home.chapterMeta": "{sections} mục · {minutes} phút đọc",
        "home.chapterMetaOneSection": "1 mục · {minutes} phút đọc",
        "home.chapterMetaNoSections": "{minutes} phút đọc",
        "home.alsoInEdition": "Còn có trong bản này",
        "home.colophonEyebrow": "Thông tin ấn bản",
        "home.aboutEdition": "Về bản sách này",
        "home.colophonText": (
            "Đây là toàn văn của {title}{subtitle}, được dựng từ {source} thành một "
            "trang web tĩnh. Phần điều hướng, các đoạn mã và các lớp ẩn đã được lược bỏ; "
            "phần chữ, tiêu đề, hình ảnh, chú thích, ghi chú, tài liệu tham khảo và chỉ "
            "mục vẫn được giữ nguyên."
        ),
        "home.fidelityText": (
            "Mỗi đoạn văn đều được đối chiếu với bản gốc bằng bước kiểm tra độ trung thực "
            "văn bản. Nếu một từ bị thêm, bớt hoặc đổi vị trí, quá trình dựng trang sẽ dừng "
            "lại. Chỉ phần trình bày thay đổi."
        ),
        "home.unabridgedPublisher": (
            "Bản đọc trên trình duyệt này giữ nguyên toàn văn và không liên kết với nhà xuất bản."
        ),
        "home.typography": "Kiểu chữ",
        "home.build": "Cách dựng",
        "home.search": "Tìm kiếm",
        "home.source": "Nguồn",
        "home.searchValue": "Chỉ mục toàn văn tích hợp",
        "home.heroIntro": (
            "Toàn văn nguyên bản, được trình bày cho trình duyệt. {summary} — không bỏ sót "
            "phần nào."
        ),
        "home.heroIntroBare": (
            "Toàn văn nguyên bản, được trình bày cho trình duyệt, không bỏ sót phần nào."
        ),
        "home.heroChapters": "{count} chương",
        "home.heroChaptersOne": "1 chương",
        "home.heroFigures": "{count} hình",
        "home.heroFiguresOne": "1 hình",
        "home.heroWords": "{count} từ",
        "home.heroWordsOne": "1 từ",
        "home.heroCharacters": "{count} ký tự",
        "home.heroCharactersOne": "1 ký tự",
        "stats.chapters": "Chương",
        "stats.words": "Từ",
        "stats.characters": "Ký tự",
        "stats.figures": "Hình",
        # Trang mục lục
        "contents.title": "MỤC LỤC",
        "contents.intro": (
            "Mọi chương và mục, cùng phần đầu và phần cuối sách. Mỗi mục đều có liên kết."
        ),
        "contents.quickLinks": "Liên kết nhanh",
        "contents.minutes": "{minutes} phút",
        # Thông tin trang
        "readTime.minutes": "{minutes} phút đọc",
        "readTime.chapter": "Chương {current}/{total} · {minutes} phút đọc",
        # Công cụ đánh dấu và ghi chú
        "toolbar.label": "Đánh dấu hoặc ghi chú đoạn đã chọn",
        "toolbar.highlight": "Đánh dấu",
        "toolbar.highlightTitle": "Đánh dấu (H)",
        "toolbar.note": "Ghi chú",
        "toolbar.noteTitle": "Thêm ghi chú (N)",
        "toolbar.chooseColor": "Chọn màu đánh dấu",
        "toolbar.colorGroup": "Màu đánh dấu",
        "toolbar.cardLabel": "Đánh dấu",
        "toolbar.closeCard": "Đóng đánh dấu",
        "toolbar.addNote": "Thêm ghi chú",
        "toolbar.color": "Màu",
        "toolbar.copy": "Sao chép",
        "toolbar.remove": "Xóa",
        "color.yellow": "Đánh dấu màu vàng",
        "color.green": "Đánh dấu màu xanh lá",
        "color.blue": "Đánh dấu màu xanh dương",
        "color.pink": "Đánh dấu màu hồng",
        "color.purple": "Đánh dấu màu tím",
        # Khung soạn ghi chú
        "note.addTitle": "Thêm ghi chú",
        "note.editTitle": "Sửa ghi chú",
        "note.close": "Đóng ghi chú",
        "note.label": "Ghi chú của bạn",
        "note.placeholder": "Viết ghi chú…",
        "note.placeholderOptional": "Thêm ghi chú (không bắt buộc)",
        "note.hint": (
            "Nhấn <kbd>Ctrl</kbd>/<kbd>⌘</kbd> + <kbd>Enter</kbd> để lưu. <kbd>Esc</kbd> để hủy."
        ),
        "note.hintLabel": "Nhấn Control hoặc Command cùng Enter để lưu. Nhấn Escape để hủy.",
        "note.remove": "Xóa ghi chú",
        "note.cancel": "Hủy",
        "note.save": "Xong",
        # Bảng đánh dấu và ghi chú
        "annotations.open": "Đánh dấu và ghi chú",
        "annotations.openCountOne": "Đánh dấu và ghi chú, 1 mục",
        "annotations.openCount": "Đánh dấu và ghi chú, {count} mục",
        "annotations.title": "Đánh dấu & ghi chú",
        "annotations.close": "Đóng đánh dấu và ghi chú",
        "annotations.eyebrow": "Đọc sách",
        "annotations.filter": "Lọc đánh dấu và ghi chú",
        "annotations.all": "Tất cả",
        "annotations.highlights": "Đánh dấu",
        "annotations.notes": "Ghi chú",
        "annotations.locationNote": "Ghi chú ở trang này",
        "annotations.searchLabel": "Tìm trong đánh dấu và ghi chú",
        "annotations.searchPlaceholder": "Tìm đánh dấu và ghi chú…",
        "annotations.shortcuts": (
            "<kbd>H</kbd> đánh dấu · <kbd>N</kbd> ghi chú · <kbd>?</kbd> xem phím tắt"
        ),
        "annotations.empty": (
            "Chưa có đánh dấu hay ghi chú nào. Chọn một đoạn văn rồi nhấn H để đánh dấu, "
            "hoặc dùng thanh công cụ khi chọn văn bản."
        ),
        "annotations.privacy": (
            "Đánh dấu và ghi chú chỉ lưu trong trình duyệt này và không bao giờ được tải lên."
        ),
        "annotations.keep": "Giữ trên thiết bị này",
        "annotations.copyAll": "Sao chép tất cả",
        "annotations.export": "Xuất",
        "annotations.exportMarkdown": "Markdown (.md)",
        "annotations.exportJson": "Bản sao lưu JSON (.json)",
        "annotations.import": "Nhập",
        "annotations.note": "Ghi chú",
        "annotations.needsReview": "Cần xem lại",
        "annotations.book": "Sách",
        "annotations.actions": "Thao tác với đánh dấu này",
        "annotations.editNote": "Sửa ghi chú",
        "annotations.addNote": "Thêm ghi chú",
        "annotations.copyQuote": "Sao chép trích dẫn",
        "annotations.remove": "Xóa",
        "annotations.highlightRemoved": "Đã xóa đánh dấu",
        "annotations.noteRemoved": "Đã xóa ghi chú",
        "annotations.noteSaved": "Đã lưu ghi chú",
        "annotations.highlighted": "Đã đánh dấu",
        "annotations.highlightTabOnly": (
            "Đánh dấu chỉ được lưu trong thẻ này. Hãy xuất để giữ lại."
        ),
        "annotations.noteTabOnly": "Ghi chú chỉ được xóa trong thẻ này. Hãy xuất để giữ lại.",
        "annotations.copied": "Đã sao chép",
        "annotations.copiedSentence": "Đã sao chép.",
        "annotations.quoteCopied": "Đã sao chép trích dẫn",
        "annotations.noteCopied": "Đã sao chép ghi chú",
        "annotations.undo": "Hoàn tác",
        "annotations.noteAtLocation": "Ghi chú tại vị trí này",
        "annotations.couldNotFind": "Không tìm thấy đánh dấu này trên trang.",
        "annotations.otherPage": "Đánh dấu này nằm ở trang khác.",
        "annotations.noNoteSpot": "Không tìm được vị trí để ghi chú trên trang này.",
        "annotations.matchOne": "1 kết quả cho “{query}”",
        "annotations.matches": "{count} kết quả cho “{query}”",
        "annotations.noMatches": "Không có kết quả cho “{query}”",
        "annotations.noFilterMatch": "Không có đánh dấu nào khớp bộ lọc này.",
        "annotations.noQueryMatch": "Không có đánh dấu nào khớp với “{query}”.",
        "annotations.importTooLarge": "Tệp đánh dấu này quá lớn.",
        "annotations.importInvalidJson": "Tệp này không phải JSON hợp lệ.",
        "annotations.importInvalid": "Đây không phải tệp đánh dấu hợp lệ của epub2web.",
        "annotations.importOtherBook": "Tệp này thuộc về một cuốn sách khác.",
        "annotations.importNone": "Không có đánh dấu mới.",
        "annotations.importOne": "Đã nhập 1 đánh dấu{detail}.",
        "annotations.importMany": "Đã nhập {count} đánh dấu{detail}.",
        "annotations.importDetail": " ({added} mới, {updated} cập nhật)",
        "annotations.importUnsaved": (
            "Đã nhập đánh dấu nhưng trình duyệt không thể lưu. Hãy xuất để giữ lại."
        ),
        "annotations.copyNone": "Không có đánh dấu nào để sao chép.",
        "annotations.copiedCount": "Đã sao chép {count} vào bộ nhớ tạm.",
        "annotations.copyFailed": "Không thể sao chép. Hãy dùng Xuất.",
        "annotations.exportNone": "Không có đánh dấu nào để xuất.",
        "annotations.exportedMarkdown": "Đã xuất {count} dưới dạng Markdown.",
        "annotations.exportedJson": "Đã xuất {count} dưới dạng JSON.",
        "annotations.countOne": "1 đánh dấu",
        "annotations.count": "{count} đánh dấu",
        "annotations.markdownTitle": "Đánh dấu và ghi chú",
        "annotations.noteError": (
            "Trình duyệt không thể lưu ghi chú. Hãy xuất đánh dấu và ghi chú để giữ lại."
        ),
        "annotations.noteMarker": "Ghi chú: {text}",
        # Lưu trữ
        "storage.eyebrow": "Quyền riêng tư",
        "storage.title": "Giữ đánh dấu trên thiết bị này",
        "storage.close": "Đóng cài đặt lưu trữ",
        "storage.intro": (
            "Đánh dấu và ghi chú chỉ được lưu trong trình duyệt này. Chúng không bao giờ "
            "được tải lên hay đưa vào trang web đã xuất bản."
        ),
        "storage.risk": (
            "Khi bộ nhớ sắp đầy, trình duyệt có thể xóa dữ liệu của trang. Bạn có thể yêu "
            "cầu trình duyệt giữ dữ liệu của trang này trên thiết bị; trình duyệt có thể sẽ "
            "hỏi quyền trước."
        ),
        "storage.note": (
            "epub2web không nhận nội dung sách hay ghi chú của bạn. Nếu muốn có bản sao để "
            "mang đi nơi khác, hãy xuất bản sao lưu."
        ),
        "storage.notNow": "Để sau",
        "storage.request": "Yêu cầu trình duyệt giữ dữ liệu",
        "storage.unsupported": (
            "Trình duyệt này không hỗ trợ lưu trữ lâu dài. Hãy xuất bản sao lưu nếu bạn "
            "cần giữ một bản."
        ),
        "storage.notSupported": "Không hỗ trợ",
        "storage.alreadyKept": ("Trình duyệt này đang giữ dữ liệu của trang trên thiết bị."),
        "storage.alreadyKeptButton": "Đã giữ",
        "storage.permissionMaybe": ("Khi bạn tiếp tục, trình duyệt có thể sẽ hỏi quyền."),
        "storage.checking": "Đang kiểm tra trình duyệt…",
        "storage.requesting": "Đang yêu cầu…",
        "storage.waiting": "Đang chờ trình duyệt…",
        "storage.granted": ("Trình duyệt sẽ giữ đánh dấu và ghi chú của bạn trên thiết bị này."),
        "storage.keptButton": "Đã giữ trên thiết bị",
        "storage.denied": (
            "Trình duyệt không cấp quyền lưu trữ lâu dài. Hãy xuất bản sao lưu để giữ một bản."
        ),
        "storage.tryAgain": "Thử lại",
        # Trình xem hình
        "lightbox.label": "Xem hình",
        "lightbox.close": "Đóng hình",
        "lightbox.previous": "Hình trước",
        "lightbox.next": "Hình sau",
        "lightbox.position": "Hình {current}/{total}",
        # Không tìm thấy trang
        "notFound.title": "Trang này không có trong sách.",
        "notFound.body": "Địa chỉ có thể không đúng, hoặc mục này đã được chuyển đi.",
        "notFound.cover": "Về trang bìa",
        # Tiêu đề trang cho các trang tiện ích
        "document.contents": "Mục lục — {book}",
        "document.notFound": "Không tìm thấy trang — {book}",
    },
}


def normalize_language(value: str | None) -> str:
    """Return a supported interface language, defaulting to English."""
    key = (value or "").strip().lower().replace("_", "-")
    base = key.split("-", 1)[0]
    return base if base in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE


def messages_for(language: str | None) -> dict[str, str]:
    """Return the message table for *language*."""
    return MESSAGES[normalize_language(language)]


def ui_messages() -> dict[str, dict[str, str]]:
    """Return every language table for embedding in generated pages."""
    return {language: dict(MESSAGES[language]) for language in SUPPORTED_LANGUAGES}


def translate(language: str | None, key: str, **values: Any) -> str:
    """Translate *key* for *language* and fill ``{name}`` placeholders."""
    table = messages_for(language)
    template = table.get(key)
    if template is None:
        template = MESSAGES[DEFAULT_LANGUAGE].get(key, key)

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        return str(values[name]) if name in values else match.group(0)

    return _PLACEHOLDER.sub(replace, template)
