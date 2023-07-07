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


@app.post("/upload")
def upload():
    print(request.form)


@app.post("/guess_inputs")
def guess_inputs():
    print(request.form.getlist("lines[]"))

    return ""


@app.post("/calculate")
def calculate():
    print(request.form)
    formula = request.form["formula"]
    file = request.files["upload"]
    adduct = request.form["adduct"]
    if adduct == "Auto":
        adduct = None
    loadtxt_kws = {
        "delimiter": request.form["delimiter"],
        "skiprows": int(request.form["skiprows"]),
        "usecols": (int(request.form["masscol"]), int(request.form["signalcol"])),
    }
    dget = DGet(
        deuterated_formula=formula, tofdata=file, adduct=adduct, loadtxt_kws=loadtxt_kws
    )
    if request.form["align"]:
        offset = dget.align_tof_with_spectra()
    if request.form["baseline"]:
        baseline = dget.subtract_baseline()
    pass


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8080, debug=True)
