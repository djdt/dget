from io import TextIOWrapper

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
    print(request.form)
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
    if request.form.get("align") == "true":
        offset = dget.align_tof_with_spectra()
    if request.form.get("baseline") == "true":
        baseline = dget.subtract_baseline()

    return {"x": dget.x.tolist(), "y": dget.y.tolist()}

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080, debug=True)
