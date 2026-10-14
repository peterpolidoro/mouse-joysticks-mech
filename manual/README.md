# The manual

One PDF for the whole rig, assembled from the documentation the four
repositories already keep, so a new lab member gets one file and the rig
keeps one record of how it was built.

| File | What it is |
| --- | --- |
| `manifest.yaml` | the parts of the manual and, in reading order, every document as `<repository>@<ref>:<path>`, with the refs pinned at the citable tags |
| `build.py` | fetches each document at its ref, rewrites its figures and links to work inside one file, writes `tmp/manual/manual.md`, then pandoc to typst and typst to PDF |

```sh
pixi run manual                 # tmp/manual/mouse-joystick-rig-manual-<date>.pdf
pixi run manual --md-only       # just the combined Markdown, to read what went in
pixi run manual --out dist/     # the PDF somewhere else
```

The `manual` pixi environment holds pandoc, typst and PyYAML. A document is
read from the sibling checkout when one is there (`git show <ref>:<path>`;
the ref `worktree` is this checkout's own working tree), otherwise from
GitHub at the ref, which is how the release workflow
(`.github/workflows/manual.yml`) builds it: publishing a release of this
repository attaches the PDF to it. The PDF is not committed.

## What the rewriting does

- The document's first heading becomes its title (or the `title` the
  manifest gives it); the rest of its headings move down so the parts are
  chapters and the documents sections.
- Images are fetched at the same ref into `tmp/manual/files/` (web images
  too). An image that cannot be fetched, or is not PNG, JPEG, SVG or GIF,
  is replaced by a note.
- A link to another document that is in the manual, whether written as a
  relative path or as a GitHub URL, points into the manual. Any other
  relative link becomes the file's URL on GitHub at the ref, and outside
  tables and headings the URL is repeated in a footnote so a printed page
  still has it.
- Tables: each column's width follows its longest cell (damped, so one
  long column does not take the page), tables may break across pages, and
  long code in cells and in prose gets zero-width spaces after `_`, `/`,
  `-`, `.` and `:` so typst can wrap a path or a net name instead of
  running it into the next column. Copying such a name out of the PDF can
  carry those invisible characters; the web pages do not have them.
- Raw HTML is dropped by pandoc on the way to typst, so pages that depend
  on it (the site's front page with the model viewer) are not listed in the
  manifest.
- `header.typ` holds the typst rules pandoc includes: breakable figures,
  left-aligned cells, a smaller face in tables.

The build exits non-zero, after writing the PDF, if any document or image
could not be fetched; the log names each one.
