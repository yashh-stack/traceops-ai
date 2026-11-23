import os
import sys
import subprocess
import imageio_ffmpeg
from concurrent.futures import ThreadPoolExecutor
from PIL import Image, ImageDraw, ImageFont

PITCH_DIR = "C:/Users/yashs/Projects/traceops-ai/pitch"
DECK_SLIDES_DIR = os.path.join(PITCH_DIR, "deck_slides")
AUDIO_DIR = os.path.join(PITCH_DIR, "elite_audio")
CLIPS_DIR = os.path.join(PITCH_DIR, "elite_clips")
os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(CLIPS_DIR, exist_ok=True)

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

ELITE_ACTS = [
    {
        "id": "act1_crisis",
        "slide": os.path.join(DECK_SLIDES_DIR, "slide_02.png"),
        "title": "ACT 1: THE AUTONOMOUS AGENT CRISIS",
        "caption": "64% of enterprise multi-agent pilots stall due to runaway loops & state drift.",
        "accent": "#ef4444"
    },
    {
        "id": "act2_conventional_trap",
        "slide": os.path.join(DECK_SLIDES_DIR, "slide_03.png"),
        "title": "ACT 2: THE CONVENTIONAL TRAP",
        "caption": "GPU SLM guardrails add 152 ms latency per hop and burn thousands in idle compute.",
        "accent": "#f59e0b"
    },
    {
        "id": "act3_architecture",
        "slide": os.path.join(DECK_SLIDES_DIR, "slide_07.png"),
        "title": "ACT 3: THE DUAL-PATH ARCHITECTURAL BREAKTHROUGH",
        "caption": "Hot-Path CPU Determinism (<15 ms) + Async Cold-Path Gemini 3.5 Intelligence.",
        "accent": "#38bdf8"
    },
    {
        "id": "act4_process_flow",
        "slide": os.path.join(DECK_SLIDES_DIR, "slide_05.png"),
        "title": "ACT 4: DETERMINISTIC FAILURE INTERCEPTION",
        "caption": "Without TraceOps: unchecked damage. With TraceOps: microsecond circuit halt.",
        "accent": "#10b981"
    },
    {
        "id": "act5_live_prototype",
        "slide": os.path.join(DECK_SLIDES_DIR, "slide_10.png"),
        "title": "ACT 5: LIVE PROTOTYPE CONTROL ROOM",
        "caption": "Live on Cloud Run: SHADOW ROI audit, ENFORCE microsecond halt, 9/9 passing tests.",
        "accent": "#a855f7"
    },
    {
        "id": "act6_benchmarks",
        "slide": os.path.join(DECK_SLIDES_DIR, "slide_11.png"),
        "title": "ACT 6: EMPIRICAL BENCHMARKS & GOOGLE STACK",
        "caption": "7.11 ms p95 on CPU — 21.4x faster than GPU SLMs with zero idle GPU pods.",
        "accent": "#06b6d4"
    },
    {
        "id": "act7_roadmap_mission",
        "slide": os.path.join(DECK_SLIDES_DIR, "slide_13.png"),
        "title": "ACT 7: UNIT ECONOMICS, ROADMAP & MISSION",
        "caption": ">82% gross margins, 90-day roadmap, and deterministic safety for Viksit Bharat.",
        "accent": "#3b82f6"
    }
]

def get_audio_duration(audio_path):
    cmd = [FFMPEG, "-i", audio_path]
    proc = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    for line in proc.stderr.split("\n"):
        if "Duration" in line:
            dur_str = line.split("Duration:")[1].split(",")[0].strip()
            h, m, s = dur_str.split(":")
            return float(h)*3600 + float(m)*60 + float(s)
    return 25.0

def create_enhanced_slide_frame(act, out_frame_path):
    base_img = Image.open(act["slide"]).convert("RGB")
    W, H = base_img.size

    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    hud_h = 100
    hud_y = H - hud_h
    draw.rectangle([(0, hud_y), (W, H)], fill=(11, 15, 25, 240))
    draw.rectangle([(0, hud_y), (W, hud_y + 4)], fill=act["accent"])

    try:
        font_act = ImageFont.truetype("arialbd.ttf", 24)
        font_cap = ImageFont.truetype("arial.ttf", 22)
        font_comp = ImageFont.truetype("arialbd.ttf", 18)
    except:
        font_act = ImageFont.load_default()
        font_cap = font_act
        font_comp = font_act

    comp_text = "GOOGLE DEEPMIND x CLOUD STARTUP BUILDATHON INDIA 2026"
    draw.text((W - 620, hud_y + 14), comp_text, fill=(148, 163, 184, 255), font=font_comp)
    draw.text((40, hud_y + 12), act["title"], fill=act["accent"], font=font_act)
    draw.text((40, hud_y + 50), act["caption"], fill=(241, 245, 249, 255), font=font_cap)

    base_img.paste(overlay, (0, 0), overlay)
    base_img.save(out_frame_path, quality=95)

def encode_single_clip(act):
    audio_file = os.path.join(AUDIO_DIR, f"{act['id']}.mp3")
    dur = get_audio_duration(audio_file) + 0.6
    enhanced_slide = os.path.join(PITCH_DIR, f"frame_{act['id']}.png")
    create_enhanced_slide_frame(act, enhanced_slide)

    clip_out = os.path.join(CLIPS_DIR, f"{act['id']}.mp4")
    print(f"Encoding {act['id']} ({dur:.2f}s)...")

    cmd = [
        FFMPEG, "-y",
        "-loop", "1",
        "-framerate", "30",
        "-i", enhanced_slide,
        "-i", audio_file,
        "-c:v", "libx264",
        "-tune", "stillimage",
        "-preset", "ultrafast",
        "-c:a", "aac",
        "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-shortest",
        clip_out
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if res.returncode != 0:
        print(f"Error encoding {act['id']}: {res.stderr.decode('utf-8', errors='ignore')}")
        return None
    print(f"Completed clip: {act['id']}")
    return clip_out

def build_all_clips_parallel():
    print("Encoding all 7 clips in parallel using ThreadPoolExecutor(3)...")
    with ThreadPoolExecutor(max_workers=3) as executor:
        results = list(executor.map(encode_single_clip, ELITE_ACTS))
    return [r for r in results if r is not None]

def concat_all(clip_files):
    master_video = os.path.join(PITCH_DIR, "TraceOps_AI_Elite_Pitch_3Min_1080p.mp4")
    concat_txt = os.path.join(PITCH_DIR, "concat_elite.txt")
    print(f"Concatenating {len(clip_files)} clips into master video: {master_video}")

    with open(concat_txt, "w") as f:
        for act in ELITE_ACTS:
            clip = os.path.join(CLIPS_DIR, f"{act['id']}.mp4")
            norm_clip = clip.replace("\\", "/")
            f.write(f"file '{norm_clip}'\n")

    cmd = [
        FFMPEG, "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", concat_txt,
        "-c", "copy",
        master_video
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if res.returncode != 0:
        print("Error during concat:", res.stderr.decode("utf-8", errors="ignore"))
    else:
        standard_path = os.path.join(PITCH_DIR, "traceops_ai_pitch_3min.mp4")
        import shutil
        shutil.copyfile(master_video, standard_path)
        print("Master video rendered successfully!")
        print("1080p Master Path:", master_video)
        print("Standard Path:", standard_path)

if __name__ == "__main__":
    clips = build_all_clips_parallel()
    concat_all(clips)
