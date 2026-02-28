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
