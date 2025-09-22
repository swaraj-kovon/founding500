

import streamlit as st
from dotenv import load_dotenv
import os
from PIL import Image, ImageDraw, ImageFont
import io
import uuid
from datetime import datetime
from supabase import create_client

# ---------------- config ----------------
st.set_page_config(page_title="User Info Form", page_icon=":memo:", layout="centered")
load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.getenv("SERVICE_ROLE_KEY") or os.getenv("ANON_KEY")
if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
    st.error("Missing SUPABASE_URL or SERVICE_ROLE_KEY/ANON_KEY in .env")
    st.stop()

supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
STORAGE_BUCKET = "forms"
TABLE_NAME = "forms"

# ---------------- helpers ----------------
def ensure_bucket_exists(bucket_name: str):
    try:
        resp = supabase.storage.list_buckets()
        existing = [b["name"] for b in resp] if isinstance(resp, list) else []
        if bucket_name in existing:
            return
    except Exception:
        pass
    try:
        supabase.storage.create_bucket(bucket_name, public=True)
    except Exception:
        pass

try:
    ensure_bucket_exists(STORAGE_BUCKET)
except Exception:
    pass

def process_and_compose(template_path, profile_image_bytes, name_text, submission_num):
    background = Image.open(template_path).convert("RGBA")
    new_size = (520, 520)
    profile_pic = Image.open(profile_image_bytes).convert("RGBA").resize(new_size)
    mask = Image.new("L", new_size, 0)
    draw_mask = ImageDraw.Draw(mask)
    draw_mask.ellipse((0,0,new_size[0],new_size[1]), fill=255)
    profile_pic.putalpha(mask)
    profile_x, profile_y = 275, 600
    background.paste(profile_pic, (profile_x, profile_y), profile_pic)

    draw = ImageDraw.Draw(background)
    try:
        font = ImageFont.truetype("arial.ttf", 65)
        font_small = ImageFont.truetype("arial.ttf", 36)
    except Exception:
        font = ImageFont.load_default()
        font_small = ImageFont.load_default()

    # name
    rect_x, rect_y, rect_w, rect_h = 270, 1255, 560, 62
    bbox = draw.textbbox((0,0), name_text, font=font)
    w, h = bbox[2]-bbox[0], bbox[3]-bbox[1]
    name_x = rect_x + (rect_w - w)//2
    name_y = rect_y + (rect_h - h)//2
    shadow_color = (0,0,0,180)
    text_color = (255,230,128,255)
    for off in [(-2,0),(2,0),(0,-2),(0,2)]:
        draw.text((name_x+off[0], name_y+off[1]), name_text, font=font, fill=shadow_color)
    draw.text((name_x, name_y), name_text, font=font, fill=text_color)

    # submission number
    sub_text = str(submission_num).zfill(3)
    sub_bbox = draw.textbbox((0,0), sub_text, font=font_small)
    sub_w, sub_h = sub_bbox[2]-sub_bbox[0], sub_bbox[3]-sub_bbox[1]
    background_width, _ = background.size
    sub_x = background_width - sub_w - 60
    sub_y = 68
    for off in [(-1,0),(1,0),(0,-1),(0,1)]:
        draw.text((sub_x+off[0], sub_y+off[1]), sub_text, font=font_small, fill=shadow_color)
    draw.text((sub_x, sub_y), sub_text, font=font_small, fill=text_color)

    out = io.BytesIO()
    background.save(out, format="PNG")
    out.seek(0)
    return out

def upload_to_storage(bucket: str, file_bytes: bytes, dest_path: str):
    try:
        storage = supabase.storage
        bucket_ref = storage.from_(bucket)
        try:
            bucket_ref.upload(dest_path, file_bytes)
        except TypeError:
            bucket_ref.upload(dest_path, io.BytesIO(file_bytes))
        try:
            public = bucket_ref.get_public_url(dest_path)
            if isinstance(public, dict):
                return public.get("publicURL") or public.get("public_url") or public.get("publicUrl")
            elif isinstance(public, str):
                return public
        except Exception:
            return f"{SUPABASE_URL}/storage/v1/object/public/{bucket}/{dest_path}"
    except Exception as e:
        st.warning(f"Storage upload failed: {e}")
        return None

def get_submission_count():
    try:
        res = supabase.table(TABLE_NAME).select("id", count="exact").execute()
        if hasattr(res, "count") and res.count is not None:
            return res.count
        if isinstance(res, dict):
            return res.get("count") or len(res.get("data", []))
        if isinstance(res, list):
            return len(res)
        try:
            return len(res.data)
        except Exception:
            return 0
    except Exception:
        return 0

# ---------------- UI ----------------
# center logo

import base64

