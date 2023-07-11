var chart;

// Chart.Interaction.modes.nearestWithRadius = function(chart, e, options, useFinalPosition) {
//     items = Chart.Interaction.modes.nearest(chart, e, options, useFinalPosition);
//     console.log(items);
//     return items.filter(item => item.element.options.radius > 0);
// }

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
                animation: false,
                hoverRadius: 0,
            },
            {
                type: "scatter",
                label: "Deconvolved Spectra",
                backgroundColor: "#db5461",
                pointRadius: 4,
                hoverRadius: 8,
                order: 1,
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
                    }
                },
                y: {
                    ticks: {
                        callback: (v) => (v.toExponential());
                    },
                    beginAtZero: true,
                }
            },
            interaction: {
                intersect: false,
                mode: "point",
            },
            plugins: {
                legend: {
                    display: false,
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
    // chart.data.datasets[1].backgroundColor = dlabels.map((l, i) => {
    //     return states.includes(i) ? "#db5461" : "#8aa29e";
    // });
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
