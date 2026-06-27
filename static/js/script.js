// Oggetto per tenere traccia dei tempi selezionati per ogni pilota
let selectedLapTimes = {};
// Tiene traccia del tempo del primo giro di ogni pilota (sempre escluso dal grafico)
let firstLapTimes = {};
// Tiene traccia di quali piloti hanno richiesto la visualizzazione del grafico
let chartRequested = {};
// Tiene traccia delle istanze Chart.js attive, per poterle distruggere prima di ridisegnare
let chartInstances = {};

function initializeSelectedTimes(pilotIndex, lapTimes) {
    selectedLapTimes[pilotIndex] = [...lapTimes];
    firstLapTimes[pilotIndex] = lapTimes.length > 0 ? lapTimes[0] : null;
    calculateAverageTime(pilotIndex);
    displayFastestAndSlowestLap(pilotIndex, lapTimes);
}

function toggleLapTime(pilotIndex, lapTime, buttonElement) {
    if (!selectedLapTimes[pilotIndex]) {
        selectedLapTimes[pilotIndex] = [];
    }

    const index = selectedLapTimes[pilotIndex].indexOf(lapTime);
    if (index > -1) {
        selectedLapTimes[pilotIndex].splice(index, 1);
        buttonElement.classList.remove('selected');
        buttonElement.classList.add('unselected');
    } else {
        selectedLapTimes[pilotIndex].push(lapTime);
        buttonElement.classList.remove('unselected');
        buttonElement.classList.add('selected');
    }
    calculateAverageTime(pilotIndex);
    displayFastestAndSlowestLap(pilotIndex, selectedLapTimes[pilotIndex]);
    // Aggiorna il grafico solo se il pilota lo ha già richiesto
    renderChartForPilot(pilotIndex);
}

// Mostra/nasconde il grafico di un pilota; lo disegna alla prima richiesta
function toggleChart(pilotIndex, buttonElement) {
    const panel = document.getElementById(`chart-panel-${pilotIndex}`);
    if (!panel) return;

    const isVisible = panel.classList.contains('visible');

    if (isVisible) {
        panel.classList.remove('visible');
        buttonElement.textContent = 'Mostra grafico';
        buttonElement.setAttribute('aria-expanded', 'false');
    } else {
        panel.classList.add('visible');
        buttonElement.textContent = 'Nascondi grafico';
        buttonElement.setAttribute('aria-expanded', 'true');
        chartRequested[pilotIndex] = true;
        renderChartForPilot(pilotIndex);
    }
}

// Disegna (o ridisegna) il grafico di un pilota, escludendo sempre il primo giro
function renderChartForPilot(pilotIndex) {
    if (!chartRequested[pilotIndex]) {
        return; // Il grafico non è mai stato richiesto: non c'è nulla da disegnare
    }

    const times = (selectedLapTimes[pilotIndex] || []).filter(
        time => time !== firstLapTimes[pilotIndex]
    );
    drawChart(pilotIndex, times);
}

function calculateAverageTime(pilotIndex) {
    const averageDisplay = document.getElementById(`average-time-${pilotIndex}`);

    if (!selectedLapTimes[pilotIndex] || selectedLapTimes[pilotIndex].length === 0) {
        averageDisplay.innerText = 'Race pace: Non selezionato';
        return;
    }

    const total = selectedLapTimes[pilotIndex].reduce((sum, time) => sum + timeToSeconds(time), 0);
    const average = total / selectedLapTimes[pilotIndex].length;

    averageDisplay.innerText = 'Race pace: ' + formatTime(average);
}

function timeToSeconds(time) {
    const parts = time.split(':');
    return parseInt(parts[0]) * 60 + parseFloat(parts[1]);
}

function formatTime(seconds) {
    const minutes = Math.floor(seconds / 60);
    const secs = (seconds % 60).toFixed(3);
    return `${minutes}:${secs.padStart(5, '0')}`;
}

function formatTimeWithMilliseconds(seconds) {
    const minutes = Math.floor(seconds / 60);
    const secs = Math.floor(seconds % 60);
    const ms = Math.round((seconds - Math.floor(seconds)) * 1000);
    return `${minutes}:${secs.toString().padStart(2, '0')}:${ms.toString().padStart(3, '0')}`;
}

