// Oggetto per tenere traccia dei tempi selezionati per ogni pilota
let selectedLapTimes = {};

function initializeSelectedTimes(pilotIndex, lapTimes) {
    selectedLapTimes[pilotIndex] = [...lapTimes];
    calculateAverageTime(pilotIndex);
    drawChart(pilotIndex, lapTimes);
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
    drawChart(pilotIndex, selectedLapTimes[pilotIndex]);
    displayFastestAndSlowestLap(pilotIndex, selectedLapTimes[pilotIndex]);
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

/*
// Funzione per deselezionare il primo giro di tutti i piloti
function deselectFirstLap() {
    for (const pilotIndex in selectedLapTimes) {
        if (selectedLapTimes[pilotIndex].length > 0) {
            const firstLapTime = selectedLapTimes[pilotIndex][0];
            selectedLapTimes[pilotIndex].splice(0, 1); // Rimuovi il primo giro
            // Aggiorna i pulsanti per il primo giro
            const button = document.querySelector(`.pilot[data-pilot-index="${pilotIndex}"] .lap-time button`);
            if (button) {
                button.classList.remove('selected');
                button.classList.add('unselected');
            }
            calculateAverageTime(pilotIndex); // Ricalcola la media
            displayFastestAndSlowestLap(pilotIndex, selectedLapTimes[pilotIndex]); // Ricalcola il giro veloce e lento
        }
    }
}
*/

function drawChart(pilotIndex, lapTimes) {
    const ctx = document.getElementById(`chart-${pilotIndex}`).getContext('2d');

    // Converte i tempi in secondi
    const lapTimesInSeconds = lapTimes.map(time => timeToSeconds(time));

    new Chart(ctx, {
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