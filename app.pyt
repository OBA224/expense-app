from flask import Flask, request, send_file
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
import io
import pytesseract
import re

app = Flask(__name__)

@app.route('/')
def upload_page():
    return '''
    <h2>Upload Bank Debit and Receipt</h2>
    <form method="post" enctype="multipart/form-data" action="/process">
      Bank Debit Image: <input type="file" name="bank_image"><br>
      Receipt Image: <input type="file" name="receipt_image"><br>
      <input type="submit" value="Generate PDF">
    </form>
    '''

@app.route('/process', methods=['POST'])
def process_files():
    bank_file = request.files['bank_image']
    receipt_file = request.files['receipt_image']

    # Convert bank image to PIL
    bank_img = Image.open(bank_file.stream).convert("RGB")
    ocr_text = pytesseract.image_to_string(bank_img, lang="eng+heb")

    # Print OCR text for debugging
    print("===== OCR Output =====")
    print(ocr_text)
    print("======================")

    # Extract merchant name
    expense_match = re.search(r"(WWW\.\S+)", ocr_text)
    expense = expense_match.group(1).strip() if expense_match else "Unknown Expense"

    # Find all numbers (for first amount)
    numbers = re.findall(r"([\d]+[.,]\d+)", ocr_text)
    ils_amount = numbers[0] if len(numbers) >= 1 else "Unknown"

    # Remove leading zero in first amount
    if ils_amount != "Unknown" and ils_amount.startswith("0") and len(ils_amount) > 1:
        ils_amount = ils_amount[1:]

    # Find currency-amount pairs for the second amount
    currency_amounts = re.findall(r"([A-Z]{2,3})\s*([\d]+[.,]\d+)", ocr_text)
    if len(currency_amounts) >= 1:
        second_currency, second_amount = currency_amounts[0]
        second_amount_text = f"{second_amount} {second_currency}"
    else:
        second_amount_text = "Unknown"

    # Convert receipt image to PIL
    receipt_img = Image.open(receipt_file.stream).convert("RGB")

    # Save PIL images to BytesIO and wrap with ImageReader
    bank_io = io.BytesIO()
    bank_img.save(bank_io, format="PNG")
    bank_io.seek(0)
    bank_image_reader = ImageReader(bank_io)

    receipt_io = io.BytesIO()
    receipt_img.save(receipt_io, format="PNG")
    receipt_io.seek(0)
    receipt_image_reader = ImageReader(receipt_io)

    # Create PDF in memory
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    def draw_centered_image(c, img_reader):
        # Max dimensions
        max_width = 500
        max_height = 500
        # Get image size
        img_width, img_height = img_reader.getSize()
        # Compute scaling factor
        scale = min(max_width / img_width, max_height / img_height, 1.0)
        new_width = img_width * scale
        new_height = img_height * scale
        # Compute x position to center
        x = (A4[0] - new_width) / 2
        y = 842 - new_height - 100  # 100pt top margin
        c.drawImage(img_reader, x, y, width=new_width, height=new_height, preserveAspectRatio=True, mask='auto')

    # Page 1: Bank Debit Image
    draw_centered_image(c, bank_image_reader)
    c.setFont("Helvetica", 10)
    c.drawString(50, 50, f"Expense: {expense}, ILS: {ils_amount}, Other: {second_amount_text}")
    c.showPage()

    # Page 2: Receipt Image
    draw_centered_image(c, receipt_image_reader)
    c.setFont("Helvetica", 10)
    c.drawString(50, 50, f"Receipt for {expense}")
    c.save()

    buffer.seek(0)

    # Create filename with all parts
    filename = f"{expense} - {ils_amount} ILS - {second_amount_text}.pdf"

    return send_file(buffer, as_attachment=True, download_name=filename, mimetype='application/pdf')

if __name__ == "__main__":
    app.run(debug=True)