// Tiene traccia dello stato del pulsante globale "giro 1 per tutti"
let firstLapsExcluded = false;

// Interruttore globale: esclude o riabilita il giro 1 per tutti i piloti
function toggleAllFirstLaps(buttonElement) {
    firstLapsExcluded = !firstLapsExcluded;

    Object.keys(selectedLapTimes).forEach(pilotIndexStr => {
        const pilotIndex = Number(pilotIndexStr);
        const firstLapTime = firstLapTimes[pilotIndex];
        if (firstLapTime == null) return;

        const button = document.querySelector(
            `.pilot[data-pilot-index="${pilotIndex}"] .lap-time[data-lap-index="0"] button`
        );
        const index = selectedLapTimes[pilotIndex].indexOf(firstLapTime);

        if (firstLapsExcluded) {
            // Escludi il giro 1, se non è già escluso
            if (index > -1) {
                selectedLapTimes[pilotIndex].splice(index, 1);
            }
            if (button) {
                button.classList.remove('selected');
                button.classList.add('unselected');
            }
        } else {
            // Riabilita il giro 1, se non è già incluso
            if (index === -1) {
                selectedLapTimes[pilotIndex].unshift(firstLapTime);
            }
            if (button) {
                button.classList.remove('unselected');
                button.classList.add('selected');
            }
        }

        calculateAverageTime(pilotIndex);
        displayFastestAndSlowestLap(pilotIndex, selectedLapTimes[pilotIndex]);
        renderChartForPilot(pilotIndex);
    });

    buttonElement.textContent = firstLapsExcluded
        ? 'Riabilita il giro 1 per tutti i piloti'
        : 'Escludi il giro 1 per tutti i piloti';
    buttonElement.setAttribute('aria-pressed', String(firstLapsExcluded));
}

function drawChart(pilotIndex, lapTimes) {
    const ctx = document.getElementById(`chart-${pilotIndex}`).getContext('2d');

    // Distrugge l'istanza precedente, se presente, prima di ridisegnare sullo stesso canvas
    if (chartInstances[pilotIndex]) {
        chartInstances[pilotIndex].destroy();
    }

    // Converte i tempi in secondi
    const lapTimesInSeconds = lapTimes.map(time => timeToSeconds(time));

    chartInstances[pilotIndex] = new Chart(ctx, {
        type: 'line',
        data: {
            labels: lapTimes.map((_, index) => `Lap ${index + 1}`),
            datasets: [{
                label: 'Lap Times (mm:ss:ms)',
                data: lapTimesInSeconds,
                borderColor: 'rgba(75, 192, 192, 1)',
                borderWidth: 2,
                fill: false,
                tension: 0.1
            }]
        },
        options: {
            scales: {
                x: {
                    title: {
                        display: true,
                        text: 'Laps'
                    }
                },
                y: {
                    title: {
                        display: true,
                        text: 'Laptime (mm:ss:ms)',
                    },
                    ticks: {
                        callback: function(value) {
                            return formatTimeWithMilliseconds(value); // Formatta i valori sull'asse Y
                        }
                    }
                }
            },
            plugins: {
                tooltip: {
                    callbacks: {
                        title: function(tooltipItem) {
                            return `Lap ${tooltipItem[0].label}`;
                        },
                        label: function(tooltipItem) {
                            return `Time: ${formatTimeWithMilliseconds(tooltipItem.raw)}`;
                        }
                    }
                }
            }
        }
    });
}

function displayFastestAndSlowestLap(pilotIndex, lapTimes) {
    const fastestLapDisplay = document.getElementById(`fastest-lap-${pilotIndex}`);
    const slowestLapDisplay = document.getElementById(`slowest-lap-${pilotIndex}`);

    if (!lapTimes || lapTimes.length === 0) {
        fastestLapDisplay.innerText = 'Fastest lap: N/A';
        slowestLapDisplay.innerText = 'Slowest lap: N/A';
        return;
    }

    const lapTimesInSeconds = lapTimes.map(time => timeToSeconds(time));
    const fastestLapTime = Math.min(...lapTimesInSeconds);
    const slowestLapTime = Math.max(...lapTimesInSeconds);

    fastestLapDisplay.innerText = 'Fastest lap: ' + formatTime(fastestLapTime);
    slowestLapDisplay.innerText = 'Slowest lap: ' + formatTime(slowestLapTime);
}