import os
import shutil
import subprocess
import traceback
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse
from extraction_engine1 import process_files_in_folder as process_rtf_files_in_folder

app = FastAPI(title="File Processor Microservice")


class AppAPI:
    def __init__(self):
        self.failed_files = []  # List of files that failed conversion
        self.generated_file_name = ""  # Excel output path

    def convert_docx_to_rtf(self, docx_path, rtf_path):
        """
        Convert .docx to .rtf using LibreOffice headless mode (cross-platform)
        """
        try:
            # Use LibreOffice CLI to convert
            subprocess.run([
                "soffice", "--headless", "--convert-to", "rtf", docx_path, "--outdir",
                os.path.dirname(rtf_path)
            ], check=True)
            print(f"Converted {os.path.basename(docx_path)} to {os.path.basename(rtf_path)}")
            return True
        except subprocess.CalledProcessError as e:
            print(f"Failed to convert {os.path.basename(docx_path)}: {e}")
            self.failed_files.append(os.path.basename(docx_path))
            return False

    def convert_all_docx_in_folder(self, folder_path):
        """
        Convert all .docx files in folder to .rtf
        """
        try:
            docx_files = [f for f in os.listdir(folder_path) if f.lower().endswith(".docx")]
            if not docx_files:
                return True

            for docx_file in docx_files:
                docx_path = os.path.join(folder_path, docx_file)
                rtf_file = os.path.splitext(docx_file)[0] + ".rtf"
                rtf_path = os.path.join(folder_path, rtf_file)
                if os.path.exists(rtf_path):
                    print(f"Skipping {docx_file}: {rtf_file} already exists")
                    continue
                self.convert_docx_to_rtf(docx_path, rtf_path)

            return True
        except Exception as e:
            print(f"Error converting DOCX files: {e}")
            return False

    def process_files(self, folder_path):
        """
        Process files: convert .docx to .rtf and generate Excel
        """
        try:
            if not os.path.isdir(folder_path):
                return {
                    "success": False,
                    "message": "Invalid folder path"
                }

            self.failed_files = []

            # Convert DOCX → RTF
            if not self.convert_all_docx_in_folder(folder_path):
                return {
                    "success": False,
                    "message": "Failed to convert DOCX files"
                }

            # Process RTF → Excel
            try:
                self.generated_file_name = process_rtf_files_in_folder(folder_path, "check")
            except Exception as e:
                print(f"Error processing RTF files: {e}")
                return {
                    "success": False,
                    "message": "Failed to process RTF files"
                }

            message = f"Processing completed! Output file: {self.generated_file_name}"
            if self.failed_files:
                message += f"\nFailed files: {', '.join(self.failed_files)}"

            return {
                "success": True,
                "message": message,
                "fileName": self.generated_file_name
            }

        except Exception as e:
            print(f"Unexpected error: {e}")
            traceback.print_exc()
            return {
                "success": False,
                "message": "Unexpected error occurred"
            }


@app.post("/process-file/")
async def upload_and_process(file: UploadFile = File(...)):
    """
    Upload a single file and process it.
    """
    try:
        # Create temporary folder to store uploaded file
        temp_dir = "temp_uploads"
        os.makedirs(temp_dir, exist_ok=True)

        temp_file_path = os.path.join(temp_dir, file.filename)
        with open(temp_file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        # Initialize processor and process folder
        processor = AppAPI()
        result = processor.process_files(temp_dir)

        # Clean up uploaded files
        shutil.rmtree(temp_dir, ignore_errors=True)

        return JSONResponse(content=result)

    except Exception as e:
        print(f"Error in upload_and_process: {e}")
        traceback.print_exc()
        return JSONResponse(
            content={"success": False, "message": "Failed to process file"},
            status_code=500
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
