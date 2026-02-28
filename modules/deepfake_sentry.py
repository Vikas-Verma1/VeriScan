import os
import sys
import re
import json

# --- 1. ULTIMATE SILENCE BLOCK ---
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3' 
os.environ['ABSL_LOG_LEVEL'] = 'error'

def mute_stderr():
    try:
        null_fd = os.open(os.devnull, os.O_RDWR)
        save_fd = os.dup(2)
        os.dup2(null_fd, 2)
        return save_fd, null_fd
    except Exception:
        return None, None

def unmute_stderr(save_fd, null_fd):
    if save_fd is not None:
        os.dup2(save_fd, 2)
        os.close(save_fd)
        os.close(null_fd)

saved_fd, null_fd = mute_stderr()

try:
    import cv2
    import numpy as np
    import mediapipe as mp
    # New Audio Imports
    import librosa
    import soundfile as sf
    from PIL import Image, ImageChops
    
    test_load = mp.solutions.face_mesh
    HAS_MEDIAPIPE = True
except (ImportError, AttributeError):
    HAS_MEDIAPIPE = False
    mp = None
finally:
    unmute_stderr(saved_fd, null_fd)

# --- END SILENCE BLOCK ---

class DeepFakeSentry:
    def __init__(self):
        self.use_mediapipe = HAS_MEDIAPIPE
        
        self.face_cascade_path = "haarcascade_frontalface_default.xml"
        self.eye_cascade_path = "haarcascade_eye.xml"
        
        self._download_model(self.face_cascade_path, "https://raw.githubusercontent.com/opencv/opencv/master/data/haarcascades/haarcascade_frontalface_default.xml")
        self._download_model(self.eye_cascade_path, "https://raw.githubusercontent.com/opencv/opencv/master/data/haarcascades/haarcascade_eye.xml")

        if self.use_mediapipe:
            self.mp_face_mesh = mp.solutions.face_mesh
            self.face_mesh = self.mp_face_mesh.FaceMesh(
                max_num_faces=1,
                refine_landmarks=True,
                min_detection_confidence=0.5,
                min_tracking_confidence=0.5
            )
        else:
            self.face_cascade = cv2.CascadeClassifier(self.face_cascade_path)
            self.eye_cascade = cv2.CascadeClassifier(self.eye_cascade_path)

    def _download_model(self, filename, url):
        import urllib.request
        if not os.path.exists(filename):
            try:
                with urllib.request.urlopen(url) as response, open(filename, 'wb') as out_file:
                    out_file.write(response.read())
            except Exception:
                pass

    def analyze_video(self, video_path):
        cap = cv2.VideoCapture(video_path)
        
        # --- 1. FILE INTEGRITY & METADATA CHECK ---
        metadata_score, metadata_evidence = self._analyze_metadata(video_path)
        
        if not cap.isOpened():
             return self._generate_error_result("FAKE: Corrupted File (WhatsApp Reject)")
        
        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        
        if frame_count < 1 or fps <= 0:
             return self._generate_error_result("FAKE: Invalid Video Structure")

        # --- 2. AUDIO FORENSICS (Extract & Analyze) ---
        audio_score, audio_evidence = self._analyze_audio(video_path)

        # --- 3. BIOMETRIC & VISUAL ANALYSIS ---
        frames_analyzed = 0
        total_blinks = 0
        total_head_movement = 0
        texture_scores = []
        fft_scores = []
        ela_scores = [] # Error Level Analysis scores
        
        # Lip Sync Tracking
        mar_scores = [] 
        ear_scores = [] 
        
        prev_nose_landmark = None
        eye_closed = False 
        blink_frames_counter = 0 
        
        # Indices
        LEFT_EYE = [362, 385, 387, 263, 373, 380]
        RIGHT_EYE = [33, 160, 162, 133, 153, 144]
        MOUTH_INNER = [13, 14, 312, 317, 82, 87]

        max_frames = 200
        
        while cap.isOpened() and frames_analyzed < max_frames:
            ret, frame = cap.read()
            if not ret:
                break
            
            frames_analyzed += 1
            h, w, _ = frame.shape
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # Frequency Analysis (Every 10th frame)
            if frames_analyzed % 10 == 0:
                fft_score = self._analyze_frequency_spectrum(gray)
                fft_scores.append(fft_score)
                
                # ELA Analysis (Every 20th frame to save speed)
                if frames_analyzed % 20 == 0:
                    ela_score = self._analyze_ela(frame)
                    ela_scores.append(ela_score)

            if self.use_mediapipe:
                rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = self.face_mesh.process(rgb_frame)
                
                if results.multi_face_landmarks:
                    for face_landmarks in results.multi_face_landmarks:
                        landmarks = face_landmarks.landmark
                        
                        # Head Movement
                        nose_x, nose_y = int(landmarks[1].x * w), int(landmarks[1].y * h)
                        nose_point = np.array([nose_x, nose_y])
                        if prev_nose_landmark is not None:
                            total_head_movement += np.linalg.norm(nose_point - prev_nose_landmark)
                        prev_nose_landmark = nose_point

                        # Skin Texture
                        cheek_x, cheek_y = int(landmarks[234].x * w), int(landmarks[234].y * h)
                        y1, y2 = max(0, cheek_y-20), min(h, cheek_y+20)
                        x1, x2 = max(0, cheek_x-20), min(w, cheek_x+20)
                        if y2 > y1 and x2 > x1:
                            cheek_roi = gray[y1:y2, x1:x2]
                            if cheek_roi.size > 0:
                                texture_scores.append(cv2.Laplacian(cheek_roi, cv2.CV_64F).var())

                        # Blink & Lip Sync
                        left_ear = self.calculate_ear(landmarks, LEFT_EYE, w, h)
                        right_ear = self.calculate_ear(landmarks, RIGHT_EYE, w, h)
                        avg_ear = (left_ear + right_ear) / 2.0
                        ear_scores.append(avg_ear)

                        if avg_ear < 0.22: 
                            blink_frames_counter += 1
                            eye_closed = True
                        else: 
                            if eye_closed and 1 <= blink_frames_counter <= 10:
                                 total_blinks += 1
                            blink_frames_counter = 0
                            eye_closed = False
                        
                        mar_scores.append(self.calculate_mar(landmarks, MOUTH_INNER, w, h))

            else:
                # Backup OpenCV Logic
                faces = self.face_cascade.detectMultiScale(gray, 1.3, 5)
                if len(faces) > 0:
                    (x, y, fw, fh) = faces[0]
                    roi = gray[y:y+fh, x:x+fw]
                    texture_scores.append(cv2.Laplacian(roi, cv2.CV_64F).var())

        cap.release()
        
        # Calculate Variances
        mar_var = np.var(mar_scores) if mar_scores else 0
        ear_var = np.var(ear_scores) if ear_scores else 0
        
        return self._calculate_verdict(
            frames_analyzed, total_blinks, total_head_movement, 
            texture_scores, fft_scores, mar_var, ear_var, 
            metadata_score, metadata_evidence, 
            audio_score, audio_evidence,
            ela_scores
        )

    # --- NEW DETECTION MODULES ---

    def _analyze_metadata(self, file_path):
        """Scans raw file header for known AI generator tags."""
        score = 0
        evidence = []
        try:
            with open(file_path, 'rb') as f:
                header = f.read(4096) # Read first 4KB
                header_str = str(header)
                
                # Check for Suspicious Tags
                suspicious_tags = {
                    b'Lavf': 'FFmpeg/Lavf (Common in AI Generators)',
                    b'Adobe': 'Adobe Software (Edited)',
                    b'FakeApp': 'FakeApp Metadata',
                    b'DeepFace': 'DeepFaceLab Signature',
                    b'Stable': 'Stable Diffusion Tag'
                }
                
                for tag, desc in suspicious_tags.items():
                    if tag in header:
                        score += 30
                        evidence.append(f"Metadata tag found: {desc}")
                        
        except Exception:
            pass
        return score, evidence

    def _analyze_audio(self, video_path):
        """Analyzes audio for robotic spectral flatness and silence gaps."""
        score = 0
        evidence = []
        try:
            # Load audio (only first 10 seconds to save time)
            y, sr = librosa.load(video_path, duration=10, sr=None)
            
            # 1. Spectral Flatness (Robotic Check)
            flatness = librosa.feature.spectral_flatness(y=y)
            avg_flatness = np.mean(flatness)
            
            # 2. Silence Detection
            non_silent_intervals = librosa.effects.split(y, top_db=20)
            silence_ratio = 1.0 - (np.sum([end-start for start, end in non_silent_intervals]) / len(y))
            
            # Scoring
            if avg_flatness > 0.4: # Robotic/Noise
                score += 40
                evidence.append(f"Audio is spectrally flat/robotic (Score: {round(avg_flatness, 2)}).")
                
            if silence_ratio > 0.8: # Too much silence
                score += 20
                evidence.append("Audio contains unnatural silence gaps.")
                
        except Exception:
            # No audio track found
            pass 
        return score, evidence

    def _analyze_ela(self, frame):
        """Error Level Analysis to find spliced/edited pixels."""
        try:
            # Convert OpenCV image to PIL
            img = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            im = Image.fromarray(img)
            
            # Save at 90% quality
            im.save("temp_ela.jpg", "JPEG", quality=90)
            resaved_im = Image.open("temp_ela.jpg")
            
            # Calculate difference
            ela_im = ImageChops.difference(im, resaved_im)
            extrema = ela_im.getextrema()
            max_diff = max([ex[1] for ex in extrema])
            
            return max_diff
        except Exception:
            return 0

    def _analyze_frequency_spectrum(self, gray_frame):
        try:
            f = np.fft.fft2(gray_frame)
            fshift = np.fft.fftshift(f)
            magnitude_spectrum = 20 * np.log(np.abs(fshift) + 1e-9)
            avg_energy = np.mean(magnitude_spectrum)
            max_energy = np.max(magnitude_spectrum)
            return max_energy / (avg_energy + 1e-5)
        except Exception:
            return 0

    def calculate_ear(self, landmarks, indices, w, h):
        def dist(p1, p2):
            return np.linalg.norm(np.array([landmarks[p1].x*w, landmarks[p1].y*h]) - np.array([landmarks[p2].x*w, landmarks[p2].y*h]))
        return (dist(indices[1], indices[5]) + dist(indices[2], indices[4])) / (2.0 * dist(indices[0], indices[3]))

    def calculate_mar(self, landmarks, indices, w, h):
        def dist(p1, p2):
            return np.linalg.norm(np.array([landmarks[p1].x*w, landmarks[p1].y*h]) - np.array([landmarks[p2].x*w, landmarks[p2].y*h]))
        return (dist(indices[1], indices[5]) + dist(indices[2], indices[4]) + dist(indices[3], indices[5])) / (2.0 * dist(indices[0], indices[4]))

    def _calculate_verdict(self, frames, blinks, movement, texture_scores, fft_scores, mar_var, ear_var, meta_score, meta_ev, audio_score, audio_ev, ela_scores):
        fake_score = 10 
        status = "LIKELY REAL"
        evidence = []
        suspected_ai = []
        
        avg_texture = np.mean(texture_scores) if texture_scores else 0
        avg_movement = movement / frames if frames > 0 else 0
        avg_fft = np.mean(fft_scores) if fft_scores else 0
        avg_ela = np.mean(ela_scores) if ela_scores else 0
        
        # --- 11-POINT FORENSIC ANALYSIS ---
        
        # 1. Metadata Check
        if meta_score > 0:
            fake_score += meta_score
            evidence.extend(meta_ev)
            suspected_ai.append("Edited/Generated File")

        # 2. Audio Forensics
        if audio_score > 0:
            fake_score += audio_score
            evidence.extend(audio_ev)
            suspected_ai.append("Synthetic Audio")

        # 3. ELA Check (Patching)
        if avg_ela > 40: # High difference = Edit
            fake_score += 30
            evidence.append(f"ELA Analysis detected potential image splicing (Score: {int(avg_ela)}).")

        # 4. Viggle Check (Motion + No Blink)
        if avg_movement > 0.7 and blinks <= 1:
            fake_score += 85
            suspected_ai.append("Viggle AI")
            evidence.append(f"High kinetic motion (Score: {round(avg_movement, 1)}) with eyes nearly frozen.")

        # 5. Lip-Sync Check
        if mar_var > 0.005 and ear_var < 0.0005: 
            fake_score += 75
            suspected_ai.append("Wav2Lip / SadTalker")
            evidence.append("Mouth moving (talking) but upper face is static.")

        # 6. Static Image Check
        if avg_movement < 0.4:
            fake_score += 50
            suspected_ai.append("Static AI Animator")
            evidence.append("Micro-movement is unnaturally low (Static Image).")

        # 7. Frequency Check (Grid)
        if avg_fft > 12.0: 
            fake_score += 45
            suspected_ai.append("GANs/Diffusion")
            evidence.append(f"Frequency Grid artifacts detected (Score: {round(avg_fft, 1)}).")

        # 8. Texture Check
        if avg_texture < 35: 
            fake_score += 30
            evidence.append(f"Skin texture lacks biological detail (Score: {int(avg_texture)}).")

        # 9. Long Stare
        if frames > 120 and blinks == 0:
            fake_score += 25
            evidence.append("Subject maintained an impossible unblinking stare.")
            
        # 10. SynthID Check (Placeholder for Cloud API)
        # We check for specific high-frequency noise patterns that mimic watermarks
        if avg_fft > 20.0:
            evidence.append("High-frequency noise pattern detected (Possible Watermark).")

        # --- FINAL SCORING ---
        final_score = min(fake_score, 99)
        
        if final_score > 70:
            status = "FAKE: High Confidence"
        elif final_score > 40:
            status = "SUSPICIOUS / UNCERTAIN"
        else:
            status = "LIKELY REAL"
            final_score = 10
            evidence = ["Natural biological and file patterns detected."]
            suspected_ai = ["None"]

        ai_model_str = ", ".join(list(set(suspected_ai))) if suspected_ai else "None"
        if ai_model_str == "": ai_model_str = "None"

        return {
            "frames_analyzed": frames, "blinks_detected": blinks,
            "fake_score": final_score, "status": status,
            "suspected_ai": ai_model_str, "evidence": evidence,
            "texture_score": int(avg_texture)
        }

    def _generate_error_result(self, status):
        return {
            "frames_analyzed": 0, "blinks_detected": 0, "fake_score": 100,
            "status": status, "suspected_ai": "Corrupted File",
            "evidence": ["Video file structure is invalid."], "texture_score": 0
        }


























