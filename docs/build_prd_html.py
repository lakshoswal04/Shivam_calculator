#!/usr/bin/env python3
"""Render docs/PRD.md into a styled, static single-page HTML document.

Static by design: mermaid blocks and all prose are present in the initial
markup, so the page is complete the moment it loads.

Design plan
  Color   paper #FAFAFB · ink #15181F · rule #E1E5EC · accent #33417E (flat indigo)
          semantics pass #1D6F4C · warn #96650B · block #A32B22 · review #7040A8
  Type    Archivo (headings/UI) · Source Serif 4 (prose) · IBM Plex Mono (IDs, citations)
  Layout  fixed sidebar TOC with scroll-spy; 72ch prose column; tables and
          diagrams break wider into their own scroll containers; requirement
          blocks are flat objects keyed by a priority-coloured left rule.
"""
import html
import re
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "PRD.md"
OUT = ROOT / "prd.html"

TOC_GROUPS = [
    ("Foundation", range(1, 7)), ("Users", range(7, 10)), ("Product", range(10, 13)),
    ("Engines", range(13, 20)), ("Platform", range(20, 25)), ("Assurance", range(25, 29)),
    ("Experience", range(29, 32)), ("Delivery", range(32, 48)),
]

CSS = """
:root{
  --paper:#FAFAFB; --surface:#FFFFFF; --surface-2:#F3F5F8;
  --ink:#15181F; --ink-2:#39404E; --muted:#5A6373; --faint:#8B93A2;
  --rule:#E1E5EC; --rule-strong:#C9D0DA;
  --accent:#33417E; --accent-soft:#EDF0FA;
  --pass:#1D6F4C; --pass-bg:#E7F3ED;
  --warn:#96650B; --warn-bg:#FBF1DE;
  --block:#A32B22; --block-bg:#FBEAE8;
  --review:#7040A8; --review-bg:#F2EBFA;
  --na:#6B7280; --na-bg:#EEF0F3;
  --shadow:0 1px 2px rgba(21,24,31,.05);
  --sans:"Archivo",-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
  --serif:"Source Serif 4",Georgia,"Times New Roman",serif;
  --mono:"IBM Plex Mono",ui-monospace,SFMono-Regular,Menlo,monospace;
}
@media (prefers-color-scheme:dark){
  :root:not([data-theme="light"]){
    --paper:#0F1218; --surface:#161A22; --surface-2:#1C212B;
    --ink:#E4E8F0; --ink-2:#BFC7D4; --muted:#98A1B0; --faint:#6E7787;
    --rule:#262C36; --rule-strong:#39414F;
    --accent:#8C9BE0; --accent-soft:#1B2135;
    --pass:#56B589; --pass-bg:#12241C;
    --warn:#DCA63C; --warn-bg:#2A2114;
    --block:#EF7B70; --block-bg:#2C1917;
    --review:#A992F0; --review-bg:#221B33;
    --na:#8B93A2; --na-bg:#1E222A;
    --shadow:0 1px 2px rgba(0,0,0,.4);
  }
}
:root[data-theme="dark"]{
  --paper:#0F1218; --surface:#161A22; --surface-2:#1C212B;
  --ink:#E4E8F0; --ink-2:#BFC7D4; --muted:#98A1B0; --faint:#6E7787;
  --rule:#262C36; --rule-strong:#39414F;
  --accent:#8C9BE0; --accent-soft:#1B2135;
  --pass:#56B589; --pass-bg:#12241C;
  --warn:#DCA63C; --warn-bg:#2A2114;
  --block:#EF7B70; --block-bg:#2C1917;
  --review:#A992F0; --review-bg:#221B33;
  --na:#8B93A2; --na-bg:#1E222A;
  --shadow:0 1px 2px rgba(0,0,0,.4);
}

*{box-sizing:border-box}
body{background:var(--paper);color:var(--ink);font-family:var(--serif);
  font-size:16.5px;line-height:1.68;-webkit-font-smoothing:antialiased}
::selection{background:var(--accent-soft);color:var(--ink)}

/* ---------------------------------------------------------------- shell */
.shell{display:grid;grid-template-columns:274px minmax(0,1fr);gap:0;
  max-width:1440px;margin:0 auto;align-items:start}

/* ------------------------------------------------------------- sidebar */
.side{position:sticky;top:0;height:100vh;overflow-y:auto;padding:26px 18px 40px;
  border-right:1px solid var(--rule);background:var(--surface)}
.brand{font-family:var(--sans);font-weight:700;font-size:14px;letter-spacing:-.01em;
  line-height:1.35;color:var(--ink);margin-bottom:3px}
.brand-sub{font-family:var(--mono);font-size:10.5px;letter-spacing:.06em;
  text-transform:uppercase;color:var(--faint);margin-bottom:20px}
.toc-group{font-family:var(--mono);font-size:10px;letter-spacing:.1em;
  text-transform:uppercase;color:var(--faint);margin:18px 0 7px;padding-left:8px}
.toc a{display:flex;gap:9px;align-items:baseline;padding:4px 8px;border-radius:4px;
  color:var(--muted);text-decoration:none;font-family:var(--sans);font-size:12.9px;
  line-height:1.35;transition:background .12s,color .12s}
.toc a:hover{background:var(--surface-2);color:var(--ink)}
.toc a.on{background:var(--accent-soft);color:var(--accent);font-weight:600}
.toc a .n{font-family:var(--mono);font-size:10.5px;color:var(--faint);
  min-width:17px;text-align:right;font-variant-numeric:tabular-nums}
.toc a.on .n{color:var(--accent)}

/* ---------------------------------------------------------------- main */
main{padding:0 clamp(20px,4vw,64px) 120px;min-width:0}
.masthead{padding:64px 0 34px;border-bottom:2px solid var(--ink)}
.eyebrow{font-family:var(--mono);font-size:11px;letter-spacing:.14em;
  text-transform:uppercase;color:var(--accent);margin-bottom:14px}
h1.doc-title{font-family:var(--sans);font-weight:700;font-size:clamp(30px,4.4vw,46px);
  line-height:1.08;letter-spacing:-.025em;margin:0 0 12px;text-wrap:balance;max-width:19ch}
.doc-sub{font-size:18px;color:var(--muted);max-width:60ch;margin:0}

.prose{max-width:74ch}
.prose.wide{max-width:none}

h1{font-family:var(--sans);font-weight:700;font-size:26px;letter-spacing:-.02em;
  line-height:1.2;margin:66px 0 18px;padding-top:20px;border-top:1px solid var(--rule);
  scroll-margin-top:22px;text-wrap:balance}
h1 .secnum{font-family:var(--mono);font-size:13px;font-weight:500;color:var(--accent);
  display:block;margin-bottom:7px;letter-spacing:.04em;font-variant-numeric:tabular-nums}
h2{font-family:var(--sans);font-weight:650;font-size:19px;letter-spacing:-.012em;
  margin:38px 0 12px;scroll-margin-top:22px}
h3{font-family:var(--sans);font-weight:650;font-size:16px;margin:28px 0 10px}
h4{font-family:var(--sans);font-weight:650;font-size:15px;margin:24px 0 8px}
p{margin:0 0 15px}
strong{font-weight:600;color:var(--ink)}
em{color:var(--ink-2)}
a{color:var(--accent);text-decoration:underline;text-underline-offset:2.5px;
  text-decoration-thickness:1px;text-decoration-color:color-mix(in srgb,var(--accent) 35%,transparent)}
a:hover{text-decoration-color:var(--accent)}
ul,ol{margin:0 0 15px;padding-left:22px}
li{margin-bottom:6px}
li::marker{color:var(--faint)}
hr{border:0;border-top:1px solid var(--rule);margin:44px 0}

blockquote{margin:20px 0;padding:15px 20px;background:var(--surface-2);
  border-left:3px solid var(--accent);border-radius:0 5px 5px 0;color:var(--ink-2)}
blockquote p:last-child{margin-bottom:0}
blockquote strong{color:var(--ink)}

code{font-family:var(--mono);font-size:.855em;background:var(--surface-2);
  padding:1.5px 5px;border-radius:3.5px;color:var(--ink-2);
  border:1px solid var(--rule);white-space:nowrap}
pre{background:var(--surface-2);border:1px solid var(--rule);border-radius:7px;
  padding:16px 18px;overflow-x:auto;margin:20px 0;line-height:1.55}
pre code{background:none;border:0;padding:0;font-size:12.6px;white-space:pre;color:var(--ink-2)}

/* -------------------------------------------------------------- tables */
.tw{overflow-x:auto;margin:20px 0;border:1px solid var(--rule);border-radius:7px;
  background:var(--surface)}
table{border-collapse:collapse;width:100%;font-family:var(--sans);font-size:13.4px;
  line-height:1.5}
th{text-align:left;font-weight:650;color:var(--ink);background:var(--surface-2);
  padding:10px 14px;border-bottom:1px solid var(--rule-strong);white-space:nowrap;
  font-size:11.6px;letter-spacing:.045em;text-transform:uppercase}
td{padding:10px 14px;border-bottom:1px solid var(--rule);color:var(--ink-2);
  vertical-align:top}
tr:last-child td{border-bottom:0}
td strong{color:var(--ink)}
td code{white-space:normal}
tbody tr:hover td{background:var(--surface-2)}

/* ------------------------------------------------------- requirement blocks */
.req{margin:26px 0;background:var(--surface);border:1px solid var(--rule);
  border-left:3px solid var(--rule-strong);border-radius:0 7px 7px 0;padding:16px 20px 6px;
  box-shadow:var(--shadow)}
.req[data-p="MUST"]{border-left-color:var(--block)}
.req[data-p="SHOULD"]{border-left-color:var(--warn)}
.req[data-p="COULD"]{border-left-color:var(--na)}
.req-head{display:flex;flex-wrap:wrap;gap:10px;align-items:baseline;margin-bottom:12px}
.req-id{font-family:var(--mono);font-size:12px;font-weight:600;color:var(--accent);
  letter-spacing:.02em}
.req-title{font-family:var(--sans);font-weight:650;font-size:15.5px;color:var(--ink);
  flex:1;min-width:200px}
.req .tw{margin:0 0 14px;border:0;border-radius:0;background:none}
.req table{font-size:13.2px}
.req th{display:none}
.req td:first-child{width:150px;white-space:nowrap;font-weight:600;color:var(--muted);
  font-size:11.6px;letter-spacing:.045em;text-transform:uppercase;
  font-family:var(--sans);padding-left:0;border-bottom-color:var(--rule)}
.req td:first-child strong{color:var(--muted);font-weight:600}
.req td:last-child{padding-right:0}
.req tbody tr:hover td{background:none}
.req>p{font-size:15px;color:var(--ink-2);margin-bottom:12px}

/* --------------------------------------------------------------- chips */
.chip{display:inline-flex;align-items:center;gap:5px;font-family:var(--mono);
  font-size:10.5px;font-weight:600;letter-spacing:.07em;padding:3px 8px;
  border-radius:4px;border:1px solid transparent;white-space:nowrap;text-transform:uppercase}
.chip::before{content:"";width:5px;height:5px;border-radius:50%;background:currentColor}
.chip-MUST{color:var(--block);background:var(--block-bg);border-color:color-mix(in srgb,var(--block) 25%,transparent)}
.chip-SHOULD{color:var(--warn);background:var(--warn-bg);border-color:color-mix(in srgb,var(--warn) 25%,transparent)}
.chip-COULD{color:var(--na);background:var(--na-bg);border-color:color-mix(in srgb,var(--na) 25%,transparent)}
.chip-WONT{color:var(--na);background:var(--na-bg);border-color:color-mix(in srgb,var(--na) 25%,transparent)}
.st{font-family:var(--mono);font-size:.82em;font-weight:600;padding:1.5px 6px;
  border-radius:3.5px;border:1px solid transparent;white-space:nowrap}
.st-PASS{color:var(--pass);background:var(--pass-bg);border-color:color-mix(in srgb,var(--pass) 22%,transparent)}
.st-WARNING{color:var(--warn);background:var(--warn-bg);border-color:color-mix(in srgb,var(--warn) 22%,transparent)}
.st-BLOCK{color:var(--block);background:var(--block-bg);border-color:color-mix(in srgb,var(--block) 22%,transparent)}
.st-REVIEW_REQUIRED{color:var(--review);background:var(--review-bg);border-color:color-mix(in srgb,var(--review) 22%,transparent)}
.st-NOT_APPLICABLE{color:var(--na);background:var(--na-bg);border-color:color-mix(in srgb,var(--na) 22%,transparent)}

/* ------------------------------------------------------------- mermaid */
pre.mermaid{background:var(--surface);border:1px solid var(--rule);border-radius:7px;
  padding:22px;text-align:center;overflow-x:auto;margin:24px 0}

/* ------------------------------------------------------------ built tag */
.built{display:inline-flex;align-items:center;gap:6px;font-family:var(--mono);
  font-size:10.5px;font-weight:600;letter-spacing:.06em;color:var(--pass);
  background:var(--pass-bg);border:1px solid color-mix(in srgb,var(--pass) 25%,transparent);
  padding:3px 8px;border-radius:4px;text-transform:uppercase}

:focus-visible{outline:2px solid var(--accent);outline-offset:2px;border-radius:3px}
@media (prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}

@media (max-width:1000px){
  .shell{grid-template-columns:1fr}
  .side{position:static;height:auto;max-height:none;border-right:0;
    border-bottom:1px solid var(--rule)}
  .toc{columns:2;column-gap:20px}
  .toc-group{break-inside:avoid}
  main{padding:0 20px 80px}
  .req td:first-child{width:auto;display:block;padding-bottom:2px;border-bottom:0}
  .req td:last-child{display:block;padding-top:0;padding-left:0}
}
"""

