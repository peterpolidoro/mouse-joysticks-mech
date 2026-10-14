#!/usr/bin/env python3
"""Assemble the rig manual from the repositories' Markdown and typeset it.

    python manual/build.py                # tmp/manual/mouse-joystick-rig-manual-<date>.pdf
    python manual/build.py --md-only      # stop after tmp/manual/manual.md
    python manual/build.py --out dist/    # write the PDF there instead

`manual/manifest.yaml` names the parts and, in reading order, every document
as `<repository>@<ref>:<path>`. A document is read from the sibling checkout
when there is one (`git show <ref>:<path>`; the ref `worktree` is this
checkout's working tree), otherwise from GitHub at that ref, which is how the
release workflow builds without checkouts. Each document's images are fetched
the same way into tmp/manual/files/. Links to other included documents become
cross-references; links to anything else become that file's URL on GitHub at
the ref, repeated as a footnote outside tables so the printed page keeps it.
pandoc writes typst, typst writes the PDF.
"""

import argparse
import datetime
import hashlib
import pathlib
import posixpath
import re
import shutil
import subprocess
import sys
import urllib.request

import yaml

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "tmp" / "manual"
FILES = OUT / "files"
SOURCE = re.compile(r"^([^@\s]+)@([^:\s]+):(.+)$")
GITHUB_BLOB = re.compile(r"^https?://github\.com/([^/]+/[^/#?]+)/(?:blob|tree)/([^/#?]+)/([^#?]+)")
FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})")
HEADING = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
IMAGE = re.compile(r"!\[([^\]]*)\]\(\s*(<[^>]*>|[^)\s]+)(\s+\"[^\"]*\")?\s*\)")
HTML_IMAGE = re.compile(r"<img\b[^>]*\bsrc=\"([^\"]+)\"[^>]*>")
LINK = re.compile(r"(?<!!)\[((?:[^\[\]]|\[[^\]]*\])*)\]\(\s*(<[^>]*>|[^)\s]+)(\s+\"[^\"]*\")?\s*\)")
IMAGE_TYPES = {".png", ".jpg", ".jpeg", ".svg", ".gif"}
TABLE_SEP = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$")
ZWSP = "\u200b"   # a break opportunity typst honours inside code, which otherwise never wraps


def split_row(line):
    """A pipe-table row's cells; pipes inside code spans or escaped stay put."""
    t = line.strip()
    if t.startswith("|"):
        t = t[1:]
    if t.endswith("|") and not t.endswith("\\|"):
        t = t[:-1]
    cells, buf, code = [], [], False
    for i, c in enumerate(t):
        if c == "`":
            code = not code
        if c == "|" and not code and (i == 0 or t[i - 1] != "\\"):
            cells.append("".join(buf)); buf = []
        else:
            buf.append(c)
    cells.append("".join(buf))
    return cells


def visible_len(cell):
    t = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", cell)
    return len(t.replace("`", "").replace("**", "").strip())


def breakable_code(text, min_len):
    """Zero-width spaces after the separators of long code spans, so typst can
    wrap a path or an identifier instead of running it off the cell."""
    def span(m):   # backticks pair left to right; only long spans change
        inner = m.group(1)
        if len(inner) < min_len:
            return m.group(0)
        return "`" + re.sub(r"([_/:.\-])", "\\1" + ZWSP, inner) + "`"
    return re.sub(r"`([^`\n]+)`", span, text)


def fix_table(lines):
    """A pipe table's separator row rewritten so pandoc gives each column a
    width in proportion to its longest cell (damped and capped), and long
    code in its cells made breakable. pandoc reads relative widths off the
    dash counts once a line is wider than its --columns."""
    if len(lines) < 2 or not TABLE_SEP.match(lines[1]):
        return lines
    rows = [split_row(l) for l in lines]
    n = len(rows[1])
    longest = [1] * n
    for i, r in enumerate(rows):
        if i != 1:
            for c, cell in enumerate(r[:n]):
                longest[c] = max(longest[c], visible_len(cell))
    weights = [min(L, 60) ** 0.75 for L in longest]
    total = sum(weights) or 1.0
    dashes = [max(3, round(80 * w / total)) for w in weights]
    out = []
    for i, r in enumerate(rows):
        if i == 1:
            cells = []
            for c in range(n):
                t = r[c].strip()
                cells.append((":" if t.startswith(":") else "") + "-" * dashes[c] + (":" if t.endswith(":") else ""))
        else:
            cells = [breakable_code(c.strip(), 12) for c in r]
        out.append("| " + " | ".join(cells) + " |")
    return out


