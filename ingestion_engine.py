import os
import datetime
import json
import asyncio
from playwright.async_api import async_playwright
from googleapiclient.discovery import build
from dotenv import load_dotenv

load_dotenv()
SPREADSHEET_ID = os.getenv("GOOGLE_SPREADSHEET_ID")
sheets_service = build('sheets', 'v4')

# Generate today's date as our Tab/Partition Name (e.g., "2026-05-28")
TODAY_TAB_NAME = datetime.datetime.now().strftime("%Y-%m-%d")
YESTERDAY_TAB_NAME = (datetime.datetime.now() - datetime.timedelta(days=1)).strftime("%Y-%m-%d")
def ensure_daily_sheet_exists():
    """
    Manages daily partition tabs. 
    If today's tab exists, it truncates (wipes) all data to force a clean overwrite.
    If it doesn't exist, it creates it.
    """
    try:
        # 1. Fetch all current tabs in the spreadsheet
        sheet_metadata = sheets_service.spreadsheets().get(spreadsheetId=SPREADSHEET_ID).execute()
        sheets = sheet_metadata.get('sheets', '')
        sheet_names = [sheet.get("properties", {}).get("title", "") for sheet in sheets]
        
        # 2. If the tab exists, clear it completely for a fresh overwrite
        if TODAY_TAB_NAME in sheet_names:
            print(f"🧹 Tab '{TODAY_TAB_NAME}' already exists. Wiping old data for a fresh overwrite...")
            sheets_service.spreadsheets().values().clear(
                spreadsheetId=SPREADSHEET_ID,
                range=f"{TODAY_TAB_NAME}!A:F",
                body={}
            ).execute()
        else:
            # Create the sheet if it's the first run of the day
            print(f"🆕 Creating new daily partition tab: '{TODAY_TAB_NAME}'")
            batch_update_request = {
                "requests": [{"addSheet": {"properties": {"title": TODAY_TAB_NAME}}}]
            }
            sheets_service.spreadsheets().batchUpdate(
                spreadsheetId=SPREADSHEET_ID, body=batch_update_request).execute()
        
        # 3. Write a fresh Header Row (for both brand new and freshly wiped sheets)
        headers = [["id", "timestamp", "genre", "raw_topic", "post_body", "raw_comments_blob"]]
        sheets_service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{TODAY_TAB_NAME}!A1:F1",
            valueInputOption="RAW",
            body={'values': headers}
        ).execute()
            
    except Exception as e:
        print(f"❌ Error during sheet truncation/creation: {e}")

def get_existing_ids():
    """
    Looks back at yesterday's sheet partition to pull already processed IDs.
    This prevents scraping the same rolling 24h viral posts on consecutive days.
    """
    try:
        # Check if yesterday's tab even exists in the spreadsheet metadata first
        sheet_metadata = sheets_service.spreadsheets().get(spreadsheetId=SPREADSHEET_ID).execute()
        sheets = sheet_metadata.get('sheets', '')
        sheet_names = [sheet.get("properties", {}).get("title", "") for sheet in sheets]
        
        if YESTERDAY_TAB_NAME not in sheet_names:
            print(f"ℹ️ No historical tab found for yesterday ({YESTERDAY_TAB_NAME}). Skipping history check.")
            return set()
            
        print(f"🔍 Reading historical post IDs from yesterday's tab ({YESTERDAY_TAB_NAME}) to prevent cross-day duplication...")
        result = sheets_service.spreadsheets().values().get(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{YESTERDAY_TAB_NAME}!A2:A" # Read only Column A (IDs)
        ).execute()
        
        rows = result.get('values', [])
        # Extract IDs into a set for O(1) lightning-fast lookups
        historical_ids = set([row[0] for row in rows if row])
        print(f"🚫 Found {len(historical_ids)} IDs to guard against.")
        return historical_ids
        
    except Exception as e:
        print(f"⚠️ Could not read yesterday's history (it might be empty or deleted): {e}")
        return set()

