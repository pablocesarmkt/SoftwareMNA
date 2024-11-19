document.addEventListener("DOMContentLoaded", async () => {
    const messageElement = document.getElementById("message");
    const logsTable = document.getElementById("logs-table");

    try {
        const response = await fetch("/api/v1/logs");
        if (response.ok) {
            const logs = await response.json();

            if (logs.length === 0) {
                messageElement.textContent = "No logs found.";
                return;
            }

            // Generar filas para la tabla
            logs.forEach(log => {
                const row = document.createElement("tr");

                row.innerHTML = `
                    <td class="py-2 px-4 border-b">${log.id}</td>
                    <td class="py-2 px-4 border-b">${log.user_id || "N/A"}</td>
                    <td class="py-2 px-4 border-b">${new Date(log.time).toLocaleString()}</td>
                    <td class="py-2 px-4 border-b">${log.status}</td>
                    <td class="py-2 px-4 border-b">
                        ${log.image_path ? `<a href="${log.image_path}" target="_blank" class="text-blue-500 underline">View</a>` : "N/A"}
                    </td>
                `;

                logsTable.appendChild(row);
            });
        } else {
            messageElement.textContent = "Failed to fetch logs. Please try again later.";
        }
    } catch (error) {
        console.error("Error fetching logs:", error);
        messageElement.textContent = "An error occurred while fetching the logs.";
    }
});