def fix_tables(seg):
    """Every pipe table in a prose segment through fix_table; long code in
    the prose around them made breakable too."""
    out, block = [], []
    for line in seg.splitlines():
        if line.lstrip().startswith("|"):
            block.append(line)
            continue
        if block:
            out.extend(fix_table(block)); block = []
        out.append(line if line.lstrip().startswith("#") else breakable_code(line, 30))
    if block:
        out.extend(fix_table(block))
    return "\n".join(out) + ("\n" if seg.endswith("\n") else "")


def log(*a):
    print("[manual]", *a, file=sys.stderr)


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def gh_slug(heading):
    """The anchor GitHub gives a heading, which is what the documents' own
    fragment links use: code spans and link text kept, punctuation dropped,
    spaces to hyphens."""
    t = re.sub(r"`([^`]*)`", r"\1", heading)
    t = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", t)
    t = re.sub(r"\s*\{#[^}]*\}\s*$", "", t)
    t = re.sub(r"[^\w\- ]", "", t.strip().lower())
    return t.replace(" ", "-")


_urls = {}


def fetch_url(url):
    if url not in _urls:
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                _urls[url] = r.read()
        except Exception as e:  # offline, or gone
            log(f"could not fetch {url}: {e}")
            _urls[url] = None
    return _urls[url]


class Repo:
    def __init__(self, name, spec):
        self.name = name
        self.github = spec["github"]
        local = spec.get("local")
        self.local = (ROOT / local).resolve() if local else None
        if self.local and not (self.local / ".git").exists():
            self.local = None

    def branch_or_ref(self, ref):
        return "main" if ref == "worktree" else ref

    def blob_url(self, ref, path, directory=False):
        kind = "tree" if directory else "blob"
        return f"https://github.com/{self.github}/{kind}/{self.branch_or_ref(ref)}/{path}"

    def raw_url(self, ref, path):
        return f"https://raw.githubusercontent.com/{self.github}/{self.branch_or_ref(ref)}/{path}"

    def read(self, ref, path):
        """The file's bytes at the ref, or None."""
        if ref == "worktree":
            p = (self.local or ROOT) / path
            return p.read_bytes() if p.is_file() else None
        if self.local:
            r = subprocess.run(["git", "-C", str(self.local), "show", f"{ref}:{path}"], capture_output=True)
            if r.returncode == 0:
                return r.stdout
        return fetch_url(self.raw_url(ref, path))


class Doc:
    def __init__(self, repo, ref, path, title=None):
        self.repo, self.ref, self.path, self.title = repo, ref, path, title
        self.id = "doc-" + slug(f"{repo.name}-{path}")
        self.text = None
        self.anchors = {}   # GitHub-style fragment -> the id the heading gets in the manual

    def fetch(self):
        data = self.repo.read(self.ref, self.path)
        if data is None:
            self.title = self.title or posixpath.basename(self.path)
            return False
        self.text = data.decode("utf-8", "replace")
        seen = {}
        fence = None
        first_h1 = True
        for line in self.text.splitlines():
            fm = FENCE.match(line)
            if fm:
                if fence is None:
                    fence = fm.group(1)[0]
                elif line.strip().startswith(fence):
                    fence = None
                continue
            if fence:
                continue
            hm = HEADING.match(line)
            if not hm:
                continue
            level, body = len(hm.group(1)), hm.group(2)
            frag = gh_slug(body)
            n = seen.get(frag, 0)
            seen[frag] = n + 1
            if n:
                frag = f"{frag}-{n}"
            if level == 1 and first_h1:
                first_h1 = False
                self.title = self.title or re.sub(r"\s*\{#[^}]*\}\s*$", "", body)
                self.anchors[frag] = self.id
            else:
                self.anchors[frag] = f"{self.id}-{frag}" if frag else self.id
        self.title = self.title or posixpath.basename(self.path)
        return True

    def anchor(self, frag):
        """The manual's id for a fragment of this document; the document itself when unknown."""
        return self.anchors.get(frag.lower(), self.id)

    @property
    def key(self):
        return (self.repo.name, self.path)

    @property
    def url(self):
        return self.repo.blob_url(self.ref, self.path)


