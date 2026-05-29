import os
from googleapiclient.discovery import build
from dotenv import load_dotenv

# Import your modularized transformation logic!
from transformation_engine import process_pipeline

load_dotenv()
SPREADSHEET_ID = os.getenv("GOOGLE_SPREADSHEET_ID")
sheets_service = build('sheets', 'v4')

TARGET_TAB = "Production_Scripts"

def ensure_production_tab_exists():
    """Checks if the Gold Layer tab exists, creates it with headers if it doesn't."""
    sheet_metadata = sheets_service.spreadsheets().get(spreadsheetId=SPREADSHEET_ID).execute()
    sheets = sheet_metadata.get('sheets', '')
    sheet_names = [sheet.get("properties", {}).get("title", "") for sheet in sheets]
    
    if TARGET_TAB not in sheet_names:
        print(f"🆕 Creating permanent '{TARGET_TAB}' tab...")
        batch_update_request = {
            "requests": [{"addSheet": {"properties": {"title": TARGET_TAB}}}]
        }
        sheets_service.spreadsheets().batchUpdate(
            spreadsheetId=SPREADSHEET_ID, body=batch_update_request).execute()
            
        # Write permanent headers
        headers = [["Date", "Subreddit", "Instagram Hook", "Pro Statement", "Pro %", "Con Statement", "Con %", "Status"]]
        sheets_service.spreadsheets().values().append(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{TARGET_TAB}!A1:H1",
            valueInputOption="RAW",
            body={'values': headers}
        ).execute()
    else:
        print(f"✅ '{TARGET_TAB}' tab verified.")

def publish_scripts(scripts_data):
    """Takes the dictionary list and appends it to the Google Sheet."""
    if not scripts_data:
        print("⚠️ No scripts to publish today.")
        return

    # Convert the list of dictionaries into a list of lists (which Google Sheets requires)
    rows_to_insert = []
    for script in scripts_data:
        row = [
            script["date"],
            script["subreddit"],
            script["instagram_hook"],
            script["pro_statement"],
            script["pro_percentage"],
            script["con_statement"],
            script["con_percentage"],
            script["status"]
        ]
        rows_to_insert.append(row)
        
    # Append the new rows to the bottom of the Production sheet
    sheets_service.spreadsheets().values().append(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{TARGET_TAB}!A:H",
        valueInputOption="RAW",
        body={'values': rows_to_insert}
    ).execute()
    
    print(f"🚀 Successfully published {len(rows_to_insert)} final video scripts to Google Sheets!")

def run_daily_production():
    print("🎬 Starting Phase 2 & 3: Transform and Publish Pipeline...")
    ensure_production_tab_exists()
    
    # 1. Ask transform_engine to do the heavy lifting and give us the results
    final_scripts = process_pipeline()
    
    # 2. Publish those results to the permanent database
    publish_scripts(final_scripts)
    print("🏁 Daily pipeline completely finished.")

if __name__ == "__main__":
    run_daily_production()