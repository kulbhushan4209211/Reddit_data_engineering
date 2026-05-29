import os
import datetime
import json
import re
import statistics
import pandas as pd
from textblob import TextBlob
from googleapiclient.discovery import build
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Load Environment Variables
load_dotenv()
SPREADSHEET_ID = os.getenv("GOOGLE_SPREADSHEET_ID")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# Initialize API Clients
sheets_service = build('sheets', 'v4')
ai_client = genai.Client(api_key=GEMINI_API_KEY)

# TODAY_TAB_NAME = datetime.datetime.now().strftime("%Y-%m-%d")
TODAY_TAB_NAME = '2026-05-28'
def fetch_raw_data():
    """Reads the raw data from today's daily partition sheet."""
    try:
        print(f"📖 Fetching raw ingestion data from tab: {TODAY_TAB_NAME}...")
        result = sheets_service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{TODAY_TAB_NAME}!A:F"
        ).execute()
        
        rows = result.get('values', [])
        if not rows or len(rows) <= 1:
            print("⚠️ No data rows found to process today.")
            return None
            
        headers = rows[0]
        data_records = rows[1:]
        return pd.DataFrame(data_records, columns=headers)
    except Exception as e:
        print(f"❌ Failed reading from Google Sheets: {e}")
        return None

def clean_post_body(text):
    """Cleans structural debris and whitespace out of the scraped post body."""
    if not text or pd.isna(text): return ""
    text = re.sub(r'(?i)\bread more\b|\bview more\b', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def calculate_divergence_via_metrics(row):
    """
    Finds real debate using concrete structural numbers.
    Highly active comment pools mean deep human engagement.
    """
    try:
        comments_list = json.loads(row['raw_comments_blob'])
        total_comments_scraped = len(comments_list)
        
        if total_comments_scraped == 0:
            return 0
            
        # Calculate the variance in upvotes among the top comments.
        # High variance means some counter-arguments are getting mass-upvoted!
        scores = [c['score'] for c in comments_list]
        if len(scores) >= 2:
            return statistics.stdev(scores)
        return total_comments_scraped
    except Exception:
        return 0

def call_gemini_analyzer(post_title, clean_body, comments_list):
    """Sends top comments to Gemini, demanding an Instagram Hook and strict JSON categorization."""
    
    prompt = f"""
    You are a viral content strategist and data analyst. Combine these skills to break down an internet debate.
    
    POST TITLE: {post_title}
    POST BODY: {clean_body}
    
    COMMENTS POOL:
    {json.dumps(comments_list, indent=2)}
    
    CRITICAL INSTRUCTIONS:
    1. Write an 'instagram_hook'. This must be a highly engaging, controversial 1-sentence scroll-stopper. 
    2. Write a 1-sentence 'PRO' argument.
    3. Write a 1-sentence 'CON' argument. 
    4. AUDIO SCRIPTING RULES: Write these statements for a dramatic voice actor. 
       - Use ellipses (...) to force dramatic pauses and breaths. 
       - Use em-dashes (—) for sharp shifts in tone. 
       - Capitalize ONE OR TWO words per sentence to force vocal emphasis. 
       - End the hook with an exclamation point (!) to raise energy.
    5. Categorize every comment ID into 'pro', 'con', or 'neutral'.
    
    Output ONLY valid JSON in this exact structure:
    {{
      "instagram_hook": "A viral, high-retention opening hook statement",
      "pro_statement": "The core pro argument sentence",
      "con_statement": "The core con argument sentence",
      "classification": {{"c_0": "pro", "c_1": "con", "c_2": "neutral"}}
    }}
    """
    
    response = ai_client.models.generate_content(
        model='gemini-2.5-flash-lite',
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            temperature=0.4, # Raised slightly to give the Instagram Hook some creative edge
        ),
    )
    return json.loads(response.text)
    

def process_pipeline():
    df = fetch_raw_data()
    if df is None or df.empty: 
        return [] # Return empty list if no data
        
    print(f"📋 Loaded {len(df)} posts into memory. Applying text sanitation & divergence math...")
    
    df['post_body_clean'] = df['post_body'].apply(clean_post_body)
    df['divergence'] = df.apply(calculate_divergence_via_metrics, axis=1)
    top_3_df = df.nlargest(3, 'divergence')
    
    # Create an empty list to store our final video objects
    final_video_scripts = []
    
    for index, row in top_3_df.iterrows():
        post_title = row['raw_topic']
        clean_body = row['post_body_clean']
        comments_list = json.loads(row['raw_comments_blob'])
        sub = row['genre']
        
        print(f"🧠 Sending to Gemini: 'r/{sub} | {post_title[:40]}...'")
        
        try:
            gemini_data = call_gemini_analyzer(post_title, clean_body, comments_list)
            
            pro_score = 0
            con_score = 0
            
            for comment in comments_list:
                c_id = comment['id']
                raw_score = comment["score"] 
                stance = gemini_data["classification"].get(c_id, "neutral")
                
                if stance == "pro":
                    if raw_score >= 0: pro_score += raw_score
                    else: con_score += abs(raw_score) 
                elif stance == "con":
                    if raw_score >= 0: con_score += raw_score
                    else: pro_score += abs(raw_score)
                    
            total_score = pro_score + con_score
            if total_score > 0:
                pro_percentage = round((pro_score / total_score) * 100)
                con_percentage = round((con_score / total_score) * 100)
            else:
                pro_percentage, con_percentage = 50, 50
            
            # 🎯 THE FIX: Force 100/0 splits to 99/1 to prevent visual UI glitches downstream
            if pro_percentage >= 100:
                pro_percentage = 99
                con_percentage = 1
            elif con_percentage >= 100:
                con_percentage = 99
                pro_percentage = 1
            
            # Package all the calculated data into a clean dictionary
            script_package = {
                "date": datetime.datetime.now().strftime("%Y-%m-%d"),
                "subreddit": sub,
                "instagram_hook": gemini_data.get('instagram_hook', ''),
                "pro_statement": gemini_data.get('pro_statement', ''),
                "pro_percentage": pro_percentage,
                "con_statement": gemini_data.get('con_statement', ''),
                "con_percentage": con_percentage,
                "status": "Ready for Video Production"
            }
            
            final_video_scripts.append(script_package)
            print(f"✅ Successfully packaged script for: {post_title[:20]}...")
            
        except Exception as e:
            print(f"❌ Failed to process with Gemini: {e}")

    # Return the data to whatever script called this function
    return final_video_scripts

# 🎯 NEW: Only run this if we are testing the file directly, otherwise just act as a module
if __name__ == "__main__":
    scripts = process_pipeline()
    print(f"\n🎉 Pipeline finished. Generated {len(scripts)} scripts.")