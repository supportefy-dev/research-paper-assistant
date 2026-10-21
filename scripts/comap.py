#!/usr/bin/env python3
"""comap.py - co-citation map: the intellectual structure of a field, from OpenAlex.

Takes candidate files from `scholar.py search --out` (or any file in the same
shape), fetches each paper's reference list, counts how often two references
are cited together by the input papers (co-citation), clusters the resulting
graph into schools of thought (label propagation, numpy, deterministic), and
reports seminal papers, the research frontier, bridge papers and a summary
skeleton that the agent fills in after reading.

Every number in the report comes from OpenAlex. Cluster names, the frontier
score and the bridge score are heuristics and are labelled as such: the agent
confirms them by reading the papers.

Commands
  build     build the map:  comap.py build --in cand.json [--in cand2.json] --out comap.md --html comap.html --json comap.json
  selftest  offline test on a planted two-community graph plus a too-small input (no network)

Credits (OpenAlex): one filter list per 50 input DOIs + one per 100 reference
nodes fetched; 100 input papers cost about 4 credits. No search calls.

Run with:  python -X utf8 comap.py build --help
"""

import argparse
import collections
import datetime as dt
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from scholar import openalex, HTTPError, clean, norm_doi, short, table, TODAY  # noqa: E402

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

try:
    import numpy as np
except ImportError:
    sys.exit("numpy is missing: pip install numpy")

CUR_YEAR = dt.date.today().year
MIN_PAPERS_DEFAULT = 10          # fewer input papers than this: the map is too small
MIN_NODES_DEFAULT = 8            # fewer references passing the threshold: too small to cluster

STOP = set("""a an the of and or in on for to with by from at as is are was were be been this that these those
study studies research paper article review effect effects impact impacts among between using use used based
analysis analyses approach approaches evidence role relationship relationships toward towards into its their
than more new case cases model models data results findings implications perspective perspectives
how what why when where which who does do not no via during through across within without about after before
over under some also two three one first second toward issue issues journal international""".split())

CLUSTER_COLOURS = ["#1f77b4", "#d62728", "#2ca02c", "#ff7f0e", "#9467bd", "#8c564b", "#e377c2",
                   "#17becf", "#bcbd22", "#7f7f7f", "#393b79", "#ad494a"]


# ---------------------------------------------------------------- input

def load_candidates(paths, max_papers):
    """Merge cand*.json files; one row per DOI; rows without a usable DOI are reported, not used."""
    rows, seen, skipped = [], set(), []
    for p in paths:
        with open(p, encoding="utf-8") as f:
            data = json.load(f)
        results = data.get("results") if isinstance(data, dict) else data
        for r in results or []:
            doi = norm_doi(r.get("doi") or "").lower()
            if not doi:
                skipped.append((short(r.get("title", ""), 60), "no DOI"))
                continue
            if "|" in doi or "," in doi:
                skipped.append((short(r.get("title", ""), 60), "DOI has | or , (cannot go in an OpenAlex filter)"))
                continue
            if doi in seen:
                continue
            seen.add(doi)
            rows.append({"doi": doi, "title": clean(r.get("title")), "year": r.get("year"),
                         "cites": r.get("cites"), "first_author": clean(r.get("first_author"))})
    return rows[:max_papers], skipped, len(rows)


def first_author_of(w):
    auths = w.get("authorships") or []
    return clean(((auths[0].get("author") or {}).get("display_name", "")) if auths else "")


def fetch_input_works(rows, batch=50):
    """One filter list per `batch` DOIs (1 credit each). Returns {doi: work}."""
    found = {}
    sel = "id,doi,display_name,publication_year,cited_by_count,referenced_works,authorships"
    for i in range(0, len(rows), batch):
        chunk = rows[i:i + batch]
        params = {"filter": "doi:" + "|".join(r["doi"] for r in chunk), "select": sel, "per_page": 200}
        print(f"[openalex] works by DOI {i + 1}-{i + len(chunk)} of {len(rows)} (1 credit)", file=sys.stderr)
        data = openalex("works", params) or {}
        for w in data.get("results", []):
            d = norm_doi(w.get("doi") or "").lower()
            if d:
                found[d] = w
    return found


