"""Local review web app: edit listings, pick photos, generate post images.

    python webapp.py            # then open http://127.0.0.1:5000

Reads out/listings.json (from process.py), lets you per listing:
  - edit title / price / 原价 / condition / description
  - tick which photos to use and add a per-photo note
  - generate one merged tall image per listing into out/posts/, ready to send
    in the WeChat group.

Everything is local; nothing is uploaded anywhere.
"""

import argparse
import json
import os

from flask import Flask, abort, jsonify, request, send_file, send_from_directory

import compose

app = Flask(__name__)
app.config["BASE_DIR"] = "out"


def _listings_path():
    return os.path.join(app.config["BASE_DIR"], "listings.json")


def _load():
    with open(_listings_path(), encoding="utf-8") as fh:
        return json.load(fh)


def _save(listings):
    with open(_listings_path(), "w", encoding="utf-8") as fh:
        json.dump(listings, fh, ensure_ascii=False, indent=2)


@app.get("/")
def index():
    return PAGE


@app.get("/api/listings")
def api_listings():
    if not os.path.isfile(_listings_path()):
        return jsonify({"error": f"找不到 {_listings_path()}，请先跑 process.py"}), 404
    listings = _load()
    # Default selection = all images, if the seller hasn't chosen yet.
    for it in listings:
        if "selectedImages" not in it:
            it["selectedImages"] = list(it.get("images", []))
        it.setdefault("imageCaptions", {})
    return jsonify({"listings": listings})


@app.get("/img")
def img():
    """Serve an image file from inside the out/ base dir (safely)."""
    rel = request.args.get("p", "")
    base = os.path.abspath(app.config["BASE_DIR"])
    full = os.path.abspath(os.path.join(base, rel))
    if not full.startswith(base + os.sep) or not os.path.isfile(full):
        abort(404)
    return send_file(full)


@app.post("/api/save")
def api_save():
    _save(request.get_json(force=True)["listings"])
    return jsonify({"ok": True})


@app.post("/api/generate")
def api_generate():
    """Save edits, then compose a post image for each listing that has photos."""
    data = request.get_json(force=True)
    listings = data["listings"]
    _save(listings)

    base = app.config["BASE_DIR"]
    results = []
    for i, it in enumerate(listings, 1):
        imgs = it.get("selectedImages") or it.get("images") or []
        if not imgs:
            results.append({"index": i, "ok": False, "msg": "没有选图"})
            continue
        out_rel = os.path.join("posts", f"item{i:02d}.jpg")
        try:
            compose.compose_listing(it, base, os.path.join(base, out_rel))
            results.append({"index": i, "ok": True, "file": f"item{i:02d}.jpg"})
        except Exception as e:  # one bad listing shouldn't kill the batch
            results.append({"index": i, "ok": False, "msg": str(e)})
    return jsonify({"results": results})


@app.get("/posts/<path:name>")
def posts(name):
    return send_from_directory(os.path.join(app.config["BASE_DIR"], "posts"), name)


