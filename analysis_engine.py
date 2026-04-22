#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Upgraded analysis engine for AJS-Sastra.
Adds intertextual multi-work analysis: shared concepts, bridging concepts,
document similarity, and global semantic network export.
"""

import os
import re
import csv
from dataclasses import dataclass
from typing import Dict, List, Tuple, Optional, Set
from datetime import datetime

import pandas as pd
import networkx as nx
import matplotlib.pyplot as plt


# =========================================================
# UTIL
# =========================================================
def _clean_ws(s: str) -> str:
    return re.sub(r"\s+", " ", str(s)).strip()


def normalize_entity(name: str) -> str:
    s = _clean_ws(name)
    s = s.strip("–-•:;,.\t")
    return s


def slug_id(name: str) -> str:
    s = normalize_entity(name).lower()
    s = s.replace("’", "'")
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"\s+", "_", s).strip("_")
    return s if s else "node"


def _norm_col(c: str) -> str:
    c = _clean_ws(c).lower()
    c = re.sub(r"[^a-z0-9]+", "", c)
    return c


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


# =========================================================
# DATA CONTAINER
# =========================================================
@dataclass
class AJSParsed:
    entities_by_type: Dict[str, Set[str]]
    edges: List[Tuple[str, str, str]]
    raw_text: str


# =========================================================
# LOAD EXCEL / DOCX-TXT fallback
# =========================================================
def _read_excel_first_sheet(path: str, sheet_name: Optional[str] = None) -> pd.DataFrame:
    ext = os.path.splitext(path)[1].lower()

    if ext in [".xlsx", ".xlsm"]:
        engine = "openpyxl"
    elif ext == ".xls":
        engine = "xlrd"
    else:
        raise ValueError(f"Format file tidak didukung: {ext}. Gunakan .xlsx atau .xls")

    if sheet_name is None:
        obj = pd.read_excel(path, sheet_name=None, engine=engine)
        if isinstance(obj, dict):
            if not obj:
                raise ValueError("Excel kosong / tidak ada sheet.")
            first_key = list(obj.keys())[0]
            return obj[first_key].copy()
        return obj.copy()
    else:
        df = pd.read_excel(path, sheet_name=sheet_name, engine=engine)
        if isinstance(df, dict):
            first_key = list(df.keys())[0]
            return df[first_key].copy()
        return df.copy()


def _dedup_edges(edges: List[Tuple[str, str, str]]) -> List[Tuple[str, str, str]]:
    seen = set()
    out = []
    for s, r, t in edges:
        key = (s, r, t)
        if key not in seen:
            seen.add(key)
            out.append(key)
    return out


def load_excel(path: str, sheet_name: Optional[str] = None):
    if not os.path.exists(path):
        raise FileNotFoundError(f"File tidak ditemukan: {path}")

    df = _read_excel_first_sheet(path, sheet_name=sheet_name)

    original_cols = list(df.columns)
    colmap = {_norm_col(c): c for c in original_cols}

    def pick(*cands):
        for cand in cands:
            if cand in colmap:
                return colmap[cand]
        return None

    c_source = pick("source", "src", "from")
    c_relation = pick("relation", "relasi", "predicate", "edge")
    c_target = pick("target", "tgt", "to")

    if not c_source or not c_relation or not c_target:
        raise ValueError(
            "Kolom wajib tidak lengkap. Minimal harus ada Source, Relation, Target. "
            f"Kolom terbaca: {original_cols}"
        )

    c_stype = pick("sourcetype", "srctype", "typesource")
    c_ttype = pick("targettype", "tgttype", "typetarget")

    cols = [c_source, c_relation, c_target]
    if c_stype:
        cols.append(c_stype)
    if c_ttype:
        cols.append(c_ttype)

    df = df[cols].copy()

    for c in [c_source, c_relation, c_target]:
        df[c] = df[c].astype(str).map(normalize_entity)

    df = df[(df[c_source] != "") & (df[c_relation] != "") & (df[c_target] != "")]
    df = df.reset_index(drop=True)

    edges = [(df.loc[i, c_source], df.loc[i, c_relation], df.loc[i, c_target]) for i in range(len(df))]

    type_map: Dict[str, str] = {}
    if c_stype:
        for i in range(len(df)):
            lab = normalize_entity(df.loc[i, c_source]).lower()
            typ = normalize_entity(df.loc[i, c_stype])
            if lab and typ:
                type_map[lab] = typ

    if c_ttype:
        for i in range(len(df)):
            lab = normalize_entity(df.loc[i, c_target]).lower()
            typ = normalize_entity(df.loc[i, c_ttype])
            if lab and typ:
                type_map[lab] = typ

    parsed = AJSParsed(
        entities_by_type={},
        edges=_dedup_edges(edges),
        raw_text=f"Excel: {os.path.basename(path)} | rows={len(df)}"
    )

    df_edges = pd.DataFrame(edges, columns=["Source", "Relation", "Target"])
    return parsed, df_edges, type_map


# =========================================================
# GRAPH
# =========================================================
def guess_type(label: str, type_map_by_label_lower: Dict[str, str]) -> str:
    low = normalize_entity(label).lower()

    if low in type_map_by_label_lower:
        return type_map_by_label_lower[low]

    if re.search(r"\b(putri|ibu|pangeran|prabu|bandung|raja|kerajaan|rakyat|dayang|tokoh)\b", low):
        return "Tokoh"

    if any(k in low for k in ["tema", "kekuasaan", "keadilan", "pengorbanan", "tanggung jawab", "legitimasi", "identitas", "keluarga"]):
        return "Tema"

    if any(k in low for k in ["motif", "simbol", "kutukan", "perjanjian", "konflik", "cinta", "pengkhianatan"]):
        return "Motif"

    return "Konsep"


def build_graph(parsed: AJSParsed, type_map_by_label_lower: Dict[str, str]) -> nx.DiGraph:
    g = nx.DiGraph()

    for s, rel, t in parsed.edges:
        s2, rel2, t2 = normalize_entity(s), normalize_entity(rel), normalize_entity(t)
        if not s2 or not rel2 or not t2:
            continue

        sid = slug_id(s2)
        tid = slug_id(t2)

        if sid not in g:
            g.add_node(sid, label=s2, type=guess_type(s2, type_map_by_label_lower))
        if tid not in g:
            g.add_node(tid, label=t2, type=guess_type(t2, type_map_by_label_lower))

        if g.has_edge(sid, tid):
            old = g[sid][tid].get("relations", "")
            rels = set([x for x in old.split(";") if x])
            rels.add(rel2)
            g[sid][tid]["relations"] = ";".join(sorted(rels))
            g[sid][tid]["weight"] = g[sid][tid].get("weight", 1) + 1
        else:
            g.add_edge(sid, tid, relations=rel2, weight=1)

    return g


def merge_graphs(graph_entries: List[Dict]) -> nx.DiGraph:
    merged = nx.DiGraph()
    for entry in graph_entries:
        doc = entry["filename"]
        g = entry["graph"]
        for nid, data in g.nodes(data=True):
            if nid not in merged:
                merged.add_node(
                    nid,
                    label=data.get("label", nid),
                    type=data.get("type", "Konsep"),
                    documents=set([doc])
                )
            else:
                merged.nodes[nid].setdefault("documents", set()).add(doc)
                if merged.nodes[nid].get("type") == "Konsep" and data.get("type"):
                    merged.nodes[nid]["type"] = data.get("type")

        for u, v, edata in g.edges(data=True):
            rels_new = set(str(edata.get("relations", "")).split(";")) if edata.get("relations") else set()
            rels_new.discard("")
            if merged.has_edge(u, v):
                merged[u][v]["weight"] = merged[u][v].get("weight", 1) + edata.get("weight", 1)
                old = set(str(merged[u][v].get("relations", "")).split(";"))
                old.discard("")
                merged[u][v]["relations"] = ";".join(sorted(old | rels_new))
                merged[u][v].setdefault("documents", set()).add(doc)
            else:
                merged.add_edge(
                    u,
                    v,
                    weight=edata.get("weight", 1),
                    relations=";".join(sorted(rels_new)),
                    documents=set([doc])
                )
    return merged


# =========================================================
# METRICS
# =========================================================
def compute_metrics(g: nx.DiGraph) -> pd.DataFrame:
    cols = ["Id", "Label", "Type", "Degree", "InDegree", "OutDegree", "Betweenness", "Closeness", "PageRank"]

    if g.number_of_nodes() == 0:
        return pd.DataFrame(columns=cols)

    deg = dict(g.degree())
    indeg = dict(g.in_degree())
    outdeg = dict(g.out_degree())

    bet = nx.betweenness_centrality(g, normalized=True)
    clo = nx.closeness_centrality(g)

    try:
        pr = nx.pagerank(g, alpha=0.85)
    except Exception:
        pr = {n: 0.0 for n in g.nodes()}

    rows = []
    for nid, data in g.nodes(data=True):
        rows.append({
            "Id": nid,
            "Label": data.get("label", nid),
            "Type": data.get("type", "Unknown"),
            "Degree": deg.get(nid, 0),
            "InDegree": indeg.get(nid, 0),
            "OutDegree": outdeg.get(nid, 0),
            "Betweenness": bet.get(nid, 0.0),
            "Closeness": clo.get(nid, 0.0),
            "PageRank": pr.get(nid, 0.0),
        })

    df = pd.DataFrame(rows, columns=cols)
    return df.sort_values(["Betweenness", "Degree", "PageRank"], ascending=False).reset_index(drop=True)


def top_k(df: pd.DataFrame, col: str, k: int = 5) -> List[Tuple[str, float, str]]:
    if df.empty:
        return []
    d2 = df.sort_values(col, ascending=False).head(k)
    return [(r["Label"], float(r[col]), r["Type"]) for _, r in d2.iterrows()]


def build_summary(g: nx.DiGraph, df_nodes: pd.DataFrame) -> Dict:
    top_degree = top_k(df_nodes, "Degree", 5)
    top_between = top_k(df_nodes, "Betweenness", 5)
    top_pr = top_k(df_nodes, "PageRank", 5)

    node_type_counts = {}
    for _, data in g.nodes(data=True):
        t = data.get("type", "Unknown")
        node_type_counts[t] = node_type_counts.get(t, 0) + 1

    return {
        "n_nodes": g.number_of_nodes(),
        "n_edges": g.number_of_edges(),
        "node_type_counts": node_type_counts,
        "top_degree": top_degree,
        "top_betweenness": top_between,
        "top_pagerank": top_pr,
    }


# =========================================================
# VISUAL / EXPORT
# =========================================================
def draw_graph(g: nx.DiGraph, out_png: str, title: str = "AJS-Sastra — Jejaring Makna", size=(12, 8)) -> None:
    if g.number_of_nodes() == 0:
        return

    plt.figure(figsize=size)
    pos = nx.spring_layout(g, seed=42)

    type_to_color = {
        "Tokoh": "#4e79a7",
        "Konsep": "#f28e2b",
        "Motif": "#59a14f",
        "Tema": "#e15759",
        "Unknown": "#9c9c9c",
    }

    labels = {n: g.nodes[n].get("label", n) for n in g.nodes()}
    types = {n: g.nodes[n].get("type", "Unknown") for n in g.nodes()}
    deg = dict(g.degree())
    node_sizes = [500 + 180 * deg.get(n, 0) for n in g.nodes()]
    node_colors = [type_to_color.get(types[n], "#9c9c9c") for n in g.nodes()]

    nx.draw_networkx_edges(g, pos, arrows=True, alpha=0.35, width=1.2)
    nx.draw_networkx_nodes(g, pos, node_size=node_sizes, node_color=node_colors, linewidths=0.8, edgecolors="white", alpha=0.95)
    nx.draw_networkx_labels(g, pos, labels=labels, font_size=8)

    plt.title(title, fontsize=14)
    plt.axis("off")
    plt.tight_layout()
    plt.savefig(out_png, dpi=200, bbox_inches="tight")
    plt.close()


def export_global_outputs(g: nx.DiGraph, df_nodes: pd.DataFrame, outdir: str) -> Dict[str, str]:
    ensure_dir(outdir)

    edges_path = os.path.join(outdir, "global_edges.csv")
    with open(edges_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Source", "Relation", "Target", "Weight", "Documents"])
        for u, v, data in g.edges(data=True):
            src = g.nodes[u].get("label", u)
            tgt = g.nodes[v].get("label", v)
            rel = data.get("relations", "")
            weight = data.get("weight", 1)
            docs = "; ".join(sorted(list(data.get("documents", set()))))
            w.writerow([src, rel, tgt, weight, docs])

    nodes_path = os.path.join(outdir, "global_nodes.csv")
    df_export = df_nodes.copy()
    doc_counts = []
    docs_list = []
    for _, row in df_export.iterrows():
        docs = g.nodes[row["Id"]].get("documents", set())
        doc_counts.append(len(docs))
        docs_list.append("; ".join(sorted(list(docs))))
    df_export["DocumentCount"] = doc_counts
    df_export["Documents"] = docs_list
    df_export.to_csv(nodes_path, index=False, encoding="utf-8")

    gexf_path = os.path.join(outdir, "global_graph.gexf")
    g2 = g.copy()
    for n in g2.nodes():
        docs = g2.nodes[n].get("documents", set())
        g2.nodes[n]["documents"] = ";".join(sorted(list(docs)))
    for u, v in g2.edges():
        docs = g2[u][v].get("documents", set())
        g2[u][v]["documents"] = ";".join(sorted(list(docs)))
    nx.write_gexf(g2, gexf_path)

    return {"edges_csv": edges_path, "nodes_csv": nodes_path, "graph_gexf": gexf_path}


# =========================================================
# SINGLE ANALYSIS
# =========================================================
def render_interpretation(parsed: AJSParsed, g: nx.DiGraph, df: pd.DataFrame) -> str:
    top_degree = top_k(df, "Degree", 5)
    top_between = top_k(df, "Betweenness", 5)
    top_pr = top_k(df, "PageRank", 5)

    def fmt_top(items):
        if not items:
            return "- Tidak ada data."
        return "\n".join([f"- **{lab}** ({typ}) — {val:.4f}" for lab, val, typ in items])

    md = []
    md.append("# Laporan Interpretasi Jejaring Semantik (AJS)\n")
    md.append(f"**Sumber data:** {parsed.raw_text}")
    md.append(f"**Ringkas graf:** {g.number_of_nodes()} node, {g.number_of_edges()} relasi (graf berarah).")
    md.append("\n## 1) Pusat perputaran narasi (Degree)\n")
    md.append(fmt_top(top_degree))
    md.append("\n## 2) Jembatan makna (Betweenness)\n")
    md.append(fmt_top(top_between))
    md.append("\n## 3) Simpul paling diacu (PageRank)\n")
    md.append(fmt_top(top_pr))
    return "\n".join(md)


def run_full_analysis(input_xlsx: str, outdir: str, sheet: Optional[str] = None) -> Dict:
    ensure_dir(outdir)
    parsed, df_edges, type_map = load_excel(input_xlsx, sheet_name=sheet)
    g = build_graph(parsed, type_map)
    df_nodes = compute_metrics(g)

    edges_path = os.path.join(outdir, "edges.csv")
    with open(edges_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["Source", "Relation", "Target", "Weight"])
        for u, v, data in g.edges(data=True):
            src = g.nodes[u].get("label", u)
            tgt = g.nodes[v].get("label", v)
            rel = data.get("relations", "")
            weight = data.get("weight", 1)
            w.writerow([src, rel, tgt, weight])

    nodes_path = os.path.join(outdir, "nodes.csv")
    df_nodes.to_csv(nodes_path, index=False, encoding="utf-8")

    gexf_path = os.path.join(outdir, "graph.gexf")
    nx.write_gexf(g, gexf_path)

    graph_png = os.path.join(outdir, "graph.png")
    draw_graph(g, graph_png)

    report = render_interpretation(parsed, g, df_nodes)
    report_path = os.path.join(outdir, "report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(report)

    summary = build_summary(g, df_nodes)

    return {
        "graph": g,
        "nodes": df_nodes,
        "edges": df_edges,
        "summary": summary,
        "graph_png": graph_png.replace("\\", "/"),
        "report_md": report_path.replace("\\", "/"),
        "edges_csv": edges_path.replace("\\", "/"),
        "nodes_csv": nodes_path.replace("\\", "/"),
        "graph_gexf": gexf_path.replace("\\", "/"),
    }


# =========================================================
# MULTI ANALYSIS (UPGRADED)
# =========================================================
def run_multi_analysis(filepaths: List[str], outdir: Optional[str] = None) -> Dict:
    if outdir is None:
        stamp = datetime.now().strftime("multi_%Y%m%d_%H%M%S")
        outdir = os.path.join("outputs", stamp)
    ensure_dir(outdir)

    items = []
    graph_entries = []
    concept_sets: Dict[str, Set[str]] = {}
    errors = []

    for fp in filepaths:
        filename = os.path.basename(fp)
        try:
            parsed, df_edges, type_map = load_excel(fp)
            g = build_graph(parsed, type_map)
            df_nodes = compute_metrics(g)
            summary = build_summary(g, df_nodes)

            item = {
                "filename": filename,
                "n_nodes": g.number_of_nodes(),
                "n_edges": g.number_of_edges(),
                "top_degree": summary["top_degree"][0][0] if summary["top_degree"] else "-",
                "top_betweenness": summary["top_betweenness"][0][0] if summary["top_betweenness"] else "-",
                "top_pagerank": summary["top_pagerank"][0][0] if summary["top_pagerank"] else "-",
                "node_type_counts": summary["node_type_counts"],
            }
            items.append(item)
            graph_entries.append({"filename": filename, "graph": g, "nodes_df": df_nodes})
            concept_sets[filename] = set(g.nodes())

        except Exception as e:
            msg = str(e)
            errors.append({"filename": filename, "error": msg})
            items.append({
                "filename": filename,
                "error": msg,
                "n_nodes": 0,
                "n_edges": 0,
                "top_degree": "-",
                "top_betweenness": "-",
                "top_pagerank": "-",
                "node_type_counts": {},
            })

    if not graph_entries:
        return {
            "items_list": items,
            "table": [],
            "n_files": len(filepaths),
            "errors": errors,
            "shared_concepts": [],
            "bridging_concepts": [],
            "unique_concepts": [],
            "doc_links": [],
            "global_graph_path": None,
            "global_nodes_csv_path": None,
            "global_edges_csv_path": None,
            "global_gexf_path": None,
        }

    global_graph = merge_graphs(graph_entries)
    global_nodes_df = compute_metrics(global_graph)
    global_summary = build_summary(global_graph, global_nodes_df)

    # Shared / bridging concepts
    shared_rows = []
    bridging_rows = []
    unique_rows = []

    df_lookup = global_nodes_df.set_index("Id") if not global_nodes_df.empty else pd.DataFrame()

    for nid, data in global_graph.nodes(data=True):
        docs = sorted(list(data.get("documents", set())))
        row = {
            "label": data.get("label", nid),
            "type": data.get("type", "Konsep"),
            "document_count": len(docs),
            "documents": ", ".join(docs),
            "degree": int(df_lookup.loc[nid, "Degree"]) if nid in df_lookup.index else 0,
            "betweenness": float(df_lookup.loc[nid, "Betweenness"]) if nid in df_lookup.index else 0.0,
            "pagerank": float(df_lookup.loc[nid, "PageRank"]) if nid in df_lookup.index else 0.0,
        }
        if len(docs) > 1:
            shared_rows.append(row)
            bridging_rows.append(row)
        elif len(docs) == 1:
            row["document"] = docs[0]
            unique_rows.append(row)

    shared_rows = sorted(shared_rows, key=lambda x: (-x["document_count"], -x["degree"], -x["pagerank"], x["label"]))[:15]
    bridging_rows = sorted(bridging_rows, key=lambda x: (-x["betweenness"], -x["document_count"], -x["degree"], x["label"]))[:15]
    unique_rows = sorted(unique_rows, key=lambda x: (x["document"], -x["degree"], -x["pagerank"], x["label"]))[:20]

    # Document similarity graph/table
    doc_links = []
    docs = sorted(list(concept_sets.keys()))
    for i in range(len(docs)):
        for j in range(i + 1, len(docs)):
            d1, d2 = docs[i], docs[j]
            s1, s2 = concept_sets[d1], concept_sets[d2]
            inter = len(s1 & s2)
            union = len(s1 | s2) if (s1 | s2) else 1
            jaccard = inter / union
            if inter > 0:
                doc_links.append({
                    "source": d1,
                    "target": d2,
                    "shared_concepts": inter,
                    "jaccard": round(jaccard, 4),
                })
    doc_links = sorted(doc_links, key=lambda x: (-x["shared_concepts"], -x["jaccard"], x["source"], x["target"]))

    # Save outputs
    export_paths = export_global_outputs(global_graph, global_nodes_df, outdir)
    graph_png = os.path.join(outdir, "global_graph.png")
    draw_graph(global_graph, graph_png, title="AJS-Sastra — Jejaring Semantik Lintas Karya", size=(14, 10))

    comparison_df = pd.DataFrame(items)

    return {
        "items_list": items,
        "table": comparison_df.to_dict(orient="records") if not comparison_df.empty else [],
        "n_files": len(filepaths),
        "errors": errors,
        "global_summary": {
            "n_nodes": global_summary["n_nodes"],
            "n_edges": global_summary["n_edges"],
            "top_degree": global_summary["top_degree"],
            "top_betweenness": global_summary["top_betweenness"],
            "top_pagerank": global_summary["top_pagerank"],
        },
        "shared_concepts": shared_rows,
        "bridging_concepts": bridging_rows,
        "unique_concepts": unique_rows,
        "doc_links": doc_links,
        "global_graph_path": os.path.relpath(graph_png, "outputs").replace("\\", "/"),
        "global_nodes_csv_path": os.path.relpath(export_paths["nodes_csv"], "outputs").replace("\\", "/"),
        "global_edges_csv_path": os.path.relpath(export_paths["edges_csv"], "outputs").replace("\\", "/"),
        "global_gexf_path": os.path.relpath(export_paths["graph_gexf"], "outputs").replace("\\", "/"),
    }