# import os
# import sys

# # --- 1. AGGRESSIVE SILENCE BLOCK (Cleaner Terminal) ---
# os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3' 
# os.environ['GLOG_minloglevel'] = '3'

# stderr_backup = sys.stderr
# sys.stderr = open(os.devnull, 'w')

# try:
#     import cv2
#     import numpy as np
#     import mediapipe as mp
#     test_load = mp.solutions.face_mesh
#     HAS_MEDIAPIPE = True
# except (ImportError, AttributeError):
#     HAS_MEDIAPIPE = False
#     mp = None
# finally:
#     sys.stderr = stderr_backup

# # --- END SILENCE BLOCK ---

# class DeepFakeSentry:
#     def __init__(self):
#         self.use_mediapipe = HAS_MEDIAPIPE
        
#         self.face_cascade_path = "haarcascade_frontalface_default.xml"
#         self.eye_cascade_path = "haarcascade_eye.xml"
        
#         self._download_model(self.face_cascade_path, "https://raw.githubusercontent.com/opencv/opencv/master/data/haarcascades/haarcascade_frontalface_default.xml")
#         self._download_model(self.eye_cascade_path, "https://raw.githubusercontent.com/opencv/opencv/master/data/haarcascades/haarcascade_eye.xml")

#         if self.use_mediapipe:
#             self.mp_face_mesh = mp.solutions.face_mesh
#             self.face_mesh = self.mp_face_mesh.FaceMesh(
#                 max_num_faces=1,
#                 refine_landmarks=True,
#                 min_detection_confidence=0.5,
#                 min_tracking_confidence=0.5
#             )
#         else:
#             self.face_cascade = cv2.CascadeClassifier(self.face_cascade_path)
#             self.eye_cascade = cv2.CascadeClassifier(self.eye_cascade_path)