def fetch_nodes(ids, batch=100):
    """Titles / years / first authors for reference nodes: one call per 100 ids (1 credit each)."""
    out = {}
    sel = "id,doi,display_name,publication_year,cited_by_count,authorships"
    ids = list(ids)
    for i in range(0, len(ids), batch):
        chunk = ids[i:i + batch]
        params = {"filter": "openalex_id:" + "|".join(x.rsplit("/", 1)[-1] for x in chunk),
                  "select": sel, "per_page": 200}
        print(f"[openalex] reference metadata {i + 1}-{i + len(chunk)} of {len(ids)} (1 credit)", file=sys.stderr)
        data = openalex("works", params) or {}
        for w in data.get("results", []):
            out[w["id"]] = w
    return out


# ---------------------------------------------------------------- graph

def build_graph(ref_lists, min_cocited, min_edge, max_nodes):
    """ref_lists: {paper_doi: [ref ids]}. Returns (node ids, in-set counts, raw co-citation matrix)."""
    count = collections.Counter()
    for refs in ref_lists.values():
        for r in set(refs):
            count[r] += 1
    kept = [r for r, c in count.items() if c >= min_cocited]
    kept.sort(key=lambda r: (-count[r], r))
    kept = kept[:max_nodes]
    idx = {r: i for i, r in enumerate(kept)}
    n = len(kept)
    C = np.zeros((n, n))
    for refs in ref_lists.values():
        ks = sorted({idx[r] for r in refs if r in idx})
        for a in range(len(ks)):
            for b in range(a + 1, len(ks)):
                C[ks[a], ks[b]] += 1
                C[ks[b], ks[a]] += 1
    C[C < min_edge] = 0
    return kept, {r: count[r] for r in kept}, C


def association_strength(C):
    """Van Eck & Waltman normalisation: a_ij = 2m * c_ij / (s_i s_j). Keeps hubs from swallowing the map."""
    s = C.sum(axis=1)
    m2 = C.sum()
    if m2 == 0:
        return C.copy()
    denom = np.outer(s, s)
    with np.errstate(divide="ignore", invalid="ignore"):
        A = np.where(denom > 0, m2 * C / denom, 0.0)
    return A


def modularity(C, labels):
    m2 = C.sum()
    if m2 == 0:
        return 0.0
    k = C.sum(axis=1)
    same = labels[:, None] == labels[None, :]
    return float(((C - np.outer(k, k) / m2) * same).sum() / m2)


def label_propagation(W, seed=0, max_iter=200):
    """Asynchronous label propagation. Ties go to the smallest label; order is a seeded permutation."""
    n = W.shape[0]
    rng = np.random.default_rng(seed)
    labels = np.arange(n)
    for _ in range(max_iter):
        changed = 0
        for i in rng.permutation(n):
            nb = np.nonzero(W[i])[0]
            if nb.size == 0:
                continue
            scores = np.bincount(labels[nb], weights=W[i, nb], minlength=n)
            best = scores.max()
            cands = np.nonzero(scores >= best - 1e-12)[0]
            new = labels[i] if labels[i] in cands else int(cands[0])
            if new != labels[i]:
                labels[i] = new
                changed += 1
        if changed == 0:
            break
    return labels


def cluster(C, seeds=(0, 1, 2, 3, 4), min_size=3):
    """Run label propagation on association-strength weights for several fixed seeds, keep the
    partition with the best modularity (deterministic), then fold clusters smaller than
    min_size into the cluster they are most connected to. Isolated nodes get cluster 0."""
    n = C.shape[0]
    if n == 0:
        return np.zeros(0, dtype=int), 0.0
    A = association_strength(C)
    best, best_q = None, -2.0
    for s in seeds:
        lab = label_propagation(A, seed=s)
        q = modularity(C, lab)
        if q > best_q + 1e-9:
            best, best_q = lab, q
    labels = best.copy()
    deg = (C > 0).sum(axis=1)
    labels[deg == 0] = -1                      # isolated nodes take no part in folding
    # fold small clusters into the neighbour they share most co-citation weight with
    for _ in range(n):
        sizes = collections.Counter(int(l) for l in labels if l >= 0)
        small = [l for l, c in sizes.items() if c < min_size]
        if not small:
            break
        l = min(small, key=lambda x: (sizes[x], x))
        members = np.nonzero(labels == l)[0]
        others = [x for x in sizes if x != l]
        if not others:
            break
        weights = {o: C[np.ix_(members, np.nonzero(labels == o)[0])].sum() for o in others}
        target = max(others, key=lambda o: (weights[o], -sizes[o]))
        labels[members] = target
    # renumber: 0 = isolated (no edges), then 1..k by size desc
    out = np.zeros(n, dtype=int)
    order = sorted({int(l) for l in labels if l >= 0}, key=lambda l: (-(labels == l).sum(), l))
    for k, l in enumerate(order, 1):
        out[labels == l] = k
    return out, best_q


