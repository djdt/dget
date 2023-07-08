from io import TextIOWrapper

from io import StringIO

import numpy as np
from flask import Flask, render_template, request

from dget import DGet

app = Flask(__name__)

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

ms_data = None


@app.route("/")
def index():
    return render_template("index.html", adducts=adducts, delimiters=delimiters)


@app.post("/guess_inputs")
def guess_inputs():
    lines = request.form.getlist("lines[]")
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


@app.post("/calculate")
def calculate():
    formula = request.form["formula"]
    file = TextIOWrapper(request.files["data"])
    adduct = request.form["adduct"]
    if adduct == "Auto":
        adduct = None
    loadtxt_kws = {
        "delimiter": request.form["delimiter"],
        "skiprows": request.form.get("skiprows", type=int),
        "usecols": (
            request.form.get("masscol", type=int) - 1,
            request.form.get("signalcol", type=int) - 1,
        ),
    }
    dget = DGet(
        deuterated_formula=formula, tofdata=file, adduct=adduct, loadtxt_kws=loadtxt_kws
    )
    if adduct is None:
        adduct, diff = dget.guess_adduct_from_base_peak()
        dget.adduct = adduct
    if request.form.get("align") == "true":
        offset = dget.align_tof_with_spectra()
    if request.form.get("baseline") == "true":
        baseline = dget.subtract_baseline()

    dx = dget.targets
    dy = np.convolve(dget.deuteration_probabilites, dget.psf, mode="full")
    dy /= dy.max()

    start, end = np.searchsorted(dget.x, (dget.targets[0], dget.targets[-1]))
    x = dget.x[start:end]
    y = dget.y[start:end]
    y /= y.max()

    probabilities = dget.deuteration_probabilites[dget.deuteration_states]
    probabilities /= probabilities.sum()

    return {
        "x": x.tolist(),
        "y": y.tolist(),
        "dx": dx.tolist(),
        "dy": dy.tolist(),
        "formula": dget.base_name,
        "adduct": dget.adduct.adduct,
        "m/z": dget.adduct.base.isotope.mz,
        "adduct m/z": dget.formula.isotope.mz,
        "deuteration": dget.deuteration,
        "states": dget.deuteration_states.tolist(),
        "probabilities": probabilities.tolist(),
    }


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080, debug=True)
