#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from flask import Flask, render_template, request, send_file, send_from_directory
import os
from datetime import datetime
from werkzeug.utils import secure_filename

from analysis_engine import run_full_analysis, run_multi_analysis

app = Flask(__name__)

UPLOAD_FOLDER = "uploads"
OUTPUT_FOLDER = "outputs"
SAMPLE_FOLDER = "sample_data"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)
os.makedirs(SAMPLE_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

@app.route("/")
def index():
    sample_files = []
    if os.path.exists(SAMPLE_FOLDER):
        sample_files = sorted(os.listdir(SAMPLE_FOLDER))
    return render_template("index.html", samples=sample_files)

@app.route("/outputs/<path:filepath>")
def serve_output(filepath):
    return send_from_directory(OUTPUT_FOLDER, filepath)

@app.route("/download/<path:filepath>")
def download(filepath):
    return send_file(filepath, as_attachment=True)

@app.route("/analyze_single", methods=["POST"])
def analyze_single():
    file = request.files.get("file")
    if not file or file.filename == "":
        return "No file uploaded", 400

    filename = secure_filename(file.filename)
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    file.save(filepath)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = os.path.splitext(filename)[0]
    outdir = os.path.join(OUTPUT_FOLDER, f"{base_name}_{timestamp}")

    result = run_full_analysis(filepath, outdir)

    graph_relpath = os.path.relpath(result["graph_png"], OUTPUT_FOLDER).replace("\\", "/")
    report_relpath = os.path.relpath(result["report_md"], OUTPUT_FOLDER).replace("\\", "/")
    nodes_relpath = os.path.relpath(result["nodes_csv"], OUTPUT_FOLDER).replace("\\", "/")
    edges_relpath = os.path.relpath(result["edges_csv"], OUTPUT_FOLDER).replace("\\", "/")
    gexf_relpath = os.path.relpath(result["graph_gexf"], OUTPUT_FOLDER).replace("\\", "/")

    return render_template(
        "result_single.html",
        nodes=result["nodes"].to_dict(orient="records"),
        summary=result["summary"],
        graph_path=graph_relpath,
        report_path=report_relpath,
        nodes_csv_path=nodes_relpath,
        edges_csv_path=edges_relpath,
        gexf_path=gexf_relpath
    )

@app.route("/analyze_multi", methods=["POST"])
def analyze_multi():
    files = request.files.getlist("files")
    if not files or all(f.filename == "" for f in files):
        return "No files uploaded", 400

    paths = []
    for f in files:
        if f and f.filename:
            filename = secure_filename(f.filename)
            filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            f.save(filepath)
            paths.append(filepath)

    timestamp = datetime.now().strftime("multi_%Y%m%d_%H%M%S")
    outdir = os.path.join(OUTPUT_FOLDER, timestamp)
    result = run_multi_analysis(paths, outdir=outdir)
    return render_template("result_multi.html", comparison=result)

if __name__ == "__main__":
    app.run(debug=True, port=5001)