# ---------------------------------------------------------------- naming, ranking

def title_words(title):
    return [w for w in re.findall(r"[a-z][a-z\-]{3,}", clean(title).lower()) if w not in STOP]


def name_cluster(members, meta, all_df, n_all):
    """Top 3 title words that are frequent in the cluster AND distinctive for it: a word in more
    than half of all node titles (the search terms, usually) says nothing about one cluster."""
    df = collections.Counter()
    tf = collections.Counter()
    for nid in members:
        ws = title_words((meta.get(nid) or {}).get("display_name", ""))
        tf.update(ws)
        df.update(set(ws))
    cands = [w for w in df if all_df[w] / max(1, n_all) <= 0.5]
    top = sorted(cands, key=lambda w: (-(df[w] * df[w] / all_df[w]), -tf[w], w))[:3]
    return ", ".join(top) if top else "(no distinctive title words)"


def family_name(display_name):
    """Last token that is not a bare initial: OpenAlex has 'Reynol Junco A' style names."""
    toks = [t for t in re.split(r"\s+", clean(display_name)) if t]
    while len(toks) > 1 and re.fullmatch(r"[A-Za-z]\.?", toks[-1]):
        toks.pop()
    return toks[-1] if toks else "?"


def node_title(nid, meta):
    w = meta.get(nid)
    if not w:
        return f"(no metadata: OpenAlex work {nid.rsplit('/', 1)[-1]} is deleted or merged)"
    return clean(w.get("display_name")) or nid


def node_label(nid, meta):
    w = meta.get(nid) or {}
    fam = family_name(first_author_of(w)) if w else "?"
    y = w.get("publication_year") or "n.d."
    return f"{fam} ({y})"


def node_line(nid, meta, inset):
    w = meta.get(nid) or {}
    doi = norm_doi(w.get("doi") or "")
    return [node_label(nid, meta), short(node_title(nid, meta), 70), str(inset.get(nid, "")),
            str(w.get("cited_by_count", "")), doi or nid.rsplit("/", 1)[-1]]


def frontier(rows, works):
    """Citation velocity of the INPUT papers: cites / years since publication (heuristic)."""
    out = []
    for r in rows:
        w = works.get(r["doi"])
        if not w:
            continue
        y, c = w.get("publication_year"), w.get("cited_by_count") or 0
        if not y:
            continue
        age = max(0.5, CUR_YEAR - y + 0.5)
        out.append({"doi": r["doi"], "title": clean(w.get("display_name")), "year": y, "cites": c,
                    "first_author": first_author_of(w), "velocity": round(c / age, 1)})
    out.sort(key=lambda x: (-x["velocity"], -x["cites"]))
    return out


def bridges(C, labels, nodes):
    """Nodes whose co-citation weight reaches into other clusters. score = weight to other clusters."""
    out = []
    for i, nid in enumerate(nodes):
        if labels[i] == 0:
            continue
        other = collections.Counter()
        for j in np.nonzero(C[i])[0]:
            if labels[j] != labels[i]:
                other[int(labels[j])] += C[i, j]
        if not other:
            continue
        own = C[i][labels == labels[i]].sum()
        tot = sum(other.values())
        top2 = other.most_common(2)
        out.append({"id": nid, "cluster": int(labels[i]), "to": [c for c, _ in top2],
                    "score": float(tot), "own": float(own), "share": round(tot / (tot + own), 2) if tot + own else 0})
    out.sort(key=lambda x: (-x["score"], x["id"]))
    return out


# ---------------------------------------------------------------- outputs

