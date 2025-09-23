import streamlit as st
from dotenv import load_dotenv
import os
from PIL import Image, ImageDraw, ImageFont
import io
import uuid
from datetime import datetime, timezone
from supabase import create_client
import base64

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

def get_submission_count():
    try:
        res = supabase.table(TABLE_NAME).select("id", count="exact").execute()
        if hasattr(res, "count") and res.count is not None:
            return res.count
        if isinstance(res, dict):
            return res.get("count") or len(res.get("data", []))
        return len(res.data)
    except:
        return 0

def process_and_compose(template_path, profile_image_bytes, name_text, badge_number):
    background = Image.open(template_path).convert("RGBA")
    bg_w, bg_h = background.size

    new_size = (520, 520)
    profile_pic = Image.open(profile_image_bytes).convert("RGBA").resize(new_size)
    mask = Image.new("L", new_size, 0)
    ImageDraw.Draw(mask).ellipse((0,0,new_size[0],new_size[1]), fill=255)
    profile_pic.putalpha(mask)
    background.paste(profile_pic, (bg_w//2 - new_size[0]//2, 600), profile_pic)

    draw = ImageDraw.Draw(background)
    try:
        base_font_size = 400 # increased for mobile readability
        font = ImageFont.truetype("arial.ttf", base_font_size)
        font_small = ImageFont.truetype("arial.ttf", 30)  # bigger badge number
    except:
        font = ImageFont.load_default()
        font_small = ImageFont.load_default()

    max_width = 560
    bbox = draw.textbbox((0,0), name_text, font=font)
    text_w = bbox[2]-bbox[0]

    # dynamically shrink font only if name is too long
    if text_w > max_width:
        font_size = max(int(base_font_size * max_width / text_w), 60)  # min font 60
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except:
            font = ImageFont.load_default()
        bbox = draw.textbbox((0,0), name_text, font=font)
        text_w = bbox[2]-bbox[0]
    text_h = bbox[3]-bbox[1]

    rect_x, rect_y, rect_w, rect_h = 270, 1220, 560, 80  # slightly taller rect
    name_x = rect_x + (rect_w - text_w)//2
    name_y = rect_y + (rect_h - text_h)//2

    shadow_color = (0,0,0,220)
    text_color = (255, 230, 128, 255)
    for off in [(-3,0),(3,0),(0,-3),(0,3)]:  # bigger shadow for visibility
        draw.text((name_x+off[0], name_y+off[1]), name_text, font=font, fill=shadow_color)
    draw.text((name_x, name_y), name_text, font=font, fill=text_color)

    sub_text = str(badge_number).zfill(3)
    sub_bbox = draw.textbbox((0,0), sub_text, font=font_small)
    sub_w, sub_h = sub_bbox[2]-sub_bbox[0], sub_bbox[3]-sub_bbox[1]
    sub_x = bg_w - sub_w - 70
    sub_y = 70
    for off in [(-2,0),(2,0),(0,-2),(0,2)]:
        draw.text((sub_x+off[0], sub_y+off[1]), sub_text, font=font_small, fill=shadow_color)
    draw.text((sub_x, sub_y), sub_text, font=font_small, fill=text_color)

    out = io.BytesIO()
    background.save(out, format="PNG")
    out.seek(0)
    return out

def upload_to_storage(bucket, file_bytes, dest_path):
    try:
        supabase.storage.from_(bucket).upload(dest_path, file_bytes, {"cacheControl": "3600"})
        public_url = supabase.storage.from_(bucket).get_public_url(dest_path)
        return public_url
    except Exception as e:
        st.error(f"Upload failed: {e}")
        return None

# Logo
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

# Step 1: Generate & download badge
if st.button("Download Badge", key="download_badge_btn"):
    if not name:
        st.error("Enter your name before generating badge.")
    else:
        if profile_image:
            profile_bytes_local = profile_image.read()
        else:
            default_file = "man.jpg" if gender=="Male" else "women.jpg" if gender=="Female" else None
            if not default_file or not os.path.exists(default_file):
                st.error("Upload a profile image or ensure default exists.")
                st.stop()
            profile_bytes_local = open(default_file,"rb").read()

        badge_number = current_count + FIRST_BADGE_NUMBER
        composed_io = process_and_compose("new.jpg", io.BytesIO(profile_bytes_local), name, badge_number)
        composed_bytes = composed_io.getvalue()
        st.session_state["composed_bytes"] = composed_bytes
        st.session_state["badge_number"] = badge_number

        st.image(io.BytesIO(composed_bytes), caption=f"Generated Badge Preview (#{badge_number})", use_container_width=True)
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

# Step 2: Upload WhatsApp screenshot
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
                "job": other_job if job=="Others" else job,
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

