import os
import requests
import matplotlib.pyplot as plt
from googleapiclient.discovery import build
from dotenv import load_dotenv
from moviepy.editor import *

# Load Environment Variables
load_dotenv()
SPREADSHEET_ID = os.getenv("GOOGLE_SPREADSHEET_ID")
sheets_service = build('sheets', 'v4')

TARGET_TAB = "Production_Scripts"
AUDIO_DIR = "assets/audio"
VIDEO_DIR = "assets/videos"
TEMP_DIR = "assets/temp"
os.makedirs(VIDEO_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

# ---------------------------------------------------------
# HELPER: Free AI Background Generator
# ---------------------------------------------------------
def generate_background(topic, filename):
    if os.path.exists(filename): return filename
    
    print(f"🎨 Generating unique background for topic: {topic}...")
    safe_prompt = f"Stylized vector art realistic background for {topic}, highly saturated, bright clean colors, cinematic depth"
    url = f"https://image.pollinations.ai/prompt/{requests.utils.quote(safe_prompt)}?width=1440&height=1920&nologo=true"
    
    response = requests.get(url)
    with open(filename, 'wb') as f:
        f.write(response.content)
    return filename

# ---------------------------------------------------------
# HELPER: Glowing Pie Chart Generator
# ---------------------------------------------------------
def generate_pie_chart(pro_pct, con_pct, active_side, filename):
    fig, ax = plt.subplots(figsize=(4, 4), subplot_kw=dict(aspect="equal"))
    fig.patch.set_alpha(0.0)
    
    sizes = [pro_pct, con_pct]
    
    colors = ['#00FF88', '#222222'] if active_side == 'pro' else ['#222222', '#FF3366']
    explode = (0.15, 0) if active_side == 'pro' else (0, 0.15)
    
    wedges, texts, autotexts = ax.pie(
        sizes, explode=explode, colors=colors,
        autopct='%1.0f%%', shadow=True, startangle=90,
        textprops=dict(color="white", weight="bold", fontsize=20)
    )
    
    plt.savefig(filename, transparent=True, dpi=150, bbox_inches='tight')
    plt.close()
    return filename

# ---------------------------------------------------------
# HELPER: Flashing Subtitles (Viral Format)
# ---------------------------------------------------------
def create_flashing_subtitles(full_text, audio_duration):
    """Breaks a long sentence into fast-flashing 2-3 word chunks for high retention."""
    words = full_text.split()
    if not words: return []
    
    # Group words into chunks of 2
    chunks = [" ".join(words[i:i+2]) for i in range(0, len(words), 2)]
    
    clips = []
    chunk_duration = audio_duration / len(chunks)
    t_offset = 0
    
    for chunk in chunks:
        # Huge, aggressive text in the center of the screen
        clip = (TextClip(chunk, fontsize=110, color='#FFFF00', font='Impact', 
                         stroke_color='#000000', stroke_width=5, 
                         method='caption', size=(900, None), align='center')
                .set_duration(chunk_duration)
                .set_start(t_offset)
                .set_position('center'))
        clips.append(clip)
        t_offset += chunk_duration
        
    return clips

# ---------------------------------------------------------
# THE MAIN VIDEO COMPILER
# ---------------------------------------------------------
def compile_video(script):
    base_name = f"{script['date']}_{script['subreddit'].replace(' ', '_')}_row{script['row_index']}"
    print(f"🎬 Compiling Viral Format Video: Row {script['row_index']}...")

    # 1. Load Audio
    audio_hook = AudioFileClip(f"{AUDIO_DIR}/{base_name}_1_hook.wav")
    audio_pro = AudioFileClip(f"{AUDIO_DIR}/{base_name}_2_pro.wav")
    audio_con = AudioFileClip(f"{AUDIO_DIR}/{base_name}_3_con.wav")
    audio_outro = AudioFileClip(f"{AUDIO_DIR}/{base_name}_4_outro.wav")
    
    # 2. Generate 3 Distinct Backgrounds for visual resets
    bg_hook = generate_background(script['hook'][:80].strip(), f"{TEMP_DIR}/{base_name}_bg_hook.jpg")
    bg_pro = generate_background(script['pro'][:80].strip(), f"{TEMP_DIR}/{base_name}_bg_pro.jpg")
    bg_con = generate_background(script['con'][:80].strip(), f"{TEMP_DIR}/{base_name}_bg_con.jpg")

    # 3. Generate Charts
    pro_chart = generate_pie_chart(script['pro_pct'], script['con_pct'], 'pro', f"{TEMP_DIR}/{base_name}_chart_pro.png")
    con_chart = generate_pie_chart(script['pro_pct'], script['con_pct'], 'con', f"{TEMP_DIR}/{base_name}_chart_con.png")

    # 4. Build Individual Scenes
    # --- HOOK SCENE ---
    clip_bg_hook = ImageClip(bg_hook).resize(height=1920).set_position(lambda t: (-int(10 * t), 'center')).set_duration(audio_hook.duration)
    hook_texts = create_flashing_subtitles(script['hook'], audio_hook.duration)
    hook_comp = CompositeVideoClip([clip_bg_hook] + hook_texts, size=(1080, 1920)).set_audio(audio_hook)

    # --- PRO SCENE ---
    clip_bg_pro = ImageClip(bg_pro).resize(height=1920).set_position(lambda t: (-int(10 * t), 'center')).set_duration(audio_pro.duration)
    pro_texts = create_flashing_subtitles(script['pro'], audio_pro.duration)
    pro_chart_clip = ImageClip(pro_chart).set_duration(audio_pro.duration).set_position(('center', 1300))
    pro_comp = CompositeVideoClip([clip_bg_pro, pro_chart_clip] + pro_texts, size=(1080, 1920)).set_audio(audio_pro)

    # --- CON SCENE ---
    clip_bg_con = ImageClip(bg_con).resize(height=1920).set_position(lambda t: (-int(10 * t), 'center')).set_duration(audio_con.duration)
    con_texts = create_flashing_subtitles(script['con'], audio_con.duration)
    con_chart_clip = ImageClip(con_chart).set_duration(audio_con.duration).set_position(('center', 1300))
    con_comp = CompositeVideoClip([clip_bg_con, con_chart_clip] + con_texts, size=(1080, 1920)).set_audio(audio_con)

    # --- OUTRO SCENE ---
    # Reusing the hook background for a cyclic feel
    clip_bg_outro = ImageClip(bg_hook).resize(height=1920).set_position('center').set_duration(audio_outro.duration)
    outro_text = (TextClip("Which side are you on?\nAnswer below.", fontsize=90, color='#FFFF00', font='Impact', 
                           stroke_color='#000000', stroke_width=5, method='caption', size=(900, None), align='center')
                  .set_duration(audio_outro.duration).set_position('center'))
    outro_comp = CompositeVideoClip([clip_bg_outro, outro_text], size=(1080, 1920)).set_audio(audio_outro)

    # 5. Concatenate Scenes together
    final_video = concatenate_videoclips([hook_comp, pro_comp, con_comp, outro_comp], method="compose")
    
    output_path = f"{VIDEO_DIR}/{base_name}_FINAL.mp4"
    final_video.write_videofile(
        output_path, fps=30, codec="libx264", audio_codec="aac", threads=4, logger=None
    )
    print(f"✅ FINAL VIDEO RENDERED: {output_path}")

def process_video_pipeline():
    result = sheets_service.spreadsheets().values().get(spreadsheetId=SPREADSHEET_ID, range=f"{TARGET_TAB}!A:H").execute()
    rows = result.get('values', [])
    
    for i, row in enumerate(rows):
        if i == 0: continue
        if len(row) == 8 and row[7] == "Audio Generated":
            try:
                # Pure data pull
                script = {
                    "row_index": i + 1, "date": row[0], "subreddit": row[1],
                    "hook": row[2], 
                    "pro": f"Approximately {row[4]}% of users agree: {row[3]}",
                    "con": f"While {row[6]}% argue: {row[5]}",
                    "pro_pct": int(row[4]), "con_pct": int(row[6])
                }
                compile_video(script)
                
                sheets_service.spreadsheets().values().update(
                    spreadsheetId=SPREADSHEET_ID, range=f"{TARGET_TAB}!H{i+1}",
                    valueInputOption="RAW", body={'values': [["Video Completed"]]}
                ).execute()

                cleanup_temporary_assets(script)
                
            except Exception as e:
                print(f"❌ Failed to render video for row {i+1}: {e}")

def cleanup_temporary_assets(script):
    """Deletes temporary WAV pieces and raw background images to save disk space."""
    base_name = f"{script['date']}_{script['subreddit'].replace(' ', '_')}_row{script['row_index']}"
    print(f"🧹 Clearing temporary assets for {base_name}...")
    
    # 🎯 Updated to delete the 3 distinct backgrounds
    files_to_delete = [
        f"{AUDIO_DIR}/{base_name}_1_hook.wav",
        f"{AUDIO_DIR}/{base_name}_2_pro.wav",
        f"{AUDIO_DIR}/{base_name}_3_con.wav",
        f"{AUDIO_DIR}/{base_name}_4_outro.wav",
        f"{TEMP_DIR}/{base_name}_bg_hook.jpg",
        f"{TEMP_DIR}/{base_name}_bg_pro.jpg",
        f"{TEMP_DIR}/{base_name}_bg_con.jpg",
        f"{TEMP_DIR}/{base_name}_chart_pro.png",
        f"{TEMP_DIR}/{base_name}_chart_con.png"
    ]
    
    for file_path in files_to_delete:
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
        except Exception as e:
            print(f"⚠️ Could not delete file {file_path}: {e}")

if __name__ == "__main__":
    process_video_pipeline()
    print("🏁 Phase 5 Video pipeline completely finished.")