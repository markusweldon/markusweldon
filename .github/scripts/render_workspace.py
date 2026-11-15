#!/usr/bin/env python3
"""Render the README's Workspace images in the markusweldon.com style.

Writes images/workspace-vscode.png and images/workspace-warp.png: VS Code
with SynthWave '84 syntax colours, and Warp running neofetch over the
header's scene. Both use the site's palette and Geist Mono and sit in a
rounded window with a pink neon edge. They are rendered recreations of
Markus's own setup (the file and neofetch readout come from his
screenshots), not screen captures.

Usage:
    pip install fonttools brotli pygments pillow
    npm pack @fontsource/orbitron@5.0.19 geist@1.3.1   (extract both)
    python3 .github/scripts/render_workspace.py <folder-with-the-extracted-packages>
Needs Node with Playwright and Chromium.
"""

import html
import subprocess
import sys
import tempfile
from pathlib import Path

from pygments.lexers import JavascriptLexer
from pygments.token import Comment, Keyword, Name, Number, Operator, Punctuation, String

sys.path.insert(0, str(Path(__file__).parent))
import build_images as bi  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SCALE = 1.5  # device pixel ratio of the output PNGs

# ── VS Code: routes/index.js from Snyk's nodejs-goof demo app ───────────────
CODE = """var utils = require('../utils');
var mongoose = require('mongoose');
var Todo = mongoose.model('Todo');
var User = mongoose.model('User');
// TODO:
var hms = require('humanize-ms');
var ms = require('ms');
var streamBuffers = require('stream-buffers');
var readline = require('readline');
var moment = require('moment');
var exec = require('child_process').exec;
var validator = require('validator');

// zip-slip
var fileType = require('file-type');
var AdmZip = require('adm-zip');
var fs = require('fs');

// prototype-pollution
var _ = require('lodash');

exports.index = function (req, res, next) {
  Todo.
    find({}).
    sort('-updated_at').
    exec(function (err, todos) {
      if (err) return next(err);

      res.render('index', {
        title: 'Markus TODO',
        subhead: 'Vulnerabilities at their best',
        todos: todos,
      });
    });
};

exports.loginHandler = function (req, res, next) {
  if (validator.isEmail(req.body.username)) {
    User.find({ username: req.body.username, password: req.body.password }, function (err, users) {
      if (users.length > 0) {
        const redirectPage = req.body.redirectPage
        const session = req.session"""

# Lines Snyk Code flags in this file: command injection, zip slip, prototype
# pollution, NoSQL injection.
FLAGGED = {11, 16, 20, 39}
CURRENT_LINE = 22

TREE = [  # (depth, name, kind, decoration)
    (0, "OPEN EDITORS", "section", ""),
    (1, "index.js  routes", "js-open", "9+"),
    (0, "NODEJS-GOOF", "section", ""),
    (1, ".github", "dir", ""), (1, "entity", "dir", ""), (1, "exploits", "dir", ""),
    (1, "node_modules", "dir-dim", ""), (1, "public", "dir", ""), (1, "routes", "dir-open", "dot"),
    (2, "index.js", "js-active", "9+"), (2, "users.js", "js", ""),
    (1, "service", "dir", ""), (1, "tests", "dir", ""), (1, "views", "dir", ""),
    (1, ".gitignore", "file", ""), (1, "app.js", "js", "5"), (1, "app.json", "json", ""),
    (1, "docker-compose.yml", "file", ""), (1, "Dockerfile", "file", ""),
    (1, "mongoose-db.js", "js", "1"), (1, "mySBOM.json", "json", "U"),
    (1, "package.json", "json", "9+"), (1, "README.md", "file", ""),
    (1, "snyk-report.html", "file", "U"), (1, "snyk_results.json", "json", "U"),
    (1, "typeorm-db.js", "js", "1"), (1, "utils.js", "js", "1"),
]

SYNTH = {  # SynthWave '84 token colours
    "keyword": "#fede5d", "string": "#ff8b39", "call": "#36f9f6", "name": "#ff7edb",
    "prop": "#ffffff", "comment": "#848bbd", "number": "#f97e72", "punct": "#bbbbbb",
}


def svg_icon(name: str, size: float, width: float) -> str:
    """A lucide icon as inline HTML <svg>, coloured by the surrounding text."""
    return (f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}">'
            f'{bi.icon(name, 0, 0, size, "currentColor", width)}</svg>')


