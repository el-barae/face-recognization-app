const videoElement = document.getElementById("videoElement");
const captureButton = document.getElementById("captureButton");
const submitButton = document.getElementById("submitButton");
const statusLabel = document.getElementById("statusLabel");
const capturesGrid = document.getElementById("capturesGrid");

let autoCaptureActive = false;
let capturedFaces = [];
const maxCaptures = 20;

// Initialize webcam stream
navigator.mediaDevices.getUserMedia({ video: true })
    .then((stream) => {
        videoElement.srcObject = stream;
    })
    .catch((err) => {
        console.error("Error accessing webcam:", err);
        statusLabel.textContent = "Status: Webcam access denied";
    });

// Toggle auto-capture functionality
captureButton.addEventListener("click", () => {
    autoCaptureActive = !autoCaptureActive;

    if (autoCaptureActive) {
        captureButton.textContent = "Stop Auto-Capture";
        statusLabel.textContent = "Status: Auto-capture started...";
        capturedFaces = [];
        capturesGrid.innerHTML = ""; // Clear the grid for new captures
        startAutoCapture();
    } else {
        captureButton.textContent = "Start Auto-Capture";
        statusLabel.textContent = "Status: Auto-capture stopped.";
    }
});

// Start auto-capture process
async function startAutoCapture() {
    if (!autoCaptureActive || capturedFaces.length >= maxCaptures) {
        return;
    }

    const canvas = document.createElement("canvas");
    canvas.width = videoElement.videoWidth;
    canvas.height = videoElement.videoHeight;
    const ctx = canvas.getContext("2d");

    // Draw the video frame into the canvas
    ctx.drawImage(videoElement, 0, 0, canvas.width, canvas.height);

    // Use a face detection library or custom detection logic
    const detectedFaces = await detectFaces(canvas); // Replace with actual detection logic

    detectedFaces.forEach((face) => {
        const { x, y, width, height } = face;

        // Crop the face from the canvas
        const faceCanvas = document.createElement("canvas");
        faceCanvas.width = width;
        faceCanvas.height = height;
        const faceCtx = faceCanvas.getContext("2d");
        faceCtx.drawImage(canvas, x, y, width, height, 0, 0, width, height);

        // Convert cropped face to data URL
        const faceImage = faceCanvas.toDataURL("image/jpeg");
        capturedFaces.push(faceImage);

        // Display captured face in the grid
        const img = document.createElement("img");
        img.src = faceImage;
        img.alt = `Captured face ${capturedFaces.length}`;
        capturesGrid.appendChild(img);

        statusLabel.textContent = `Status: Auto-captured ${capturedFaces.length} of ${maxCaptures} faces`;

        if (capturedFaces.length >= maxCaptures) {
            autoCaptureActive = false;
            captureButton.textContent = "Start Auto-Capture";
            submitButton.disabled = false;
            statusLabel.textContent = "Status: Auto-capture completed.";
        }
    });

    if (autoCaptureActive) {
        setTimeout(startAutoCapture, 1000); // Adjust the interval as needed
    }
}

// Mock function for face detection (replace with actual logic or library)
async function detectFaces(canvas) {
    // Simulating face detection
    return [
        {
            x: canvas.width / 4 - 40,
            y: canvas.height / 4 - 40,
            width: canvas.width / 2 +  40* 2,
            height: canvas.height / 2 + 40 * 2,
        },
    ];
}


// Submit captured faces to the server
submitButton.addEventListener("click", () => {
    if (capturedFaces.length === 0) {
        alert("No faces to submit!");
        return;
    }

    // Collect form data
    const name = document.getElementById("name").value.trim();
    const age = document.getElementById("age").value.trim();
    const gender = document.getElementById("gender").value.trim();

    if (!name || !age || !gender) {
        alert("All fields are required!");
        return;
    }

    // Send captured faces and form data to the server
    fetch("/submit_faces", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
            name,
            age,
            gender,
            faces: capturedFaces,
        }),
    })
        .then((response) => {
            if (!response.ok) {
                throw new Error("Failed to submit faces");
            }
            return response.json();
        })
        .then((data) => {
            alert(data.message || "Faces submitted successfully!");
            capturedFaces = [];
            capturesGrid.innerHTML = "";
            submitButton.disabled = true;
            validateForm(); // Revalidate the form after submission
        })
        .catch((err) => {
            console.error("Error submitting faces:", err);
            alert("Failed to submit faces. Please try again.");
        });
});

// Form validation
const validateForm = () => {
    const name = document.getElementById("name").value.trim();
    const age = document.getElementById("age").value.trim();
    const gender = document.getElementById("gender").value.trim();
    const capturedFacesCount = capturesGrid.children.length;

    // Enable submit button only if all fields are filled and at least one face is captured
    submitButton.disabled = !(name && age && gender && capturedFacesCount > 0);
};

