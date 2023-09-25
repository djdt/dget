function isComplete() {
    var formula = $("#formula").val();
    if (formula.length == 0 || !formula.includes("D")) {
        return false;
    }
    // if ($("#adduct").val().length == 0) {
    //     return false;
    // }
    if ($("#upload")[0].files.length == 0) {
        return false;
    }
    return true;
}

function completeChanged() {
    var complete = isComplete();
    $("#calculate").prop("disabled", !complete);
}

var result;
function clearResult() {
    result = null;
    $("button#report").prop("disabled", true);
}
function storeResult(res) {
    result = res;
    $("button#report").prop("disabled", false);
}

function getFormData() {
    var fd = new FormData();
    fd.append("formula", $("#formula").val());
    fd.append("adduct", $("#adduct").val());
    fd.append("delimiter", $("#delimiter").val());
    fd.append("skiprows", $("#skiprows").val());
    fd.append("masscol", $("#masscol").val());
    fd.append("signalcol", $("#signalcol").val());
    fd.append("align", $("#align").prop("checked"));
    fd.append("baseline", $("#baseline").prop("checked"));
    fd.append("cutoff", $("#cutoff").val());
    return fd;
}

function updateOutputs(result) {
    var html = `<p>Formula: ${result["formula"]}<br>
        Adduct: ${result["adduct"]}<br>
        m/z: ${result["m/z"].toFixed(4)}<br>
        Adduct m/z: ${result["adduct m/z"].toFixed(4)}<br>
        %Deuteration: ${(result["deuteration"] * 100.0).toFixed(2)} ± ${(result["error"] * 100.0).toFixed(2)} %<br>
        <br>
        Deuteration Ratio Spectra<br>
        `
    html += result["states"].map((s, i) => {
        return `D${s}: ${(result["probabilities"][i] * 100).toFixed(2)} %`
    }).join("<br>");
    html += "</p>";
    $("#output").html(html);
}

window.addEventListener("load", function() {
    completeChanged();
    clearResult();
});
