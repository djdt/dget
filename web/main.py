import datetime
import secrets
from pathlib import Path

import numpy as np
from flask import Flask, abort, json, render_template, request, session
from molmass import Formula, FormulaError

from dget import DGet, __version__
from dget.adduct import Adduct
from dget.io import shimadzu, text
from dget.plot import scale_to_match

__web_version__ = "0.25.1"

app = Flask(__name__)
app.config["SECRET_KEY"] = "dev56179e7461961afa552021c4e0957"
app.config["GCLOUD_FIRESTORE"] = False
app.config.from_pyfile("app.cfg", silent=True)
app.config["SESSION_COOKIE_SECURE"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["UPLOAD_PATH"] = "/tmp/uploads"

if app.config["GCLOUD_FIRESTORE"]:
    # If running on google cloud, store some data about runs
    # (id, time, formula, adduct, options)
    from google.cloud import firestore

    fs = firestore.Client()


adducts = [
    "Auto",
    "[M]+",
    "[M+H]+",
    "[M+Na]+",
    "[M+2H]2+",
    "[M]-",
    "[M-H]-",
    "[2M-H]-",
    "[M-2H]2-",
    "[M+Cl]-",
]
delimiters = {"Comma": ",", "Semicolon": ";", "Tab": "\t", "Space": " "}


def get_chart_results(dget: DGet, start: int, end: int) -> dict:
    x = dget.x[start:end]
    y = dget.y[start:end]

    # The deconv prediction
    pred_X = dget.targets
    pred_y = np.convolve(dget.deuteration_probabilites, dget.psf, mode="full")
    pred_y = scale_to_match(x, y, pred_X, pred_y, dget.mass_width)

    # Generate labels D0-Dmax, Dmax + 1-X
    labels = [f"D{i}" for i in range(0, dget.deuterium_count + 1)] + [
        f"D{dget.deuterium_count} + {i}" for i in range(1, dget.psf.size)
    ]

    # Get the isotopic spectra
    spec_x = np.array([i.mz for i in dget.spectrum.values()])
    spec_y = dget.psf
    spec_y = spec_y / spec_y[0] * pred_y[dget.deuterium_count]

    return {
        "x": x.tolist(),
        "y": y.tolist(),
        "pred x": pred_X.tolist(),
        "pred y": pred_y.tolist(),
        "pred labels": labels,
        "spec x": spec_x.tolist(),
        "spec y": spec_y.tolist(),
    }


@app.errorhandler(500)
def handle_error(error):
    return {"error": str(error)}, 500


@app.route("/help")
def help():
    return render_template(
        "help.html", version=__version__, web_version=__web_version__
    )


@app.route("/")
def index():
    if "id" not in session:
        session["id"] = secrets.token_hex(4)

    return render_template(
        "index.html",
        version=__version__,
        web_version=__web_version__,
        adducts=adducts,
        delimiters=delimiters,
    )


@app.post("/report")
def report():
    result = json.loads(request.form["result"])

    return render_template(
        "report.html",
        version=__version__,
        web_version=__web_version__,
        date=datetime.date.today(),
        formula=result["formula"],
        adduct=result["adduct"],
        mz=result["m/z"],
        adduct_mz=result["adduct m/z"],
        deuteration=result["deuteration"] * 100.0,
        error=result["error"] * 100.0,
        ratios={
            s: p * 100.0 for s, p in zip(result["states"], result["probabilities"])
        },
        image=request.form["img"],
    )


@app.post("/api/upload")
def upload():
    if "id" not in session:
        abort(500, description="No ID for session, are cookies enabled?")

    if "data" not in request.files:
        abort(500, description="Missing MS data upload.")

    dir = Path(app.config["UPLOAD_PATH"])
    if not dir.exists():
        dir.mkdir()

    path = dir.joinpath(secrets.token_hex(4))
    request.files["data"].save(path)
    session["upload"] = str(path)
    return {"upload": str(path)}


@app.post("/api/guess_inputs")
def guess_inputs():
    if "upload" not in request.form:
        print("upload not in request")
        if "upload" not in session:
            abort(500, description="No upload found for session or request.")
        path = session["upload"]
    else:
        path = request.form["upload"]

    if shimadzu.is_shimadzu_file(path):
        return shimadzu.get_loadtxt_kws(path)

    return text.guess_loadtxt_kws(path)


@app.post("/api/calculate")
def calculate():
    formula = request.form["formula"]
    if len(formula) == 0:
        abort(500, description="Missing formula.")
    elif formula.count("D") == 0:
        abort(500, description="Formula must contain deuterium.")
    else:
        try:
            formula = Formula(formula)
            _ = formula.monoisotopic_mass
        except FormulaError:
            abort(500, description="Invalid formula.")

    if "upload" not in request.form:
        if "upload" not in session:
            abort(500, description="No upload found for session or request.")
        path = session["upload"]
    else:
        path = request.form["upload"]

    adduct = request.form["adduct"]
    use_auto_adduct = adduct.lower() == "auto" or len(adduct) == 0
    if not use_auto_adduct and not Adduct.is_valid_adduct(adduct):
        abort(500, description="Invalid adduct string.")

    if any(
        len(request.form[x]) == 0
        for x in ["delimiter", "skiprows", "masscol", "signalcol"]
    ):
        abort(500, description="Missing one or more MS data options.")

    loadtxt_kws = {
        "delimiter": request.form["delimiter"],
        "skiprows": request.form.get("skiprows", type=int),
        "usecols": (
            request.form.get("masscol", type=int) - 1,
            request.form.get("signalcol", type=int) - 1,
        ),
    }

    use_align = request.form["align"] == "true"
    use_baseline = request.form["baseline"] == "true"

    cutoff = request.form["cutoff"]
    use_auto_cutoff = cutoff.lower() == "auto" or len(cutoff) == 0

    if use_auto_cutoff:
        cutoff = None
    elif cutoff[0] == "D" and cutoff[1:].isdecimal():
        cutoff = cutoff
    else:
        try:
            cutoff = float(cutoff)
        except ValueError:
            abort(
                500, description="Calculation Cutoff must be 'Auto', a m/z or D{int}."
            )

    try:
        dget = DGet(
            deuterated_formula=formula,
            tofdata=path,
            adduct=adduct if adduct.lower() != "auto" else "[M]+",
            cutoff=cutoff,
            loadtxt_kws=loadtxt_kws,
        )
        if use_auto_adduct:
            dget.adduct, _ = dget.guess_adduct_from_base_peak()
        if use_align:
            _ = dget.align_tof_with_spectra()
        if use_baseline:
            _ = dget.subtract_baseline()

        probabilities = dget.deuteration_probabilites[dget.deuteration_states]
        probabilities /= probabilities.sum()
    except Exception as e:
        abort(500, description=f"Processing error: {e}")

    start, end = np.searchsorted(dget.x, (dget.targets[0], dget.targets[-1]))
    start, end = np.clip((start, end), 0, dget.x.size)
    if start == end:
        abort(500, description="Entire spectra falls outside of m/z range.")
    chart_results = get_chart_results(dget, start, end)

    # Store some information about successful runs
    if app.config["GCLOUD_FIRESTORE"]:
        fs.collection("dget").add(
            {
                "session": session.get("id", "nosession"),
                "timestamp": datetime.datetime.now(),
                "formula": dget.base_name,
                "adduct": dget.adduct.adduct,
                "auto adduct": use_auto_adduct,
                "auto cutoff": use_auto_cutoff,
                "align": use_align,
                "baseline": use_baseline,
            }
        )

    return {
        "chart": chart_results,
        "compound": {
            "formula": dget.base_name,
            "adduct": dget.adduct.adduct,
            "m/z": dget.adduct.base.isotope.mz,
            "adduct m/z": dget.formula.isotope.mz,
            "deuteration": dget.deuteration,
            "error": dget.deuteration_error,
            "states": dget.deuteration_states.tolist(),
            "probabilities": probabilities.tolist(),
        },
    }


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080, debug=True)
