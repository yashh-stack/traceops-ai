from PIL import Image, ImageDraw, ImageFont, ImageFilter
import os

SCREENSHOTS_DIR = "C:/Users/yashs/Projects/traceops-ai/pitch/screenshots"

def make_card(src_path, out_path, title_text, badge_color="#22c55e", badge_text="LIVE"):
    # Target dimensions: 1920 x 1817 (aspect ratio 2560320 / 2423160 = 1.0566)
    W = 1920
    H = 1817
    
    card = Image.new("RGBA", (W, H), (11, 15, 25, 255)) # Dark slate #0b0f19
    draw = ImageDraw.Draw(card)
    
    # Outer subtle border
    draw.rounded_rectangle([(4, 4), (W - 5, H - 5)], radius=24, outline=(51, 65, 85, 255), width=3)
    
    # Header bar inside the card
    draw.rounded_rectangle([(16, 16), (W - 17, 100)], radius=16, fill=(22, 27, 34, 255))
    
    # Window controls (macOS / clean style dots)
    draw.ellipse([(40, 48), (64, 72)], fill=(239, 68, 68, 255))
    draw.ellipse([(76, 48), (100, 72)], fill=(245, 158, 11, 255))
    draw.ellipse([(112, 48), (136, 72)], fill=(34, 197, 94, 255))
    
    # Load default or Arial font
    try:
        font_title = ImageFont.truetype("arialbd.ttf", 36)
        font_badge = ImageFont.truetype("arialbd.ttf", 26)
    except:
        font_title = ImageFont.load_default()
        font_badge = ImageFont.load_default()
        
    draw.text((160, 40), title_text, fill=(226, 232, 240, 255), font=font_title)
    
    # Badge on right
    bbox = draw.textbbox((0, 0), badge_text, font=font_badge)
    badge_w = bbox[2] - bbox[0] + 30
    badge_x = W - 40 - badge_w
    draw.rounded_rectangle([(badge_x, 34), (badge_x + badge_w, 82)], radius=10, fill=badge_color)
    draw.text((badge_x + 15, 42), badge_text, fill=(255, 255, 255, 255), font=font_badge)
    
    # Open and process the main screenshot
    src = Image.open(src_path)
    
    # We want to crop / fit the primary area of interest
    # For a full 3840x2160 image, let's resize to fit width inside card with margins
    content_w = W - 32
    # Available height for content: H - 120 - 16 = 1681
    # If 16:9, height is content_w * 9 / 16 = 1888 * 9 / 16 = 1062
    src_fitted = src.resize((content_w, int(content_w * src.height / src.width)), Image.Resampling.LANCZOS)
    
    # If the fitted image is shorter than available space, center it vertically
    content_h = src_fitted.height
    pos_y = 116 + (H - 116 - content_h) // 2
    
    card.paste(src_fitted, (16, max(116, pos_y)))
    
    # Save as high-quality PNG
    card.convert("RGB").save(out_path, quality=95)
    print("Generated card:", out_path)

if __name__ == "__main__":
    make_card(
        f"{SCREENSHOTS_DIR}/snapshot_a_shadow_mode.png",
        f"{SCREENSHOTS_DIR}/card_a_shadow_mode.png",
        "TraceOps Live HUD  ·  SHADOW AUDIT",
        badge_color="#3b82f6",
        badge_text="SHADOW MODE"
    )
    make_card(
        f"{SCREENSHOTS_DIR}/snapshot_b_enforce_mode.png",
        f"{SCREENSHOTS_DIR}/card_b_enforce_mode.png",
        "TraceOps Circuit Breaker  ·  CIRCUIT_BREAKER_HALT",
        badge_color="#ef4444",
        badge_text="HALTED <0.5 ms"
    )
    make_card(
        f"{SCREENSHOTS_DIR}/snapshot_c_pytest_terminal.png",
        f"{SCREENSHOTS_DIR}/card_c_pytest_terminal.png",
        "Adversarial Verification Suite  ·  9/9 PASSED",
        badge_color="#22c55e",
        badge_text="100% PASS (0 warnings)"
    )
