var chart;

Chart.Interaction.modes.nearestInRadius = function(chart, e, options, useFinalPosition) {
    // Mode to select nearest point inside interaction
    // Use with pointHitRadius and filters points with pointHitRadius<=0
    items = Chart.Interaction.modes.point(chart, e, options, useFinalPosition);
    items = items.filter(item => item.element.options.hitRadius > 0);
    if (items.length < 2) {
        return items;
    }

    let min_dist = Number.POSITIVE_INFINITY;
    let index = 0;
    const pos = Chart.helpers.getRelativePosition(e, chart);
    items.forEach(function (item, i) {
        const center = item.element.getCenterPoint(useFinalPosition);
        const dist = Math.sqrt(
            Math.pow(Math.abs(pos.x - center.x), 2)
            + Math.pow(Math.abs(pos.y - center.y), 2)
        );
        if (dist < min_dist) {
            min_dist = dist;
            index = i;
        }
    });
    return [items[index]];
}

function createChart(canvas) {
    chart = new Chart(canvas, {
        data: {
            datasets: [
            {
                type: "scatter",
                label: "MS Data",
                animation: false,
                borderColor: "black",
                borderWidth: 1,
                order: 3,
                pointHitRadius: 0,
                pointRadius: 0,
                showLine: true,
            },
            {
                type: "scatter",
                label: "Deconvolution",
                backgroundColor: "#db5461",
                hoverBackgroundColor: "#db5461",
                hoverRadius: 8,
                order: 1,
                pointHitRadius: 10,
                pointRadius: 4,
            },
            {
                type: "scatter",
                label: "Isotope Spectra",
                backgroundColor: "#ffffff00",
                borderColor: "#364699",
                borderWidth: 2,
                hoverRadius: 0,
                order: 2,
                pointHitRadius: 0,
                pointRadius: 6,
                pointStyle: "circle",
            },
            ]
        },
        options: {
            maintainAspectRatio: false,
            responsive: true,
            resizeDelay: 0,
            spanGaps: true,
            borderJoinStyle: "round",
            scales: {
                x: {
                    title: {
                        display: true,
                        text: "m/z",
                    },
                    grid: {
                        display: false,
                    },
                },
                y: {
                    ticks: {
                        callback: (v) => (v.toExponential()),
                    },
                    beginAtZero: true,
                    grid: {
                        display: false,
                    },
                }
            },
            interaction: {
                intersect: true,
                mode: "nearestInRadius",
            },
            plugins: {
                legend: {
                    // display: false,
                    labels: {
                        usePointStyle: true,
                        filter: function(item, data) {  // remove ms data
                            return item.datasetIndex != 0;
                        },
                        generateLabels: function(chart) { // override green color
                            var labels = Chart.Legend.defaults.labels.generateLabels(chart);
                            return labels.map((label, i) => {
                                if (label.fillStyle == "#8aa29e") {
                                    label.fillStyle = "#db5461";
                                }
                                return label;
                            });
                        },
                    }
                },
                subtitle: {
                    display: true,
                    position: "right",
                    text: "DGet! (doi:10.1186/s13321-024-00828-x)"
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
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

function updateChartData(x, y) {
    chart.data.datasets[0].data = x.map((ix, i) => {
        return {x: ix, y: y[i]}
    });
    chart.update("none");
}

function updateChartPrediction(x, y, labels, states) {
    chart.data.datasets[1].data = x.map((ix, i) => {
        return {x: ix, y: y[i]}
    });
    chart.data.datasets[1].labels = labels;
    const max_state = Math.max.apply(null, states);
    chart.data.datasets[1].backgroundColor = x.map((_, i) => {
        return states.includes(i) || ((max_state > 0) && (i > max_state)) ? "#db5461" : "#8aa29e";
    });
    chart.update();
}

function updateChartSpectra(x, y) {
    chart.data.datasets[2].data = x.map((ix, i) => {
        return {x: ix, y: y[i]}
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
