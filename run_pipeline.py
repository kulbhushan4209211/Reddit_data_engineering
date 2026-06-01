import subprocess
import sys
import time

def run_script(script_name):
    """Runs a python script and halts the pipeline if it crashes."""
    print(f"\n{'='*50}")
    print(f"🚀 STARTING PHASE: {script_name}")
    print(f"{'='*50}\n")
    
    start_time = time.time()
    
    try:
        # Execute the script and stream the output to the console
        result = subprocess.run(
            [sys.executable, f"src/{script_name}"], 
            check=True, 
            text=True
        )
        
        elapsed_time = round(time.time() - start_time, 2)
        print(f"\n✅ PHASE COMPLETE: {script_name} (Took {elapsed_time}s)")
        
    except subprocess.CalledProcessError as e:
        print(f"\n❌ FATAL ERROR: {script_name} crashed with exit code {e.returncode}.")
        print("🛑 Halting the entire pipeline to prevent downstream data corruption.")
        sys.exit(1) # Kill the master script

def execute_full_pipeline():
    print("🎬 BOOTING MASTER AUTOMATION PIPELINE...\n")
    total_start = time.time()
    
    # The exact sequential order of your ELT & Rendering architecture
    pipeline_phases = [
        "ingestion_engine.py",
        "transformation_engine.py",
        "publish_engine.py",
        "audio_engine.py",
        "video_engine.py",
        "youtube_uploader.py"
    ]
    
    for script in pipeline_phases:
        run_script(script)
        # Optional: Add a 2-second breather between heavy processes to clear RAM
        time.sleep(2) 
        
    total_time = round((time.time() - total_start) / 60, 2)
    print(f"\n🎉 FULL PIPELINE SUCCESSFUL! Total execution time: {total_time} minutes.")

if __name__ == "__main__":
    # Note: Ensure your scripts are either in the same folder, 
    # or adjust the path in subprocess.run() (e.g., f"src/{script_name}")
    execute_full_pipeline()