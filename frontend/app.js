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
    let imageData = canvas.toDataURL("image/png");

    sendImageToBackend(imageData);
}

function sendImageToBackend(imageData) {
    // Convert the base64 data to a Blob
    let byteString = atob(imageData.split(',')[1]);
    let mimeString = imageData.split(',')[0].split(':')[1].split(';')[0];
    let buffer = new ArrayBuffer(byteString.length);
    let data = new Uint8Array(buffer);

    for (let i = 0; i < byteString.length; i++) {
        data[i] = byteString.charCodeAt(i);
    }

    let blob = new Blob([buffer], { type: mimeString });

    // Send the image to the backend
    let formData = new FormData();
    formData.append("file", blob, "capture.png");

    fetch("http://34.172.135.76:8000/analyze/", {
        method: "POST",
        body: formData
    })
    .then(response => response.json())
    .then(data => {
        let messageElement = document.querySelector("#message");
        if (data.result === "approved") {
            messageElement.innerText = "Access Approved";
        } else {
            messageElement.innerText = "Access Denied";
        }
    })
    .catch(error => {
        console.error("Error:", error);
    });
}
