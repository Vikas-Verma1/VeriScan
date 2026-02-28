from flask import Flask, render_template, request, redirect, url_for
import os
from modules.phish_guard import PhishGuard
from modules.deepfake_sentry import DeepFakeSentry
from modules.image_sentry import ImageSentry

app = Flask(__name__)
UPLOAD_FOLDER = 'static/uploads'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Ensure upload directory exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Initialize Modules
phish_tool = PhishGuard(UPLOAD_FOLDER)
deepfake_tool = DeepFakeSentry()
image_tool = ImageSentry()

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

if __name__ == '__main__':
    app.run(debug=True)




















# from flask import Flask, render_template, request, redirect, url_for
# import os
# from modules.phish_guard import PhishGuard
# from modules.deepfake_sentry import DeepFakeSentry
# from modules.image_sentry import ImageSentry  # NEW IMPORT

# app = Flask(__name__)
# UPLOAD_FOLDER = 'static/uploads'
# app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# # Ensure upload directory exists
# os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# # Initialize Modules
# phish_tool = PhishGuard(UPLOAD_FOLDER)
# deepfake_tool = DeepFakeSentry()
# image_tool = ImageSentry()  # NEW MODULE INIT

# @app.route('/')
# def home():
#     return render_template('index.html')

# @app.route('/scan_phish', methods=['POST'])
# def scan_phish():
#     url = request.form.get('url')
#     if not url:
#         return redirect(url_for('home'))
    
#     result = phish_tool.analyze_url(url)
#     return render_template('result.html', result=result, type='phish')

# @app.route('/scan_deepfake', methods=['POST'])
# def scan_deepfake():
#     if 'video' not in request.files:
#         return redirect(url_for('home'))
    
#     file = request.files['video']
#     if file.filename == '':
#         return redirect(url_for('home'))

#     file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
#     file.save(file_path)
    
#     result = deepfake_tool.analyze_video(file_path)
#     return render_template('result.html', result=result, type='deepfake')

# # --- NEW ROUTE FOR AI IMAGES ---
# @app.route('/scan_image', methods=['POST'])
# def scan_image():
#     if 'image' not in request.files:
#         return redirect(url_for('home'))
    
#     file = request.files['image']
#     if file.filename == '':
#         return redirect(url_for('home'))

#     file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
#     file.save(file_path)
    
#     result = image_tool.analyze_image(file_path)
#     return render_template('result.html', result=result, type='image')

# if __name__ == '__main__':
#     app.run(debug=True)


























# # from flask import Flask, render_template, request, redirect, url_for
# # import os
# # from modules.phish_guard import PhishGuard
# # from modules.deepfake_sentry import DeepFakeSentry

# # app = Flask(__name__)
# # UPLOAD_FOLDER = 'static/uploads'
# # app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# # # Ensure upload directory exists
# # os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# # # Initialize Modules
# # phish_tool = PhishGuard(UPLOAD_FOLDER)
# # deepfake_tool = DeepFakeSentry()

# # @app.route('/')
# # def home():
# #     return render_template('index.html')

# # @app.route('/scan_phish', methods=['POST'])
# # def scan_phish():
# #     url = request.form.get('url')
# #     if not url:
# #         return redirect(url_for('home'))
    
# #     # Run PhishGuard Logic
# #     result = phish_tool.analyze_url(url)
# #     return render_template('result.html', result=result, type='phish')

# # @app.route('/scan_deepfake', methods=['POST'])
# # def scan_deepfake():
# #     if 'video' not in request.files:
# #         return redirect(url_for('home'))
    
# #     file = request.files['video']
# #     if file.filename == '':
# #         return redirect(url_for('home'))

# #     file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
# #     file.save(file_path)
    
# #     # Run DeepFake Logic (No Metadata Check)
# #     result = deepfake_tool.analyze_video(file_path)
# #     return render_template('result.html', result=result, type='deepfake')

# # if __name__ == '__main__':
# #     app.run(debug=True)






















# # # from flask import Flask, render_template, request, redirect, url_for
# # # import os
# # # from modules.phish_guard import PhishGuard
# # # from modules.deepfake_sentry import DeepFakeSentry

# # # app = Flask(__name__)
# # # UPLOAD_FOLDER = 'static/uploads'
# # # app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# # # # Ensure upload directory exists
# # # os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# # # # Initialize Modules
# # # phish_tool = PhishGuard(UPLOAD_FOLDER)
# # # deepfake_tool = DeepFakeSentry()

# # # @app.route('/')
# # # def home():
# # #     return render_template('index.html')

# # # @app.route('/scan_phish', methods=['POST'])
# # # def scan_phish():
# # #     url = request.form.get('url')
# # #     if not url:
# # #         return redirect(url_for('home'))
    
# # #     # Run PhishGuard Logic
# # #     result = phish_tool.analyze_url(url)
# # #     return render_template('result.html', result=result, type='phish')

# # # @app.route('/scan_deepfake', methods=['POST'])
# # # def scan_deepfake():
# # #     if 'video' not in request.files:
# # #         return redirect(url_for('home'))
    
# # #     file = request.files['video']
# # #     if file.filename == '':
# # #         return redirect(url_for('home'))

# # #     file_path = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
# # #     file.save(file_path)
    
# # #     # Run DeepFake Logic
# # #     result = deepfake_tool.analyze_video(file_path)
# # #     return render_template('result.html', result=result, type='deepfake')

# # # if __name__ == '__main__':
# # #     app.run(debug=True)