#     def _download_model(self, filename, url):
#         import urllib.request
#         if not os.path.exists(filename):
#             try:
#                 with urllib.request.urlopen(url) as response, open(filename, 'wb') as out_file:
#                     out_file.write(response.read())
#             except Exception:
#                 pass

#     def analyze_video(self, video_path):
#         cap = cv2.VideoCapture(video_path)
        
#         # --- PHASE 1: FILE INTEGRITY CHECK ---
#         if not cap.isOpened():
#              return self._generate_error_result("FAKE: Corrupted File (WhatsApp Reject)")
        
#         fps = cap.get(cv2.CAP_PROP_FPS)
#         frame_count = cap.get(cv2.CAP_PROP_FRAME_COUNT)
        
#         if frame_count < 1 or fps <= 0:
#              return self._generate_error_result("FAKE: Invalid Video Structure")

#         # --- PHASE 2: BIOMETRIC & FREQUENCY ANALYSIS ---
#         frames_analyzed = 0
#         total_blinks = 0
#         total_head_movement = 0
#         texture_scores = []
#         fft_scores = [] 
        
#         prev_nose_landmark = None
#         eye_closed = False 
#         blink_frames_counter = 0 
        
#         # MediaPipe Eye Indices
#         LEFT_EYE = [362, 385, 387, 263, 373, 380]
#         RIGHT_EYE = [33, 160, 162, 133, 153, 144]

