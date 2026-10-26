from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest
from PIL import Image


def _write_epub(path: Path) -> None:
    container = """<?xml version="1.0"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""
    opf = """<?xml version="1.0" encoding="utf-8"?>
<package xmlns="http://www.idpf.org/2007/opf" version="2.0" unique-identifier="id">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>A Tiny Book</dc:title>
    <dc:creator>Test Author</dc:creator>
    <dc:language>en</dc:language>
    <dc:identifier id="id">urn:uuid:test-book</dc:identifier>
    <dc:publisher>Test Press</dc:publisher>
    <dc:date>2024-01-01</dc:date>
    <dc:rights>Public domain test fixture.</dc:rights>
    <meta name="cover" content="cover"/>
  </metadata>
  <manifest>
    <item id="cover" href="images/cover.png" media-type="image/png"/>
    <item id="ch1" href="ch1.xhtml" media-type="application/xhtml+xml"/>
    <item id="ch2" href="ch2.xhtml" media-type="application/xhtml+xml"/>
    <item id="ncx" href="toc.ncx" media-type="application/x-dtbncx+xml"/>
  </manifest>
  <spine toc="ncx">
    <itemref idref="ch1"/>
    <itemref idref="ch2"/>
  </spine>
  <guide>
    <reference type="cover" title="Cover" href="images/cover.png"/>
  </guide>
</package>
"""
    ncx = """<?xml version="1.0" encoding="UTF-8"?>
<ncx xmlns="http://www.daisy.org/z3986/2005/ncx/" version="2005-1">
  <head><meta name="dtb:uid" content="urn:uuid:test-book"/></head>
  <docTitle><text>A Tiny Book</text></docTitle>
  <navMap>
    <navPoint id="n1" playOrder="1">
      <navLabel><text>Chapter One</text></navLabel>
      <content src="ch1.xhtml"/>
    </navPoint>
    <navPoint id="n2" playOrder="2">
      <navLabel><text>Chapter Two</text></navLabel>
      <content src="ch2.xhtml"/>
    </navPoint>
  </navMap>
</ncx>
"""
    ch1 = """<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en">
<head><title>Chapter One</title></head>
<body>
  <h1 id="ch1">Chapter One</h1>
  <p>Hello <em>world</em>.</p>
  <h2 id="section-one">A Section</h2>
  <p>This is a short section with a <a href="#note1" id="ref1">note</a>.</p>
  <p id="note1" class="footnote"><a href="#ref1">1</a> A note in the text.</p>
  <figure>
    <img src="images/cover.png" alt="A small red rectangle"/>
    <figcaption>Figure one.</figcaption>
  </figure>
</body>
</html>
"""
    ch2 = """<?xml version="1.0" encoding="utf-8"?>
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="en">
<head><title>Chapter Two</title></head>
<body>
  <h1 id="ch2">Chapter Two</h1>
  <p>Goodbye world.</p>
  <blockquote><p>A quoted line.</p></blockquote>
  <ul><li>One</li><li>Two</li></ul>
</body>
</html>
"""
    image = io.BytesIO()
    Image.new("RGB", (40, 60), (180, 58, 27)).save(image, "PNG")

    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr(zipfile.ZipInfo("mimetype"), "application/epub+zip")
        zf.writestr("META-INF/container.xml", container)
        zf.writestr("OEBPS/content.opf", opf)
        zf.writestr("OEBPS/toc.ncx", ncx)
        zf.writestr("OEBPS/ch1.xhtml", ch1)
        zf.writestr("OEBPS/ch2.xhtml", ch2)
        zf.writestr("OEBPS/images/cover.png", image.getvalue())


@pytest.fixture()
def tiny_epub(tmp_path: Path) -> Path:
    path = tmp_path / "tiny.epub"
    _write_epub(path)
    return path
