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
    
    # 🎨 Topic-specific prompt using the actual script hook
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
# HELPER: High-Contrast Text Overlay Builder
# ---------------------------------------------------------
def create_text_overlay(text, duration):
    # 🎯 OPTIMIZATION: Switched to universal 'Impact' font, dropped size to 52 for clean scaling
    return TextClip(
        text, fontsize=52, color='#00FFFF', font='Impact', 
        stroke_color='#000000', stroke_width=3, # Black outline for maximum contrast
        size=(920, None), method='caption', align='center',
        bg_color='rgba(0,0,0,0.3)' # Lighter background tint
    ).set_duration(duration)

# ---------------------------------------------------------
# THE MAIN VIDEO COMPILER
# ---------------------------------------------------------
def compile_video(script):
    base_name = f"{script['date']}_{script['subreddit'].replace(' ', '_')}_row{script['row_index']}"
    print(f"🎬 Compiling Viral Format Video: Row {script['row_index']}...")

    # Load Audio
    audio_hook = AudioFileClip(f"{AUDIO_DIR}/{base_name}_1_hook.wav")
    audio_pro = AudioFileClip(f"{AUDIO_DIR}/{base_name}_2_pro.wav")
    audio_con = AudioFileClip(f"{AUDIO_DIR}/{base_name}_3_con.wav")
    audio_outro = AudioFileClip(f"{AUDIO_DIR}/{base_name}_4_outro.wav")
    final_audio = concatenate_audioclips([audio_hook, audio_pro, audio_con, audio_outro])
    
    # 🎯 Generate topic-specific background (uses the first 80 chars of the hook)
    topic_snippet = script['hook'][:80].strip()
    bg_img_path = generate_background(topic_snippet, f"{TEMP_DIR}/{base_name}_bg.jpg")
    
    # Generate Charts
    pro_chart = generate_pie_chart(script['pro_pct'], script['con_pct'], 'pro', f"{TEMP_DIR}/{base_name}_chart_pro.png")
    con_chart = generate_pie_chart(script['pro_pct'], script['con_pct'], 'con', f"{TEMP_DIR}/{base_name}_chart_con.png")

    # The 1440px wide Animated Panning Background
    moving_bg = (ImageClip(bg_img_path)
                 .resize(height=1920)
                 .set_position(lambda t: (-int(6 * t), 'center'))
                 .set_duration(final_audio.duration))

    # Master Timeline Composition
    t_start = 0
    
    hook_text = create_text_overlay(script['hook'], audio_hook.duration).set_position('center').set_start(t_start)
    t_start += audio_hook.duration

    pro_text = create_text_overlay(script['pro'], audio_pro.duration).set_position(('center', 250)).set_start(t_start)
    pro_chart_clip = ImageClip(pro_chart).set_duration(audio_pro.duration).set_position(('center', 1100)).set_start(t_start)
    t_start += audio_pro.duration

    con_text = create_text_overlay(script['con'], audio_con.duration).set_position(('center', 250)).set_start(t_start)
    con_chart_clip = ImageClip(con_chart).set_duration(audio_con.duration).set_position(('center', 1100)).set_start(t_start)
    t_start += audio_con.duration

    outro_text = create_text_overlay("Which side are you on?\nAnswer in the comments.", audio_outro.duration).set_position('center').set_start(t_start)

    # Snap everything to the 1080x1920 frame
    final_video = CompositeVideoClip(
        [moving_bg, hook_text, pro_text, pro_chart_clip, con_text, con_chart_clip, outro_text],
        size=(1080, 1920)
    ).set_audio(final_audio)
    
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
                # 🎯 Pure data pull. No overrides. It trusts the sheet entirely.
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
    
    # Define paths to files we want to destroy
    files_to_delete = [
        f"{AUDIO_DIR}/{base_name}_1_hook.wav",
        f"{AUDIO_DIR}/{base_name}_2_pro.wav",
        f"{AUDIO_DIR}/{base_name}_3_con.wav",
        f"{AUDIO_DIR}/{base_name}_4_outro.wav",
        f"{TEMP_DIR}/{base_name}_bg.jpg",
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