def html_map(payload):
    data = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    return """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>Co-citation map</title>
<style>
body{font-family:Segoe UI,Arial,sans-serif;margin:0;background:#fafafa;color:#222}
#wrap{display:flex;height:100vh}
#map{flex:1;position:relative}
svg{width:100%;height:100%;display:block}
#side{width:300px;padding:14px;overflow:auto;border-left:1px solid #ddd;background:#fff;font-size:13px}
#tip{position:absolute;pointer-events:none;background:#222;color:#fff;padding:6px 8px;border-radius:4px;font-size:12px;max-width:320px;display:none}
.sw{display:inline-block;width:12px;height:12px;border-radius:6px;margin-right:6px;vertical-align:middle}
h2{font-size:15px;margin:0 0 8px} h3{font-size:13px;margin:12px 0 4px}
line{stroke:#999} circle{stroke:#fff;stroke-width:1;cursor:pointer} text.lbl{font-size:10px;fill:#333;pointer-events:none}
</style></head><body><div id="wrap"><div id="map"><svg id="svg"></svg><div id="tip"></div></div>
<div id="side"><h2>Co-citation map</h2><div id="meta"></div><h3>Clusters</h3><div id="legend"></div>
<h3>How to read</h3><p>Node = a reference cited by at least <span id="mc"></span> of the input papers. Size = co-citation degree. Colour = cluster (label propagation). Edge = co-cited by at least <span id="me"></span> papers. Hover for title, year, DOI; click opens the DOI.</p></div></div>
<script>
var D = """ + data + """;
var svg=document.getElementById('svg'),tip=document.getElementById('tip');
var W=document.getElementById('map').clientWidth||900,H=document.getElementById('map').clientHeight||650;
var N=D.nodes,E=D.edges,n=N.length;
var seed=42;function rnd(){seed=(seed*1664525+1013904223)%4294967296;return seed/4294967296;}
N.forEach(function(d){d.x=W/2+(rnd()-0.5)*W*0.6;d.y=H/2+(rnd()-0.5)*H*0.6;d.vx=0;d.vy=0;d.r=4+2*Math.sqrt(d.degree);});
var byId={};N.forEach(function(d){byId[d.id]=d;});
var maxw=1;E.forEach(function(e){if(e.w>maxw)maxw=e.w;});
function step(alpha){
  for(var i=0;i<n;i++){var a=N[i];for(var j=i+1;j<n;j++){var b=N[j];var dx=b.x-a.x,dy=b.y-a.y,d2=dx*dx+dy*dy+0.01;var f=1800*alpha/d2;var d=Math.sqrt(d2);dx/=d;dy/=d;a.vx-=dx*f;a.vy-=dy*f;b.vx+=dx*f;b.vy+=dy*f;}}
  E.forEach(function(e){var a=byId[e.s],b=byId[e.t];if(!a||!b)return;var dx=b.x-a.x,dy=b.y-a.y,d=Math.sqrt(dx*dx+dy*dy)+0.01;var want=40+60*(1-e.w/maxw);var f=(d-want)*0.02*alpha*(0.3+e.w/maxw);dx/=d;dy/=d;a.vx+=dx*f;a.vy+=dy*f;b.vx-=dx*f;b.vy-=dy*f;});
  N.forEach(function(d){d.vx+=(W/2-d.x)*0.01*alpha;d.vy+=(H/2-d.y)*0.01*alpha;d.x+=d.vx;d.y+=d.vy;d.vx*=0.6;d.vy*=0.6;d.x=Math.max(d.r+2,Math.min(W-d.r-2,d.x));d.y=Math.max(d.r+2,Math.min(H-d.r-2,d.y));});
}
for(var t=0;t<400;t++){step(1-t/400);}
var ns='http://www.w3.org/2000/svg';
svg.setAttribute('viewBox','0 0 '+W+' '+H);
E.forEach(function(e){var a=byId[e.s],b=byId[e.t];if(!a||!b)return;var l=document.createElementNS(ns,'line');l.setAttribute('x1',a.x);l.setAttribute('y1',a.y);l.setAttribute('x2',b.x);l.setAttribute('y2',b.y);l.setAttribute('stroke-width',0.5+2*e.w/maxw);l.setAttribute('stroke-opacity',0.15+0.5*e.w/maxw);svg.appendChild(l);});
N.forEach(function(d){var c=document.createElementNS(ns,'circle');c.setAttribute('cx',d.x);c.setAttribute('cy',d.y);c.setAttribute('r',d.r);c.setAttribute('fill',D.colours[d.cluster%D.colours.length]);
  c.addEventListener('mousemove',function(ev){tip.style.display='block';tip.style.left=(ev.offsetX+12)+'px';tip.style.top=(ev.offsetY+12)+'px';tip.innerHTML='<b>'+esc(d.title)+'</b><br>'+esc(d.first_author)+' ('+(d.year||'n.d.')+')<br>'+(d.doi?'doi: '+esc(d.doi):'no DOI')+'<br>cited by '+d.inset+' input papers, '+d.cites+' overall, cluster '+d.cluster+(d.cluster_name?' ('+esc(d.cluster_name)+')':'');});
  c.addEventListener('mouseleave',function(){tip.style.display='none';});
  c.addEventListener('click',function(){if(d.doi)window.open('https://doi.org/'+d.doi,'_blank');});
  svg.appendChild(c);
  if(d.label_on_map){var tx=document.createElementNS(ns,'text');tx.setAttribute('x',d.x+d.r+2);tx.setAttribute('y',d.y+3);tx.setAttribute('class','lbl');tx.textContent=d.label;svg.appendChild(tx);}
});
function esc(s){return String(s==null?'':s).replace(/[&<>"]/g,function(c){return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];});}
document.getElementById('meta').innerHTML=esc(D.meta.summary);
document.getElementById('mc').textContent=D.meta.min_cocited;document.getElementById('me').textContent=D.meta.min_edge;
var lg='';D.clusters.forEach(function(c){lg+='<div><span class="sw" style="background:'+D.colours[c.id%D.colours.length]+'"></span><b>'+c.id+'</b> '+esc(c.name)+' ('+c.size+')</div>';});
if(D.meta.isolated)lg+='<div><span class="sw" style="background:'+D.colours[0]+'"></span><b>0</b> isolated ('+D.meta.isolated+')</div>';
document.getElementById('legend').innerHTML=lg;
</script></body></html>
"""


