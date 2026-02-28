import os
import requests
import shutil
import json
from urllib.parse import urlparse
from google import genai
from dotenv import load_dotenv

# Load the hidden environment variables
load_dotenv()

class PhishGuard:
    def __init__(self, upload_folder):
        self.upload_folder = upload_folder
        
        # Pull keys safely from the .env file
        self.screenshot_api_key = os.getenv("SCREENSHOT_API_KEY")
        self.screenshot_api_url = "https://shot.screenshotapi.net/screenshot"
        
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        
        # Initialize the Gemini Client
        self.client = genai.Client(api_key=self.gemini_api_key)

    def analyze_url(self, url):
        screenshot_filename = "site_screenshot.png"
        screenshot_path = os.path.join(self.upload_folder, screenshot_filename)
        domain = urlparse(url).netloc
        
        print(f"Sending {url} to Sandbox API...")
        params = {
            "token": self.screenshot_api_key,
            "url": url,
            "width": 1280,
            "height": 720,
            "output": "image",
            "file_type": "png",
            "wait_for_event": "load"
        }

        try:
            response = requests.get(self.screenshot_api_url, params=params, stream=True)
            if response.status_code == 200:
                with open(screenshot_path, 'wb') as out_file:
                    shutil.copyfileobj(response.raw, out_file)
                print("Screenshot downloaded successfully.")
            else:
                return {"screenshot": screenshot_filename, "domain": domain, "error": "Could not verify site safety. Sandbox API Error."}
        except Exception as e:
            return {"screenshot": screenshot_filename, "domain": domain, "error": f"Connection failed: {str(e)}"}

        print("Sending screenshot and URL to Gemini for forensic analysis...")
        
        try:
            sample_file = self.client.files.upload(file=screenshot_path, config={'display_name': 'Website Screenshot'})
            
            prompt = f"""
            You are an expert cybersecurity analyst. I am providing you with the URL: {url}
            and a screenshot of the website loaded safely in a sandbox. 
            
            Analyze the image and the URL, and provide a JSON response with the following keys exactly:
            - "requested_details": A list of strings describing what information the site is asking the user to fill out.
            - "ads_detected": A brief description of any ads shown (or "None detected").
            - "domain_analysis": Does the URL domain look legitimate, or is it typosquatting/suspicious?
            - "phishing_risk": Score from 1 to 100 (100 being extremely dangerous).
            - "alert": boolean (true if risk is > 50, false otherwise).
            - "message": A 1-2 sentence final verdict on the safety of this website.

            Output ONLY valid JSON. Do not include markdown formatting.
            """

            response = self.client.models.generate_content(
                model='gemini-2.5-flash',
                contents=[sample_file, prompt]
            )
            
            self.client.files.delete(name=sample_file.name)

            raw_text = response.text.strip()
            if raw_text.startswith("```json"):
                raw_text = raw_text[7:-3].strip()
                
            ai_analysis = json.loads(raw_text)

        except Exception as e:
            return {
                "screenshot": screenshot_filename, "domain": domain, "alert": True,
                "message": f"AI Analysis Blocked. This usually happens if the site contains unsafe/explicit content. System error: {str(e)}",
                "requested_details": ["Unknown"], "ads_detected": "Unknown", "domain_analysis": "Unknown", "phishing_risk": 100
            }

        return {
            "screenshot": screenshot_filename, "domain": domain,
            "alert": ai_analysis.get("alert", False),
            "message": ai_analysis.get("message", "Analysis complete."),
            "requested_details": ai_analysis.get("requested_details", []),
            "ads_detected": ai_analysis.get("ads_detected", "Unknown"),
            "domain_analysis": ai_analysis.get("domain_analysis", "Unknown"),
            "phishing_risk": ai_analysis.get("phishing_risk", 0)
        }
