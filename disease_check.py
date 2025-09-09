import pypandoc
import fitz  # PyMuPDF
from PIL import Image
import pytesseract

# --- Step 1: Convert RTF to PDF ---
input_rtf = r"C:\Users\Mekkanos\Downloads\check_disease\check.rtf"
output_pdf =r"C:\Users\Mekkanos\Downloads\check_disease\check.pdf"

pypandoc.convert_file(input_rtf, 'pdf', outputfile=output_pdf)

# --- Step 2: Open PDF and render first page as image ---
doc = fitz.open(output_pdf)
page = doc[0]  # first page
pix = page.get_pixmap(dpi=200)
img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

# --- Step 3: Convert to grayscale ---
gray_img = img.convert("L")
gray_img.save("first_page_gray.png")

# --- Step 4: OCR ---
text = pytesseract.image_to_string(gray_img)

print("Extracted OCR Text:\n")
print(text)
