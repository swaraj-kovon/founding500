

# app.py
import streamlit as st
from dotenv import load_dotenv
import os
from PIL import Image, ImageDraw, ImageFont
import io
import uuid
from datetime import datetime, timezone
from supabase import create_client
import base64
import requests
import traceback

st.set_page_config(page_title="Kovon VVIP Circle — Limited Seats Only", page_icon=":star:", layout="centered")
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SERVICE_ROLE_KEY") or os.getenv("ANON_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    st.error("Missing SUPABASE_URL or SUPABASE key in .env")
    st.stop()

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
STORAGE_BUCKET = "forms"
TABLE_NAME = "forms"
MAX_SEATS = 500
FIRST_BADGE_NUMBER = 190

# ======= CONFIG: BASE (reference) positions & sizes - tuned for your template resolution =======
TEMPLATE_REF_WIDTH = 2480  # width you designed coordinates against
NAME_FONT_SIZE_REF = 120
BADGE_FONT_SIZE_REF = 64

# reference absolute positions (for the reference width above)
NAME_X_REF = 270
NAME_Y_REF = 1255
BADGE_X_REF = 1900
BADGE_Y_REF = 68
# name bounding box width (how wide the name area is on the template)
NAME_BOX_WIDTH_REF = 1750  # tune to the width of the rounded rect where name appears
NAME_BOX_HEIGHT_REF = 200

# Fonts directory (optional) - you can place a .ttf here; otherwise the script will try system fonts / download.
FONTS_DIR = "fonts"
os.makedirs(FONTS_DIR, exist_ok=True)
FONT_CANDIDATES = [
    os.path.join(FONTS_DIR, "DejaVuSans-Bold.ttf"),
    os.path.join(FONTS_DIR, "DejaVuSans.ttf"),
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
]

def try_download_poppins(dest_path):
    """Best-effort: download Poppins TTF from Google Fonts Github raw. Returns True if saved."""
    try:
        url_map = {
            "Poppins-Regular.ttf": "https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-Regular.ttf",
            "Poppins-Bold.ttf": "https://github.com/google/fonts/raw/main/ofl/poppins/Poppins-Bold.ttf",
        }
        filename = os.path.basename(dest_path)
        if filename in url_map:
            url = url_map[filename]
            r = requests.get(url, timeout=15)
            if r.status_code == 200:
                with open(dest_path, "wb") as f:
                    f.write(r.content)
                return True
    except Exception:
        return False
    return False

def find_usable_ttf():
    """Return path to a usable TTF or None. Try candidates, then try download to fonts/."""
    for p in FONT_CANDIDATES:
        if os.path.exists(p):
            return p
    # try common names with PIL's default locations by name-only
    try_names = ["DejaVuSans-Bold.ttf", "DejaVuSans.ttf", "Poppins-Bold.ttf", "Poppins-Regular.ttf"]
    for name in try_names:
        try:
            # attempt to load by name via truetype; if it raises, skip
            ImageFont.truetype(name, 20)
            return name
        except Exception:
            continue
    # try to download Poppins into fonts dir
    dest = os.path.join(FONTS_DIR, "Poppins-Regular.ttf")
    if try_download_poppins(dest):
        return dest
    dest_b = os.path.join(FONTS_DIR, "Poppins-Bold.ttf")
    if try_download_poppins(dest_b):
        return dest_b
    return None

def load_truetype_or_default(size):
    """
    Try to load a TTF that respects pixel size. If none found, fall back to ImageFont.load_default()
    (which does not respect size). Returns font object and a flag whether it's a scalable truetype.
    """
    path = find_usable_ttf()
    if path:
        try:
            return ImageFont.truetype(path, size), True
        except Exception:
            pass
    # Last resort
    return ImageFont.load_default(), False

def fit_text_to_box(draw, text, max_width, max_height, max_start_size):
    """
    Find the largest font size (<= max_start_size) such that text fits in (max_width, max_height).
    Returns a ImageFont object and resulting size. Uses truetype if available; otherwise returns default.
    """
    # start from max_start_size and step down
    # Try to load scalable font at candidate sizes; if not available, fallback to load_default immediately.
    # We'll attempt to use load_truetype_or_default with candidate size.
    for trial in range(max_start_size, 5, -1):
        font, is_truetype = load_truetype_or_default(trial)
        if not font:
            continue
        # measure
        try:
            bbox = draw.textbbox((0,0), text, font=font)
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
        except Exception:
            # fallback older API
            w, h = draw.textsize(text, font=font)
        if w <= max_width and h <= max_height:
            return font, trial, is_truetype
    # final fallback: smallest default
    font, is_tt = load_truetype_or_default(12)
    return font, 12, is_tt

def get_submission_count():
    try:
        res = supabase.table(TABLE_NAME).select("id", count="exact").execute()
        if hasattr(res, "count") and res.count is not None:
            return res.count
        if isinstance(res, dict):
            return res.get("count") or len(res.get("data", []))
        return len(res.data)
    except Exception:
        return 0