#         max_frames = 200
        
#         while cap.isOpened() and frames_analyzed < max_frames:
#             ret, frame = cap.read()
#             if not ret:
#                 break
            
#             frames_analyzed += 1
#             h, w, _ = frame.shape
#             gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

#             # Frequency Analysis (Every 10th frame)
#             if frames_analyzed % 10 == 0:
#                 fft_score = self._analyze_frequency_spectrum(gray)
#                 fft_scores.append(fft_score)

#             if self.use_mediapipe:
#                 # ================= MEDIAPIPE LOGIC =================
#                 rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
#                 results = self.face_mesh.process(rgb_frame)
                
#                 if results.multi_face_landmarks:
#                     for face_landmarks in results.multi_face_landmarks:
#                         landmarks = face_landmarks.landmark
                        
#                         # A. Head Movement
#                         nose_x, nose_y = int(landmarks[1].x * w), int(landmarks[1].y * h)
#                         nose_point = np.array([nose_x, nose_y])
                        
#                         if prev_nose_landmark is not None:
#                             dist = np.linalg.norm(nose_point - prev_nose_landmark)
#                             total_head_movement += dist
#                         prev_nose_landmark = nose_point

#                         # B. Skin Texture
#                         cheek_x, cheek_y = int(landmarks[234].x * w), int(landmarks[234].y * h)
#                         y1, y2 = max(0, cheek_y-20), min(h, cheek_y+20)
#                         x1, x2 = max(0, cheek_x-20), min(w, cheek_x+20)
                        
