const videoElement = document.getElementById("videoElement");
const statusLabel = document.getElementById("statusLabel");
const startButton = document.getElementById("startButton");
const stopButton = document.getElementById("stopButton");
const overlayCanvas = document.getElementById("overlayCanvas");
const ctx = overlayCanvas.getContext("2d");

let streamInterval;
let isProcessing = false;
const processingCanvas = document.createElement("canvas");
const processingCtx = processingCanvas.getContext("2d");
let lastFrameTime = 0;
const MIN_FRAME_INTERVAL = 100;

function updateOverlayCanvas() {
    // Match overlay canvas size to video dimensions
    overlayCanvas.width = videoElement.videoWidth;
    overlayCanvas.height = videoElement.videoHeight;
}

function drawFaceBoxes(faces) {
    // Clear previous drawings
    ctx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height);

    // Update canvas size if needed
    updateOverlayCanvas();

    faces.forEach(face => {
        const [x1, y1, x2, y2] = face.box;
        const name = face.name;
        const boxWidth = x2 - x1;
        const boxHeight = y2 - y1;

        // Draw box with thicker border
        ctx.lineWidth = 3;
        ctx.strokeStyle = name === "Unknown" ? "#ff0000" : "#00ff00";
        ctx.strokeRect(x1, y1, boxWidth, boxHeight);

        // Add inner box for better visibility
        ctx.lineWidth = 1;
        ctx.strokeStyle = "rgba(255, 255, 255, 0.5)";
        ctx.strokeRect(x1 + 2, y1 + 2, boxWidth - 4, boxHeight - 4);

        // Improved name label
        ctx.font = "bold 16px Arial";
        const textMetrics = ctx.measureText(name);
        const textWidth = textMetrics.width;
        const textHeight = 20;
        const padding = 8;
        const labelWidth = textWidth + (padding * 2);

        // Position label above face box with proper spacing
        let labelY = y1 - textHeight - 5;
        // If too close to top, position below the box
        if (labelY < 10) {
            labelY = y2 + 5;
        }

        // Draw label background with rounded corners
        ctx.fillStyle = name === "Unknown" ? "rgba(255, 0, 0, 0.85)" : "rgba(0, 255, 0, 0.85)";
        roundRect(
            ctx,
            x1,
            labelY,
            labelWidth,
            textHeight + (padding / 2),
            5
        );

        // Draw label text
        ctx.fillStyle = "#000000";
        ctx.fillText(
            name,
            x1 + padding,
            labelY + textHeight - (padding / 2)
        );
    });
}

// Helper function to draw rounded rectangles
function roundRect(ctx, x, y, width, height, radius) {
    ctx.beginPath();
    ctx.moveTo(x + radius, y);
    ctx.lineTo(x + width - radius, y);
    ctx.quadraticCurveTo(x + width, y, x + width, y + radius);
    ctx.lineTo(x + width, y + height - radius);
    ctx.quadraticCurveTo(x + width, y + height, x + width - radius, y + height);
    ctx.lineTo(x + radius, y + height);
    ctx.quadraticCurveTo(x, y + height, x, y + height - radius);
    ctx.lineTo(x, y + radius);
    ctx.quadraticCurveTo(x, y, x + radius, y);
    ctx.closePath();
    ctx.fill();
}

// WebSocket connection setup
const socket = io('http://127.0.0.1:5000');
let isConnected = false;

socket.on('connect', () => {
    console.log('Connected to recognition server');
    isConnected = true;
    statusLabel.textContent = 'Status: Connected to recognition server';
});

socket.on('disconnect', () => {
    console.log('Disconnected from recognition server');
    isConnected = false;
    statusLabel.textContent = 'Status: Disconnected from server';
});

socket.on('recognition_result', (data) => {
    if (data.error) {
        console.error('Recognition error:', data.error);
        statusLabel.textContent = `Status: Error - ${data.error}`;
        ctx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height);
        return;
    }

    if (Array.isArray(data.faces)) {
        statusLabel.textContent = `Status: Detected ${data.faces.length} face(s)`;
        drawFaceBoxes(data.faces);
    } else {
        statusLabel.textContent = "Status: No face detected";
        ctx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height);
    }
});

async function processFrame() {
    if (isProcessing || !videoElement.srcObject || !isConnected) return;

    const currentTime = Date.now();
    if (currentTime - lastFrameTime < MIN_FRAME_INTERVAL) return;

    isProcessing = true;
    lastFrameTime = currentTime;

    try {
        // Match processing canvas size to video dimensions
        processingCanvas.width = videoElement.videoWidth;
        processingCanvas.height = videoElement.videoHeight;

        // Draw the current video frame onto the canvas
        processingCtx.drawImage(videoElement, 0, 0, processingCanvas.width, processingCanvas.height);

        // Apply sharpening filter
        const imageData = processingCtx.getImageData(0, 0, processingCanvas.width, processingCanvas.height);
        const sharpenedData = applySharpeningFilter(imageData);
        processingCtx.putImageData(sharpenedData, 0, 0);

        // Convert canvas to base64 string
        const base64Frame = processingCanvas.toDataURL('image/jpeg', 0.9);

        // Send frame through WebSocket if connected
        if (isConnected) {
            socket.emit('frame', base64Frame);
        } else {
            statusLabel.textContent = 'Status: Not connected to server';
            ctx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height);
        }

    } catch (err) {
        console.error("Error:", err);
        statusLabel.textContent = "Status: Error processing frame";
        ctx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height);
    } finally {
        isProcessing = false;
    }
}