def write_to_sheet(row_data):
    """Appends a completed raw dataset row to today's staging sheet."""
    try:
        body = {'values': [row_data]}
        sheets_service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{TODAY_TAB_NAME}!A:F", # Writing strictly to today's tab
            valueInputOption="RAW",
            body=body
        ).execute()
        print("📁 Successfully committed raw data row to Google Sheet.")
    except Exception as e:
        print(f"❌ Failed writing to Google Sheet: {e}")

async def scrape_post_details(context, permalink):
    """
    Uses the Dual-URL Hack to let Reddit's backend do the heavy lifting.
    Pass 1: Default sort (Best/Top) for Consensus.
    Pass 2: Controversial sort for Dissent.
    """
    base_url = f"https://www.reddit.com{permalink}"
    
    # ---------------------------------------------------------
    # PASS 1: The Consensus (Default Sort)
    # ---------------------------------------------------------
    page = await context.new_page()
    await page.goto(base_url, wait_until="domcontentloaded")
    await page.wait_for_timeout(3000)
    
    # Grab the full post body while we are here
    body_locator = page.locator("shreddit-post div[slot='text-body']")
    post_body = await body_locator.text_content() if await body_locator.count() > 0 else ""
    post_body = post_body.strip()
    
    # Shallow scroll to load the top-level trunk (No deep nesting required!)
    for _ in range(2):
        await page.evaluate("window.scrollBy(0, window.innerHeight);")
        await page.wait_for_timeout(1000)
        
    # JS Bouncer: Grab the first 10 valid human comments from the "Best" feed
    pass_1_comments = await page.evaluate("""() => {
        const allComments = Array.from(document.querySelectorAll('shreddit-comment'));
        const validTexts = [];
        
        for (const comment of allComments) {
            if (validTexts.length >= 10) break; // Stop at 10
            
            const author = (comment.getAttribute('author') || '').toLowerCase();
            if (author === 'automoderator' || author.includes('bot')) continue;
            
            const scoreStr = comment.getAttribute('score');
            const score = scoreStr ? parseInt(scoreStr, 10) : 1; 
            
            const paragraphs = Array.from(comment.querySelectorAll('p'));
            const fullText = paragraphs.map(p => p.innerText.trim()).join(' ');
            
            if (fullText.split(/\\s+/).length > 3) {
                // Grab Reddit's official comment ID so we can deduplicate later
                const real_id = comment.getAttribute('thingid') || Math.random().toString();
                validTexts.push({id: real_id, score: score, text: fullText});
            }
        }
        return validTexts;
    }""")

    # ---------------------------------------------------------
    # PASS 2: The Dissent (Controversial Sort)
    # ---------------------------------------------------------
    print("🔄 Pass 1 Complete. Appending ?sort=controversial to find the Dissent...")
    await page.goto(f"{base_url}?sort=controversial", wait_until="domcontentloaded")
    await page.wait_for_timeout(3000)
    
    for _ in range(2):
        await page.evaluate("window.scrollBy(0, window.innerHeight);")
        await page.wait_for_timeout(1000)
        
    # JS Bouncer: Grab the first 10 valid human comments from the "Controversial" feed
    pass_2_comments = await page.evaluate("""() => {
        const allComments = Array.from(document.querySelectorAll('shreddit-comment'));
        const validTexts = [];
        
        for (const comment of allComments) {
            if (validTexts.length >= 10) break; 
            
            const author = (comment.getAttribute('author') || '').toLowerCase();
            if (author === 'automoderator' || author.includes('bot')) continue;
            
            const scoreStr = comment.getAttribute('score');
            // If hidden on controversial, it usually leans negative
            const score = scoreStr ? parseInt(scoreStr, 10) : -1; 
            
            const paragraphs = Array.from(comment.querySelectorAll('p'));
            const fullText = paragraphs.map(p => p.innerText.trim()).join(' ');
            
            if (fullText.split(/\\s+/).length > 3) {
                const real_id = comment.getAttribute('thingid') || Math.random().toString();
                validTexts.push({id: real_id, score: score, text: fullText});
            }
        }
        return validTexts;
    }""")
    
    await page.close()
    
    # ---------------------------------------------------------
    # PASS 3: Merge, Deduplicate, and Re-Index
    # ---------------------------------------------------------
    seen_ids = set()
    final_comments = []
    
    # Combine both passes. If a comment appears in both (rare, but possible), it only gets added once.
    for c in pass_1_comments + pass_2_comments:
        if c['id'] not in seen_ids:
            seen_ids.add(c['id'])
            final_comments.append(c)
            
    # Rewrite the IDs to a clean c_0, c_1 format so Gemini can map them perfectly in Phase 2
    for idx, c in enumerate(final_comments):
        c['id'] = f"c_{idx}"
        
    print(f"⚖️ Dual-URL Hack Complete. Extracted {len(final_comments)} balanced comments.")
    return post_body, final_comments

