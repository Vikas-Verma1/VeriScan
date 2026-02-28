from flask import Flask, render_template, request, redirect, url_for
import os
from modules.phish_guard import PhishGuard
from modules.deepfake_sentry import DeepFakeSentry
from modules.image_sentry import ImageSentry
from modules.docu_guard import DocuGuard  # NEW IMPORT

app = Flask(__name__)
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Ensure upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Initialize Modules
phish_tool = PhishGuard(UPLOAD_FOLDER)
deepfake_tool = DeepFakeSentry()
image_tool = ImageSentry()
docu_tool = DocuGuard()  # NEW MODULE INIT

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/scan_phish', methods=['POST'])
def scan_phish():
    url = request.form.get('url')
    if not url:
        return redirect(url_for('home'))
    
    result = phish_tool.analyze_url(url)
    return render_template('result.html', result=result, type='phish')

@app.route('/scan_deepfake', methods=['POST'])
def scan_deepfake():
    if 'video' not in request.files:
        return redirect(url_for('home'))
    
    file = request.files['video']
    if file.filename == '':
        return redirect(url_for('home'))

    file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(file_path)
    
    result = deepfake_tool.analyze_video(file_path)
    return render_template('result.html', result=result, type='deepfake')

@app.route('/scan_image', methods=['POST'])
def scan_image():
    if 'image' not in request.files:
        return redirect(url_for('home'))
    
    file = request.files['image']
    if file.filename == '':
        return redirect(url_for('home'))

    file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(file_path)
    
    result = image_tool.analyze_image(file_path)
    return render_template('result.html', result=result, type='image')

# --- NEW ROUTE FOR DOCUGUARD ---
@app.route('/scan_document', methods=['POST'])
def scan_document():
    if 'document' not in request.files:
        return redirect(url_for('home'))
    
    file = request.files['document']
    if file.filename == '':
        return redirect(url_for('home'))

    file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    file.save(file_path)
    
    result = docu_tool.analyze_document(file_path)
    return render_template('result.html', result=result, type='document')

if __name__ == '__main__':
    app.run(debug=True)
