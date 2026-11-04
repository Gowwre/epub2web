import type { Copy } from "./en";

export const vi: Copy = {
  common: {
    localeName: "Tiếng Việt",
    switchLanguage: "Chuyển sang tiếng Anh",
    skipToContent: "Bỏ qua, đến nội dung",
    nav: {
      primary: "Điều hướng chính",
      features: "Tính năng",
      fidelity: "Độ trung thực",
      howItWorks: "Cách hoạt động",
      changelog: "Nhật ký thay đổi",
      faq: "Câu hỏi thường gặp",
    },
    header: {
      homeSuffix: "— trang chủ",
      githubLabel: "epub2web trên GitHub (mở trong thẻ mới)",
      githubTitle: "Xem epub2web trên GitHub",
      themeLabel: "Chuyển giữa giao diện sáng và tối",
      themeTitle: "Đổi giao diện màu",
      download: "Tải xuống",
    },
    footer: {
      homeSuffix: "— trang chủ",
      tagline:
        "Một trang đọc được tạo từ EPUB bạn sở hữu. Có thể tìm kiếm, đánh dấu và giữ lại cho riêng bạn.",
      viewProject: "Xem dự án trên GitHub",
      product: "Sản phẩm",
      learn: "Tìm hiểu",
      project: "Dự án",
      download: "Tải xuống",
      liveDemo: "Bản demo trực tiếp",
      latestRelease: "Bản phát hành mới nhất",
      changelog: "Nhật ký thay đổi",
      highlights: "Đánh dấu và ghi chú",
      checks: "Kiểm tra văn bản và hình ảnh",
      runSite: "Chạy trang của bạn",
      firstLaunch: "FAQ lần mở đầu tiên",
      readme: "README",
      desktopDocs: "Tài liệu ứng dụng desktop",
      github: "GitHub",
      reportIssue: "Báo lỗi",
      license: "Giấy phép GPLv3",
      contributing: "Đóng góp",
      base: "Mã nguồn mở theo GPLv3. Sách của bạn vẫn thuộc về bạn.",
      builtWith: "Xây dựng bằng",
      firstLaunchNotes: "Ghi chú lần mở đầu tiên",
    },
  },
  home: {
    metaTitle:
      "epub2web — Biến EPUB thành trang web đọc sách có đánh dấu và ghi chú",
    metaDescription:
      "Biến EPUB bạn sở hữu thành một trang web đọc sách với đánh dấu và ghi chú riêng tư. Tệp của bạn ở lại trên máy, và thư mục thành phẩm là của bạn để giữ hoặc xuất bản.",
    hero: {
      newBadge: "Mới",
      launchPill: "Đánh dấu & ghi chú",
      titleLine1: "Biến EPUB",
      titleLine2Before: "thành ",
      titleLine2Accent: "trang web.",
      intro:
        "Một trang web đọc sách được dựng từ EPUB bạn sở hữu. Văn bản và hình ảnh được giữ nguyên, tìm kiếm và đánh dấu có sẵn, và thư mục thành phẩm là của bạn để giữ hoặc xuất bản.",
      downloadApp: "Tải ứng dụng",
      openDemo: "Mở bản demo trực tiếp",
      atAGlance: "Tóm tắt nhanh",
      meta: [
        "Miễn phí & mã nguồn mở",
        "Windows · macOS · Linux",
        "Không cần tài khoản · Không tải lên",
      ],
      imageAlt:
        "Trang chủ trình đọc epub2web cho Alice's Adventures in Wonderland, hiển thị bìa, tiêu đề, tác giả và nút Bắt đầu đọc.",
      caption: "Alice's Adventures in Wonderland, dựng từ EPUB.",
    },
    fidelity: {
      eyebrow: "Độ trung thực",
      titleLine1: "Bố cục thay đổi.",
      titleAccent: "Còn chữ thì không.",
      lede: "epub2web đối chiếu trang web thành phẩm với EPUB gốc. Nếu văn bản, hình ảnh hoặc liên kết không được giữ nguyên sau khi chuyển đổi, quá trình dựng sẽ dừng lại thay vì xuất bản một cuốn sách bị hỏng.",
      checks: [
        {
          label: "Văn bản",
          body: "Mỗi trang đọc đều được so với EPUB gốc. Một câu bị mất, dấu câu bị đổi hoặc đoạn văn bị dời chỗ sẽ khiến quá trình dựng dừng lại.",
        },
        {
          label: "Hình ảnh",
          body: "Mỗi hình được đếm và đối chiếu với bản gốc. Thiếu một hình là quá trình dựng thất bại, thay vì xuất bản một lỗ hổng trong sách.",
        },
        {
          label: "Liên kết",
          body: "Liên kết nội bộ, neo, hình ảnh và ID trùng đều được kiểm tra trước khi xuất bản. Người đọc không gặp ngõ cụt giữa các chương.",
        },
      ],
      colophon: {
        kicker: "Thông tin bản dựng",
        title: "Một bản dựng thật",
        verified: "Đã kiểm tra",
        rows: [
          { label: "Nguồn", value: "alice.epub" },
          { label: "Từ", value: "29.564" },
          { label: "Trang", value: "13/13 khớp" },
          { label: "Hình ảnh", value: "12/12 có mặt" },
          { label: "Liên kết", value: "Đã kiểm tra 743 · 0 hỏng" },
          { label: "Tải lên", value: "Không có" },
        ],
        caption: "Tạo cục bộ trong 0,57 giây. Không có gì được tải lên.",
      },
      failStrong: "Nếu một bước kiểm tra thất bại, quá trình dựng sẽ dừng lại.",
      failRest:
        "Trang cũ của bạn vẫn nằm nguyên tại chỗ, và báo cáo lỗi cho biết phần nào không khớp.",
    },
    edition: {
      eyebrow: "Trang đọc",
      titleLine1: "Một cuốn sách,",
      titleAccent: "không phải một mớ HTML.",
      lede: "Bạn nhận được bìa, mục lục, một trang cho mỗi chương, hình ảnh, chú thích cuối trang, tìm kiếm và một lớp riêng cho đánh dấu và ghi chú. Tất cả nằm trong một thư mục tĩnh để bạn giữ hoặc xuất bản.",
      features: {
        reading: {
          title: "Đọc như sách",
          body: "Kiểu chữ dễ chịu, cỡ chữ và giãn dòng tùy chỉnh, giao diện sáng và tối, cùng dấu vị trí nhớ nơi bạn đã dừng đọc.",
          imageAlt:
            "Giao diện đọc: một chương của Alice's Adventures in Wonderland với thanh mục lục, thanh tiến trình và kiểu chữ serif dễ đọc.",
          caption: "Giao diện đọc",
        },
        search: {
          title: "Tìm khắp cuốn sách",
          body: "Cuốn sách được lập chỉ mục ngay khi dựng trang. Tìm một từ và nhảy thẳng đến đó; không cần dịch vụ tìm kiếm, không cần tài khoản.",
          imageAlt:
            "Bảng tìm kiếm tích hợp hiển thị kết quả được tô sáng cho từ rabbit trong nhiều chương.",
          caption: "Kết quả tìm kiếm",
        },
        keep: {
          title: "Của bạn để giữ",
          body: "Một thư mục gồm HTML, CSS, hình ảnh, phông chữ và dữ liệu tìm kiếm. Đưa lên bất kỳ host tĩnh nào, hoặc giữ trên máy của bạn.",
        },
        book: {
          title: "Cả cuốn sách đi cùng",
          body: "Hình ảnh kèm chú thích, bảng, danh sách, chú thích cuối trang và tham chiếu chéo đều được giữ nguyên.",
          tags: ["Hình minh họa", "Bảng", "Chú thích cuối trang", "Tham chiếu chéo"],
        },
        a11y: {
          title: "Dễ đọc với nhiều người hơn",
          body: "Điều hướng bằng bàn phím, nhãn rõ ràng và mô tả hình ảnh là một phần của trình đọc, không phải phần thêm vào sau.",
          tags: ["Bàn phím", "Nhãn", "Văn bản thay thế"],
        },
      },
      demo: "Mở bản demo trực tiếp",
    },
    annotations: {
      eyebrow: "Đánh dấu & ghi chú",
      titleLine1: "Đọc sách với",
      titleAccent: "cây bút trên tay.",
      lede: "Chọn một đoạn văn để đánh dấu. Thêm ghi chú riêng khi bạn muốn. Mọi thứ nằm trong trình duyệt của bạn và không bao giờ được ghi vào trang đã xuất bản.",
      points: [
        {
          title: "Đánh dấu chỉ với một thao tác",
          body: "Chọn văn bản và đánh dấu bằng màu dùng gần nhất. Ghi chú là tùy chọn, không phải bước thứ hai bắt buộc.",
        },
        {
          title: "Tìm mọi dấu đã đặt",
          body: "Xem theo chương, tìm theo trích dẫn hoặc ghi chú, và quay lại đoạn văn chỉ với một cú nhấp.",
        },
        {
          title: "Mang theo bên mình",
          body: "Sao chép mọi thứ dưới dạng Markdown, xuất tệp dễ đọc hoặc giữ bản sao lưu JSON. Các dấu không bao giờ đi vào trang web.",
        },
      ],
      demoLink: "Thử đánh dấu trong bản demo trực tiếp",
      demo: {
        kicker: "Chương I",
        title: "Down the Rabbit-Hole",
        firstText:
          "Alice was beginning to get very tired of sitting by her sister on the bank, and of having nothing to do: ",
        markedText:
          "once or twice she had peeped into the book her sister was reading, but it had no pictures or conversations in it.",
        secondText:
          "So she was considering in her own mind whether the pleasure of making a daisy-chain would be worth the trouble of getting up and picking the daisies.",
        noteAria: "Ghi chú ví dụ",
        noteHead: "Ghi chú · Chương I",
        noteQuote:
          "“...what is the use of a book, without pictures or conversations?”",
        noteBody:
          "Alice muốn một cuốn sách có hình ảnh và trò chuyện. Bản web giữ lại cả hai.",
        copyMarkdown: "Sao chép dạng Markdown",
        exportJson: "Xuất JSON",
        caption:
          "Minh họa lớp đánh dấu chỉ chạy trong trình duyệt. Không có gì được tải lên.",
      },
    },
    privacy: {
      eyebrow: "Cục bộ theo thiết kế",
      titleLine1: "Sách của bạn ở lại",
      titleAccent: "trên máy của bạn.",
      lede: "Không có tài khoản và không tải lên. Ứng dụng đọc EPUB ngay trên máy bạn và dựng trang web tại đó. Chạy lại và bạn nhận được đúng trang web cũ.",
      github: "Đọc mã nguồn trên GitHub",
      points: [
        {
          title: "Không có gì rời khỏi máy bạn",
          body: "EPUB, trang web thành phẩm, nhật ký và mọi báo cáo lỗi đều ở trên máy bạn. Đánh dấu và ghi chú ở lại trong trình duyệt.",
        },
        {
          title: "Cùng một cuốn sách cho ra cùng một trang web",
          body: "Chạy trình chuyển đổi hai lần, bạn nhận được cùng văn bản và cấu trúc. Chỉ dấu thời gian dựng trong sitemap thay đổi.",
        },
        {
          title: "Bạn có thể tự kiểm tra",
          body: "Trình chuyển đổi, giao diện đọc và bộ kiểm thử đều theo giấy phép GPLv3. Nếu muốn biết chính xác điều gì xảy ra với cuốn sách, mã nguồn luôn ở đó để đọc.",
        },
      ],
    },
    process: {
      eyebrow: "Cách hoạt động",
      titleLine1: "Từ EPUB đến trang web",
      titleAccent: "chỉ với ba bước.",
      lede: "Ứng dụng desktop đã gồm trình chuyển đổi, Python và phông chữ. Chọn một cuốn sách, nhấn Convert, và trang web thành phẩm sẽ mở trong trình duyệt.",
      steps: [
        {
          title: "Chọn EPUB của bạn",
          body: "Chọn một cuốn sách bạn sở hữu. Tệp EPUB 2 và EPUB 3 tiêu chuẩn hoạt động tốt nhất.",
        },
        {
          title: "Nhấn Convert",
          body: "Ứng dụng chuyển đổi sách và kiểm tra từng trang trong khi làm. Tiến trình hiển thị rõ, nên một cuốn sách dài không trông như bị treo.",
        },
        {
          title: "Đọc hoặc xuất bản",
          body: "Đọc trang web trong trình duyệt, hoặc tải thư mục lên bất kỳ host tĩnh nào.",
        },
      ],
      cliLabel: "Thích dùng dòng lệnh?",
      docs: "Đọc tài liệu",
    },
    faq: {
      eyebrow: "Câu hỏi",
      title: "Trước khi bạn tải xuống.",
      intro:
        "Những câu hỏi thường gặp trước khi dùng thử epub2web, gồm nơi lưu tệp và lý do máy bạn có thể cảnh báo trong lần mở ứng dụng đầu tiên.",
      ask: "Đặt câu hỏi trên GitHub",
      first: {
        summary: "Vì sao máy tôi cảnh báo khi mở ứng dụng?",
        p1Before:
          "Bản desktop chưa được ký mã, nên Windows SmartScreen và macOS Gatekeeper có thể cảnh báo về nhà phát triển không xác định trong lần mở đầu tiên. Đây là điều bình thường. Chỉ tiếp tục với tệp tải từ ",
        p1Link: "trang phát hành chính thức trên GitHub",
        p1After: ".",
        p2Before:
          "Trang tải xuống có hướng dẫn từng bước cho Windows và macOS, gồm cả cách Open Anyway. ",
        p2GuideLink: "Đọc hướng dẫn lần mở đầu tiên",
        p2Mid: " hoặc ",
        p2ReadmeLink: "ghi chú đầy đủ trong README",
        p2After: ".",
      },
      items: [
        {
          question: "Sách của tôi có được tải lên đâu đó không?",
          answer:
            "Không. EPUB được đọc trên máy bạn, trang web được dựng tại đó và thư mục thành phẩm ở lại đó. Không có tài khoản và không có bước tải lên. Nếu bạn xuất bản nó, đó là lựa chọn của bạn.",
        },
        {
          question: "Văn bản có bị thay đổi không?",
          answer:
            "Không. Từ ngữ và dấu câu giữ nguyên. epub2web có thể thay đổi cách cuốn sách trông như thế nào, nhưng không thay đổi nội dung. Một bước kiểm tra độ trung thực so từng trang với bản gốc và dừng quá trình dựng nếu thiếu bất cứ thứ gì.",
        },
        {
          question: "Tôi nhận được chính xác những gì?",
          answer:
            "Một thư mục gồm bìa, mục lục, trang cho từng chương, hình ảnh, phông chữ và chỉ mục tìm kiếm. Trang có giao diện đọc gọn nhẹ hoạt động trên điện thoại và máy tính. Sách EPUB 2 và EPUB 3 tiêu chuẩn hoạt động tốt nhất; sách có DRM và bố cục cố định có thể không dùng được.",
        },
        {
          question: "Tôi có thể đánh dấu đoạn văn và ghi chú không?",
          answer:
            "Có. Chọn văn bản để đánh dấu chỉ với một thao tác, thêm ghi chú riêng khi muốn, và xem mọi dấu trong bảng Đánh dấu & ghi chú. Sao chép dưới dạng Markdown hoặc xuất bản sao lưu JSON. Mọi thứ ở lại trong trình duyệt và không bao giờ được thêm vào trang đã xuất bản.",
        },
        {
          question: "Đánh dấu và ghi chú có đồng bộ giữa các thiết bị không?",
          answer:
            "Không tự động. Chúng nằm trong trình duyệt đã tạo ra chúng. Dùng Sao chép tất cả hoặc Xuất để chuyển đi, và giữ bản sao lưu trước khi xóa dữ liệu trang. Trình đọc chỉ hỏi quyền lưu trữ lâu dài sau khi bạn chọn Giữ trên thiết bị này.",
        },
        {
          question: "Tôi có thể đưa trang lên mạng hoặc đọc lại sau không?",
          answer:
            "Có. Kết quả là một thư mục tĩnh thông thường, nên hoạt động trên GitHub Pages, Cloudflare Pages, Netlify, S3, nginx hoặc bất kỳ host tĩnh nào. Để đọc lại trên máy, hãy mở ứng dụng và nhấn Convert, hoặc chạy thư mục bằng một máy chủ tĩnh cục bộ. Có hỗ trợ host dưới đường dẫn con bằng tùy chọn dòng lệnh --base-path.",
        },
        {
          question: "Nếu sách của tôi không chuyển đổi được thì sao?",
          answer:
            "epub2web dừng lại thay vì bỏ nội dung, giữ nguyên trang cũ đang hoạt động và tạo một tệp ZIP hỗ trợ để bạn đính kèm vào issue trên GitHub. Đừng đính kèm chính cuốn sách. ZIP có thể chứa đường dẫn tệp, metadata và trích đoạn ngắn, nên hãy xem qua trước.",
        },
      ],
    },
    closing: {
      eyebrow: "Bắt đầu",
      titleLine1: "Tạo bản đọc trên web",
      titleAccent: "cho cuốn sách của bạn.",
      intro:
        "Chọn một EPUB, nhấn Convert, và trang web thành phẩm sẽ mở trong trình duyệt. Giữ nó, hoặc chia sẻ thư mục với bất kỳ ai.",
      download: "Tải epub2web",
      demo: "Xem bản demo trực tiếp",
      meta: "Miễn phí & mã nguồn mở · Giấy phép GPLv3 · Không cần tài khoản · ",
      latestRelease: "Bản phát hành mới nhất trên GitHub",
    },
  },
  download: {
    metaTitle: "Tải epub2web cho Windows, macOS và Linux",
    metaDescription:
      "Tải ứng dụng desktop epub2web cho Windows, macOS hoặc Linux. Biến EPUB thành trang web đọc sách với đánh dấu và ghi chú riêng tư, không cần cài Python.",
    hero: {
      eyebrow: "Tải xuống",
      titleLine1: "Tải ứng dụng.",
      titleAccent: "Mở sách của bạn.",
      lede: "Python và phông chữ đã có sẵn trong bản tải. Chọn máy của bạn bên dưới rồi mở tệp.",
      choosePlatform: "Chọn nền tảng của bạn",
      allPlatforms: "Tất cả nền tảng",
      versionMeta:
        "Phiên bản {version} · Tải tệp trực tiếp · Windows, macOS, Linux · Giấy phép GPLv3",
      releaseAria: "Thông tin phát hành epub2web {version}",
      latestRelease: "Bản phát hành mới nhất",
      github: "GitHub",
      releaseDescription: "Ứng dụng desktop, sẵn sàng chuyển đổi sách.",
      specs: {
        version: "Phiên bản",
        published: "Ngày phát hành",
        platforms: "Nền tảng",
        install: "Cài đặt",
        none: "Không cần",
      },
      releaseNotes: "Ghi chú phát hành",
      releaseNoteBefore: "Mọi nền tảng được liệt kê bên dưới. Các phiên bản cũ nằm trên ",
      releaseNoteLink: "trang phát hành",
      releaseNoteAfter: ".",
    },
    platforms: {
      eyebrow: "Chọn máy của bạn",
      titleBefore: "Chọn bản tải ",
      titleAccent: "phù hợp với máy của bạn.",
      lede: "Mỗi nút sẽ bắt đầu tải từ GitHub. Nếu chưa chắc cần tệp nào, ghi chú dưới mỗi nút sẽ giúp bạn.",
      recommended: "Đề xuất",
      downloadForSr: "Tải epub2web cho ",
      fileSr: "Tệp: {filename}. Quá trình tải sẽ bắt đầu ngay.",
      variants: {
        windows: "bộ cài x64",
        macosArm64: "Apple Silicon",
        macosX64: "Intel",
        linux: "x86_64",
      },
      hints: {
        windows: "Nhấp đúp vào tệp để mở ứng dụng.",
        macosArm64: "Dành cho hầu hết máy Mac sản xuất từ cuối năm 2020.",
        macosX64: "Dành cho máy Mac cũ hơn.",
        linux: "Cấp quyền chạy cho tệp rồi mở tệp.",
      },
      noteBefore: "AppImage trên Linux có thể cần được cấp quyền chạy trước: chạy ",
      noteMid: ". Nếu FUSE không khả dụng, dùng ",
      noteAfter: ". Kiểm tra tệp với ",
      noteAfterLink: ".",
    },
    launch: {
      eyebrow: "Trước khi mở ứng dụng",
      title: "Cảnh báo lần mở đầu tiên là bình thường.",
      intro:
        "Bản desktop chưa có chứng chỉ ký mã trả phí, nên Windows SmartScreen và macOS Gatekeeper có thể cảnh báo rằng không xác minh được nhà phát triển. Đây là điều bình thường. Chỉ tiếp tục nếu bạn tải tệp từ bản phát hành chính thức trên GitHub.",
      readFaq: "Đọc toàn bộ FAQ lần mở đầu tiên",
      windowsTitle: "Trên Windows",
      windowsLead: "Nếu bạn thấy “Windows protected your PC”:",
      windowsSteps: [
        "Nhấn <strong>More info</strong> (Thông tin thêm).",
        "Nhấn <strong>Run anyway</strong> (Vẫn chạy).",
        "Mở ứng dụng và chọn một tệp EPUB.",
      ],
      windowsFine:
        "Trên máy công ty hoặc máy trường học được quản lý, Smart App Control có thể chặn hoàn toàn ứng dụng chưa ký. Hãy hỏi quản trị viên thay vì tắt các tính năng bảo mật.",
      macosTitle: "Trên macOS",
      macosLead: "Trên macOS 15 trở lên, sau khi kéo ứng dụng vào Applications:",
      macosSteps: [
        "Mở ứng dụng một lần, rồi nhấn <strong>Done</strong> (Xong).",
        "Mở <strong>System Settings → Privacy &amp; Security</strong> (Cài đặt hệ thống → Quyền riêng tư &amp; Bảo mật).",
        "Trong mục <strong>Security</strong> (Bảo mật), nhấn <strong>Open Anyway</strong> (Vẫn mở).",
        "Xác thực, rồi mở lại ứng dụng.",
      ],
      macosFineBefore: "Trên macOS 14 trở về trước, nhấp chuột phải vào ứng dụng, chọn ",
      macosFineStrong: "Open",
      macosFineMid:
        " (Mở), rồi nhấn <strong>Open</strong> (Mở) trong hộp thoại. Nếu macOS báo ứng dụng bị hỏng, hãy tải lại trước khi thử cách xử lý bằng Terminal.",
      verifyBefore: "Kiểm tra bản tải với tệp ",
      verifyAfter: ". Xem thêm trong ",
      verifyReadme: "README",
      verifyDocsMid: " và ",
      verifyDocs: "tài liệu ứng dụng desktop",
      verifyDocsAfter: ".",
    },
    other: {
      eyebrow: "Cách khác để dùng thử",
      titleBefore: "Thích Python? ",
      titleAccent: "Hay chỉ muốn xem qua?",
      lede: "Ứng dụng desktop là cách bắt đầu đơn giản nhất. Nếu quen với Python, bạn có thể cài gói và chạy trình chuyển đổi từ terminal. Hoặc dùng thử bản demo trước.",
      sourceEyebrow: "Từ mã nguồn",
      sourceTitle: "Cài bằng pipx",
      sourceBody:
        "epub2web cần Python 3.10 trở lên. Cài từ GitHub, rồi dựng và xem trước một cuốn sách:",
      sourceLink: "Cài đặt và tùy chọn CLI",
      demoTry: "Dùng thử trước",
      demoTitle: "Xem một trang đã hoàn thiện.",
      demoBody:
        "Bản demo trực tiếp là một trang epub2web hoàn chỉnh, dựng từ một cuốn sách thuộc phạm vi công cộng và chạy dưới dạng tệp tĩnh. Đọc một chương, tìm kiếm, thử giao diện tối.",
      demoButton: "Mở bản demo trực tiếp",
      footBefore: "Mã nguồn dự án, issue và lịch sử phát hành nằm trên ",
      footLink: "GitHub",
      footAfter: ".",
    },
    dialog: {
      closeAria: "Đóng hướng dẫn lần mở đầu tiên",
      status: "Đang tải xuống",
      title: "Trước khi bạn mở ứng dụng.",
      description:
        "Quá trình tải tiếp tục trong nền. Ứng dụng chưa được ký mã, nên hãy làm theo các bước sau trong lần đầu mở trên ",
      descriptionName: "máy của bạn",
      descriptionAfter: ".",
      onPlatform: "Trên {platform}",
      verifyBefore: "Kiểm tra tệp với ",
      verifyAfter: " nếu bạn muốn xác minh.",
      gotIt: "Đã hiểu",
      fullGuide: "Hướng dẫn đầy đủ lần mở đầu tiên",
    },
    guides: {
      windows: {
        name: "Windows",
        steps: [
          "Nhấp đúp vào tệp <code>.exe</code> đã tải.",
          "Nếu bạn thấy “Windows protected your PC”, nhấn <strong>More info</strong> (Thông tin thêm), rồi <strong>Run anyway</strong> (Vẫn chạy).",
          "Chọn tệp EPUB của bạn khi ứng dụng mở.",
        ],
        note: "Trên máy công ty hoặc máy trường học được quản lý, Smart App Control có thể chặn hoàn toàn ứng dụng chưa ký. Hãy hỏi quản trị viên thay vì tắt các tính năng bảo mật.",
      },
      macos: {
        name: "macOS",
        steps: [
          "Mở tệp <code>.dmg</code> và kéo epub2web vào <strong>Applications</strong> (Ứng dụng).",
          "Mở ứng dụng một lần, rồi nhấn <strong>Done</strong> (Xong) khi macOS chặn.",
          "Mở <strong>System Settings → Privacy &amp; Security</strong> (Cài đặt hệ thống → Quyền riêng tư &amp; Bảo mật), rồi nhấn <strong>Open Anyway</strong> (Vẫn mở) trong mục Security (Bảo mật) và xác thực.",
          "Mở lại ứng dụng và chọn tệp EPUB của bạn.",
        ],
        note: "Trên macOS 14 trở về trước, nhấp chuột phải vào ứng dụng, chọn Open (Mở), rồi chọn Open (Mở) lần nữa. Nút Open Anyway (Vẫn mở) chỉ khả dụng trong khoảng một giờ sau lần thử đầu tiên.",
      },
      linux: {
        name: "Linux",
        steps: [
          "Cấp quyền chạy cho AppImage: <code>chmod +x epub2web-gui-*.AppImage</code>.",
          "Chạy tệp: <code>./epub2web-gui-*.AppImage</code>.",
          "Nếu FUSE không khả dụng, chạy với <code>--appimage-extract-and-run</code>.",
        ],
        note: "Linux không hiển thị cảnh báo lần mở đầu tiên. Bạn có thể kiểm tra tệp với SHA256SUMS.txt trước khi chạy.",
      },
    },
    js: {
      yourComputer: "máy của bạn",
      choosePlatform: "Chọn nền tảng của bạn",
      downloadFor: "Tải bản cho {platform}",
      messages: {
        fallbackChoose: "Chọn tệp phù hợp với máy bạn sẽ dùng.",
        mobile: "Bạn đang dùng điện thoại hoặc máy tính bảng. Hãy chọn máy bạn sẽ dùng.",
        windows: "Đã nhận diện Windows. Bộ cài x64 được chọn.",
        macIntel: "Đã nhận diện máy Mac Intel. Bản Intel được chọn.",
        macArm: "Đã nhận diện Apple Silicon. Bản arm64 được chọn.",
        macUnknown:
          "Hầu hết máy Mac dùng Apple Silicon. Chọn bản Intel bên dưới nếu máy bạn cũ hơn.",
        chromeos: "Đã nhận diện ChromeOS. Hãy chọn máy bạn sẽ dùng.",
        linuxArm: "Bản phát hành này dành cho Linux x86_64; Linux ARM chưa có.",
        linux: "Đã nhận diện Linux. AppImage x86_64 được chọn.",
      },
    },
  },
  changelog: {
    metaTitle: "Nhật ký thay đổi — epub2web",
    metaDescription:
      "Những thay đổi trong từng bản phát hành epub2web, kèm liên kết trực tiếp đến ghi chú trên GitHub.",
    eyebrow: "Nhật ký thay đổi",
    titleLine1: "Mọi bản phát hành,",
    titleAccent: "trong một nơi.",
    lede: "Toàn bộ lịch sử epub2web, từ bản công khai đầu tiên đến hôm nay. Mỗi phiên bản đều có liên kết đến ghi chú phát hành trên GitHub.",
    latestRelease: "Bản phát hành mới nhất",
    github: "GitHub",
    viewRelease: "Xem bản phát hành",
    viewReleaseSr: "cho phiên bản {version} (mở trong thẻ mới)",
    latestNoteBefore: "Tải ",
    latestNoteMid: " hoặc đọc ghi chú trên GitHub.",
    releases: "Các bản phát hành",
    allVersions: "Tất cả phiên bản",
    sourceNoteBefore: "Các thay đổi chưa phát hành được theo dõi trong ",
    sourceNoteLink: "nhật ký thay đổi gốc",
    sourceNoteAfter: ".",
    latestBadge: "Mới nhất",
    preGithubBadge: "Trước GitHub Releases",
    viewChangelog: "Xem nhật ký thay đổi",
    viewChangelogSr: "cho phiên bản {version} trên GitHub (mở trong thẻ mới)",
    preGithubNote:
      "Phiên bản này có trước lịch sử GitHub Releases của dự án. Nút sẽ mở phần tương ứng trong nhật ký thay đổi trên GitHub.",
    translationNotice:
      "Ghi chú phát hành được dịch sang tiếng Việt khi có bản dịch. Phiên bản chưa có bản dịch sẽ hiển thị ghi chú tiếng Anh; nhật ký thay đổi tiếng Anh trên GitHub vẫn là nguồn chính thức.",
    untranslatedBadge: "Chỉ có tiếng Anh",
    untranslatedNote:
      "Bản phát hành này chưa có bản dịch tiếng Việt. Đang hiển thị ghi chú tiếng Anh.",
  },
};