// // Helper function to draw face boxes and labels
// function drawFaceBoxes(faces) {
//     ctx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height);
//
//     faces.forEach(face => {
//         const [x, y, x2, y2] = face.box;
//         const width = x2 - x;
//         const height = y2 - y;
//
//         // Draw box
//         ctx.strokeStyle = face.name === "Unknown" ? "#ff0000" : "#00ff00";
//         ctx.lineWidth = 2;
//         ctx.strokeRect(x, y, width, height);
//
//         // Draw label background
//         ctx.fillStyle = "rgba(0, 0, 0, 0.7)";
//         const labelText = `${face.name} ${face.confidence ? `(${(face.confidence * 100).toFixed(1)}%)` : ''}`;
//         const textWidth = ctx.measureText(labelText).width;
//         ctx.fillRect(x, y - 25, textWidth + 10, 25);
//
//         // Draw label text
//         ctx.fillStyle = "#ffffff";
//         ctx.font = "16px Arial";
//         ctx.fillText(labelText, x + 5, y - 7);
//     });
// }

// Optional: Add reconnection logic
let reconnectAttempts = 0;
const MAX_RECONNECT_ATTEMPTS = 5;

function attemptReconnect() {
    if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
        reconnectAttempts++;
        statusLabel.textContent = `Status: Reconnecting (Attempt ${reconnectAttempts})...`;
        socket.connect();
    } else {
        statusLabel.textContent = 'Status: Failed to reconnect to server';
    }
}

socket.on('connect_error', (error) => {
    console.error('Connection error:', error);
    statusLabel.textContent = 'Status: Connection error';
    setTimeout(attemptReconnect, 2000);
});

socket.on('connect', () => {
    reconnectAttempts = 0;
});

// Sharpening filter function
function applySharpeningFilter(imageData) {
    const weights = [0, -1, 0, -1, 5, -1, 0, -1, 0]; // Sharpen kernel
    const side = Math.round(Math.sqrt(weights.length));
    const halfSide = Math.floor(side / 2);

    const src = imageData.data;
    const sw = imageData.width;
    const sh = imageData.height;

    const output = new Uint8ClampedArray(src.length);
    const w = sw;
    const h = sh;

    for (let y = 0; y < h; y++) {
        for (let x = 0; x < w; x++) {
            const dstOffset = (y * w + x) * 4;

            let r = 0, g = 0, b = 0;
            for (let cy = 0; cy < side; cy++) {
                for (let cx = 0; cx < side; cx++) {
                    const scy = Math.min(sh - 1, Math.max(0, y + cy - halfSide));
                    const scx = Math.min(sw - 1, Math.max(0, x + cx - halfSide));
                    const srcOffset = (scy * sw + scx) * 4;

                    const weight = weights[cy * side + cx];
                    r += src[srcOffset] * weight;
                    g += src[srcOffset + 1] * weight;
                    b += src[srcOffset + 2] * weight;
                }
            }

            output[dstOffset] = Math.min(255, Math.max(0, r));
            output[dstOffset + 1] = Math.min(255, Math.max(0, g));
            output[dstOffset + 2] = Math.min(255, Math.max(0, b));
            output[dstOffset + 3] = src[dstOffset + 3]; // Alpha channel
        }
    }

    return new ImageData(output, sw, sh);
}


function startVideoProcessing() {
    if (!streamInterval) {
        streamInterval = setInterval(processFrame, MIN_FRAME_INTERVAL);
    }
}

async function initializeVideo() {
    try {
        statusLabel.textContent = "Starting face recognition...";
        startButton.disabled = true;
        stopButton.disabled = false;

        const stream = await navigator.mediaDevices.getUserMedia({
            video: {
                width: { ideal: 640 },
                height: { ideal: 480 }
            }
        });

        videoElement.srcObject = stream;
        await videoElement.play();

        // Initialize overlay canvas size
        updateOverlayCanvas();

        startVideoProcessing();
    } catch (err) {
        console.error("Error accessing camera:", err);
        statusLabel.textContent = "Error: Could not access camera";
        startButton.disabled = false;
    }
}

startButton.addEventListener("click", initializeVideo);

stopButton.addEventListener("click", () => {
    statusLabel.textContent = "Face recognition stopped";
    startButton.disabled = false;
    stopButton.disabled = true;

    clearInterval(streamInterval);
    streamInterval = null;
    isProcessing = false;

    const stream = videoElement.srcObject;
    if (stream) {
        stream.getTracks().forEach(track => track.stop());
    }
    videoElement.srcObject = null;
    ctx.clearRect(0, 0, overlayCanvas.width, overlayCanvas.height);
});