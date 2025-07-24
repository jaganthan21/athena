



// Wait until the DOM is fully loaded
document.addEventListener("DOMContentLoaded", function () {
    // Handle folder selection
    document.getElementById("upload-icon").addEventListener("click", async function () {
        try {
            const folderPath = await pywebview.api.select_folder();
            if (folderPath) {
                console.log("Folder Path Selected:", folderPath);  // Debug log
                document.querySelector(".path-box-input").value = folderPath; // Update the input field
            } else {
                console.error("No folder selected.");
            }
        } catch (error) {
            console.error("Error selecting folder:", error);
        }
    });

    document.getElementById("process-icon").addEventListener("click", async function () {
        const folderPath = document.querySelector(".path-box-input").value;
    
        if (!folderPath) {
            alert("Please select a folder before processing.");
            return;
        }
        console.log(folderPath)
        // Show the loader while processing
        document.getElementById("loader").style.display = "block";
    
        try {
            // Call Python's process_files method with the folder path
            const result = await pywebview.api.process_files(folderPath);
            
            // Check result and handle the response
            if (result.success) {
                // Store the generated file name in session storage for later use
                sessionStorage.setItem("generatedFileName", result.fileName);
    
                // Display a success message with the file name
                const successMessage = `Processing complete! File saved in same folder path as: ${result.fileName}`;
                document.getElementById("message").textContent = successMessage;
                document.getElementById("message").style.color = "green";
            } else {
                alert(`Processing failed: ${result.message}`);
            }
        } catch (error) {
            console.error("Error during processing:", error);
            alert("An error occurred during processing.");
        } finally {
            document.getElementById("loader").style.display = "none"; // Hide loader
        }
    });
    
});

// // Save options in save.html
// if (document.getElementById("save-same-location")) {
//     document.getElementById("save-same-location").addEventListener("click", async () => {
//         const fileName = document.getElementById("file-name").value.trim();
//         if (fileName) {
//             const response = await pywebview.api.save_excel(fileName, "same_location");
//             alert(response.message);
//         } else {
//             alert("Please provide a file name.");
//         }
//     });
// }

// if (document.getElementById("save-as")) {
//     document.getElementById("save-as").addEventListener("click", async () => {
//         const fileName = document.getElementById("file-name").value.trim();
//         if (fileName) {
//             const folderPath = await pywebview.api.select_folder();
//             if (folderPath) {
//                 const response = await pywebview.api.save_excel(fileName, "save_as", folderPath);
//                 alert(response.message);
//             } else {
//                 alert("No folder selected.");
//             }
//         } else {
//             alert("Please provide a file name.");
//         }
//     });
// }

// // Cancel button navigation
// if (document.getElementById("cancel")) {
//     document.getElementById("cancel").addEventListener("click", () => {
//         window.location.href = "index.html"; // Navigate back to index.html
//     });
// }