logo_path = "logo.png"
if os.path.exists(logo_path):
    with open(logo_path, "rb") as f:
        data = f.read()
    b64 = base64.b64encode(data).decode()
    st.markdown(
        f"""
        <div style="display:flex; justify-content:center; align-items:center; margin-bottom:12px;">
            <img src="data:image/png;base64,{b64}" width="150" style="display:block;">
        </div>
        """,
        unsafe_allow_html=True
    )
else:
    st.warning(f"Logo file not found at: {logo_path}")


# VVIP box (keeps your previous content)
with st.container():
    st.markdown(
    """
    <div style="background:#0b1221; padding:16px; border-radius:8px; color: #fff;">
    <h3 style="margin:0 0 8px 0;">Kovon <span style="color:#ffd166;">VVIP Circle</span> — <em>Limited Seats Only</em></h3>
    <p style="margin:0 0 8px 0;">✨ <strong>Benefits:</strong></p>
    <ul style="margin-top:4px; margin-bottom:8px;">
    <li>Early access to overseas job updates</li>
    <li>Priority guidance (training, visa, recruiters)</li>
    <li>Your name featured on the Kovon Platform</li>
    <li>Win exclusive Kovon merchandise!</li>
    </ul>
    <p style="margin:16px 0 4px 0;">✅ <strong>How to Join (Limited seats only):</strong></p>
    <ol style="margin-top:4px; margin-bottom:0; padding-left:20px;">
    <li>Post your VVIP badge on your WhatsApp and other Social Media channels (with the link to join the community)</li>
    <li>Bring in maximum number of friends/colleagues who can utilize this opportunity</li>
    <li>Fill this form →</li>
    </ol>
    </div>
    """,
    unsafe_allow_html=True,
)

st.title("User Info Form")

name = st.text_input("Name")
profile_image = st.file_uploader("Upload your profile image (optional)", type=["png","jpg","jpeg"])
city = st.text_input("City")
job = st.selectbox("Job", ["Construction","Facility Management","Logistics","Office","Others"])
other_job = st.text_input("Please specify your job") if job == "Others" else None
country_target = st.text_input("Country Target")
about_you = st.text_area("About you (15-20 words)")

# Gender dropdown (controls default image)
gender = st.selectbox("Gender", ["Male","Female","Other"])

# session state for generated badge
if "composed_bytes" not in st.session_state:
    st.session_state["composed_bytes"] = None
if "composed_filename" not in st.session_state:
    st.session_state["composed_filename"] = None
if "generated_submission_num" not in st.session_state:
    st.session_state["generated_submission_num"] = None

col1, col2 = st.columns([1,1])
with col1:
    if st.button("Generate Badge"):
        if not name:
            st.error("Enter your name before generating the badge.")
        else:
            # pick profile bytes: uploaded wins; else default based on gender; Other must upload
            profile_bytes_local = None
            if profile_image:
                try:
                    profile_image.seek(0)
                except Exception:
                    pass
                try:
                    profile_bytes_local = profile_image.read()
                except Exception as e:
                    st.error(f"Failed to read uploaded profile image: {e}")
                    st.stop()
            else:
                default_file = None
                if gender == "Male":
                    default_file = "man.jpg"
                elif gender == "Female":
                    default_file = "women.jpg"

                if default_file:
                    if not os.path.exists(default_file):
                        st.error(f"Default image '{default_file}' not found. Place it next to this script.")
                        st.stop()
                    try:
                        with open(default_file, "rb") as f:
                            profile_bytes_local = f.read()
                    except Exception as e:
                        st.error(f"Failed to read default image: {e}")
                        st.stop()
                else:
                    st.error("Please upload a profile image if you selected 'Other' for gender.")
                    st.stop()

            try:
                temp_num = get_submission_count() + 1
            except Exception:
                temp_num = int(datetime.utcnow().timestamp()) % 1000

            try:
                profile_stream = io.BytesIO(profile_bytes_local)
                composed_io = process_and_compose("new.jpg", profile_stream, name, temp_num)
                composed_bytes = composed_io.getvalue()
                composed_filename = f"card_{uuid.uuid4().hex}.png"

                st.session_state["composed_bytes"] = composed_bytes
                st.session_state["composed_filename"] = composed_filename
                st.session_state["generated_submission_num"] = str(temp_num).zfill(3)

                st.success("Badge generated. Download it, post it to your WhatsApp status, then upload the screenshot below.")
                st.image(io.BytesIO(composed_bytes), caption="Generated Badge Preview")
                st.download_button("Download Badge (PNG)", data=composed_bytes, file_name=composed_filename, mime="image/png")
            except Exception as e:
                st.error(f"Failed to generate badge: {e}")

with col2:
    st.write("")  # spacer

st.markdown("**Next step:** After downloading the badge, upload a screenshot of *your WhatsApp status* showing **this badge**.")
screenshot = st.file_uploader("Upload a screenshot of your WhatsApp status (required to enable Submit)", type=["png","jpg","jpeg"])

