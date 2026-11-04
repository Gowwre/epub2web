export const en = {
  common: {
    localeName: "English",
    switchLanguage: "Switch to Vietnamese",
    skipToContent: "Skip to content",
    nav: {
      primary: "Primary",
      features: "Features",
      fidelity: "Fidelity",
      howItWorks: "How it works",
      changelog: "Changelog",
      faq: "FAQ",
    },
    header: {
      homeSuffix: "— home",
      githubLabel: "epub2web on GitHub (opens in a new tab)",
      githubTitle: "View epub2web on GitHub",
      themeLabel: "Switch between light and dark themes",
      themeTitle: "Switch color theme",
      download: "Download",
    },
    footer: {
      homeSuffix: "— home",
      tagline:
        "A reading website made from the EPUB you own. Searchable, annotatable, and yours to keep.",
      viewProject: "View the project on GitHub",
      product: "Product",
      learn: "Learn",
      project: "Project",
      download: "Download",
      liveDemo: "Live demo",
      latestRelease: "Latest release",
      changelog: "Changelog",
      highlights: "Highlights and notes",
      checks: "Text and image checks",
      runSite: "Run your site",
      firstLaunch: "First-launch FAQ",
      readme: "README",
      desktopDocs: "Desktop app docs",
      github: "GitHub",
      reportIssue: "Report an issue",
      license: "GPLv3 license",
      contributing: "Contributing",
      base: "Open source under GPLv3. Your books remain yours.",
      builtWith: "Built with",
      firstLaunchNotes: "First-launch notes",
    },
  },
  home: {
    metaTitle:
      "epub2web — Turn an EPUB into a reading website with highlights and notes",
    metaDescription:
      "Turn an EPUB you own into a reading website with private highlights and notes. Your files stay on your computer, and the folder is yours to keep or publish.",
    hero: {
      newBadge: "New",
      launchPill: "Highlights & notes",
      titleLine1: "Turn an EPUB",
      titleLine2Before: "into a ",
      titleLine2Accent: "website.",
      intro:
        "A reading website built from the EPUB you own. The text and images survive intact, search and highlights are built in, and the finished folder is yours to keep or publish.",
      downloadApp: "Download the app",
      openDemo: "Open the live demo",
      atAGlance: "At a glance",
      meta: ["Free & open source", "Windows · macOS · Linux", "No account · No upload"],
      imageAlt:
        "The epub2web reader home page for Alice's Adventures in Wonderland, showing the cover, title, author, and Start reading button.",
      caption: "Alice's Adventures in Wonderland, built from EPUB.",
    },
    fidelity: {
      eyebrow: "Fidelity",
      titleLine1: "The layout changes.",
      titleAccent: "The words don't.",
      lede: "epub2web compares the finished site with the EPUB it came from. If text, images, or links do not survive the conversion, the build stops instead of publishing a damaged book.",
      checks: [
        {
          label: "Text",
          body: "Every reading page is compared with the EPUB it came from. A dropped sentence, changed punctuation, or moved paragraph stops the build.",
        },
        {
          label: "Images",
          body: "Each figure is counted and checked against the source. A missing image fails the build instead of publishing a hole in the book.",
        },
        {
          label: "Links",
          body: "Internal links, anchors, images, and duplicate IDs are checked before anything is published. Readers do not hit a dead end between chapters.",
        },
      ],
      colophon: {
        kicker: "Colophon",
        title: "A real build",
        verified: "Verified",
        rows: [
          { label: "Source", value: "alice.epub" },
          { label: "Words", value: "29,564" },
          { label: "Pages", value: "13 / 13 match" },
          { label: "Images", value: "12 / 12 present" },
          { label: "Links", value: "743 checked · 0 broken" },
          { label: "Uploads", value: "None" },
        ],
        caption: "Generated locally in 0.57 seconds. Nothing was uploaded.",
      },
      failStrong: "If a check fails, the build stops.",
      failRest:
        "Your previous site stays exactly where it was, and the error report tells you what did not match.",
    },
    edition: {
      eyebrow: "The reading site",
      titleLine1: "A book, not a",
      titleAccent: "dump of HTML.",
      lede: "You get a cover, a table of contents, a page for each chapter, the pictures, footnotes, search, and a private layer for highlights and notes. It is all one static folder you can keep or publish.",
      features: {
        reading: {
          title: "Reads like a book",
          body: "Comfortable type, adjustable size and spacing, light and dark themes, and a place marker that remembers where you stopped.",
          imageAlt:
            "The reading view: a chapter of Alice's Adventures in Wonderland with a contents sidebar, progress line, and comfortable serif typography.",
          caption: "The reading view",
        },
        search: {
          title: "Search the whole book",
          body: "The book is indexed when the site is built. Search for a word and jump straight to it; no search service and no account.",
          imageAlt:
            "The built-in search panel showing highlighted results for the word rabbit across chapters.",
          caption: "Search results",
        },
        keep: {
          title: "Yours to keep",
          body: "One folder of HTML, CSS, images, fonts, and search data. Put it on any static host, or keep it on your computer.",
        },
        book: {
          title: "The whole book comes along",
          body: "Pictures with captions, tables, lists, footnotes, and cross-references all survive the move.",
          tags: ["Figures", "Tables", "Footnotes", "Cross-references"],
        },
        a11y: {
          title: "Works for more readers",
          body: "Keyboard navigation, clear labels, and image descriptions are part of the reader, not an afterthought.",
          tags: ["Keyboard", "Labels", "Alt text"],
        },
      },
      demo: "Open the live demo",
    },
    annotations: {
      eyebrow: "Highlights & notes",
      titleLine1: "Read with a",
      titleAccent: "pencil in hand.",
      lede: "Select a passage to highlight it. Add a private note when you want one. Everything stays in your browser and is never written into the published site.",
      points: [
        {
          title: "Highlight in one action",
          body: "Select text and highlight it in your last-used color. A note is optional, never a required second step.",
        },
        {
          title: "Find every mark",
          body: "Review by chapter, search by quote or note, and jump back to the passage in one click.",
        },
        {
          title: "Take it with you",
          body: "Copy everything as Markdown, export a readable file, or keep a JSON backup. The marks never enter the site itself.",
        },
      ],
      demoLink: "Try highlights in the live demo",
      demo: {
        kicker: "Chapter I",
        title: "Down the Rabbit-Hole",
        firstText:
          "Alice was beginning to get very tired of sitting by her sister on the bank, and of having nothing to do: ",
        markedText:
          "once or twice she had peeped into the book her sister was reading, but it had no pictures or conversations in it.",
        secondText:
          "So she was considering in her own mind whether the pleasure of making a daisy-chain would be worth the trouble of getting up and picking the daisies.",
        noteAria: "Example note",
        noteHead: "Note · Chapter I",
        noteQuote:
          "“...what is the use of a book, without pictures or conversations?”",
        noteBody:
          "Alice wants a book with pictures and conversation. The web edition keeps both.",
        copyMarkdown: "Copy as Markdown",
        exportJson: "Export JSON",
        caption:
          "An illustrative look at the browser-only annotation layer. Nothing is uploaded.",
      },
    },
    privacy: {
      eyebrow: "Local by design",
      titleLine1: "Your book stays on",
      titleAccent: "your computer.",
      lede: "There is no account and no upload. The app reads the EPUB on your machine and builds the site there. Run it again and you get the same site.",
      github: "Read the source on GitHub",
      points: [
        {
          title: "Nothing leaves your computer",
          body: "The EPUB, the finished site, the logs, and any error reports stay on your machine. Highlights and notes stay in your browser.",
        },
        {
          title: "The same book gives the same site",
          body: "Run the converter twice and you get the same text and structure. Only the build timestamp in the sitemap changes.",
        },
        {
          title: "You can check the work",
          body: "The converter, the reader theme, and the tests are GPLv3 licensed. If you want to know exactly what happens to your book, the code is there to read.",
        },
      ],
    },
    process: {
      eyebrow: "How it works",
      titleLine1: "From EPUB to website",
      titleAccent: "in three steps.",
      lede: "The desktop app includes the converter, Python, and the fonts. Choose a book, press Convert, and the finished site opens in your browser.",
      steps: [
        {
          title: "Choose your EPUB",
          body: "Pick a book you own. Standard EPUB 2 and EPUB 3 files work best.",
        },
        {
          title: "Press Convert",
          body: "The app converts the book and checks each page as it goes. Progress is visible, so a long book does not look stuck.",
        },
        {
          title: "Read it or publish it",
          body: "Read the site in your browser, or upload the folder to any static host.",
        },
      ],
      cliLabel: "Prefer the command line?",
      docs: "Read the docs",
    },
    faq: {
      eyebrow: "Questions",
      title: "Before you download.",
      intro:
        "What people ask before trying epub2web, including where the files go and why your computer may warn you the first time you open the app.",
      ask: "Ask a question on GitHub",
      first: {
        summary: "Why does my computer warn me when I open the app?",
        p1Before:
          "The desktop builds are not code-signed yet, so Windows SmartScreen and macOS Gatekeeper may warn about an unidentified developer on first launch. That is expected. Only continue with a file from the ",
        p1Link: "official GitHub releases page",
        p1After: ".",
        p2Before:
          "The download page has the step-by-step steps for Windows and macOS, including the Open Anyway flow. ",
        p2GuideLink: "Read the first-launch guide",
        p2Mid: " or the ",
        p2ReadmeLink: "full notes in the README",
        p2After: ".",
      },
      items: [
        {
          question: "Is my book uploaded anywhere?",
          answer:
            "No. The EPUB is read on your computer, the site is built there, and the finished folder stays there. There is no account and no upload step. If you publish it, that is your choice.",
        },
        {
          question: "Will the text be changed?",
          answer:
            "No. The words and punctuation stay as they are. epub2web may change how the book looks, but not what it says. A fidelity gate compares every page with the source and stops the build if anything is missing.",
        },
        {
          question: "What exactly do I get?",
          answer:
            "A folder with a cover, a table of contents, a page for each chapter, images, fonts, and a search index. It includes a small reading theme that works on phones and desktops. Standard EPUB 2 and EPUB 3 books work best; DRM-protected and fixed-layout books may not.",
        },
        {
          question: "Can I highlight passages and take notes?",
          answer:
            "Yes. Select text to highlight it in one action, add a private note when you want one, and find every mark in the Highlights & notes panel. Copy them as Markdown or export a JSON backup. Everything stays in your browser and is never added to the published site.",
        },
        {
          question: "Do highlights and notes sync between devices?",
          answer:
            "Not automatically. They live in the browser that created them. Use Copy all or Export to move them, and keep a backup before clearing site data. The reader only asks for persistent storage after you choose Keep on this device.",
        },
        {
          question: "Can I put the site online, or read it later?",
          answer:
            "Yes. The output is a plain static folder, so it works on GitHub Pages, Cloudflare Pages, Netlify, S3, nginx, or any static host. To read it later on your own computer, reopen the app and press Convert, or serve the folder with any local static server. Subpath hosting is supported with the command-line --base-path option.",
        },
        {
          question: "What if my book does not convert?",
          answer:
            "epub2web stops instead of dropping content, leaves any previous working site untouched, and creates a support ZIP you can attach to a GitHub issue. Do not attach the book itself. The ZIP can contain file paths, metadata, and short excerpts, so look through it first.",
        },
      ],
    },
    closing: {
      eyebrow: "Get started",
      titleLine1: "Make a web edition",
      titleAccent: "of your book.",
      intro:
        "Choose an EPUB, press Convert, and the finished site opens in your browser. Keep it, or share the folder with anyone.",
      download: "Download epub2web",
      demo: "Read the live demo",
      meta: "Free & open source · GPLv3 licensed · No account required · ",
      latestRelease: "Latest release on GitHub",
    },
  },
  download: {
    metaTitle: "Download epub2web for Windows, macOS, and Linux",
    metaDescription:
      "Download the epub2web desktop app for Windows, macOS, or Linux. Turn an EPUB into a reading website with private highlights and notes, without installing Python.",
    hero: {
      eyebrow: "Download",
      titleLine1: "Get the app.",
      titleAccent: "Open your book.",
      lede: "Python and the fonts are already inside the download. Pick your computer below and open the file.",
      choosePlatform: "Choose your platform",
      allPlatforms: "All platforms",
      versionMeta:
        "Version {version} · Direct file downloads · Windows, macOS, Linux · GPLv3 licensed",
      releaseAria: "epub2web {version} release information",
      latestRelease: "Latest release",
      github: "GitHub",
      releaseDescription: "The desktop app, ready to convert a book.",
      specs: {
        version: "Version",
        published: "Published",
        platforms: "Platforms",
        install: "Install",
        none: "None",
      },
      releaseNotes: "Release notes",
      releaseNoteBefore:
        "Every platform is listed below. Older versions are on the ",
      releaseNoteLink: "releases page",
      releaseNoteAfter: ".",
    },
    platforms: {
      eyebrow: "Choose your computer",
      titleBefore: "Pick the download ",
      titleAccent: "for your computer.",
      lede: "Each button starts the download from GitHub. If you're not sure which file you need, the note under each one should help.",
      recommended: "Recommended",
      downloadForSr: "Download epub2web for ",
      fileSr: "File: {filename}. Download starts immediately.",
      variants: {
        windows: "x64 installer",
        macosArm64: "Apple Silicon",
        macosX64: "Intel",
        linux: "x86_64",
      },
      hints: {
        windows: "Double-click the file to start the app.",
        macosArm64: "For most Macs made since late 2020.",
        macosX64: "For older Macs.",
        linux: "Make the file executable, then run it.",
      },
      noteBefore:
        "Linux AppImages may need to be made executable first: run ",
      noteMid: ". If FUSE is unavailable, use ",
      noteAfter: ". Verify any file against ",
      noteAfterLink: ".",
    },
    launch: {
      eyebrow: "Before you open it",
      title: "The first-launch warning is expected.",
      intro:
        "The desktop builds don't have a paid code-signing certificate yet, so Windows SmartScreen and macOS Gatekeeper may warn that the developer can't be verified. That's expected. Only continue if you downloaded the file from the official GitHub release.",
      readFaq: "Read the full first-launch FAQ",
      windowsTitle: "On Windows",
      windowsLead: "If “Windows protected your PC” appears:",
      windowsSteps: [
        "Click <strong>More info</strong>.",
        "Click <strong>Run anyway</strong>.",
        "Open the app and choose an EPUB.",
      ],
      windowsFine:
        "On a managed workplace or school PC, Smart App Control may block unsigned apps completely. Ask your administrator rather than disabling security features.",
      macosTitle: "On macOS",
      macosLead: "On macOS 15 and later, after dragging the app to Applications:",
      macosSteps: [
        "Try to open it once, then click <strong>Done</strong>.",
        "Open <strong>System Settings → Privacy &amp; Security</strong>.",
        "Under <strong>Security</strong>, click <strong>Open Anyway</strong>.",
        "Authenticate, then open the app again.",
      ],
      macosFineBefore:
        "On macOS 14 and earlier, right-click the app, choose ",
      macosFineStrong: "Open",
      macosFineMid:
        ", then click <strong>Open</strong> in the dialog. If macOS says the app is damaged, re-download it before trying the Terminal workaround.",
      verifyBefore: "Verify downloads against the ",
      verifyAfter:
        " file. More detail is in the ",
      verifyReadme: "README",
      verifyDocsMid: " and the ",
      verifyDocs: "desktop app docs",
      verifyDocsAfter: ".",
    },
    other: {
      eyebrow: "Other ways to try it",
      titleBefore: "Prefer Python? ",
      titleAccent: "Or just looking?",
      lede: "The desktop app is the simplest way to start. If you're comfortable with Python, you can install the package and run the converter from a terminal. Or try the demo first.",
      sourceEyebrow: "From source",
      sourceTitle: "Install with pipx",
      sourceBody:
        "epub2web needs Python 3.10 or newer. Install it from GitHub, then build and preview a book:",
      sourceLink: "Installation and CLI options",
      demoTry: "Try it first",
      demoTitle: "See a finished site.",
      demoBody:
        "The live demo is a complete epub2web site, built from a public-domain book and served as plain static files. Read a chapter, search it, try the dark theme.",
      demoButton: "Open the live demo",
      footBefore: "Project source, issues, and release history live on ",
      footLink: "GitHub",
      footAfter: ".",
    },
    dialog: {
      closeAria: "Close the first-launch guide",
      status: "Download started",
      title: "Before you open it.",
      description:
        "Your download continues in the background. The app isn’t code-signed yet, so follow these steps the first time you open it on ",
      descriptionName: "your computer",
      descriptionAfter: ".",
      onPlatform: "On {platform}",
      verifyBefore: "Check the file against ",
      verifyAfter: " if you want to verify it.",
      gotIt: "Got it",
      fullGuide: "Full first-launch guide",
    },
    guides: {
      windows: {
        name: "Windows",
        steps: [
          "Double-click the downloaded <code>.exe</code> file.",
          "If “Windows protected your PC” appears, click <strong>More info</strong>, then <strong>Run anyway</strong>.",
          "Choose your EPUB when the app opens.",
        ],
        note: "On a managed workplace or school PC, Smart App Control may block unsigned apps completely. Ask your administrator rather than disabling security features.",
      },
      macos: {
        name: "macOS",
        steps: [
          "Open the <code>.dmg</code> and drag epub2web into <strong>Applications</strong>.",
          "Try to open the app once, then click <strong>Done</strong> when macOS blocks it.",
          "Open <strong>System Settings → Privacy &amp; Security</strong>, then click <strong>Open Anyway</strong> under Security and authenticate.",
          "Open the app again and choose your EPUB.",
        ],
        note: "On macOS 14 and earlier, right-click the app, choose Open, then Open again. The Open Anyway button is available for about an hour after the first attempt.",
      },
      linux: {
        name: "Linux",
        steps: [
          "Make the AppImage executable: <code>chmod +x epub2web-gui-*.AppImage</code>.",
          "Run it: <code>./epub2web-gui-*.AppImage</code>.",
          "If FUSE is unavailable, run it with <code>--appimage-extract-and-run</code>.",
        ],
        note: "Linux doesn’t show a first-launch warning. You can verify the file against SHA256SUMS.txt before running it.",
      },
    },
    js: {
      yourComputer: "your computer",
      choosePlatform: "Choose your platform",
      downloadFor: "Download for {platform}",
      messages: {
        fallbackChoose: "Choose the file that matches the computer you’ll use.",
        mobile: "You’re on a phone or tablet. Choose the computer you’ll use.",
        windows: "Detected Windows. The x64 installer is selected.",
        macIntel: "Detected an Intel Mac. The Intel build is selected.",
        macArm: "Detected Apple Silicon. The arm64 build is selected.",
        macUnknown:
          "Most Macs use Apple Silicon. Choose Intel below if yours is older.",
        chromeos: "ChromeOS detected. Choose the computer you’ll use.",
        linuxArm:
          "This release is for x86_64 Linux; ARM Linux isn’t available yet.",
        linux: "Detected Linux. The x86_64 AppImage is selected.",
      },
    },
  },
  changelog: {
    metaTitle: "Changelog — epub2web",
    metaDescription:
      "What changed in each epub2web release, with a direct link to the notes on GitHub.",
    eyebrow: "Changelog",
    titleLine1: "Every release,",
    titleAccent: "in one place.",
    lede: "The full history of epub2web, from the first public release to today. Each version links to its release notes on GitHub.",
    latestRelease: "Latest release",
    github: "GitHub",
    viewRelease: "View release",
    viewReleaseSr: "for version {version} (opens in a new tab)",
    latestNoteBefore: "Download ",
    latestNoteMid: " or read the notes on GitHub.",
    releases: "Releases",
    allVersions: "All versions",
    sourceNoteBefore: "Unreleased changes are tracked in the ",
    sourceNoteLink: "source changelog",
    sourceNoteAfter: ".",
    latestBadge: "Latest",
    preGithubBadge: "Pre-GitHub Releases",
    viewChangelog: "View changelog",
    viewChangelogSr: "for version {version} on GitHub (opens in a new tab)",
    preGithubNote:
      "This version predates the project's GitHub Releases history. The button opens its section in the GitHub-hosted changelog.",
    translationNotice:
      "Release notes are translated into Vietnamese where available. Releases without a translation show the English notes, and the English changelog on GitHub remains the canonical source.",
    untranslatedBadge: "English only",
    untranslatedNote:
      "This release has not been translated into Vietnamese yet. Showing the English notes.",
  },
};

export type Copy = typeof en;