def write_report(path, rows, works, skipped, nodes, inset, C, labels, meta, clusters, sem, front, br, q, a):
    L = []
    resolved = sum(1 for r in rows if r["doi"] in works)
    L.append(f"# Co-citation map: {a.label or ', '.join(os.path.basename(p) for p in a.inp)}")
    L.append("")
    L.append(f"{TODAY} | input papers: {len(rows)} ({resolved} resolved in OpenAlex) | references cited by >= {a.min_cocited} "
             f"input papers: {len(nodes)} | edges (co-cited >= {a.min_edge} times): {int((C > 0).sum() // 2)} | "
             f"clusters: {len(clusters)} | modularity Q = {q:.2f}")
    L.append("")
    L.append("Numbers are OpenAlex counts as of today. Cluster names, the frontier score and the bridge score are "
             "heuristics (title words, cites per year, cross-cluster weight): confirm each by reading the papers before "
             "writing about the field's structure.")
    L.append("")
    L.append("## Clusters (schools of thought, candidate names)")
    L.append("")
    for c in clusters:
        L.append(f"### Cluster {c['id']}: {c['name']} ({c['size']} references)")
        L.append("")
        L.append(table([node_line(nid, meta, inset) for nid in c["top"]],
                       ["first author (year)", "title", "cited by inputs", "cites (all)", "doi / id"]))
        L.append("")
    if meta.get("_isolated"):
        L.append(f"Isolated references (no edge at the threshold): {meta['_isolated']}")
        L.append("")
    L.append("## Seminal papers (most cited by the input set)")
    L.append("")
    L.append(table([[str(i + 1)] + node_line(nid, meta, inset) + [str(labels[nodes.index(nid)])] for i, nid in enumerate(sem)],
                   ["#", "first author (year)", "title", "cited by inputs", "cites (all)", "doi / id", "cluster"]))
    L.append("")
    L.append("## Frontier (input papers with the fastest citation growth; heuristic: cites / years since publication)")
    L.append("")
    L.append(table([[str(i + 1), f"{short(f['first_author'], 22)} ({f['year']})", short(f["title"], 70), str(f["cites"]),
                     str(f["velocity"]), f["doi"]] for i, f in enumerate(front)],
                   ["#", "first author (year)", "title", "cites", "cites/year", "doi"]))
    L.append("")
    L.append("## Bridges (references co-cited across clusters)")
    L.append("")
    if br:
        L.append(table([[node_label(b["id"], meta), short(node_title(b["id"], meta), 60),
                         str(b["cluster"]), " + ".join(str(x) for x in b["to"]), str(int(b["score"])), str(b["share"])]
                        for b in br],
                       ["first author (year)", "title", "home cluster", "links to", "cross-cluster weight", "share outside home"]))
    else:
        L.append("None: no reference links two clusters at this edge threshold.")
    L.append("")
    L.append("## Structure summary skeleton (fill every [ ] after reading; delete what the reading does not support)")
    L.append("")
    names = [f"[{c['name']}]" for c in clusters[:3]]
    while len(names) < 3:
        names.append("[ ]")
    nstream = {1: "One stream", 2: "Two streams", 3: "Three streams"}.get(min(len(clusters), 3), "Three streams")
    sem_names = ", ".join(node_label(nid, meta) for nid in sem[:3])
    L.append(f"{nstream} dominate the literature on [topic]: {', '.join(names[:max(1, min(3, len(clusters)))])}"
             f"{' and further smaller strands' if len(clusters) > 3 else ''}. "
             f"The field rests on {sem_names or '[seminal papers]'}, which [what they established: the construct, the "
             f"instrument or the first effect estimate]. "
             f"Recent work ({', '.join(family_name(f['first_author']) + ' (' + str(f['year']) + ')' for f in front[:3]) or '[frontier papers]'}) "
             f"moves toward [the frontier: method, population or moderator], leaving [the gap this paper addresses] open.")
    L.append("")
    L.append("## Not checked")
    L.append("")
    L.append(f"- Input papers skipped: {len(skipped)} (no DOI or DOI unusable in a filter). Not resolved in OpenAlex: "
             f"{len(rows) - resolved}. These contribute no references.")
    L.append("- Reference lists come from OpenAlex and are incomplete for many publishers; a missing seminal paper may be "
             "a data gap, not a real absence.")
    L.append("- Papers citing the inputs (forward citations) were not fetched: the frontier is scored on citation counts only.")
    L.append("- Cluster membership of a paper is a graph artefact until the agent reads the paper.")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(L) + "\n")


