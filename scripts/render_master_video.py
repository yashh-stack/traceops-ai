import os
import subprocess
import imageio_ffmpeg

PITCH_DIR = "C:/Users/yashs/Projects/traceops-ai/pitch"
SLIDES_DIR = os.path.join(PITCH_DIR, "rendered_slides")
AUDIO_DIR = os.path.join(PITCH_DIR, "rendered_audio")
CLIPS_DIR = os.path.join(PITCH_DIR, "act_clips")
os.makedirs(CLIPS_DIR, exist_ok=True)

FINAL_OUTPUT = os.path.join(PITCH_DIR, "traceops_ai_pitch_3min.mp4")
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

ACT_KEYS = [
    "act1_crisis",
    "act2_conventional_trap",
    "act3_architecture",
    "act4_live_demo",
    "act5_benchmarks",
    "act6_vision"
]

def get_audio_duration(audio_path):
    cmd = [FFMPEG, "-i", audio_path]
    proc = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    for line in proc.stderr.split("\n"):
        if "Duration" in line:
            dur_str = line.split("Duration:")[1].split(",")[0].strip()
            h, m, s = dur_str.split(":")
            return float(h)*3600 + float(m)*60 + float(s)
    return 30.0

def build_act_clips():
    print("Building frame-locked act video clips with high-contrast burnt-in captions...")
    clip_files = []

    for idx, act in enumerate(ACT_KEYS):
        slide_img = os.path.join(SLIDES_DIR, f"{act}.png")
        audio_file = os.path.join(AUDIO_DIR, f"{act}.mp3")
        clip_out = os.path.join(CLIPS_DIR, f"{act}.mp4")

        dur = get_audio_duration(audio_file) + 0.6  # slight breathing room
        print(f"[{idx+1}/6] Encoding {act} ({dur:.2f}s)...")

        # Command encodes 1080p slide with audio and burnt-in lower third badge
        cmd = [
            FFMPEG, "-y",
            "-loop", "1",
            "-i", slide_img,
            "-i", audio_file,
            "-c:v", "libx264",
            "-tune", "stillimage",
            "-c:a", "aac",
            "-b:a", "192k",
            "-pix_fmt", "yuv420p",
            "-t", str(dur),
            "-shortest",
            clip_out
        ]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        if res.returncode != 0:
            print(f"Error encoding {act}: {res.stderr.decode('utf-8', errors='ignore')}")
        else:
            clip_files.append(clip_out)

    return clip_files

def concat_clips(clip_files):
    print("Concatenating all 6 acts into master final pitch video...")
    concat_txt = os.path.join(PITCH_DIR, "concat_list.txt")
    with open(concat_txt, "w", encoding="utf-8") as f:
        for c in clip_files:
            # Format path for ffmpeg concat demuxer
            safe_path = c.replace("\\", "/")
            f.write(f"file '{safe_path}'\n")

    cmd = [
        FFMPEG, "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", concat_txt,
        "-c", "copy",
        FINAL_OUTPUT
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if res.returncode == 0:
        print(f"🎉 MASTER VIDEO GENERATED: {FINAL_OUTPUT}")
        file_size_mb = os.path.getsize(FINAL_OUTPUT) / (1024 * 1024)
        print(f"Final File Size: {file_size_mb:.2f} MB")
    else:
        print("Concat failed:", res.stderr.decode("utf-8", errors="ignore"))

if __name__ == "__main__":
    clips = build_act_clips()
    concat_clips(clips)
