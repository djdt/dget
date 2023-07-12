import datetime
from io import TextIOWrapper

import numpy as np
from flask import Flask, abort, json, render_template, request
from google.cloud import firestore

from dget import DGet, __version__
from dget.plot import scale_to_match

app = Flask(__name__)
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
    return render_template("help.html", version=__version__)


@app.route("/")
def index():
    return render_template(
        "index.html", version=__version__, adducts=adducts, delimiters=delimiters
    )


@app.post("/report")
def report():
    result = json.loads(request.form["result"])
    return render_template(
        "report.html",
        version=__version__,
        date=datetime.date.today(),
        formula=result["formula"],
        adduct=result["adduct"],
        mz=result["m/z"],
        adduct_mz=result["adduct m/z"],
        deuteration=result["deuteration"] * 100.0,
        ratios={
            s: p * 100.0 for s, p in zip(result["states"], result["probabilities"])
        },
        image=request.form["img"],
    )


@app.post("/api/guess_inputs")
def guess_inputs():
    lines = request.form.getlist("lines[]")
    if len(lines) == 0:
        raise ValueError("Text not uploaded.")
    result = {}

    # find delimiter
    for key, val in delimiters.items():
        if all(val in line for line in lines[10:]):
            result["delimiter"] = val
            break

    if "delimiter" in result:
        result["skiprows"] = 0
        # check for first line able to be parsed
        for line in lines:
            try:
                float(line.split(result["delimiter"])[-1])
                break
            except ValueError:
                pass
            result["skiprows"] = result["skiprows"] + 1

        # try to find the signal / mass columns
        header_line = lines[result["skiprows"] - 1].split(result["delimiter"])
        for i, text in enumerate(header_line):
            if any(x in text.lower() for x in ["mass", "m/z"]):
                result["masscol"] = i
            if any(x in text.lower() for x in ["signal", "intensity", "counts"]):
                result["signalcol"] = i

    return result


@app.post("/api/calculate")
def calculate():
    formula = request.form["formula"]
    if len(formula) == 0 or formula.count("D") == 0:
        abort(500, description="Missing or invalid formula.")

    if "data" not in request.files:
        abort(500, description="Missing MS data upload.")

    file = TextIOWrapper(request.files["data"])

    adduct = request.form["adduct"]
    if len(adduct) == 0:
        abort(500, description="Missing or invalid adduct.")

    loadtxt_kws = {
        "delimiter": request.form["delimiter"],
        "skiprows": request.form.get("skiprows", type=int),
        "usecols": (
            request.form.get("masscol", type=int) - 1,
            request.form.get("signalcol", type=int) - 1,
        ),
    }

    cutoff = request.form.get("cutoff")
    if cutoff.lower() == "auto":
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
            tofdata=file,
            adduct=adduct if adduct.lower() != "auto" else "[M]+",
            cutoff=cutoff,
            loadtxt_kws=loadtxt_kws,
        )
        if adduct == "Auto":
            _adduct, _ = dget.guess_adduct_from_base_peak()
            dget.adduct = _adduct
        if request.form.get("align") == "true":
            _ = dget.align_tof_with_spectra()
        if request.form.get("baseline") == "true":
            _ = dget.subtract_baseline()

        probabilities = dget.deuteration_probabilites[dget.deuteration_states]
        probabilities /= probabilities.sum()
    except Exception as e:
        abort(500, description=f"Processing error: {e}")

    start, end = np.searchsorted(dget.x, (dget.targets[0], dget.targets[-1]))
    start, end = np.clip((start, end), 0, dget.x.size)
    if start == end:
        abort(500, description="Enitre m/z range falls outside of spetra.")

    chart_results = get_chart_results(dget, start, end)
    # Store some information about successful runs
    fs.collection("dget").add(
        {
            "timestamp": datetime.datetime.now(),
            "formula": dget.base_name,
            "adduct": dget.adduct.adduct,
        }
    )

    chart_results = get_chart_results(dget, start, end)
    return {
        "chart": chart_results,
        "compound": {
            "formula": dget.base_name,
            "adduct": dget.adduct.adduct,
            "m/z": dget.adduct.base.isotope.mz,
            "adduct m/z": dget.formula.isotope.mz,
            "deuteration": dget.deuteration,
            "states": dget.deuteration_states.tolist(),
            "probabilities": probabilities.tolist(),
        }
    }


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080, debug=True)