#                         if y2 > y1 and x2 > x1:
#                             cheek_roi = gray[y1:y2, x1:x2]
#                             if cheek_roi.size > 0:
#                                 variance = cv2.Laplacian(cheek_roi, cv2.CV_64F).var()
#                                 texture_scores.append(variance)

#                         # C. Blink Detection
#                         left_ear = self.calculate_ear(landmarks, LEFT_EYE, w, h)
#                         right_ear = self.calculate_ear(landmarks, RIGHT_EYE, w, h)
#                         avg_ear = (left_ear + right_ear) / 2.0

#                         if avg_ear < 0.22: 
#                             blink_frames_counter += 1
#                             eye_closed = True
#                         else: 
#                             if eye_closed and 1 <= blink_frames_counter <= 10:
#                                  total_blinks += 1
#                             blink_frames_counter = 0
#                             eye_closed = False
#             else:
#                 # ================= BACKUP OPENCV LOGIC =================
#                 faces = self.face_cascade.detectMultiScale(gray, 1.3, 5)
#                 if len(faces) > 0:
#                     (x, y, fw, fh) = faces[0]
#                     center = np.array([x + fw//2, y + fh//2])
#                     if prev_nose_landmark is not None:
#                         total_head_movement += np.linalg.norm(center - prev_nose_landmark)
#                     prev_nose_landmark = center
                    
#                     roi = gray[y:y+fh, x:x+fw]
#                     texture_scores.append(cv2.Laplacian(roi, cv2.CV_64F).var())
                    
#                     roi_eyes = gray[y:y+int(fh*0.6), x:x+fw]
#                     eyes = self.eye_cascade.detectMultiScale(roi_eyes)
#                     if len(eyes) == 0:
#                         blink_frames_counter += 1
#                     else:
#                         if blink_frames_counter > 1 and blink_frames_counter < 10:
#                             total_blinks += 1
#                         blink_frames_counter = 0

#         cap.release()
#         return self._calculate_verdict(frames_analyzed, total_blinks, total_head_movement, texture_scores, fft_scores)

