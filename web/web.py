from pathlib import Path

import matplotlib.pyplot as plt
from pyodide.ffi import create_proxy
from pyscript import display, js

from dget import DGet

delimiters = {"comma": ",", "semicolon": ";", "tab": "\t", "space": " "}


def parse_inputs() -> dict | None:
    inputs = {"formula": js.document.getElementById("formula").value}

    inputs["delimiter"] = delimiters[js.document.getElementById("delimiter").value]

    inputs["skiprows"] = int(js.document.getElementById("skiprows").value or 0)

    masscol = int(js.document.getElementById("masscol").value or 1) - 1
    signalcol = int(js.document.getElementById("signalcol").value or 1) - 1
    inputs["usecols"] = (masscol, signalcol)

    return inputs


def guess_inputs(path: Path) -> None:
    with path.open("r") as fp:
        lines = fp.readlines(2048)[:20]

    # Check lines 10 to 20 -> for delimiter
    for key, val in delimiters.items():
        if all(val in line for line in lines[10:]):
            js.document.getElementById("delimiter").value = key
            break

    # Check for first line able to be parsed
    skiprows = 0
    for line in lines:
        try:
            float(line.split(val)[-1])
            break
        except ValueError:
            pass
        skiprows += 1

    js.document.getElementById("skiprows").value = str(skiprows)

    header = lines[skiprows - 1].split(val)
    for i, text in enumerate(header):
        if any(x in text.lower() for x in ["mass", "m/z"]):
            js.document.getElementById("masscol").value = i
        if any(x in text.lower() for x in ["signal", "intensity", "counts"]):
            js.document.getElementById("signalcol").value = i


def run():
    # Clear the terminal
    js.document.getElementsByClassName("py-terminal")[0].innerHTML = ""

    inputs = parse_inputs()
    path = Path("data.csv")
    if inputs["formula"] == "":
        print("Error: invalid formula input.")
        return
    if inputs["usecols"][0] == inputs["usecols"][1]:
        print("Error: signal and massmcolumns cannot be the same.")
        return
    if not path.exists():
        print("Error: no file uploaded.")
        return

    try:
        dget = DGet(inputs.pop("formula"), path, loadtxt_kws=inputs)
    except Exception as e:
        print("Error:", e)
        return

    fig, ax = plt.subplots(1, 1, figsize=(5, 3))
    dget.plot_predicted_spectra(ax)
    fig.tight_layout()
    display(fig, target="figure", append=False)

    print(f"Formula          : {dget.formula}")
    print(f"M/Z              : {dget.formula.mz}")
    print(f"Monoisotopic M/Z : {dget.formula.isotope.mz}")
    print(f"%D               : {dget.deuteration * 100.0:.2f}")
    print()
    print("Deuteration Ratio Spectra")
    for i, p in enumerate(dget.deuteration_probabilites):
        print(f"D{i:<2}              : {p:.4f}")


async def get_ms_data(event):
    file = event.target.files.item(0)
    text = await file.text()
    with Path("data.csv").open("w") as fp:
        fp.write(text)
    guess_inputs(Path("data.csv"))


proxy = create_proxy(get_ms_data)
js.document.getElementById("file").addEventListener("change", proxy, False)