# state hints
if st.session_state.get("composed_bytes"):
    st.info(f"Badge generated (preview #{st.session_state.get('generated_submission_num','000')}). Upload the screenshot to enable Submit.")
else:
    st.warning("You haven't generated a badge yet. Click 'Generate Badge' to create it and download.")

# Submit button only when screenshot uploaded and badge generated
if screenshot and st.session_state.get("composed_bytes"):
    try:
        st.image(screenshot, caption="Uploaded WhatsApp screenshot (will be saved on submit)")
    except Exception:
        pass

    if st.button("Submit", key="submit_form"):
        if not name:
            st.error("Please enter a name.")
            st.stop()

        total_submissions = get_submission_count()
        submission_num = total_submissions + 1
        submission_num_str = str(submission_num).zfill(3)
        timestamp = datetime.utcnow().isoformat()

        record = {
            "name": name,
            "city": city,
            "job": other_job if job == "Others" else job,
            "country_target": country_target,
            "about_you": about_you,
            "submission": submission_num_str,
            "gender": gender,
            "created_at": timestamp,
        }

        # Upload profile: if user uploaded, use it; else upload default for Male/Female
        profile_bytes = None
        if profile_image:
            try:
                profile_image.seek(0)
            except Exception:
                pass
            try:
                profile_bytes = profile_image.read()
            except Exception:
                profile_bytes = None

            if profile_bytes:
                ext = os.path.splitext(profile_image.name)[1] or ".png"
                safe_name = f"profile_{uuid.uuid4().hex}{ext}"
                dest_path = f"{submission_num_str}/{safe_name}"
                profile_url = upload_to_storage(STORAGE_BUCKET, profile_bytes, dest_path)
                record["profile_image_url"] = profile_url
                record["profile_image_filename"] = profile_image.name
        else:
            default_file = None
            if gender == "Male":
                default_file = "man.jpeg"
            elif gender == "Female":
                default_file = "women.jpeg"
            if default_file and os.path.exists(default_file):
                try:
                    with open(default_file, "rb") as f:
                        default_bytes = f.read()
                    ext = os.path.splitext(default_file)[1] or ".png"
                    safe_name = f"profile_default_{uuid.uuid4().hex}{ext}"
                    dest_path = f"{submission_num_str}/{safe_name}"
                    profile_url = upload_to_storage(STORAGE_BUCKET, default_bytes, dest_path)
                    record["profile_image_url"] = profile_url
                    record["profile_image_filename"] = default_file
                except Exception as e:
                    st.warning(f"Could not upload default profile image: {e}")

        # Save screenshot
        try:
            screenshot.seek(0)
        except Exception:
            pass
        try:
            screenshot_bytes = screenshot.read()
        except Exception:
            screenshot_bytes = None

        if screenshot_bytes:
            ext2 = os.path.splitext(screenshot.name)[1] or ".png"
            safe_name2 = f"screenshot_{uuid.uuid4().hex}{ext2}"
            dest_path2 = f"{submission_num_str}/{safe_name2}"
            screenshot_url = upload_to_storage(STORAGE_BUCKET, screenshot_bytes, dest_path2)
            record["screenshot_url"] = screenshot_url
            record["screenshot_filename"] = screenshot.name

        # Insert record
        try:
            insert_res = supabase.table(TABLE_NAME).insert(record).execute()
            if hasattr(insert_res, "error") and insert_res.error:
                st.warning(f"Insert returned error: {insert_res.error}")
            else:
                st.success(f"Form submitted as submission number {submission_num_str} and saved to Supabase!")
        except Exception as e:
            st.error(f"Failed to insert record into Supabase table '{TABLE_NAME}': {e}")

        # Upload composed badge from session state
        try:
            composed_bytes = st.session_state.get("composed_bytes")
            composed_filename = st.session_state.get("composed_filename") or f"card_{uuid.uuid4().hex}.png"
            if composed_bytes:
                composed_dest = f"{submission_num_str}/{composed_filename}"
                composed_public_url = upload_to_storage(STORAGE_BUCKET, composed_bytes, composed_dest)
                if composed_public_url:
                    try:
                        supabase.table(TABLE_NAME).update({
                            "composed_card_url": composed_public_url,
                            "composed_card_filename": composed_filename
                        }).eq("submission", submission_num_str).execute()
                    except Exception:
                        pass
                    st.success("Composed VVIP card uploaded to storage.")
                    st.write("Composed card public URL:", composed_public_url)
                else:
                    st.warning("Composed image upload failed; showing local preview.")
                    st.image(io.BytesIO(composed_bytes), caption="Your VVIP Member Card (local only)")
        except Exception as e:
            st.error(f"Error while composing/uploading the VVIP card: {e}")

        # clear session
        st.session_state["composed_bytes"] = None
        st.session_state["composed_filename"] = None
        st.session_state["generated_submission_num"] = None

else:
    # not ready to submit
    pass