#     def _analyze_frequency_spectrum(self, gray_frame):
#         try:
#             f = np.fft.fft2(gray_frame)
#             fshift = np.fft.fftshift(f)
#             magnitude_spectrum = 20 * np.log(np.abs(fshift) + 1e-9)
#             avg_energy = np.mean(magnitude_spectrum)
#             max_energy = np.max(magnitude_spectrum)
#             spike_ratio = max_energy / (avg_energy + 1e-5)
#             return spike_ratio
#         except Exception:
#             return 0

#     def calculate_ear(self, landmarks, indices, w, h):
#         def dist(p1_idx, p2_idx):
#             p1 = np.array([landmarks[p1_idx].x * w, landmarks[p1_idx].y * h])
#             p2 = np.array([landmarks[p2_idx].x * w, landmarks[p2_idx].y * h])
#             return np.linalg.norm(p1 - p2)
#         A = dist(indices[1], indices[5])
#         B = dist(indices[2], indices[4])
#         C = dist(indices[0], indices[3])
#         return (A + B) / (2.0 * C) if C != 0 else 0

#     def _calculate_verdict(self, frames, blinks, movement, texture_scores, fft_scores):
#         fake_score = 10 
#         status = "LIKELY REAL"
#         evidence = []
#         suspected_ai = "None"
        
#         avg_texture = np.mean(texture_scores) if texture_scores else 0
#         avg_movement = movement / frames if frames > 0 else 0
#         avg_fft = np.mean(fft_scores) if fft_scores else 0
        
#         # --- TUNED SCORING LOGIC ---
        
#         # 1. Viggle/Dance Check (The Fix for 'abhishek.mp4')
#         # If moving > 0.7 AND blinks <= 1 (Catches 0 OR 1 blink)
#         # Real dancers blink heavily. 1 blink in 8 seconds of dancing is impossible.
#         if avg_movement > 0.7 and blinks <= 1:
#             fake_score = 95
#             status = "FAKE: Robotic Eye Motion"
#             suspected_ai = "Viggle AI / MagicAnimate"
#             evidence.append(f"Subject is moving/dancing but eyes are nearly frozen ({blinks} blinks).")

#         # 2. Static Image Check
#         elif avg_movement < 0.4:
#             fake_score += 80
#             status = "FAKE: Static Image"
#             suspected_ai = "Midjourney / DALL-E"
#             evidence.append("Micro-movement is zero (Static Photo).")

#         # 3. Frequency Check (Digital Artifacts)
#         if avg_fft > 15.0: 
#             fake_score += 40
#             evidence.append("Strong digital artifacts found in frequency map.")

#         # 4. Texture Check (Relaxed for phone cameras)
#         if avg_texture < 30: 
#             fake_score += 20
#             evidence.append("Skin texture is unusually smooth.")

#         # 5. Low Blink Penalty (General)
#         if frames > 100 and blinks == 0:
#             fake_score += 30
#             evidence.append("Unnatural lack of blinking in long video.")

#         # Final Decision
#         if fake_score > 60:
#             if status == "LIKELY REAL": status = "SUSPICIOUS"
#         elif fake_score < 40:
#             status = "LIKELY REAL"
#             fake_score = 10
#             evidence.append("Natural biological patterns detected.")
        
#         return {
#             "frames_analyzed": frames, "blinks_detected": blinks,
#             "fake_score": min(fake_score, 99), "status": status,
#             "suspected_ai": suspected_ai, "evidence": evidence,
#             "texture_score": int(avg_texture)
#         }

#     def _generate_error_result(self, status):
#         return {
#             "frames_analyzed": 0, "blinks_detected": 0, "fake_score": 100,
#             "status": status, "suspected_ai": "Corrupted File",
#             "evidence": ["Video file structure is invalid."], "texture_score": 0
#         }


















# # import cv2
# # import os
# # import urllib.request
# # import numpy as np

# # class DeepFakeSentry:
# #     def __init__(self):
# #         # 1. Setup paths for standard OpenCV models
# #         self.face_cascade_path = "haarcascade_frontalface_default.xml"
# #         self.eye_cascade_path = "haarcascade_eye.xml"
        
# #         # 2. Auto-Download models if missing
# #         self.download_model(self.face_cascade_path, 
# #             "https://raw.githubusercontent.com/opencv/opencv/master/data/haarcascades/haarcascade_frontalface_default.xml")
# #         self.download_model(self.eye_cascade_path, 
# #             "https://raw.githubusercontent.com/opencv/opencv/master/data/haarcascades/haarcascade_eye.xml")

