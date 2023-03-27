import matplotlib.pyplot as plt
from pyodide.ffi import create_proxy
from pathlib import Path
from dget import DGet

def parse_inputs() -> dict | None:
    inputs = {"formula": Element('formula').value}
    inputs['delimiter'] = js.document.querySelector("[name='delimiter']:checked").value
    if inputs['delimiter'] == "tab":
        inputs['delimiter'] = "\t"
    inputs['skiprows'] = int(Element('skiprows').value or 0)
    masscol = int(Element('masscol').value or 1) - 1
    signalcol = int(Element('signalcol').value or 1) - 1
    inputs['usecols'] = (masscol, signalcol)
    return inputs

def run():
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
        print(e)
        return

    fig, ax = plt.subplots(1, 1, figsize=(5,3))
    dget.plot_predicted_spectra(ax)
    fig.tight_layout()
    display(fig, target="figure", append=False)
    # Clear the terminal
    js.document.getElementsByClass("py-termial")[0].innerHTML = ""
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
    path = Path("data.csv")
    with Path("data.csv").open("w") as fp:
        fp.write(text)

proxy = create_proxy(get_ms_data)
js.document.getElementById("file").addEventListener("change", proxy, False)
