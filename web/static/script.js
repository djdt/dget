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
    fd.append("data", $("#upload")[0].files[0]);
    fd.append("formula", $("#formula").val());
    fd.append("adduct", $("#adduct").val());
    fd.append("delimiter", $("#delimiter").val());
    fd.append("skiprows", $("#skiprows").val());
    fd.append("masscol", $("#masscol").val());
    fd.append("signalcol", $("#signalcol").val());
    fd.append("align", $("#align").prop("checked"));
    fd.append("baseline", $("#baseline").prop("checked"));
    return fd;
}

function updateOutputs(result) {
    var html = `<p>Formula: ${result["formula"]}<br>
        Adduct: ${result["adduct"]}<br>
        m/z: ${result["m/z"].toFixed(4)}<br>
        Adduct m/z: ${result["adduct m/z"].toFixed(4)}<br>
        %Deuteration: ${(result["deuteration"] * 100.0).toFixed(2)} %<br>
        <br>
        Deuteration Ratio Spectra<br>
        `
    html += result["states"].map((s, i) => {
        return `D${s}: ${(result["probabilities"][i] * 100).toFixed(2)} %`
    }).join("<br>");
    html += "</p>";
    $("#output").html(html);
}

var chart;
function createChart(canvas) {
    chart = new Chart(canvas, {
        data: {
            datasets: [
            {
                type: "scatter",
                label: "MS Data",
                borderColor: "black",
                showLine: true,
                pointRadius: 0,
                order: 2,
            },
            {
                type: "scatter",
                label: "Deconvolved Spectra",
                backgroundColor: "#8aa29e",
                pointRadius: 5,
                hoverRadius: 10,
                order: 1,
            },
            ]
        },
        options: {
            maintainAspectRatio: false,
            normalised: true,
            responsive: true,
            resizeDelay: 0,
            spanGaps: true,
            borderJoinStyle: "round",
            scales: {
                x: {
                    title: {
                        display: true,
                        text: "m/z",
                    }
                },
                y: {
                    beginAtZero: true
                }
            },
            plugins: {
                legend: {
                    labels: {
                        usePointStyle: true,
                        filter: function(item, data) {  // remove ms data
                            return item.datasetIndex != 0;
                        },
                    }
                },
                tooltip: {
                    filter: function(item) {  // no interaction on ms data
                        return item.datasetIndex != 0;
                    },
                    callbacks: {
                        label: function(context) {
                            // var index = 
                            var mz = context.parsed.x.toFixed(4);
                            var label = context.dataset.labels[context.dataIndex];
                            if (label.length > 0) {
                                return label + ", " + mz;
                            }
                            return mz;
                        }
                    }
                }
            }
        }
    });
}

function updateChart(mx, my, dx, dy, dlabels, states) {
    chart.data.datasets[0].data = mx.map((x, i) => {
        return {x: x, y: my[i]}
    });
    chart.update("none");
    chart.data.datasets[1].data = dx.map((x, i) => {
        return {x: x, y: dy[i]}
    });
    chart.data.datasets[1].labels = dlabels;
    chart.data.datasets[1].backgroundColor = dlabels.map((l, i) => {
        return states.includes(i) ? "#db5461" : "#8aa29e";
    });
    chart.update();
}

function chartAsImage(x, y) {
    w = chart.width;
    h = chart.height;
    chart.resize(x, y)
    img = chart.toBase64Image()
    chart.resize(w, h);
    return img;
}

window.addEventListener("load", function() {
    createChart(document.getElementById("plot"));
    completeChanged();
    clearResult();
});