async def run_pipeline():
    print(f"🚀 Initializing Playwright ELT Ingestion... [Target Partition: {TODAY_TAB_NAME}]")
    
    # Run the database architecture setup first
    ensure_daily_sheet_exists()
    existing_ids = get_existing_ids()
    
    target_subs = ["SubredditDrama", "unpopularopinion", "TrueUnpopularOpinion"]
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        )
        page = await context.new_page()
        
        for sub in target_subs:
            url = f"https://www.reddit.com/r/{sub}/top/?t=day"
            print(f"\n🔍 Scanning r/{sub} feed...")
            # FIX: Changed to domcontentloaded
            await page.goto(url, wait_until="domcontentloaded")
            await page.wait_for_timeout(3000)
            
            posts = await page.locator("shreddit-post").all()
            valid_post_count = 0
            
            for post in posts:
                if valid_post_count >= 3: # (Adjusted to your 3 posts per sub plan!)
                    break
                    
                post_id = await post.get_attribute("id")
                
                # 🎯 THIS NOW WORKS CROSS-DAY: Skips if processed yesterday!
                if post_id in existing_ids:
                    print(f"⏭️ Skipping post {post_id} - already processed yesterday.")
                    continue
                    
                # post_id = await post.get_attribute("id")
                # if post_id in existing_ids:
                #     continue
                    
                post_type = await post.get_attribute("post-type")
                if post_type and post_type != "text":
                    continue
                    
                title = await post.get_attribute("post-title")
                permalink = await post.get_attribute("permalink")
                
                print(f"📥 Extracting post body and deep comment trees for: '{title[:45]}...'")
                
                # 🎯 NEW: Receive both the body and comments from the post page
                post_body, raw_comments = await scrape_post_details(context, permalink)
                
                if len(raw_comments) < 10:
                    print("⚠️ Insufficient comment depth found, skipping thread.")
                    continue
                
                # --- NEW LIMITER LOGIC (Option 1) ---
                safe_comments = []
                current_length = 2 # Start at 2 to account for the outer JSON brackets []
                
                for comment in raw_comments:
                    # Measure the exact string size of this dictionary when turned into JSON text
                    comment_string_len = len(json.dumps(comment)) + 1 # +1 for the separating comma
                    
                    if current_length + comment_string_len < 48000: 
                        safe_comments.append(comment)
                        current_length += comment_string_len
                    else:
                        print(f"✂️ Hit 48k char limit. Kept {len(safe_comments)} out of {len(raw_comments)} comments.")
                        break
                
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                comments_serialized = json.dumps(safe_comments)
                
                row_payload = [post_id, timestamp, sub, title, post_body, comments_serialized]
                write_to_sheet(row_payload)
                valid_post_count += 1
                
        await browser.close()
        print("\n✅ Phase 1 Raw Data Ingestion Complete.")

if __name__ == "__main__":
    asyncio.run(run_pipeline())