# The page builds all rows via DOM APIs and sets seller-entered values through
# element properties (.value / textContent), never by interpolating them into
# HTML — so listing text can't inject markup.
PAGE = r"""<!doctype html>
<html lang="zh">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>闲置 listing 整理</title>
<style>
  :root { --orange:#ff7a45; }
  * { box-sizing: border-box; }
  body { margin:0; font-family:-apple-system,"PingFang SC",sans-serif; background:#f5f6f8; color:#222; }
  header { position:sticky; top:0; background:#fff; padding:14px 20px; box-shadow:0 2px 8px rgba(0,0,0,.06);
           display:flex; align-items:center; gap:12px; z-index:10; }
  header h1 { font-size:18px; margin:0; flex:1; }
  button { font:inherit; border:none; border-radius:8px; padding:9px 16px; cursor:pointer; }
  .primary { background:var(--orange); color:#fff; }
  .ghost { background:#eee; color:#333; }
  #status { color:#888; font-size:13px; }
  main { max-width:880px; margin:0 auto; padding:20px; }
  .card { background:#fff; border-radius:14px; padding:18px; margin-bottom:20px; box-shadow:0 3px 12px rgba(0,0,0,.05); }
  .row { display:flex; gap:12px; flex-wrap:wrap; margin-bottom:10px; align-items:flex-end; }
  label { font-size:13px; color:#666; display:block; margin-bottom:4px; }
  input, textarea, select { width:100%; font:inherit; padding:8px 10px; border:1px solid #ddd; border-radius:8px; }
  textarea { resize:vertical; min-height:64px; }
  .field { flex:1; min-width:120px; }
  .imgs { display:flex; gap:12px; flex-wrap:wrap; }
  .thumb { width:150px; border:2px solid transparent; border-radius:10px; padding:6px; background:#fafafa; }
  .thumb.on { border-color:var(--orange); }
  .thumb img { width:100%; border-radius:6px; display:block; cursor:pointer; }
  .thumb .pick { display:flex; align-items:center; gap:6px; font-size:13px; margin:6px 0; }
  .thumb input[type=text] { font-size:12px; padding:5px 7px; }
  .muted { color:#aaa; font-size:12px; }
  .badge { font-size:12px; background:#eee; border-radius:6px; padding:2px 8px; color:#666; }
  .post { margin-top:12px; }
  .post img { max-width:280px; border-radius:8px; border:1px solid #eee; }
</style>
</head>
<body>
<header>
  <h1>闲置 listing 整理</h1>
  <span id="status"></span>
  <button class="ghost" id="btn-save">保存修改</button>
  <button class="primary" id="btn-gen">生成全部成品图</button>
</header>
<main id="app"><p class="muted">加载中…</p></main>

<script>
let LISTINGS = [];

const $ = (tag, props={}, kids=[]) => {
  const e = document.createElement(tag);
  for (const [k,v] of Object.entries(props)) {
    if (k === 'class') e.className = v;
    else if (k === 'text') e.textContent = v;          // safe text
    else if (k === 'value') e.value = v == null ? '' : v;  // safe value
    else if (k.startsWith('on')) e.addEventListener(k.slice(2), v);
    else e.setAttribute(k, v);
  }
  for (const kid of kids) if (kid) e.appendChild(kid);
  return e;
};

function setStatus(s){ document.getElementById('status').textContent = s || ''; }
function imgUrl(p){ return '/img?p=' + encodeURIComponent(p); }

async function load(){
  const r = await fetch('/api/listings');
  if(!r.ok){
    const msg = (await r.json()).error || '加载失败';
    document.getElementById('app').replaceChildren($('p',{text:msg}));
    return;
  }
  LISTINGS = (await r.json()).listings;
  render();
}

function field(labelText, value, oninput, tag='input'){
  const ctrl = $(tag, {value, oninput:e=>oninput(e.target.value)});
  return $('div',{class:'field'},[ $('label',{text:labelText}), ctrl ]);
}

function thumb(i, p){
  const it = LISTINGS[i];
  const on = it.selectedImages.includes(p);
  const im = $('img',{src:imgUrl(p), onclick:()=>toggle(i,p)});
  const cb = $('input',{type:'checkbox', onchange:()=>toggle(i,p)});
  if(on) cb.checked = true;
  const cap = $('input',{type:'text', value: it.imageCaptions[p]||'',
                         placeholder:'这张的说明（可空）', oninput:e=>{ it.imageCaptions[p]=e.target.value; }});
  return $('div',{class:'thumb'+(on?' on':'')},[
    im,
    $('div',{class:'pick'},[ cb, $('span',{text:'用这张'}) ]),
    cap
  ]);
}

function render(){
  const app = document.getElementById('app');
  app.replaceChildren();
  LISTINGS.forEach((it, i) => {
    if(!it.selectedImages) it.selectedImages = (it.images||[]).slice();
    if(!it.imageCaptions) it.imageCaptions = {};
    const imgs = $('div',{class:'imgs'}, (it.images||[]).map(p => thumb(i,p)));
    const card = $('div',{class:'card'},[
      $('div',{class:'row'},[ $('span',{class:'badge', text:`第 ${i+1} 件`}) ]),
      $('div',{class:'row'},[ field('标题', it.title, v=>it.title=v) ]),
      $('div',{class:'row'},[
        field('价格 $', it.price, v=>it.price=v),
        field('原价文本（可空）', it.marketPriceText, v=>it.marketPriceText=v),
        field('成色', it.condition, v=>it.condition=v),
      ]),
      $('div',{class:'row'},[ field('描述', it.description, v=>it.description=v, 'textarea') ]),
      $('label',{text:'选图（勾选要用的，可给每张加一句文字）'}),
      imgs,
      $('div',{class:'post', id:'post-'+i}),
    ]);
    app.appendChild(card);
  });
}

function toggle(i,p){
  const it = LISTINGS[i];
  const sel = it.selectedImages;
  const idx = sel.indexOf(p);
  if(idx>=0) sel.splice(idx,1);
  else it.selectedImages = it.images.filter(x => x===p || sel.includes(x)); // keep order
  render();
}

async function save(){
  setStatus('保存中…');
  await fetch('/api/save',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({listings:LISTINGS})});
  setStatus('已保存'); setTimeout(()=>setStatus(''),1500);
}

async function generate(){
  setStatus('生成中（每件合成一张长图）…');
  const r = await fetch('/api/generate',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({listings:LISTINGS})});
  const {results} = await r.json();
  results.forEach(res => {
    const box = document.getElementById('post-'+(res.index-1));
    if(!box) return;
    box.replaceChildren();
    if(res.ok){
      const url = '/posts/'+res.file+'?t='+Date.now();
      const im = $('img',{src:url});
      box.append($('label',{text:'成品图（右键另存，发到群里）'}),
                 $('a',{href:url, target:'_blank'},[im]));
    } else {
      box.append($('span',{class:'muted', text:'生成失败：'+res.msg}));
    }
  });
  setStatus('已生成，图片在 out/posts/'); setTimeout(()=>setStatus(''),2500);
}

document.getElementById('btn-save').addEventListener('click', save);
document.getElementById('btn-gen').addEventListener('click', generate);
load();
</script>
</body>
</html>"""


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="本地 listing 整理网页")
    ap.add_argument("--out", default="out", help="process.py 的输出目录")
    ap.add_argument("--port", type=int, default=5000)
    args = ap.parse_args()
    app.config["BASE_DIR"] = args.out
    print(f"打开 http://127.0.0.1:{args.port}  （素材目录：{args.out}）")
    app.run(port=args.port, debug=False)
