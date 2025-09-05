import os
import webview
import win32com.client
import psutil
import time
import traceback
# from helper_functions import process_rtf_files_in_folder
from pdf_helper import process_files_in_folder as process_rtf_files_in_folder


def kill_word_processes():
    """
    Terminate any stray Word processes to prevent COM conflicts.
    """
    for proc in psutil.process_iter(['name']):
        if proc.info['name'].lower() == 'winword.exe':
            try:
                proc.terminate()
                proc.wait(timeout=3)  # Wait for termination
            except Exception as e:
                print(f"Failed to terminate Word process: {e}")


class AppAPI:
    def __init__(self):
        """Initialize the AppAPI with default attributes."""
        self.folder_path = ""  # Selected folder path
        self.failed_files = []  # List to store files that failed conversion
        self.generated_file_name = ""  # Path to the generated Excel file

    def select_folder(self):
        """
        Open a folder selection dialog and store the selected path.

        Returns:
            str: Selected folder path or empty string if no folder is selected.
        """
        try:
            folder_path = webview.windows[0].create_file_dialog(webview.FOLDER_DIALOG)
            if folder_path:
                self.folder_path = folder_path[0]
                return self.folder_path
            return ""
        except Exception as e:
            print(f"Error in folder selection: {e}")
            return ""

    def convert_docx_to_rtf(self, docx_path, rtf_path, max_retries=2):
        """
        Convert a single .docx file to .rtf using Microsoft Word COM API.

        Args:
            docx_path (str): Path to the input .docx file.
            rtf_path (str): Path to the output .rtf file.
            max_retries (int): Number of retry attempts for transient errors.

        Returns:
            bool: True if conversion is successful, False otherwise.
        """
        for attempt in range(max_retries):
            word = None
            doc = None
            try:
                # Terminate stray Word processes before starting
                kill_word_processes()

                # Initialize a new Word instance
                word = win32com.client.Dispatch("Word.Application")

                # Open the .docx file
                doc = word.Documents.Open(os.path.abspath(docx_path))

                # Save as RTF (FileFormat 6 = RTF)
                doc.SaveAs(os.path.abspath(rtf_path), FileFormat=6)
                print(f"Converted {os.path.basename(docx_path)} to {os.path.basename(rtf_path)}")
                return True

            except Exception as e:
                print(f"Attempt {attempt + 1} failed for {os.path.basename(docx_path)}: {e}")
                traceback.print_exc()  # Log detailed error for debugging
                if attempt == max_retries - 1:
                    print(f"Max retries reached for {os.path.basename(docx_path)}")
                    self.failed_files.append(os.path.basename(docx_path))
                    return False

            finally:
                # Clean up
                try:
                    if doc:
                        doc.Close(SaveChanges=False)
                    if word:
                        word.Quit()
                except Exception as e:
                    print(f"Cleanup failed: {e}")
                # Terminate any remaining Word processes
                kill_word_processes()
                # Delay to allow system to release resources
                time.sleep(1)

        return False

    def convert_all_docx_in_folder(self, folder_path):
        """
        Convert all .docx files in the specified folder to .rtf.

        Args:
            folder_path (str): Path to the folder containing .docx files.

        Returns:
            bool: True if conversion process completes, False if folder is invalid.
        """
        try:
            if not os.path.isdir(folder_path):
                print(f"Invalid folder path: {folder_path}")
                return False

            # Get all .docx files in the folder
            docx_files = [f for f in os.listdir(folder_path) if f.lower().endswith(".docx")]

            if not docx_files:
                print(f"No .docx files found in {folder_path}")
                return True

            # Convert each .docx file to .rtf
            for docx_file in docx_files:
                docx_path = os.path.join(folder_path, docx_file)
                rtf_file = os.path.splitext(docx_file)[0] + ".rtf"
                rtf_path = os.path.join(folder_path, rtf_file)

                # Skip if .rtf file already exists
                if os.path.exists(rtf_path):
                    print(f"Skipping {docx_file}: {rtf_file} already exists")
                    continue

                self.convert_docx_to_rtf(docx_path, rtf_path)

            # Ensure any remaining Word processes are terminated
            kill_word_processes()
            return True

        except Exception as e:
            print(f"Error processing .docx files in folder: {e}")
            return False

    def process_files(self, folder_path):
        """
        Process files in the selected folder: convert .docx to .rtf and generate an Excel file.

        Args:
            folder_path (str): Path to the folder containing files.

        Returns:
            dict: Contains success status, user-friendly message, and generated file path (if successful).
        """
        try:
            if not os.path.isdir(folder_path):
                return {
                    "success": False,
                    "message": "The selected folder is invalid. Please choose a valid folder."
                }

            # Reset failed files list for this operation
            self.failed_files = []

            # Convert .docx files to .rtf
            if not self.convert_all_docx_in_folder(folder_path):
                return {
                    "success": False,
                    "message": "Failed to process .docx files. Please ensure the folder is accessible."
                }

            # Process RTF files to generate Excel
            try:
                self.generated_file_name = process_rtf_files_in_folder(folder_path,"check")
            except Exception as e:
                print(f"Error processing RTF files: {e}")
                return {
                    "success": False,
                    "message": "Failed to process RTF files. Please ensure the files are valid."
                }

            # Prepare user-friendly success message
            message = f"Processing completed! The output file is saved at: {self.generated_file_name}"
            if self.failed_files:
                message += f"\nThe following files could not be converted: {', '.join(self.failed_files)}"

            return {
                "success": True,
                "message": message,
                "fileName": self.generated_file_name
            }

        except Exception as e:
            print(f"Unexpected error during file processing: {e}")
            return {
                "success": False,
                "message": "An unexpected error occurred. Please try again or contact support."
            }


def main():
    """Initialize and start the webview application."""
    try:
        api = AppAPI()
        webview.create_window(
            title="File Processor",
            url="home_page.html",
            js_api=api,
            width=800,
            height=600
        )
        webview.start()
    except Exception as e:
        print(f"Failed to start application: {e}")


if __name__ == "__main__":
    main()