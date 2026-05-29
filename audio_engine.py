import os
import shutil
import soundfile as sf
from kokoro_onnx import Kokoro
from pydub import AudioSegment
from googleapiclient.discovery import build
from dotenv import load_dotenv


# Load Environment Variables
load_dotenv()
SPREADSHEET_ID = os.getenv("GOOGLE_SPREADSHEET_ID")

# Initialize Google Sheets Client
sheets_service = build('sheets', 'v4')
TARGET_TAB = "Production_Scripts"
AUDIO_DIR = "assets/audio"
os.makedirs(AUDIO_DIR, exist_ok=True)


# Ensure temp directory exists for raw wav files
TEMP_DIR = "assets/temp_raw_audio"
os.makedirs(TEMP_DIR, exist_ok=True)


# 🧠 Initialize Local AI Model 
print("🧠 Loading Kokoro-82M (v1.0) into memory...")
MODEL_PATH = "model_weights/kokoro-v1.0.onnx"
VOICES_PATH = "model_weights/voices-v1.0.bin"
kokoro = Kokoro(MODEL_PATH, VOICES_PATH)

# 🎯 CONFIGURATION: High-Velocity Settings
VOICE_NAME = "am_michael" 
AI_SPEED = 1.20              # Bumps the model's reading pace
POST_PROCESS_SPEED = 1.05    # Physical soundwave speed-up (5% extra tightness)

OUTRO_TEXT = "Which side are you on? Answer in the comments."
MASTER_OUTRO_PATH = f"{AUDIO_DIR}/master_outro.wav"

def speed_up_audio(target_path, speed_factor):
    """Physically speeds up the audio file wave parameters without changing pitch."""
    try:
        audio = AudioSegment.from_wav(target_path)
        # Change the sample rate frame pacing to accelerate speed
        fast_audio = audio._spawn(audio.raw_data, overrides={
            "frame_rate": int(audio.frame_rate * speed_factor)
        }).set_frame_rate(audio.frame_rate)
        
        fast_audio.export(target_path, format="wav")
    except Exception as e:
        print(f"⚠️ Post-process speed-up skipped (requires ffmpeg path setup): {e}")

def ensure_master_outro_exists():
    """Generates the permanent fixed CTA outro clip if it doesn't exist yet."""
    if not os.path.exists(MASTER_OUTRO_PATH):
        print("🎙️ Generating permanent Master Outro CTA track...")
        samples, sample_rate = kokoro.create(OUTRO_TEXT, voice=VOICE_NAME, speed=1.10)
        sf.write(MASTER_OUTRO_PATH, samples, sample_rate)
        # Apply extra post-processing speed to keep it snappy
        speed_up_audio(MASTER_OUTRO_PATH, POST_PROCESS_SPEED)
        print("💾 Permanent Master Outro saved successfully.")

def fetch_pending_scripts():
    """Fetches scripts that haven't had audio generated yet."""
    result = sheets_service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{TARGET_TAB}!A:H"
    ).execute()
    
    rows = result.get('values', [])
    if len(rows) <= 1: return []

    pending = []
    for i, row in enumerate(rows):
        if i == 0: continue 
        
        if len(row) >= 8 and row[7] == "Ready for Video Production":
            pending.append({
                "row_index": i + 1,
                "date": row[0],
                "subreddit": row[1],
                "hook": row[2],
                "pro": f"Approximately {row[4]} percent of users in the debate believe {row[3]}",
                "con": f"While {row[6]} percent argue that {row[5]}"
            })
    return pending

def update_status(row_index):
    """Marks the script as completed in the database."""
    sheets_service.spreadsheets().values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{TARGET_TAB}!H{row_index}",
        valueInputOption="RAW",
        body={'values': [["Audio Generated"]]}
    ).execute()

def generate_local_audio(text, filename):
    """Generates studio-quality accelerated audio, prepending silence for the hook."""
    # Build a temporary path for the rawwav file
    raw_path = f"{TEMP_DIR}/raw_{os.path.basename(filename)}"
    
    # 1. Generate the standard high-speed audio to the temp folder
    samples, sample_rate = kokoro.create(text, voice=VOICE_NAME, speed=AI_SPEED)
    sf.write(raw_path, samples, sample_rate)
    
    # 2. Add an automated post-process speed-up compressor trick
    speed_up_audio(raw_path, POST_PROCESS_SPEED)
    
    # 3. Handle physical silence prepending
    audio = AudioSegment.from_wav(raw_path)
    
    # 🎯 NEW: Create exactly 0.5 seconds of dead silence
    intro_silence = AudioSegment.silent(duration=500)
    
    # Prepend silence only to the HOOK track
    if "_1_hook" in filename:
        print("🤫 Adding 0.5 seconds of introductory silence to hook...")
        final_audio = intro_silence + audio
    else:
        final_audio = audio
        
    # Export the final track bundle
    final_audio.export(filename, format="wav")
    
    # Clean up the raw file (optional, but keeps temp clean)
    os.remove(raw_path)

def process_audio_pipeline():
    print("🎧 Booting up Phase 4: Fast-Paced Open-Source Audio Pipeline...")
    ensure_master_outro_exists()
    
    scripts = fetch_pending_scripts()
    if not scripts:
        print("✅ No pending scripts found. Everything is up to date.")
        return

    for script in scripts:
        safe_sub = script['subreddit'].replace(" ", "_")
        base_filename = f"{AUDIO_DIR}/{script['date']}_{safe_sub}_row{script['row_index']}"
        
        print(f"🎙️ Generating High-Speed Audio Elements for: r/{script['subreddit']} (Row {script['row_index']})")
        
        try:
            # Generate and automatically accelerate each track chunk
            generate_local_audio(script['hook'], f"{base_filename}_1_hook.wav")
            generate_local_audio(script['pro'], f"{base_filename}_2_pro.wav")
            generate_local_audio(script['con'], f"{base_filename}_3_con.wav")
            
            # Copy our snappy master outro
            shutil.copy(MASTER_OUTRO_PATH, f"{base_filename}_4_outro.wav")

            #  # 🎯 NEW: Cleanup temp folder after row processing
            shutil.rmtree(TEMP_DIR)
            os.makedirs(TEMP_DIR, exist_ok=True) # Reset for next row
            
            update_status(script['row_index'])
            print(f"💾 Saved high-speed WAV bundle and updated database records.\n")
            
        except Exception as e:
            print(f"❌ Kokoro Engine Error on row {script['row_index']}: {e}")

if __name__ == "__main__":
    process_audio_pipeline()
    print("🏁 Phase 4 Audio pipeline execution sequence complete.")