JS = """
const links=[...document.querySelectorAll('.toc a')];
const map=new Map(links.map(a=>[a.getAttribute('href').slice(1),a]));
const seen=new Set();
const io=new IntersectionObserver(es=>{
  es.forEach(e=>{ e.isIntersecting?seen.add(e.target.id):seen.delete(e.target.id); });
  const first=[...document.querySelectorAll('main h1[id]')].find(h=>seen.has(h.id));
  if(first){ links.forEach(a=>a.classList.remove('on')); map.get(first.id)?.classList.add('on');
    const on=map.get(first.id);
    if(on&&window.innerWidth>1000){const s=document.querySelector('.side');
      const r=on.getBoundingClientRect(),sr=s.getBoundingClientRect();
      if(r.top<sr.top+40||r.bottom>sr.bottom-40)on.scrollIntoView({block:'center'});}}
},{rootMargin:'-10% 0px -70% 0px'});
document.querySelectorAll('main h1[id]').forEach(h=>io.observe(h));
"""


def slug(text):
    s = re.sub(r"[^\w\s-]", "", text.lower()).strip()
    return re.sub(r"[\s_]+", "-", s)


def build():
    md = SRC.read_text(encoding="utf-8")

    # Strip the markdown-only TOC block; the sidebar replaces it.
    md = re.sub(r"## Table of contents.*?(?=\n---\n)", "", md, flags=re.S)

    # Pull the masthead out of the markdown so it can be styled as a masthead.
    md = re.sub(r"^# Product Requirements Document\n## .*?\n", "", md, flags=re.M)

    body = markdown.markdown(
        md, extensions=["tables", "fenced_code", "sane_lists", "attr_list"])

    # ```mermaid fences -> native artifact mermaid blocks (entities restored).
    def mermaid(m):
        return '<pre class="mermaid">' + html.unescape(m.group(1)) + "</pre>"
    body = re.sub(r'<pre><code class="language-mermaid">(.*?)</code></pre>',
                  mermaid, body, flags=re.S)

    # Number and id the 47 top-level sections; collect them for the sidebar.
    sections = []

    def h1(m):
        raw = m.group(1)
        num = re.match(r"(\d+)\.\s+(.*)", raw)
        if num:
            n, title = num.group(1), num.group(2)
            sid = f"s{n}"
            sections.append((int(n), title, sid))
            return (f'<h1 id="{sid}"><span class="secnum">Section {n}</span>'
                    f'{title}</h1>')
        sid = slug(re.sub("<[^>]+>", "", raw))
        sections.append((None, raw, sid))
        return f'<h1 id="{sid}">{raw}</h1>'
    body = re.sub(r"<h1>(.*?)</h1>", h1, body, flags=re.S)

    # Wrap tables so wide content scrolls inside its own container.
    body = re.sub(r"<table>", '<div class="tw"><table>', body)
    body = re.sub(r"</table>", "</table></div>", body)

    # Requirement blocks: h4 "FR-xxx-nnn — Title `PRIORITY`" plus what follows,
    # up to the next heading or rule, becomes one object keyed by priority.
    parts = re.split(r'(<h4>FR-[A-Z]+-\d+.*?</h4>)', body, flags=re.S)
    out = [parts[0]]
    i = 1
    while i < len(parts):
        head, rest = parts[i], parts[i + 1] if i + 1 < len(parts) else ""
        inner = re.sub(r"</?h4>", "", head)
        pri_m = re.search(r"<code>(MUST|SHOULD|COULD|WON'T)</code>", inner)
        pri = pri_m.group(1) if pri_m else ""
        inner = re.sub(r"\s*<code>(MUST|SHOULD|COULD|WON'T)</code>\s*$", "", inner)
        id_m = re.match(r"(FR-[A-Z]+-\d+)\s*[—-]\s*(.*)", inner)
        rid, title = (id_m.group(1), id_m.group(2)) if id_m else ("", inner)

        cut = re.search(r'(<h[1-4][ >]|<hr\s*/?>)', rest)
        block, tail = (rest[:cut.start()], rest[cut.start():]) if cut else (rest, "")
        pri_cls = pri.replace("'", "").replace("WONT", "WONT")
        chip = ('<span class="chip chip-' + pri_cls + '">' + pri + "</span>") if pri else ""
        out.append(
            f'<section class="req" data-p="{pri}">'
            f'<div class="req-head"><span class="req-id">{rid}</span>'
            f'<span class="req-title">{title}</span>{chip}</div>{block}</section>{tail}')
        i += 2
    body = "".join(out)

    # Status vocabulary reads as status, not as generic code.
    for st in ("REVIEW_REQUIRED", "NOT_APPLICABLE", "WARNING", "BLOCK", "PASS"):
        body = body.replace(f"<code>{st}</code>", f'<span class="st st-{st}">{st}</span>')
    body = body.replace("<strong>Built</strong>", '<span class="built">Built</span>')

    # Sidebar
    named = {n: (t, sid) for n, t, sid in sections if n}
    extra = [(t, sid) for n, t, sid in sections if not n]
    toc = []
    for label, rng in TOC_GROUPS:
        rows = [f'<a href="#{named[n][1]}"><span class="n">{n}</span>'
                f'<span>{named[n][0]}</span></a>' for n in rng if n in named]
        if rows:
            toc.append(f'<div class="toc-group">{label}</div>' + "".join(rows))
    if extra:
        toc.append('<div class="toc-group">Appendices</div>' + "".join(
            f'<a href="#{sid}"><span class="n">·</span><span>'
            f'{re.sub("^Appendix ", "", t).split(" — ")[0]}</span></a>' for t, sid in extra))

    page = f"""<title>Share Issue Compliance PRD</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Archivo:wght@400;500;600;700&family=Source+Serif+4:ital,opsz,wght@0,8..60,400;0,8..60,600;1,8..60,400&family=IBM+Plex+Mono:wght@400;500;600&display=swap">
<style>{CSS}</style>
<div class="shell">
<aside class="side">
  <div class="brand">Corporate Securities Issue<br>Assessment &amp; Compliance Platform</div>
  <div class="brand-sub">PRD v1.0 · 2026-09-07</div>
  <nav class="toc">{''.join(toc)}</nav>
</aside>
<main>
  <header class="masthead">
    <div class="eyebrow">Product Requirements Document · v1.0</div>
    <h1 class="doc-title">Corporate Securities Issue Assessment, Compliance &amp; Calculation Platform</h1>
    <p class="doc-sub">Next.js · FastAPI · PostgreSQL — for Indian companies issuing additional
    shares and securities under MCA, Companies Act 2013, SEBI, NSE and BSE requirements.</p>
  </header>
  <div class="prose wide">{body}</div>
</main>
</div>
<script>{JS}</script>
"""
    OUT.write_text(page, encoding="utf-8")
    print(f"wrote {OUT}  ({len(page):,} bytes)")
    print(f"sections: {len([s for s in sections if s[0]])} numbered + {len(extra)} appendices")
    n_req = page.count('class="req"')
    n_mmd = page.count('class="mermaid"')
    print("requirement blocks: %d" % n_req)
    print("mermaid diagrams: %d" % n_mmd)


if __name__ == "__main__":
    build()
