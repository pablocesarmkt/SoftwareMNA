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

async function sendImageToBackend(imageData) {
    // Mostrar mensaje de carga y desactivar el botón
    const messageElement = document.getElementById("message");
    const scanButton = document.querySelector("button");
    messageElement.textContent = "Processing...";
    scanButton.disabled = true;

    // Convertir la cadena base64 a un Blob
    let byteString = atob(imageData.split(',')[1]);
    let mimeString = "image/jpeg";
    let buffer = new ArrayBuffer(byteString.length);
    let data = new Uint8Array(buffer);

    for (let i = 0; i < byteString.length; i++) {
        data[i] = byteString.charCodeAt(i);
    }

    let blob = new Blob([buffer], { type: mimeString });

    // Enviar la imagen al backend
    let formData = new FormData();
    formData.append("face", blob, "capture.jpg");

    try {
        const response = await fetch("/api/v1/search_face", {
            method: "POST",
            body: formData
        });

        if (response.ok) {
            const data = await response.json();
            messageElement.textContent = `Access granted for Employee ID: ${data.employee_id}`;
        } else {
            if (response.status === 404) {
                messageElement.textContent = "Access denied: Face not recognized.";
            } else {
                const errorText = await response.text();
                if (errorText.includes("Acceso no autorizado para el empleado")) {
                    messageElement.textContent = "Access denied: Unauthorized employee access level.";
                } else {
                    messageElement.textContent = "Access denied: Unexpected error.";
                }
            }
        }
    } catch (error) {
        messageElement.textContent = "Error: Could not process the request.";
        console.error("Error:", error);
    } finally {
        // Reactivar el botón y limpiar el mensaje después de 30 segundos
        scanButton.disabled = false;
        setTimeout(() => {
            messageElement.textContent = "";
        }, 30000); // 30000 ms = 30 seconds
    }
}