class Manual:
    def __init__(self, manifest):
        self.m = manifest
        self.repos = {n: Repo(n, s) for n, s in manifest["repositories"].items()}
        self.by_github = {r.github.lower(): r for r in self.repos.values()}
        refs = manifest.get("refs", {})
        self.parts = []
        self.docs = {}
        for part in manifest["parts"]:
            docs = []
            for entry in part["documents"]:
                spec, title = (entry, None) if isinstance(entry, str) else (entry["source"], entry.get("title"))
                for k, v in refs.items():
                    spec = spec.replace("{" + k + "}", str(v))
                mm = SOURCE.match(spec)
                if not mm:
                    raise SystemExit(f"bad document source {spec!r}")
                name, ref, path = mm.groups()
                if name not in self.repos:
                    raise SystemExit(f"unknown repository {name!r} in {spec!r}")
                d = Doc(self.repos[name], ref, path.strip("/"), title)
                if d.key in self.docs:
                    raise SystemExit(f"{spec} is listed twice")
                self.docs[d.key] = d
                docs.append(d)
            self.parts.append((part, docs))
        self.missing = []
        self.footnotes = 0

    # ------------------------------------------------------------ fetching

    def stage(self, data, *parts):
        p = FILES.joinpath(*parts)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return p.relative_to(OUT).as_posix()

    def image(self, doc, target):
        """Fetch an image the document refers to; the staged path, or None."""
        target = target.strip("<>")
        if target.startswith(("http://", "https://")):
            data = fetch_url(target)
            ext = posixpath.splitext(target.split("?")[0])[1].lower() or ".png"
            if data is None or ext not in IMAGE_TYPES:
                return None
            return self.stage(data, "web", hashlib.sha1(target.encode()).hexdigest()[:12] + ext)
        path = posixpath.normpath(posixpath.join(posixpath.dirname(doc.path), target))
        ext = posixpath.splitext(path)[1].lower()
        if ext not in IMAGE_TYPES:
            return None
        data = doc.repo.read(doc.ref, path)
        if data is None:
            self.missing.append(f"{doc.repo.name}@{doc.ref}:{path} (image in {doc.path})")
            return None
        return self.stage(data, doc.repo.name, slug(doc.ref), path)

    # ------------------------------------------------------------ rewriting

    def link_target(self, doc, target):
        """(new target, url to footnote or None) for a link in the document."""
        target = target.strip("<>")
        if target.startswith("#"):
            return "#" + doc.anchor(target[1:]), None
        if target.startswith("mailto:"):
            return target, None
        if target.startswith(("http://", "https://")):
            gm = GITHUB_BLOB.match(target)
            if gm:
                repo = self.by_github.get(gm.group(1).lower())
                if repo:
                    d = self.docs.get((repo.name, gm.group(3).strip("/")))
                    if d and d.text is not None:
                        frag = target.partition("#")[2]
                        return "#" + (d.anchor(frag) if frag else d.id), None
            return target, target
        if "://" in target:
            return target, None
        path, _, frag = target.partition("#")
        if not path:
            return target, None
        directory = path.endswith("/")
        path = posixpath.normpath(posixpath.join(posixpath.dirname(doc.path), path)).strip("/")
        d = self.docs.get((doc.repo.name, path))
        if d and d.text is not None:
            return "#" + (d.anchor(frag) if frag else d.id), None
        if not directory and doc.repo.read(doc.ref, path) is None and not path.startswith(".."):
            self.missing.append(f"{doc.repo.name}@{doc.ref}:{path} (link in {doc.path})")
        url = doc.repo.blob_url(doc.ref, path, directory) + (("#" + frag) if frag else "")
        return url, url

    def rewrite(self, doc, text):
        """The document's Markdown made to live inside the manual: headings
        moved down with explicit ids, images staged, links resolved. Fenced
        code is left alone; links and images are matched across line breaks,
        since prose wraps."""
        segments = []   # (is_code, text)
        fence = None
        buf = []
        for line in text.splitlines(keepends=True):
            fm = FENCE.match(line)
            if fm and fence is None:
                segments.append((False, "".join(buf))); buf = [line]
                fence = fm.group(1)[0]
                continue
            if fence:
                buf.append(line)
                if fm and line.strip().startswith(fence):
                    segments.append((True, "".join(buf))); buf = []
                    fence = None
                continue
            buf.append(line)
        segments.append((fence is not None, "".join(buf)))
        out = []
        first_h1 = True
        seen = {}
        for is_code, seg in segments:
            if is_code or not seg:
                out.append(seg)
                continue
            lines = []
            for line in seg.splitlines(keepends=True):
                hm = HEADING.match(line.rstrip("\n"))
                if not hm:
                    lines.append(line)
                    continue
                level, body = len(hm.group(1)), hm.group(2)
                body = re.sub(r"\s*\{#[^}]*\}\s*$", "", body)
                frag = gh_slug(body)
                n = seen.get(frag, 0)
                seen[frag] = n + 1
                if n:
                    frag = f"{frag}-{n}"
                if level == 1 and first_h1:
                    first_h1 = False
                    continue  # the document's heading is written by the caller, with its id
                lines.append("#" * min(6, max(3, level + 1)) + f" {body} {{#{doc.anchor(frag)}}}\n")
            seg = "".join(lines)
            seg = HTML_IMAGE.sub(lambda m: f"![]({m.group(1)})", seg)

            def img(m):
                alt, target = m.group(1), m.group(2)
                staged = self.image(doc, target)
                if staged is None:
                    return f"*[Figure not included: {alt or target.strip('<>')}]*"
                return f"![{alt}]({staged})"

            seg = IMAGE.sub(img, seg)

            def lnk(m):
                text_, target, ttl = m.group(1), m.group(2), m.group(3) or ""
                line_start = seg.rfind("\n", 0, m.start()) + 1
                head = seg[line_start:m.start()].lstrip()
                in_table = head.startswith("|")
                in_heading = head.startswith("#")
                new, note = self.link_target(doc, target)
                s = f"[{text_}]({new}{ttl})"
                if note and not in_table and not in_heading and text_.strip() != note:
                    self.footnotes += 1
                    s += f"^[<{note}>]"
                return s

            seg = LINK.sub(lnk, seg)
            out.append(fix_tables(seg))
        return "".join(out).strip("\n") + "\n"

    # ------------------------------------------------------------ assembly

    def assemble(self, date):
        m = self.m
        for d in self.docs.values():
            if not d.fetch():
                self.missing.append(f"{d.repo.name}@{d.ref}:{d.path} (document)")
        meta = {"title": m["title"], "subtitle": m.get("subtitle", ""), "date": str(date), "toc-title": "Contents"}
        parts = [
            "---",
            yaml.safe_dump(meta, allow_unicode=True, sort_keys=False).strip(),
            "---",
            "",
        ]
        cover = m.get("cover")
        if cover:
            cm = SOURCE.match(cover)
            if cm and cm.group(1) in self.repos:
                staged = self.image(Doc(self.repos[cm.group(1)], cm.group(2), cm.group(3)), posixpath.basename(cm.group(3)))
                if staged:
                    parts += [f"![{m.get('cover_caption', '')}]({staged})", ""]
        parts += [
            "# About this manual",
            "",
            "This manual is assembled from the documentation of the rig's repositories,",
            "each at the revision named in the Sources appendix, so that one document",
            "can be handed to a new lab member or kept with the rig. Each part is the",
            "repositories' own pages, rewritten only so their figures and links work",
            "inside one file: a link to a page that is in the manual points into the",
            "manual; a link to anything else is to the file on GitHub at the same",
            "revision, and is repeated in a footnote so it survives printing.",
            "",
            "The same pages, with the turnable model and clickable renders, are the",
            f"atlas site at <https://{self.repos['mouse-joysticks-mech'].github.split('/')[0]}.github.io/mouse-joysticks-mech/>.",
            f"The manual is rebuilt by `pixi run manual` in the `mouse-joysticks-mech`",
            "repository, from `manual/manifest.yaml`.",
            "",
        ]
        for part, docs in self.parts:
            parts.append(f"# {part['title']}")
            parts.append("")
            if part.get("intro"):
                parts.append(part["intro"].strip())
                parts.append("")
            for d in docs:
                if d.text is None:
                    continue
                body = self.rewrite(d, d.text)
                parts.append(f"## {d.title} {{#{d.id}}}")
                parts.append("")
                parts.append(f"*From `{d.repo.name}` at `{d.repo.branch_or_ref(d.ref)}`, `{d.path}`.*")
                parts.append("")
                parts.append(body)
                parts.append("")
        parts += ["# Sources", "", "| Document | Repository | Revision | File |", "| --- | --- | --- | --- |"]
        for _, docs in self.parts:
            for d in docs:
                if d.text is None:
                    continue
                parts.append(f"| [{d.title}](#{d.id}) | `{d.repo.name}` | `{d.repo.branch_or_ref(d.ref)}` | [{d.path}]({d.url}) |")
        parts.append("")
        return "\n".join(parts)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", default=str(ROOT / "manual" / "manifest.yaml"))
    ap.add_argument("--out", default=None, help="PDF path, or a directory for the manifest's output name")
    ap.add_argument("--md-only", action="store_true")
    ap.add_argument("--date", default=None, help="override the manifest's date")
    args = ap.parse_args()
    manifest = yaml.safe_load(pathlib.Path(args.manifest).read_text())
    date = args.date or manifest.get("date", "auto")
    if date in (None, "auto"):
        date = datetime.date.today().isoformat()
    if FILES.exists():
        shutil.rmtree(FILES)
    OUT.mkdir(parents=True, exist_ok=True)
    man = Manual(manifest)
    md = man.assemble(str(date))
    md_path = OUT / "manual.md"
    md_path.write_text(md)
    n_docs = sum(len(d) for _, d in man.parts)
    log(f"{n_docs} documents in {len(man.parts)} parts, {man.footnotes} footnotes, {len(md) // 1024} KiB of Markdown -> {md_path.relative_to(ROOT)}")
    for miss in man.missing:
        log("missing:", miss)
    if args.md_only:
        return 1 if man.missing else 0
    name = manifest.get("output", "manual-{date}.pdf").format(date=date)
    out = pathlib.Path(args.out) if args.out else OUT / name
    if args.out and (out.is_dir() or str(args.out).endswith("/")):
        out.mkdir(parents=True, exist_ok=True)
        out = out / name
    typ = OUT / "manual.typ"
    pandoc = ["pandoc", str(md_path), "-s", "-f", "markdown+autolink_bare_uris+pipe_tables+inline_notes+implicit_figures",
              "-t", "typst", "--toc", "--toc-depth=2", "-V", "papersize=a4", "-V", "fontsize=10pt",
              "--include-in-header", str(ROOT / "manual" / "header.typ"), "-o", str(typ)]
    log(" ".join(pandoc[:3]), "...")
    subprocess.run(pandoc, check=True, cwd=OUT)
    typst = ["typst", "compile", "--root", str(OUT), str(typ), str(out.resolve())]
    log(" ".join(typst))
    subprocess.run(typst, check=True, cwd=OUT)
    pages = len(re.findall(rb"/Type\s*/Page[^s]", out.read_bytes()))
    log(f"wrote {out} ({out.stat().st_size // 1024} KiB, about {pages} pages)")
    return 1 if man.missing else 0


if __name__ == "__main__":
    sys.exit(main())
