from flask import Flask, request, send_file, render_template
from PIL import Image
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
import io
import pytesseract
pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"
import re

app = Flask(__name__)

@app.route('/')
def upload_page():
    return render_template("upload.html")

@app.route('/process', methods=['POST'])
def process_files():
    bank_file = request.files['bank_image']
    receipt_file = request.files['receipt_image']

    bank_img = Image.open(bank_file.stream).convert("RGB")
    ocr_text = pytesseract.image_to_string(bank_img, lang="eng+heb")

    print("===== OCR Output =====")
    print(ocr_text)
    print("======================")

    expense_match = re.search(r"(WWW\.\S+)", ocr_text)
    expense = expense_match.group(1).strip() if expense_match else "Unknown Expense"

    numbers = re.findall(r"([\d]+[.,]\d+)", ocr_text)
    ils_amount = numbers[0] if len(numbers) >= 1 else "Unknown"

    if ils_amount != "Unknown" and ils_amount.startswith("0") and len(ils_amount) > 1:
        ils_amount = ils_amount[1:]

    currency_amounts = re.findall(r"([A-Z]{2,3})\s*([\d]+[.,]\d+)", ocr_text)
    if len(currency_amounts) >= 1:
        second_currency, second_amount = currency_amounts[0]
        second_amount_text = f"{second_amount} {second_currency}"
    else:
        second_amount_text = "Unknown"

    receipt_img = Image.open(receipt_file.stream).convert("RGB")

    bank_io = io.BytesIO()
    bank_img.save(bank_io, format="PNG")
    bank_io.seek(0)
    bank_image_reader = ImageReader(bank_io)

    receipt_io = io.BytesIO()
    receipt_img.save(receipt_io, format="PNG")
    receipt_io.seek(0)
    receipt_image_reader = ImageReader(receipt_io)

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)

    def draw_centered_image(c, img_reader):
        max_width = 500
        max_height = 500
        img_width, img_height = img_reader.getSize()
        scale = min(max_width / img_width, max_height / img_height, 1.0)
        new_width = img_width * scale
        new_height = img_height * scale
        x = (A4[0] - new_width) / 2
        y = 842 - new_height - 100
        c.drawImage(img_reader, x, y, width=new_width, height=new_height, preserveAspectRatio=True, mask='auto')

    draw_centered_image(c, bank_image_reader)
    c.setFont("Helvetica", 10)
    c.drawString(50, 50, f"Expense: {expense}, ILS: {ils_amount}, Other: {second_amount_text}")
    c.showPage()

    draw_centered_image(c, receipt_image_reader)
    c.setFont("Helvetica", 10)
    c.drawString(50, 50, f"Receipt for {expense}")
    c.save()

    buffer.seek(0)

    filename = f"{expense} - {ils_amount} ILS - {second_amount_text}.pdf"

    return send_file(buffer, as_attachment=True, download_name=filename, mimetype='application/pdf')

if __name__ == "__main__":
    app.run(debug=True)