// Attach input event listeners for form validation
document.querySelectorAll("input").forEach((input) => {
    input.addEventListener("input", validateForm);
});




// const videoElement = document.getElementById("videoElement");
// const captureButton = document.getElementById("captureButton");
// const submitButton = document.getElementById("submitButton");
// const statusLabel = document.getElementById("statusLabel");
// const capturesGrid = document.getElementById("capturesGrid");
//
// let autoCaptureActive = false;
// let capturedFaces = [];
// const maxCaptures = 20;
//
// // Initialize webcam stream
// navigator.mediaDevices.getUserMedia({ video: true })
//     .then((stream) => {
//         videoElement.srcObject = stream;
//     })
//     .catch((err) => {
//         console.error("Error accessing webcam:", err);
//         statusLabel.textContent = "Status: Webcam access denied";
//     });
//
// // Toggle auto-capture functionality
// captureButton.addEventListener("click", () => {
//     autoCaptureActive = !autoCaptureActive;
//
//     if (autoCaptureActive) {
//         captureButton.textContent = "Stop Auto-Capture";
//         statusLabel.textContent = "Status: Auto-capture started...";
//         capturedFaces = [];
//         capturesGrid.innerHTML = ""; // Clear the grid for new captures
//         startAutoCapture();
//     } else {
//         captureButton.textContent = "Start Auto-Capture";
//         statusLabel.textContent = "Status: Auto-capture stopped.";
//     }
// });
//
// // Start auto-capture process
// function startAutoCapture() {
//     if (!autoCaptureActive || capturedFaces.length >= maxCaptures) {
//         return;
//     }
//
//     const canvas = document.createElement("canvas");
//     canvas.width = videoElement.videoWidth;
//     canvas.height = videoElement.videoHeight;
//     const ctx = canvas.getContext("2d");
//
//     // Draw the video frame into the canvas
//     ctx.drawImage(videoElement, 0, 0, canvas.width, canvas.height);
//
//     // Simulate face detection by cropping a part of the video frame
//     const faceDetected = true; // Replace with real detection logic
//     if (faceDetected) {
//         const faceImage = canvas.toDataURL("image/jpeg");
//         capturedFaces.push(faceImage);
//
//         // Display captured face in the grid
//         const img = document.createElement("img");
//         img.src = faceImage;
//         img.alt = `Captured face ${capturedFaces.length}`;
//         capturesGrid.appendChild(img);
//
//         statusLabel.textContent = `Status: Auto-captured ${capturedFaces.length} of ${maxCaptures} faces`;
//
//         if (capturedFaces.length >= maxCaptures) {
//             autoCaptureActive = false;
//             captureButton.textContent = "Start Auto-Capture";
//             submitButton.disabled = false;
//             statusLabel.textContent = "Status: Auto-capture completed.";
//             return;
//         }
//     }
//
//     // Repeat capture at regular intervals
//     setTimeout(startAutoCapture, 1000); // Adjust the interval as needed
// }
//
// // Submit captured faces to the server
// submitButton.addEventListener("click", () => {
//     if (capturedFaces.length === 0) {
//         alert("No faces to submit!");
//         return;
//     }
//
//     // Collect form data
//     const name = document.getElementById("name").value.trim();
//     const age = document.getElementById("age").value.trim();
//     const gender = document.getElementById("gender").value.trim();
//
//     if (!name || !age || !gender) {
//         alert("All fields are required!");
//         return;
//     }
//
//     // Send captured faces and form data to the server
//     fetch("/submit_faces", {
//         method: "POST",
//         headers: { "Content-Type": "application/json" },
//         body: JSON.stringify({
//             name,
//             age,
//             gender,
//             faces: capturedFaces,
//         }),
//     })
//         .then((response) => {
//             if (!response.ok) {
//                 throw new Error("Failed to submit faces");
//             }
//             return response.json();
//         })
//         .then((data) => {
//             alert(data.message || "Faces submitted successfully!");
//             capturedFaces = [];
//             capturesGrid.innerHTML = "";
//             submitButton.disabled = true;
//             validateForm(); // Revalidate the form after submission
//         })
//         .catch((err) => {
//             console.error("Error submitting faces:", err);
//             alert("Failed to submit faces. Please try again.");
//         });
// });
//
// // Form validation
// const validateForm = () => {
//     const name = document.getElementById("name").value.trim();
//     const age = document.getElementById("age").value.trim();
//     const gender = document.getElementById("gender").value.trim();
//     const capturedFacesCount = capturesGrid.children.length;
//
//     // Enable submit button only if all fields are filled and at least one face is captured
//     submitButton.disabled = !(name && age && gender && capturedFacesCount > 0);
// };
//
// // Attach input event listeners for form validation
// document.querySelectorAll("input").forEach((input) => {
//     input.addEventListener("input", validateForm);
// });