# #         # 3. Load Classifiers
# #         self.face_cascade = cv2.CascadeClassifier(self.face_cascade_path)
# #         self.eye_cascade = cv2.CascadeClassifier(self.eye_cascade_path)

# #     def download_model(self, filename, url):
# #         if not os.path.exists(filename):
# #             print(f"Downloading {filename}...")
# #             try:
# #                 with urllib.request.urlopen(url) as response, open(filename, 'wb') as out_file:
# #                     data = response.read()
# #                     out_file.write(data)
# #             except Exception as e:
# #                 print(f"Error downloading {filename}: {e}")

# #     def analyze_video(self, video_path):
# #         cap = cv2.VideoCapture(video_path)
        
# #         # --- Analysis Variables ---
# #         frames_analyzed = 0
# #         total_blinks = 0
        
# #         # State Machine: 0 = Eyes Open, 1 = Eyes Closed
# #         eye_state = 0 
# #         consecutive_closed_frames = 0
        
# #         # Movement Tracking (To detect static images)
# #         prev_face_center = None
# #         total_movement = 0

# #         max_frames = 150 # Analyze approx 5 seconds
        
# #         while cap.isOpened() and frames_analyzed < max_frames:
# #             ret, frame = cap.read()
# #             if not ret:
# #                 break
            
# #             frames_analyzed += 1
# #             gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            
# #             # 1. Detect Face
# #             faces = self.face_cascade.detectMultiScale(gray, 1.3, 5)
            
# #             if len(faces) > 0:
# #                 # Take the first face found
# #                 (x, y, w, h) = faces[0]
                
# #                 # --- Movement Check ---
# #                 face_center = np.array([x + w//2, y + h//2])
# #                 if prev_face_center is not None:
# #                     dist = np.linalg.norm(face_center - prev_face_center)
# #                     total_movement += dist
# #                 prev_face_center = face_center

# #                 # --- Blink Check ---
# #                 # Define Region of Interest (ROI) for eyes (top half of face)
# #                 roi_gray = gray[y:y + int(h*0.6), x:x + w]
# #                 eyes = self.eye_cascade.detectMultiScale(roi_gray, 1.1, 3)
                
# #                 # Logic: 
# #                 # If eyes detected -> State OPEN
# #                 # If face detected BUT no eyes -> State CLOSED (likely blinking)
                
# #                 eyes_visible = len(eyes) > 0
                
# #                 if not eyes_visible:
# #                     # Eyes are closed
# #                     consecutive_closed_frames += 1
# #                     eye_state = 1
# #                 else:
# #                     # Eyes are open
# #                     if eye_state == 1:
# #                         # Transition from Closed -> Open (A Blink!)
# #                         # Filter: A blink is usually 1-10 frames long. 
# #                         # If it was closed for 50 frames, that's not a blink (that's looking down/away).
# #                         if 1 <= consecutive_closed_frames <= 10:
# #                             total_blinks += 1
                    
# #                     # Reset
# #                     consecutive_closed_frames = 0
# #                     eye_state = 0
        
# #         cap.release()

# #         # --- FINAL SCORING LOGIC ---
# #         status = "Unknown"
# #         fake_score = 0
        
# #         # Calculate Blinks Per Minute (BPM) approximation
# #         # video fps is usually 30. 150 frames = 5 seconds.
# #         # BPM = (blinks / 5) * 60 = blinks * 12
# #         estimated_bpm = total_blinks * 12

# #         # 1. CHECK: Is it a static image? (Deepfake Type 1)
# #         if total_movement < 5: 
# #             fake_score = 95
# #             status = "FAKE: Static Image Detected (No head movement)"
        
# #         # 2. CHECK: Blink Rate (Deepfake Type 2)
# #         # Normal humans blink 10-20 times per minute (approx 1-2 times in 5 seconds).
# #         elif total_blinks == 0:
# #             fake_score = 85
# #             status = "SUSPICIOUS: Unnatural Stare (0 Blinks Detected)"
# #         elif estimated_bpm > 50:
# #             fake_score = 70
# #             status = "SUSPICIOUS: Rapid/Nervous Blinking (Possible AI Artifacts)"
# #         else:
# #             fake_score = 10
# #             status = "Likely Real: Natural behavior detected"

# #         return {
# #             "frames_analyzed": frames_analyzed,
# #             "blinks_detected": total_blinks,
# #             "fake_score": fake_score,
# #             "status": status
# #         }