def classify(tokens):
    """Pygments tokens -> (css class, text), marking calls and properties."""
    out = []
    for i, (kind, text) in enumerate(tokens):
        nxt = next((t for k, t in tokens[i + 1:] if t.strip()), "")
        prev = next((t for k, t in reversed(tokens[:i]) if t.strip()), "")
        if kind in Comment:
            cls = "comment"
        elif kind in Keyword:
            cls = "keyword"
        elif kind in String:
            cls = "string"
        elif kind in Number:
            cls = "number"
        elif kind in Name:
            cls = "call" if nxt.startswith("(") else "prop" if prev == "." else "name"
        elif kind in (Punctuation, Operator):
            cls = "punct"
        else:
            cls = ""
        out.append((cls, text))
    return out


def code_lines():
    lexer = JavascriptLexer()
    lines = []
    for line in CODE.split("\n"):
        toks = [(k, t) for k, t in lexer.get_tokens(line) if t != "\n"]
        lines.append(classify(toks))
    return lines


def vscode_html(f_mono: str) -> str:
    lines = code_lines()
    gutter, code, mini = [], [], []
    for n, toks in enumerate(lines, 1):
        cur = " cur" if n == CURRENT_LINE else ""
        gutter.append(f'<div class="ln{cur}">{n}</div>')
        spans = "".join(f'<span class="{c}">{html.escape(t)}</span>' if c else html.escape(t) for c, t in toks)
        flag = " flag" if n in FLAGGED else ""
        code.append(f'<div class="cl{cur}{flag}">{spans or "&nbsp;"}</div>')
        bars, x = [], 0
        for c, t in toks:
            w = len(t)
            if t.strip():
                bars.append(f'<i style="left:{x * 1.1:.1f}px;width:{w * 1.1:.1f}px;background:{SYNTH.get(c, "#bbb")}"></i>')
            x += w
        mini.append(f'<div class="mrow">{"".join(bars)}</div>')

    tree = []
    for depth, name, kind, deco in TREE:
        if kind == "section":
            tree.append(f'<div class="sec">⌄ {name}</div>')
            continue
        icon = {"js": "JS", "js-open": "JS", "js-active": "JS", "json": "{}", "file": "≡"}.get(kind, "›")
        icls = "js" if kind.startswith("js") else "json" if kind == "json" else "dir" if kind.startswith("dir") else "file"
        if kind == "dir-open":
            icon = "⌄"
        rcls = " active" if kind == "js-active" else " dim" if kind == "dir-dim" else ""
        dcls = "u" if deco == "U" else "m"
        badge = '<b class="dot"></b>' if deco == "dot" else f'<b class="{dcls}">{deco}</b>' if deco else ""
        tree.append(f'<div class="row{rcls}" style="padding-left:{8 + depth * 12}px"><span class="ic {icls}">{icon}</span>'
                    f'<span class="nm {dcls if deco else ""}">{html.escape(name)}</span>{badge}</div>')

    icons = "".join(f'<div class="ai{" on" if i == 0 else ""}">{svg_icon(n, 22, 1.6)}</div>'
                    for i, n in enumerate(["files", "search", "git", "play", "blocks", "shield"]))
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
@font-face{{font-family:GeistMono;src:url("file://{f_mono}")}}
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{background:transparent}}
body{{padding:44px;font-family:GeistMono,monospace;color:#d8c8f0}}
.win{{width:980px;height:620px;border-radius:14px;overflow:hidden;background:#0d0015;display:flex;flex-direction:column;
  border:1px solid rgba(249,42,173,.45);box-shadow:0 0 0 1px rgba(54,249,246,.06),0 0 34px rgba(249,42,173,.32),0 0 90px rgba(123,47,255,.22)}}
.title{{height:36px;display:flex;align-items:center;padding:0 14px;background:#0a0011;border-bottom:1px solid #2a0f4d;gap:8px}}
.tl{{width:12px;height:12px;border-radius:50%}}
.cc{{margin:0 auto;width:330px;height:22px;border-radius:6px;border:1px solid #3a1a5e;background:#130022;color:#a78bca;font-size:12px;
  display:flex;align-items:center;justify-content:center;gap:6px}}
.main{{flex:1;display:flex;min-height:0}}
.act{{width:46px;background:#0a0011;border-right:1px solid #2a0f4d;padding-top:6px}}
.ai{{height:44px;display:flex;align-items:center;justify-content:center;color:#6e4f8e}}
.ai.on{{color:#f92aad;border-left:2px solid #f92aad;filter:drop-shadow(0 0 4px rgba(249,42,173,.7))}}
.side{{width:228px;background:#130022;border-right:1px solid #2a0f4d;font-size:12px;overflow:hidden}}
.side h4{{font-size:11px;letter-spacing:.08em;color:#a78bca;padding:10px 14px 6px;font-weight:500}}
.sec{{font-size:11px;font-weight:700;color:#d8c8f0;padding:4px 10px;letter-spacing:.04em}}
.row{{height:22px;display:flex;align-items:center;gap:6px;color:#c9b6e6;white-space:nowrap}}
.row.active{{background:rgba(249,42,173,.16);box-shadow:inset 2px 0 0 #f92aad;color:#fff}}
.row.dim{{opacity:.55}}
.ic{{width:16px;text-align:center;font-size:10px;font-weight:700}}
.ic.js{{color:#fede5d}} .ic.json{{color:#fede5d}} .ic.dir{{color:#a78bca;font-size:13px}} .ic.file{{color:#a78bca}}
.nm{{flex:1}} .nm.m{{color:#ff7edb}} .nm.u{{color:#36f9f6}}
.row b{{font-weight:500;font-size:11px;margin-right:12px}} .row b.m{{color:#ff7edb}} .row b.u{{color:#36f9f6}}
.row b.dot{{width:6px;height:6px;border-radius:50%;background:#ff7edb}}
.ed{{flex:1;display:flex;flex-direction:column;min-width:0}}
.tabs{{height:35px;background:#0a0011;display:flex;border-bottom:1px solid #2a0f4d}}
.tab{{display:flex;align-items:center;gap:8px;padding:0 14px;font-size:12.5px;background:#0d0015;color:#fff;
  border-top:2px solid #f92aad;border-right:1px solid #2a0f4d}}
.tab .js{{color:#fede5d;font-weight:700;font-size:10px}} .tab .cnt{{color:#ff7edb}}
.crumbs{{height:24px;font-size:12px;color:#a78bca;display:flex;align-items:center;padding-left:18px;gap:6px}}
.body{{flex:1;display:flex;min-height:0;font-size:13px;line-height:20px}}
.gut{{width:48px;text-align:right;padding-right:14px;color:#4e3a6e}}
.ln.cur{{color:#fff}}
.code{{flex:1;white-space:pre;overflow:hidden}}
.cl.cur{{background:rgba(249,42,173,.08);box-shadow:inset 0 1px 0 rgba(249,42,173,.18),inset 0 -1px 0 rgba(249,42,173,.18)}}
.cl.flag{{text-decoration:underline wavy rgba(255,64,129,.95);text-decoration-thickness:1px;text-underline-offset:4px}}
.keyword{{color:{SYNTH['keyword']};text-shadow:0 0 2px #100c0f,0 0 5px rgba(220,120,110,.55),0 0 10px rgba(254,222,93,.25)}}
.string{{color:{SYNTH['string']}}}
.call{{color:{SYNTH['call']};text-shadow:0 0 2px #001716,0 0 5px rgba(54,249,246,.6),0 0 10px rgba(54,249,246,.3)}}
.name{{color:{SYNTH['name']};text-shadow:0 0 2px #100c0f,0 0 5px rgba(255,126,219,.55),0 0 10px rgba(255,126,219,.25)}}
.prop{{color:#fff}} .comment{{color:{SYNTH['comment']};font-style:italic}} .number{{color:{SYNTH['number']}}} .punct{{color:#bbbbbb}}
.mini{{width:80px;padding-top:4px;border-left:1px solid #1c0033;position:relative}}
.mini .view{{position:absolute;left:0;right:0;top:2px;height:150px;background:rgba(167,139,202,.08)}}
.mrow{{height:3px;position:relative;margin-left:8px}}
.mrow i{{position:absolute;top:0;height:2px;opacity:.75}}
.status{{height:24px;display:flex;align-items:center;gap:16px;padding:0 12px;font-size:11.5px;color:#fff;
  background:linear-gradient(90deg,#f92aad,#b01fff 55%,#7b2fff)}}
.status .r{{margin-left:auto;display:flex;gap:16px}}
</style></head><body><div class="win">
<div class="title"><span class="tl" style="background:#ff5f57"></span><span class="tl" style="background:#febc2e"></span>
<span class="tl" style="background:#28c840"></span><div class="cc">⌕ nodejs-goof</div></div>
<div class="main"><div class="act">{icons}</div>
<div class="side"><h4>EXPLORER</h4>{"".join(tree)}</div>
<div class="ed"><div class="tabs"><div class="tab"><span class="js">JS</span>index.js <span class="cnt">9+</span> ×</div></div>
<div class="crumbs">routes › <span style="color:#fede5d;font-size:10px;font-weight:700">JS</span> index.js › index</div>
<div class="body"><div class="gut">{"".join(gutter)}</div><div class="code">{"".join(code)}</div>
<div class="mini"><div class="view"></div>{"".join(mini)}</div></div></div></div>
<div class="status"><span>⑂ main*</span><span>⊗ 57 ⚠ 68 ⓘ 16</span><span>Snyk Security</span>
<div class="r"><span>Ln 22, Col 30</span><span>Spaces: 2</span><span>UTF-8</span><span>JavaScript</span><span>Prettier</span></div></div>
</div></body></html>"""


# ── Warp: neofetch, as in Markus's screenshot ───────────────────────────────
APPLE = """                    'c.
                 ,xNMM.
               .OMMMMo
               OMMM0,
     .;loddo:' loolloddol;.
   cKMMMMMMMMMMNWMMMMMMMMMM0:
 .KMMMMMMMMMMMMMMMMMMMMMMMWd.
 XMMMMMMMMMMMMMMMMMMMMMMMX.
;MMMMMMMMMMMMMMMMMMMMMMMM:
:MMMMMMMMMMMMMMMMMMMMMMMM:
.MMMMMMMMMMMMMMMMMMMMMMMMX.
 kMMMMMMMMMMMMMMMMMMMMMMMMWd.
 .XMMMMMMMMMMMMMMMMMMMMMMMMMMk
  .XMMMMMMMMMMMMMMMMMMMMMMMMK.
    kMMMMMMMMMMMMMMMMMMMMMMd
     ;KMMMMMMMWXXWMMMMMMMk.
       .cooc,.    .,coo:."""

INFO = [
    ("OS", "macOS 14.6.1 23G93 arm64"), ("Host", "Mac14,9"), ("Kernel", "23.6.0"),
    ("Uptime", "12 days, 20 hours, 55 mins"), ("Packages", "46 (brew)"), ("Shell", "zsh 5.9"),
    ("Resolution", "1800x1169"), ("DE", "Aqua"), ("WM", "Quartz Compositor"),
    ("WM Theme", "Blue (Dark)"), ("Terminal", "WarpTerminal"), ("CPU", "Apple M2 Pro"),
    ("GPU", "Apple M2 Pro"), ("Memory", "3027MiB / 16384MiB"),
]

# The Warp theme's 16 ANSI colours (also written to the theme file).
ANSI_NORMAL = ["#1c0033", "#ff4d7d", "#72f1b8", "#fede5d", "#7b2fff", "#f92aad", "#36f9f6", "#e8dcff"]
ANSI_BRIGHT = ["#6e4f8e", "#ff7a9c", "#9cf7d0", "#fff08a", "#a78bff", "#ff6ec7", "#8afcfa", "#ffffff"]


def warp_html(f_mono: str, scene: str) -> str:
    rows = APPLE.split("\n")
    ramp = ["#36f9f6", "#36f9f6", "#5fd3f5", "#5fd3f5", "#8aa8f8", "#a78bff", "#b01fff", "#b01fff",
            "#c94fd8", "#e03cc4", "#f92aad", "#f92aad", "#ff5fbf", "#ff6ec7", "#ff8fd4", "#ffa8de", "#ffc2e8"]
    logo = "\n".join(f'<span style="color:{ramp[i]}">{html.escape(r)}</span>' for i, r in enumerate(rows))
    info = ['<span class="u">markusweldon</span><span class="at">@</span><span class="u">Markuss-MacBook-Pro.local</span>',
            '<span class="dash">' + "-" * 37 + "</span>"]
    info += [f'<span class="k">{k}</span><span class="c">:</span> {html.escape(v)}' for k, v in INFO]
    sw = "".join(f'<i style="background:{c}"></i>' for c in ANSI_NORMAL)
    sw2 = "".join(f'<i style="background:{c}"></i>' for c in ANSI_BRIGHT)
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
@font-face{{font-family:GeistMono;src:url("file://{f_mono}")}}
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{background:transparent}}
body{{padding:44px;font-family:GeistMono,monospace;color:#e8dcff}}
.win{{width:980px;height:620px;border-radius:14px;overflow:hidden;position:relative;display:flex;flex-direction:column;
  border:1px solid rgba(249,42,173,.45);box-shadow:0 0 0 1px rgba(54,249,246,.06),0 0 34px rgba(249,42,173,.32),0 0 90px rgba(123,47,255,.22);
  background:#0d0015 url("file://{scene}") center 62%/cover no-repeat}}
.win:before{{content:"";position:absolute;inset:0;background:linear-gradient(180deg,rgba(13,0,21,.86) 0%,rgba(13,0,21,.72) 55%,rgba(13,0,21,.35) 100%)}}
.win>*{{position:relative}}
.bar{{height:42px;display:flex;align-items:center;gap:8px;padding:0 16px;border-bottom:1px solid rgba(249,42,173,.22);background:rgba(10,0,17,.6)}}
.tl{{width:12px;height:12px;border-radius:50%}}
.tabx{{margin-left:120px;width:240px;height:42px;display:flex;align-items:center;justify-content:center;font-size:13px;
  border-bottom:2px solid #f92aad;color:#fff;text-shadow:0 0 8px rgba(249,42,173,.7)}}
.plus{{margin-left:18px;color:#a78bca;font-size:18px}}
.ico{{margin-left:auto;display:flex;gap:16px;color:#a78bca}}
.block{{padding:16px 26px 0;flex:1}}
.meta{{font-size:12.5px;color:#a78bca;margin-bottom:6px}} .meta b{{color:#36f9f6;font-weight:400}}
.nf{{display:flex;gap:34px;font-size:14px;line-height:19.5px}}
pre{{font-family:inherit;font-weight:700;text-shadow:0 0 6px rgba(249,42,173,.35)}}
.info div{{white-space:pre}}
.u{{color:#36f9f6;font-weight:700;text-shadow:0 0 6px rgba(54,249,246,.5)}} .at{{color:#f92aad;font-weight:700}}
.dash{{color:#6e4f8e}} .k{{color:#f92aad;font-weight:700;text-shadow:0 0 6px rgba(249,42,173,.45)}} .c{{color:#f92aad}}
.sw{{display:flex;margin-top:10px}} .sw i{{width:30px;height:20px}}
.prompt{{padding:0 26px 18px;font-size:14px}}
.prompt .p{{color:#f92aad;font-weight:700}}
.input{{margin-top:8px;color:#8f78b3}}
.cur{{display:inline-block;width:9px;height:17px;background:#36f9f6;vertical-align:-3px;box-shadow:0 0 8px #36f9f6;margin-right:2px}}
</style></head><body><div class="win">
<div class="bar"><span class="tl" style="background:#ff5f57"></span><span class="tl" style="background:#febc2e"></span>
<span class="tl" style="background:#28c840"></span><div class="tabx">~</div><div class="plus">+</div>
<div class="ico">{svg_icon("search", 17, 1.8)}{svg_icon("sparkles", 17, 1.8)}{svg_icon("settings", 17, 1.8)}</div></div>
<div class="block"><div class="meta">~ <b>(0.348s)</b></div><div class="nf"><pre>{logo}</pre>
<div class="info">{"".join(f"<div>{x}</div>" for x in info)}<div class="sw">{sw}</div><div class="sw" style="margin-top:0">{sw2}</div></div></div></div>
<div class="prompt"><div class="p">~</div><div class="input"><span class="cur"></span>Try typing natural language instead of a command</div></div>
</div></body></html>"""


# Icons used above that build_images doesn't already carry (lucide, ISC licence).
bi.ICONS.update({
    "files": '<path d="M20 7h-3a2 2 0 0 1-2-2V2"/><path d="M9 18a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h7l4 4v10a2 2 0 0 1-2 2Z"/><path d="M3 7.6v12.8A1.6 1.6 0 0 0 4.6 22h9.8"/>',
    "sparkles": '<path d="M9.94 15.5A2 2 0 0 0 8.5 14.06l-6.13-1.58a.5.5 0 0 1 0-.96L8.5 9.94A2 2 0 0 0 9.94 8.5l1.58-6.13a.5.5 0 0 1 .96 0L14.06 8.5A2 2 0 0 0 15.5 9.94l6.13 1.58a.5.5 0 0 1 0 .96L15.5 14.06a2 2 0 0 0-1.44 1.44l-1.58 6.13a.5.5 0 0 1-.96 0z"/>',
    "search": '<circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>',
    "git": '<circle cx="18" cy="18" r="3"/><circle cx="6" cy="6" r="3"/><path d="M6 21V9a9 9 0 0 0 9 9"/>',
    "play": '<polygon points="6 3 20 12 6 21 6 3"/>',
    "blocks": '<rect width="7" height="7" x="14" y="3" rx="1"/><path d="M10 21V8a1 1 0 0 0-1-1H4a1 1 0 0 0-1 1v12a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-5a1 1 0 0 0-1-1H3"/>',
    "shield": '<path d="M20 13c0 5-3.5 7.5-7.66 8.95a1 1 0 0 1-.67-.01C7.5 20.5 4 18 4 13V6a1 1 0 0 1 1-1c2 0 4.5-1.2 6.24-2.72a1.17 1.17 0 0 1 1.52 0C14.51 3.81 17 5 19 5a1 1 0 0 1 1 1z"/>',
    "settings": '<path d="M12.22 2h-.44a2 2 0 0 0-2 2v.18a2 2 0 0 1-1 1.73l-.43.25a2 2 0 0 1-2 0l-.15-.08a2 2 0 0 0-2.73.73l-.22.38a2 2 0 0 0 .73 2.73l.15.1a2 2 0 0 1 1 1.72v.51a2 2 0 0 1-1 1.74l-.15.09a2 2 0 0 0-.73 2.73l.22.38a2 2 0 0 0 2.73.73l.15-.08a2 2 0 0 1 2 0l.43.25a2 2 0 0 1 1 1.73V20a2 2 0 0 0 2 2h.44a2 2 0 0 0 2-2v-.18a2 2 0 0 1 1-1.73l.43-.25a2 2 0 0 1 2 0l.15.08a2 2 0 0 0 2.73-.73l.22-.39a2 2 0 0 0-.73-2.73l-.15-.08a2 2 0 0 1-1-1.74v-.5a2 2 0 0 1 1-1.74l.15-.09a2 2 0 0 0 .73-2.73l-.22-.38a2 2 0 0 0-2.73-.73l-.15.08a2 2 0 0 1-2 0l-.43-.25a2 2 0 0 1-1-1.73V4a2 2 0 0 0-2-2z"/><circle cx="12" cy="12" r="3"/>',
})


SHOT_JS = """
const {chromium} = require('playwright');
(async () => {
  const [src, out, scale] = process.argv.slice(2);
  const b = await chromium.launch();
  const p = await b.newPage({viewport: {width: 1068, height: 708}, deviceScaleFactor: +scale});
  await p.goto('file://' + src);
  await p.waitForTimeout(600);
  await p.screenshot({path: out, omitBackground: true});
  await b.close();
})();
"""


def main(font_dir: Path) -> None:
    f = bi.Fonts(font_dir)
    mono = str(sorted(font_dir.rglob("GeistMono-Regular.woff2"))[0])
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        scene = tmp / "scene.svg"
        scene.write_text(bi.header(f, text=False))
        (tmp / "shot.js").write_text(SHOT_JS)
        for name, page in [("workspace-vscode", vscode_html(mono)), ("workspace-warp", warp_html(mono, str(scene)))]:
            src = tmp / f"{name}.html"
            src.write_text(page)
            raw = tmp / f"{name}.png"
            subprocess.run(["node", str(tmp / "shot.js"), str(src), str(raw), str(SCALE)], check=True)
            from PIL import Image
            img = Image.open(raw)
            img.save(ROOT / "images" / f"{name}.png", optimize=True)
            print(f"Wrote images/{name}.png ({(ROOT / 'images' / f'{name}.png').stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(Path(sys.argv[1]))
