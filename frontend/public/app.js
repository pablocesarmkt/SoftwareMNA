navigator.mediaDevices.getUserMedia({ video: { facingMode: "user" } })
    .then((stream) => {
        let videoElement = document.querySelector("#video");
        videoElement.srcObject = stream;
        videoElement.play();
    })
    .catch((err) => {
        console.error("Error accessing camera: ", err);
    });

function captureImage() {
    let videoElement = document.querySelector("#video");
    let canvas = document.createElement("canvas");
    canvas.width = videoElement.videoWidth;
    canvas.height = videoElement.videoHeight;
    let context = canvas.getContext("2d");
    context.drawImage(videoElement, 0, 0, canvas.width, canvas.height);
    let imageData = canvas.toDataURL("image/jpeg");

    sendImageToBackend(imageData);
}

function sendImageToBackend(imageData) {
    // Convert the base64 data to a Blob
    let byteString = atob(imageData.split(',')[1]);
    let mimeString = "image/jpeg";
    let buffer = new ArrayBuffer(byteString.length);
    let data = new Uint8Array(buffer);

    for (let i = 0; i < byteString.length; i++) {
        data[i] = byteString.charCodeAt(i);
    }

    let blob = new Blob([buffer], { type: mimeString });

    // Send the image to the backend
    let formData = new FormData();
    formData.append("face", blob, "capture.jpg");

    fetch("/api/v1/search_face", {
        method: "POST",
        body: formData
    })
    .then(response => {
        if (response.ok) {
            return response.json();
        } else {
            throw new Error("Face not recognized");
        }
    })
    .then(data => {
        document.getElementById("message").textContent = `Access granted for Employee ID: ${data.employee_id}`;
    })
    .catch(error => {
        document.getElementById("message").textContent = "Access denied: Face not recognized.";
    })
    .finally(() => {
        // Limpia el mensaje después de 30 segundos
        setTimeout(() => {
            document.getElementById("message").textContent = "";
        }, 30000); // 30000 ms = 30 seconds
    });
}