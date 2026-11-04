"""A pandoc Lua filter that keeps an upload from pulling local image files into its PDF.

pandoc and xelatex embed any image an upload names by path, so `![x](/home/me/photo.png)`
in Markdown or `<img src="/home/me/photo.png">` in HTML put that file in the PDF.
`--sandbox` doesn't cover PDF output and `openin_any=p` doesn't cover images, so the
filter removes them from the document before LaTeX sees it:

- Images whose source isn't a `data:` URI or an `http(s)` URL are replaced by their alt text.
- Raw LaTeX that loads files or can build such a command (`\\includegraphics`,
  `\\XeTeXpicfile`, `\\csname`, catcode changes...) is dropped. This is a blocklist, so it's
  best effort: running xelatex in a sandbox is the complete fix.

It is written to a temp file per call, so it needs no packaging entry.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager

LOCAL_FILES_LUA = r"""
local function allowed(src)
  local lower = src:lower()
  return lower:match("^data:") or lower:match("^https?://")
end

function Image(img)
  if allowed(img.src) then
    return nil
  end
  io.stderr:write("[file-converter] dropped local image: " .. img.src .. "\n")
  return img.caption
end

local blocked = {
  "includegraphics", "includepdf", "XeTeXpicfile", "XeTeXpdffile", "special",
  "csname", "endcsname", "catcode", "scantokens", "lowercase", "uppercase", "input", "include",
  "openin", "read", "directlua",
}

local function loads_files(text)
  for _, name in ipairs(blocked) do
    if text:find("\\" .. name, 1, true) then
      return true
    end
  end
  return false
end

local function raw(el)
  if (el.format == "latex" or el.format == "tex") and loads_files(el.text) then
    io.stderr:write("[file-converter] dropped raw LaTeX that loads files\n")
    return {}
  end
  return nil
end

RawInline = raw
RawBlock = raw
"""


@contextmanager
def local_files_filter() -> Iterator[list[str]]:
    """Yield pandoc arguments that apply the filter. Put them before any other --filter, so
    images a later filter generates (mermaid-filter's diagrams) aren't dropped."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".lua", delete=False, encoding="utf-8") as f:
        f.write(LOCAL_FILES_LUA)
        path = f.name
    try:
        yield ["--lua-filter", path]
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