# ---------------------------------------------------------------- commands

def too_small(reason):
    print(f"MAP TOO SMALL: {reason}")
    print("RESULT: FAIL (co-citation map not built; add more input papers, e.g. a second `scholar.py search --out` "
          "or a snowball file, and rerun)")
    sys.exit(1)


def cmd_build(a):
    rows, skipped, total = load_candidates(a.inp, a.max_papers)
    print(f"input: {total} unique papers with a DOI from {len(a.inp)} file(s); using {len(rows)}; skipped {len(skipped)} rows without a usable DOI")
    for t, why in skipped[:10]:
        print(f"  skipped: {t} ({why})")
    if len(rows) < a.min_papers:
        too_small(f"{len(rows)} input papers with a DOI; at least {a.min_papers} are needed before co-citation counts mean anything "
                  f"(a reference must be cited by >= {a.min_cocited} input papers to appear).")
    try:
        works = fetch_input_works(rows)
    except HTTPError as e:
        sys.exit(f"OpenAlex error while fetching the input papers: {e}")
    ref_lists = {d: (w.get("referenced_works") or []) for d, w in works.items()}
    n_refs = sum(len(v) for v in ref_lists.values())
    print(f"resolved {len(works)} of {len(rows)} papers in OpenAlex; {n_refs} reference links "
          f"({sum(1 for v in ref_lists.values() if not v)} papers have an empty reference list in OpenAlex)")
    nodes, inset, C = build_graph(ref_lists, a.min_cocited, a.min_edge, a.max_nodes)
    if len(nodes) < a.min_nodes:
        too_small(f"only {len(nodes)} references are cited by >= {a.min_cocited} input papers (need {a.min_nodes}). "
                  f"Try --min-cocited 2 or add input papers.")
    labels, q = cluster(C, min_size=a.min_cluster)
    try:
        meta = fetch_nodes(nodes)
    except HTTPError as e:
        sys.exit(f"OpenAlex error while fetching reference metadata: {e}")
    missing = [nid for nid in nodes if nid not in meta]
    if missing:
        print(f"{len(missing)} reference ids returned no metadata (deleted or merged works); shown by id", file=sys.stderr)
    deg = (C > 0).sum(axis=1)
    all_df = collections.Counter()
    for nid in nodes:
        all_df.update(set(title_words((meta.get(nid) or {}).get("display_name", ""))))
    clusters = []
    for cid in sorted({int(l) for l in labels if l > 0}):
        members = [nodes[i] for i in np.nonzero(labels == cid)[0]]
        members.sort(key=lambda nid: (-inset[nid], -((meta.get(nid) or {}).get("cited_by_count") or 0)))
        clusters.append({"id": cid, "name": name_cluster(members, meta, all_df, len(nodes)), "size": len(members),
                         "top": members[:3], "members": members})
    meta["_isolated"] = int((labels == 0).sum())
    sem = sorted(nodes, key=lambda nid: (-inset[nid], -((meta.get(nid) or {}).get("cited_by_count") or 0)))[:a.top]
    front = frontier(rows, works)[:a.top]
    br = bridges(C, labels, nodes)[:a.top]

    print(f"map: {len(nodes)} references, {int((C > 0).sum() // 2)} edges, {len(clusters)} clusters, Q = {q:.2f}, "
          f"{meta['_isolated']} isolated")
    print(table([[str(c["id"]), c["name"], str(c["size"]),
                  "; ".join(node_label(nid, meta) for nid in c["top"])] for c in clusters],
                ["cluster", "candidate name (title words)", "size", "top 3 (cited by inputs)"]))
    print("seminal: " + "; ".join(f"{node_label(nid, meta)} x{inset[nid]}" for nid in sem[:5]))
    print("frontier: " + "; ".join(f"{short(f['first_author'], 18)} ({f['year']}) {f['velocity']}/yr" for f in front[:5]))
    print("bridges: " + ("; ".join(f"{node_label(b['id'], meta)} {b['cluster']}->{'+'.join(map(str, b['to']))}" for b in br[:5]) or "none"))

    write_report(a.out, rows, works, skipped, nodes, inset, C, labels, meta, clusters, sem, front, br, q, a)
    print(f"report: {os.path.abspath(a.out)}")

    label_on = {nid for c in clusters for nid in c["top"]}
    cname = {c["id"]: c["name"] for c in clusters}
    payload_nodes = []
    for i, nid in enumerate(nodes):
        w = meta.get(nid) or {}
        payload_nodes.append({"id": nid, "title": node_title(nid, meta), "year": w.get("publication_year"),
                              "doi": norm_doi(w.get("doi") or ""), "first_author": first_author_of(w),
                              "cites": w.get("cited_by_count"), "inset": inset[nid], "degree": int(deg[i]),
                              "cluster": int(labels[i]), "cluster_name": cname.get(int(labels[i]), ""),
                              "label": node_label(nid, meta), "label_on_map": nid in label_on})
    edges = [{"s": nodes[i], "t": nodes[j], "w": int(C[i, j])} for i in range(len(nodes)) for j in range(i + 1, len(nodes)) if C[i, j] > 0]
    payload = {
        "meta": {"date": TODAY, "inputs": a.inp, "n_input": len(rows), "n_resolved": len(works), "min_cocited": a.min_cocited,
                 "min_edge": a.min_edge, "modularity": round(q, 3), "isolated": meta["_isolated"],
                 "summary": f"{len(rows)} input papers, {len(nodes)} references, {len(edges)} edges, {len(clusters)} clusters, Q={q:.2f}",
                 "heuristics": ["cluster names = top title words", "frontier = cites / years since publication",
                                "bridge score = co-citation weight to other clusters"]},
        "clusters": [{"id": c["id"], "name": c["name"], "size": c["size"], "top": c["top"], "members": c["members"]} for c in clusters],
        "nodes": payload_nodes, "edges": edges,
        "seminal": sem, "frontier": front, "bridges": br, "colours": CLUSTER_COLOURS,
    }
    if a.json:
        with open(a.json, "w", encoding="utf-8", newline="\n") as f:
            json.dump(payload, f, ensure_ascii=False, indent=1)
        print(f"json: {os.path.abspath(a.json)}")
    if a.html:
        with open(a.html, "w", encoding="utf-8", newline="\n") as f:
            f.write(html_map(payload))
        print(f"html: {os.path.abspath(a.html)}")
    print(f"RESULT: PASS ({len(clusters)} clusters from {len(nodes)} references; names and scores are candidates for the agent to confirm)")


