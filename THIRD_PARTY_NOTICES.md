# Third-party notices

The code is MIT-licensed. The following assets and dependencies are used under
their own licenses.

## Fonts

The packaged theme self-hosts typefaces from Google Fonts:

- **Fraunces** — Copyright 2018 The Fraunces Project Authors. SIL Open Font License 1.1.
- **Literata** — Copyright 2017 The Literata Project Authors. SIL Open Font License 1.1.
- **Inter** — Copyright 2016 The Inter Project Authors. SIL Open Font License 1.1.
- **Noto Naskh Arabic**, **Noto Sans Arabic**, **Noto Serif Hebrew**,
  **Noto Sans Hebrew**, **Noto Serif Devanagari**, **Noto Sans Devanagari**,
  **Noto Serif Thai**, **Noto Sans Thai**, and **Noto Serif SC/TC/JP/KR** —
  Copyright The Noto Project Authors. SIL Open Font License 1.1.

License: https://openfontlicense.org/

## Python dependencies

- Beautiful Soup (MIT)
- Jinja2 (BSD-3-Clause)
- lxml (BSD-3-Clause)
- Pillow (HPND)
- tkinterdnd2 (MIT) — Tkinter wrapper for native drag and drop. It bundles the
  TkDND Tcl/Tk extension, whose license is reproduced below.

Each dependency remains under its own license. See the installed distributions
for the full texts.

## TkDND

The desktop GUI uses TkDND through tkinterdnd2. TkDND is distributed under the
following BSD-style license:

```text
This software is copyrighted by:
   Georgios Petasis, Athens, Greece.
   e-mail: petasisg@yahoo.gr, petasis@iit.demokritos.gr

   Mac portions (c) 2009-2014 Kevin Walzer/WordTech Communications LLC,
   kw@codebykevin.com

The following terms apply to all files associated with the
software unless explicitly disclaimed in individual files.

The authors hereby grant permission to use, copy, modify, distribute,
and license this software and its documentation for any purpose, provided
that existing copyright notices are retained in all copies and that this
notice is included verbatim in any distributions. No written agreement,
license, or royalty fee is required for any of the authorized uses.
Modifications to this software may be copyrighted by their authors
and need not follow the licensing terms described here, provided that
the new terms are clearly indicated on the first page of each file where
they apply.

IN NO EVENT SHALL THE AUTHORS OR DISTRIBUTORS BE LIABLE TO ANY PARTY
FOR DIRECT, INDIRECT, SPECIAL, INCIDENTAL, OR CONSEQUENTIAL DAMAGES
ARISING OUT OF THE USE OF THIS SOFTWARE, ITS DOCUMENTATION, OR ANY
DERIVATIVES THEREOF, EVEN IF THE AUTHORS HAVE BEEN ADVISED OF THE
POSSIBILITY OF SUCH DAMAGE.

THE AUTHORS AND DISTRIBUTORS SPECIFICALLY DISCLAIM ANY WARRANTIES,
INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE, AND NON-INFRINGEMENT.  THIS SOFTWARE
IS PROVIDED ON AN "AS IS" BASIS, AND THE AUTHORS AND DISTRIBUTORS HAVE
NO OBLIGATION TO PROVIDE MAINTENANCE, SUPPORT, UPDATES, ENHANCEMENTS, OR
MODIFICATIONS.

GOVERNMENT USE: If you are acquiring this software on behalf of the
U.S. government, the Government shall have only "Restricted Rights"
in the software and related documentation as defined in the Federal
Acquisition Regulations (FARs) in Clause 52.227.19 (c) (2).  If you
are acquiring the software on behalf of the Department of Defense, the
software shall be classified as "Commercial Computer Software" and the
Government shall have only "Restricted Rights" as defined in Clause
252.227-7013 (c) (1) of DFARs.  Notwithstanding the foregoing, the
authors grant the U.S. Government and others acting in its behalf
permission to use and distribute the software in accordance with the
terms specified in this license.
```

Source: https://github.com/petasis/tkdnd/blob/master/license.terms

## Tcl/Tk

The optional desktop GUI uses Tkinter and the Tcl/Tk runtime. Tcl/Tk is
distributed under its own BSD-style license:
https://www.tcl.tk/software/tcltk/license.html

If you distribute a PyInstaller app that bundles Tcl/Tk, include the license
files supplied with the Tcl/Tk distribution.

## Landing site build dependencies

The Astro site in `site/` is built separately from the Python package. Its
build-time dependencies include:

- Astro (MIT)
- marked (MIT)

Neither is bundled into the book output or included in the runtime of the
generated static site.

## Platform icons

The landing site uses platform icons from
[Simple Icons](https://simpleicons.org/), released under CC0 1.0. Windows,
Apple, Linux, and GitHub are trademarks of their respective owners; the icons
identify their platforms only.
