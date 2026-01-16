import os
import io
import base64
from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename
import docx
from google import genai
from google.genai import types


app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB limit
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf', 'docx'}

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Gemini API Client Initialization
api_key = os.getenv("API_KEY")

if not api_key:
    raise ValueError("Not found")

client = genai.Client(api_key=api_key)


def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def extract_text_from_docx(file_stream):
    doc = docx.Document(file_stream)
    full_text = []
    for para in doc.paragraphs:
        full_text.append(para.text)
    return '\n'.join(full_text)

async def generate_summary(file_data, mime_type, original_text=None):
    model_id = "gemini-2.5-flash-preview-09-2025"
    prompt = "Provide a comprehensive summary of this file. " \
                "Describe what kind of file it is and its main contents. " \
                "If it contains data or text, summarize the key points."

    try:
        if original_text:
            response = client.models.generate_content(
                model=model_id,
                contents=[f"{prompt}\n\nContent:\n{original_text}"]
            )
        else:
            response = client.models.generate_content(
                model=model_id,
                contents=[
                    types.Part.from_bytes(data=file_data, mime_type=mime_type),
                    prompt
                ]
            )
        return response.text
    except Exception as e:
        return f"Error generating summary: {str(e)}"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
async def upload_file():
    if 'file' not in request.files:
        return jsonify({"error": "No file part"}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "No selected file"}), 400

    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        mime_type = file.content_type
        file_bytes = file.read()
        
        summary = ""
        extracted_content = ""

        if filename.endswith('.docx'):
            extracted_content = extract_text_from_docx(io.BytesIO(file_bytes))
            summary = await generate_summary(None, None, original_text=extracted_content)
        else:
            if mime_type == 'application/pdf':
                extracted_content = "[PDF Binary Data - Sent to AI for analysis]"
            else:
                extracted_content = "[Image Data - Sent to AI for analysis]"
            
            summary = await generate_summary(file_bytes, mime_type)

        return jsonify({
            "filename": filename,
            "summary": summary,
            "original_content": extracted_content if extracted_content else "Content extracted by AI."
        })

    return jsonify({"error": "File type not allowed"}), 400

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000,debug=True)