def cmd_selftest(a):
    """Offline: planted two-community graph with one bridge, then a too-small input."""
    rng = np.random.default_rng(7)
    n = 24
    C = np.zeros((n, n))
    for i in range(n):
        for j in range(i + 1, n):
            same = (i < 12) == (j < 12)
            if rng.random() < (0.6 if same else 0.03):
                C[i, j] = C[j, i] = rng.integers(2, 6)
    # node 23 is the bridge: strong ties into both halves
    for j in (0, 1, 2, 12, 13, 14):
        C[23, j] = C[j, 23] = 5
    labels, q = cluster(C)
    k = len({int(l) for l in labels if l > 0})
    nodes = [f"W{i}" for i in range(n)]
    br = bridges(C, labels, nodes)
    ok1 = k == 2 and labels[0] == labels[11] and labels[12] == labels[21] and labels[0] != labels[12]
    ok2 = bool(br) and br[0]["id"] == "W23"
    print(f"planted 2 communities + 1 bridge: found {k} clusters, Q = {q:.2f}, top bridge = {br[0]['id'] if br else 'none'}")
    print(f"  communities recovered: {'PASS' if ok1 else 'FAIL'}; bridge found: {'PASS' if ok2 else 'FAIL'}")
    # determinism
    labels2, _ = cluster(C)
    ok3 = bool((labels == labels2).all())
    print(f"  deterministic rerun: {'PASS' if ok3 else 'FAIL'}")
    # negative control: 2 papers
    tiny = [{"doi": "10.1/a", "title": "x"}, {"doi": "10.1/b", "title": "y"}]
    ok4 = len(tiny) < MIN_PAPERS_DEFAULT
    print(f"  2-paper input rejected before any network call (min {MIN_PAPERS_DEFAULT}): {'PASS' if ok4 else 'FAIL'}")
    # negative control: no structure at all (empty graph) must not invent clusters
    labels3, _ = cluster(np.zeros((6, 6)))
    ok5 = int(labels3.max()) == 0
    print(f"  edgeless graph yields 0 clusters: {'PASS' if ok5 else 'FAIL'}")
    ok6 = family_name("Reynol Junco A") == "Junco" and family_name("Paul A. Kirschner") == "Kirschner" \
        and family_name("Wilfred W. F. Lau") == "Lau"
    print(f"  family-name parsing (trailing initials): {'PASS' if ok6 else 'FAIL'}")
    allok = ok1 and ok2 and ok3 and ok4 and ok5 and ok6
    print(f"RESULT: {'PASS' if allok else 'FAIL'} (offline selftest, no OpenAlex calls)")
    sys.exit(0 if allok else 1)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="build the co-citation map from candidate files",
                       epilog='example: python -X utf8 comap.py build --in cand.json --out comap.md --html comap.html --json comap.json')
    b.add_argument("--in", dest="inp", action="append", required=True, help="cand.json from scholar.py search --out (repeatable)")
    b.add_argument("--max-papers", type=int, default=200, help="cap on input papers (default 200)")
    b.add_argument("--min-papers", type=int, default=MIN_PAPERS_DEFAULT, help=f"fewer input papers = too small (default {MIN_PAPERS_DEFAULT})")
    b.add_argument("--min-cocited", type=int, default=3, help="keep references cited by at least this many input papers (default 3)")
    b.add_argument("--min-edge", type=int, default=2, help="keep pairs co-cited at least this many times (default 2)")
    b.add_argument("--min-nodes", type=int, default=MIN_NODES_DEFAULT, help=f"fewer references = too small (default {MIN_NODES_DEFAULT})")
    b.add_argument("--max-nodes", type=int, default=200, help="cap on references in the map, by in-set citations (default 200 = 2 credits)")
    b.add_argument("--min-cluster", type=int, default=3, help="clusters smaller than this are folded into a neighbour (default 3)")
    b.add_argument("--top", type=int, default=10, help="rows in the seminal / frontier / bridge tables (default 10)")
    b.add_argument("--label", default="", help="title for the report")
    b.add_argument("--out", default="comap.md", help="markdown report (default comap.md)")
    b.add_argument("--html", help="self-contained interactive map (inline SVG + JS, no CDN)")
    b.add_argument("--json", help="nodes, edges, clusters, rankings as JSON")
    b.set_defaults(func=cmd_build)
    s = sub.add_parser("selftest", help="offline test: planted communities, bridge, too-small input",
                       epilog="example: python -X utf8 comap.py selftest")
    s.set_defaults(func=cmd_selftest)
    a = p.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()
