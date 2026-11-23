import os
import sys
import asyncio
import subprocess
import edge_tts
import imageio_ffmpeg
from concurrent.futures import ThreadPoolExecutor
from PIL import Image

PITCH_DIR = "C:/Users/yashs/Projects/traceops-ai/pitch"
DECK_SLIDES_DIR = os.path.join(PITCH_DIR, "deck_slides")
AUDIO_3M_DIR = os.path.join(PITCH_DIR, "audio_3min")
CLIPS_3M_DIR = os.path.join(PITCH_DIR, "clips_3min")
os.makedirs(AUDIO_3M_DIR, exist_ok=True)
os.makedirs(CLIPS_3M_DIR, exist_ok=True)

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
VOICE = "en-IN-PrabhatNeural"

EXACT_3MIN_ACTS = [
    {
        "id": "act1_crisis",
        "frame": os.path.join(PITCH_DIR, "frame_act1_crisis.png"),
        "speech": "Welcome to TraceOps AI for the Google DeepMind and Cloud Startup Buildathon India 2026. Today, sixty-four percent of enterprise multi-agent pilots stall before production. When autonomous agents hallucinate, they trigger runaway loops and state drift before alerts fire. Post-facto logs only report failure after damages occur."
    },
    {
        "id": "act2_conventional_trap",
        "frame": os.path.join(PITCH_DIR, "frame_act2_conventional_trap.png"),
        "speech": "The conventional approach places a secondary language model on the critical path. But that adds over one hundred and fifty milliseconds of latency per hop, burns thousands on idle GPUs, and hallucinates its own approvals. In a five billion dollar observability market, enterprises need deterministic CPU circuit protection."
    },
    {
        "id": "act3_architecture",
        "frame": os.path.join(PITCH_DIR, "frame_act3_architecture.png"),
        "speech": "TraceOps AI enforces one core law: LLMs advise, the deterministic state machine decides. On the synchronous hot path, there are zero remote LLM calls. In sub seven milliseconds on CPU, Tier 1 checks tool hashes and Pydantic schemas, while Tier 2 scores semantic drift. Off the critical path, Gemini 3.5 Flash Lite audits OpenTelemetry spans with zero user latency."
    },
    {
        "id": "act4_process_flow",
        "frame": os.path.join(PITCH_DIR, "frame_act4_process_flow.png"),
        "speech": "Here is the production difference. Without TraceOps, a rogue agent deleting databases runs unchecked, burning balance until a late Slack alert. With TraceOps AI, rogue calls are intercepted in microseconds. The deterministic state machine trips to HALT or SUSPEND HITL, executing a safe fallback while an async OTel span triggers automated CI test generation."
    },
    {
        "id": "act5_live_prototype",
        "frame": os.path.join(PITCH_DIR, "frame_act5_live_prototype.png"),
        "speech": "Here is our live prototype on Google Cloud Run. In SHADOW mode, panel A, TraceOps acts as an ROI auditor, proving four hundred dollars in simulated savings without blocking traffic. In ENFORCE mode, panel B, the circuit breaker halts runaway loops and unauthorized tool calls in under zero point five milliseconds. In panel C, pytest proves nine of nine attacks are intercepted with zero warnings."
    },
    {
        "id": "act6_benchmarks",
        "frame": os.path.join(PITCH_DIR, "frame_act6_benchmarks.png"),
        "speech": "Across two hundred benchmark evaluations, TraceOps AI delivers a p50 latency of two point eight five milliseconds and a p95 of seven point one one milliseconds. That is twenty-one point four times faster than GPU guardrails. Powered by Cloud Run autoscaling, Gemini 3.5 Flash Lite, and Gemini 3.8 Flash, TraceOps operates under the five dollar GCP budget with zero GPU pods."
    },
    {
        "id": "act7_roadmap_mission",
        "frame": os.path.join(PITCH_DIR, "frame_act7_roadmap_mission.png"),
        "speech": "TraceOps AI delivers over eighty-two percent gross margins at scale, supported by a clear ninety-day commercialization roadmap towards paid enterprise audits and VPC control planes. Under Viksit Bharat, TraceOps AI provides the deterministic bedrock to deploy autonomous agents with mathematical certainty. LLMs advise, the state machine decides. Thank you."
    }
]

async def synthesize_all():
    print("Synthesizing exact 3-min audio via edge_tts...")
    for act in EXACT_3MIN_ACTS:
        audio_file = os.path.join(AUDIO_3M_DIR, f"{act['id']}.mp3")
        comm = edge_tts.Communicate(act["speech"], VOICE, rate="+3%")
        await comm.save(audio_file)
    print("All 3-min audio generated!")

def get_audio_duration(audio_path):
    cmd = [FFMPEG, "-i", audio_path]
    proc = subprocess.run(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    for line in proc.stderr.split("\n"):
        if "Duration" in line:
            dur_str = line.split("Duration:")[1].split(",")[0].strip()
            h, m, s = dur_str.split(":")
            return float(h)*3600 + float(m)*60 + float(s)
    return 20.0

def encode_clip(act):
    audio_file = os.path.join(AUDIO_3M_DIR, f"{act['id']}.mp3")
    dur = get_audio_duration(audio_file) + 0.4
    clip_out = os.path.join(CLIPS_3M_DIR, f"{act['id']}.mp4")

    cmd = [
        FFMPEG, "-y",
        "-loop", "1",
        "-framerate", "30",
        "-i", act["frame"],
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
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return clip_out

def main():
    asyncio.run(synthesize_all())
    with ThreadPoolExecutor(max_workers=3) as executor:
        clips = list(executor.map(encode_clip, EXACT_3MIN_ACTS))

    final_3min = os.path.join(PITCH_DIR, "TraceOps_AI_Pitch_3Min_Master_1080p.mp4")
    concat_txt = os.path.join(PITCH_DIR, "concat_3min.txt")

    with open(concat_txt, "w") as f:
        for act in EXACT_3MIN_ACTS:
            clip = os.path.join(CLIPS_3M_DIR, f"{act['id']}.mp4")
            norm = clip.replace("\\", "/")
            f.write(f"file '{norm}'\n")

    cmd = [
        FFMPEG, "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", concat_txt,
        "-c", "copy",
        final_3min
    ]
    subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print("Exact 3-min master video rendered successfully:", final_3min)

if __name__ == "__main__":
    main()
