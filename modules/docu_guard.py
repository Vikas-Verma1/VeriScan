import os
import json
from google import genai
from dotenv import load_dotenv

# Load the hidden environment variables
load_dotenv()

class DocuGuard:
    def __init__(self):
        # Pull key safely from the .env file
        self.gemini_api_key = os.getenv("GEMINI_API_KEY")
        self.client = genai.Client(api_key=self.gemini_api_key)

    def analyze_document(self, file_path):
        filename = os.path.basename(file_path)
        print(f"Sending {filename} to Gemini for Document Forgery Analysis...")
        
        try:
            sample_file = self.client.files.upload(file=file_path, config={'display_name': 'Suspected Document'})
            
            prompt = """
            You are an expert fraud investigator and digital forensics examiner. 
            Analyze this uploaded document (which could be an invoice, bank statement, ID, or official letter) for signs of forgery, manipulation, or digital alteration.
            
            Look closely for common document forgery artifacts:
            1. Mismatched fonts, inconsistent text sizing, or misaligned text blocks.
            2. Unnatural JPEG compression artifacts or "halos" around specific numbers or names (indicating Photoshop patching).
            3. Illogical data (e.g., math on an invoice that doesn't add up correctly, wrong dates, or weird formatting).
            4. Signs of digital pasting over physical paper.
            
            Provide a JSON response with exactly these keys:
            - "forgery_confidence": Score from 0 to 100 (100 = definitely manipulated/forged, 0 = highly likely authentic).
            - "is_forged": boolean (true if forgery_confidence > 50, false otherwise).
            - "anomalies_found": A list of strings detailing specific suspicious elements OR "No anomalies detected".
            - "extracted_text_summary": A brief 1-2 sentence summary of what the document claims to be (e.g., "An invoice from Company X for $500").
            - "verdict_summary": A 1-2 sentence explanation of your final conclusion.

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
            return {"document_file": filename, "error": f"Document Analysis Blocked or Failed. System error: {str(e)}"}

        return {
            "document_file": filename,
            "is_forged": ai_analysis.get("is_forged", False),
            "forgery_confidence": ai_analysis.get("forgery_confidence", 0),
            "anomalies_found": ai_analysis.get("anomalies_found", ["No specific anomalies noted."]),
            "extracted_text_summary": ai_analysis.get("extracted_text_summary", "Document content unknown."),
            "verdict_summary": ai_analysis.get("verdict_summary", "Analysis complete.")
        }