def process_and_compose(template_path, profile_image_bytes, name_text, badge_number):
    """
    Produces an in-memory PNG BytesIO of the badge using:
    - scale-aware positions
    - auto-fit text within a bounding box
    - reliable truetype usage when available
    """
    background = Image.open(template_path).convert("RGBA")
    bg_w, bg_h = background.size

    # compute scale ratio relative to reference width
    scale = bg_w / TEMPLATE_REF_WIDTH if TEMPLATE_REF_WIDTH > 0 else 1.0

    # scaled positions and sizes
    name_x = int(round(NAME_X_REF * scale))
    name_y = int(round(NAME_Y_REF * scale))
    badge_x = int(round(BADGE_X_REF * scale))
    badge_y = int(round(BADGE_Y_REF * scale))

    # bounding box for name rendering
    name_box_w = int(round(NAME_BOX_WIDTH_REF * scale))
    name_box_h = int(round(NAME_BOX_HEIGHT_REF * scale))

    # profile image
    base_profile_size = 520
    new_dim = max(24, int(round(base_profile_size * scale)))
    new_size = (new_dim, new_dim)
    profile_pic = Image.open(profile_image_bytes).convert("RGBA").resize(new_size)

    mask = Image.new("L", new_size, 0)
    ImageDraw.Draw(mask).ellipse((0, 0, new_size[0], new_size[1]), fill=255)
    profile_pic.putalpha(mask)

    # place profile at the relative Y (scaled 600 from ref)
    profile_y = int(round(600 * scale))
    background.paste(profile_pic, (bg_w // 2 - new_size[0] // 2, profile_y), profile_pic)

    draw = ImageDraw.Draw(background)

    # Determine font for name that fits the box
    max_name_font_size = max(8, int(round(NAME_FONT_SIZE_REF * scale)))
    # Attempt to fit the name into the name box width/height
    font_for_name, used_size, is_truetype = fit_text_to_box(draw, name_text, name_box_w, name_box_h, max_name_font_size)

    # Create shadow offsets scaled
    shadow_offsets = [(-3, 0), (3, 0), (0, -3), (0, 3)]
    shadow_offsets = [(int(round(x * scale)), int(round(y * scale))) for (x, y) in shadow_offsets]

    shadow_color = (0, 0, 0, 220)
    text_color = (255, 230, 128, 255)

    # Center the name within the name box horizontally (so NAME_X_REF is treated as left edge of box)
    try:
        bbox = draw.textbbox((0, 0), name_text, font=font_for_name)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
    except Exception:
        text_w, text_h = draw.textsize(name_text, font=font_for_name)

    # Calculate left coordinate so text is centered within the reserved box (name_x is left of box)
    name_left = name_x + max(0, (name_box_w - text_w) // 2)
    name_top = name_y + max(0, (name_box_h - text_h) // 2)

    # Draw shadow then text
    for off in shadow_offsets:
        draw.text((name_left + off[0], name_top + off[1]), name_text, font=font_for_name, fill=shadow_color)
    draw.text((name_left, name_top), name_text, font=font_for_name, fill=text_color)

    # Badge number - we'll use a simpler logic: scaled badge font size
    badge_font_size = max(6, int(round(BADGE_FONT_SIZE_REF * scale)))
    badge_font, _ = load_truetype_or_default(badge_font_size)
    sub_text = str(badge_number).zfill(3)
    small_shadow_offsets = [(-2, 0), (2, 0), (0, -2), (0, 2)]
    small_shadow_offsets = [(int(round(x * scale)), int(round(y * scale))) for (x, y) in small_shadow_offsets]
    for off in small_shadow_offsets:
        draw.text((badge_x + off[0], badge_y + off[1]), sub_text, font=badge_font, fill=shadow_color)
    draw.text((badge_x, badge_y), sub_text, font=badge_font, fill=text_color)

    # Save to bytes
    out = io.BytesIO()
    background.save(out, format="PNG", dpi=(300, 300))
    out.seek(0)
    return out

def upload_to_storage(bucket, file_bytes, dest_path):
    try:
        supabase.storage.from_(bucket).upload(dest_path, file_bytes, {"cacheControl": "3600"})
        pub = supabase.storage.from_(bucket).get_public_url(dest_path)
        if isinstance(pub, dict):
            return pub.get("publicURL") or pub.get("public_url") or pub.get("url")
        if hasattr(pub, "get"):
            return pub.get("publicURL") or pub.get("public_url") or pub.get("url")
        return pub
    except Exception as e:
        st.error(f"Upload failed: {e}")
        st.text(traceback.format_exc())
        return None

# UI and rest of your app (unchanged)
logo_path = "logo.png"
if os.path.exists(logo_path):
    with open(logo_path, "rb") as f:
        data = f.read()
    b64 = base64.b64encode(data).decode()
    st.markdown(f"""
        <div style="display:flex; justify-content:center; margin-bottom:12px;">
            <img src="data:image/png;base64,{b64}" width="180">
        </div>
        """, unsafe_allow_html=True)

st.markdown("<h1 style='text-align:center;'>Kovon VVIP Circle — Limited Seats Only</h1>", unsafe_allow_html=True)

st.markdown("""<div style='border:1px solid #eee; padding:12px; border-radius:10px;'>
✨ Benefits:<br>
- Early access to overseas job updates<br>
- Priority guidance (training, visa, recruiters)<br>
- Your name featured on the Kovon Platform<br>
- Win exclusive Kovon merchandise!<br>
✅ How to Join (Limited seats only):<br>
- Post your VVIP badge on your WhatsApp and other Social Media channels<br>
- Bring in maximum number of friends/colleagues<br>
- Fill this form →
</div>""", unsafe_allow_html=True)

name = st.text_input("Name", key="name_input")
profile_image = st.file_uploader("Upload profile image", type=["png","jpg","jpeg"], key="profile_upload")
city = st.text_input("City", key="city_input")
job = st.selectbox("Job", ["Construction","Facility Management","Logistics","Office","Others"], key="job_select")
other_job = st.text_input("Please specify your job", key="other_job_input") if job=="Others" else None
country_target = st.text_input("Country Target", key="country_input")
about_you = st.text_area("About you (15-20 words)", key="about_input")
gender = st.selectbox("Gender", ["Male","Female","Other"], key="gender_select")

current_count = get_submission_count()
seats_left = MAX_SEATS - (current_count + FIRST_BADGE_NUMBER - 1)
if seats_left > 0:
    st.info(f"Seats left: {seats_left}")
else:
    st.info("Accepting more users due to high volume")

if "composed_bytes" not in st.session_state:
    st.session_state["composed_bytes"] = None
if "badge_number" not in st.session_state:
    st.session_state["badge_number"] = None

if st.button("Download Badge", key="download_badge_btn"):
    if not name:
        st.error("Enter your name before generating badge.")
    else:
        if profile_image:
            profile_bytes_local = profile_image.read()
        else:
            default_file = "man.jpg" if gender == "Male" else "women.jpg" if gender == "Female" else None
            if not default_file or not os.path.exists(default_file):
                st.error("Upload a profile image or ensure default exists.")
                st.stop()
            profile_bytes_local = open(default_file, "rb").read()

        badge_number = current_count + FIRST_BADGE_NUMBER
        composed_io = process_and_compose("new.jpg", io.BytesIO(profile_bytes_local), name, badge_number)
        composed_bytes = composed_io.getvalue()
        st.session_state["composed_bytes"] = composed_bytes
        st.session_state["badge_number"] = badge_number

        st.image(io.BytesIO(composed_bytes), caption=f"Generated Badge Preview (#{badge_number})")

        profile_path = f"{badge_number}/profile_{uuid.uuid4().hex}.png"
        profile_url = upload_to_storage(STORAGE_BUCKET, profile_bytes_local, profile_path)
        st.session_state["profile_url"] = profile_url

        b64 = base64.b64encode(composed_bytes).decode()
        href = f"""
        <html>
        <body>
        <a id="dl" download="{name}_badge.png" href="data:file/png;base64,{b64}"></a>
        <script>document.getElementById('dl').click();</script>
        </body>
        </html>
        """
        st.components.v1.html(href, height=0)

if st.session_state.get("composed_bytes"):
    st.markdown("### Upload your WhatsApp status screenshot of your badge")
    screenshot = st.file_uploader("Upload screenshot", type=["png","jpg","jpeg"], key="screenshot_upload")
    if screenshot:
        if st.button("Submit Submission", key="submit_submission_btn"):
            screenshot_bytes = screenshot.read()
            screenshot_path = f"{st.session_state['badge_number']}/screenshot_{uuid.uuid4().hex}.png"
            screenshot_url = upload_to_storage(STORAGE_BUCKET, screenshot_bytes, screenshot_path)

            submission_record = {
                "name": name,
                "city": city,
                "job": other_job if job == "Others" else job,
                "country_target": country_target,
                "about_you": about_you,
                "gender": gender,
                "submission": str(st.session_state["badge_number"]).zfill(3),
                "profile_image_url": st.session_state.get("profile_url"),
                "screenshot_url": screenshot_url,
                "created_at": datetime.now(timezone.utc).isoformat()
            }

            supabase.table(TABLE_NAME).insert(submission_record).execute()
            st.success(f"Submission recorded! Badge #{st.session_state['badge_number']}")
            st.session_state["composed_bytes"] = None
            st.session_state["badge_number"] = None
            st.info("You can refresh the page or start a new submission now.")
