import os
import re
import json
import hashlib
from io import BytesIO

import requests
import streamlit as st
from dotenv import load_dotenv
from PIL import Image, ImageDraw, ImageFont, ImageOps

from tts_utils import text_to_speech
from utils.generate_script import generate_script

from moviepy.editor import (
    ImageClip,
    AudioFileClip,
    concatenate_videoclips,
    CompositeAudioClip
)

load_dotenv()

# -------------------- FOLDERS AND PAGE --------------------

for folder in (
    "downloaded_images",
    "slide_audio",
    "processed_slides",
    "images"
):
    os.makedirs(folder, exist_ok=True)


st.set_page_config(
    page_title="Adaptive Learning Video Creator",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)


def local_css(file_name):
    if os.path.exists(file_name):
        with open(file_name, "r", encoding="utf-8") as file:
            st.markdown(
                f"<style>{file.read()}</style>",
                unsafe_allow_html=True
            )


local_css("style.css")


# -------------------- SCRIPT GENERATION --------------------

def create_offline_script(topic, level, duration, focus):

    name = topic.strip()
    lower = name.lower()

    if "heart" in lower and (
        "blood" in lower or "pump" in lower
    ):

        content = [
            (
                "Introduction to the Human Heart",
                "The human heart is a muscular organ located in the chest. It works like a pump, continuously circulating blood throughout the body. This supplies oxygen and nutrients to every cell.",
                "human heart anatomy medical illustration"
            ),
            (
                "Structure of the Heart",
                "The heart has four chambers: the right atrium, right ventricle, left atrium and left ventricle. The atria receive blood, while the ventricles pump blood out. Valves help prevent backward flow.",
                "four chambers human heart labeled diagram"
            ),
            (
                "Blood Flow to the Lungs",
                "Oxygen-poor blood from the body enters the right atrium through the vena cava. It moves into the right ventricle, which pumps it to the lungs through the pulmonary artery.",
                "human heart pulmonary blood flow diagram"
            ),
            (
                "Oxygenation in the Lungs",
                "Inside the lungs, blood releases carbon dioxide and absorbs oxygen. The oxygen-rich blood then returns to the left atrium through the pulmonary veins.",
                "lungs oxygen carbon dioxide gas exchange diagram"
            ),
            (
                "Blood Flow to the Body",
                "Blood moves from the left atrium into the left ventricle. The left ventricle pumps oxygen-rich blood through the aorta to the rest of the body.",
                "aorta systemic circulation human body diagram"
            ),
            (
                "Heartbeat and Summary",
                "Electrical signals coordinate the heart's contractions and relaxation. This continuous cycle keeps blood moving and supplies the body's organs with oxygen and nutrients.",
                "human heart electrical conduction heartbeat illustration"
            ),
        ]

    else:

        content = [
            (
                f"Introduction to {name}",
                f"In this lesson, we will explore {name}. We will begin with its meaning, why it matters, and the main ideas needed to understand it.",
                f"{name} educational overview illustration"
            ),
            (
                f"Basic Concepts of {name}",
                f"The first step in understanding {name} is to identify its important concepts and components. These ideas provide the foundation for learning the topic.",
                f"{name} key concepts diagram"
            ),
            (
                f"How {name} Works",
                f"Next, consider how the parts of {name} are connected. Understanding the process step by step makes it easier to see how the overall system works.",
                f"{name} process working diagram"
            ),
            (
                f"Examples of {name}",
                f"Examples help connect the ideas in {name} with practical situations. They also make it easier to remember where and how the topic can be used.",
                f"{name} real world example illustration"
            ),
            (
                f"Summary of {name}",
                f"To summarize, remember the main concepts, how they are connected, and why they are important. These points form the foundation for further learning about {name}.",
                f"{name} educational summary infographic"
            ),
            (
                "Quick Recap",
                f"You have reviewed the introduction, key concepts, working process, and examples of {name}. Review these ideas to strengthen your understanding.",
                f"{name} learning recap illustration"
            ),
        ]

    count = {
        "1 minute": 4,
        "2 minutes": 5,
        "3 minutes": 6
    }.get(duration, 4)

    return [
        {
            "slide_number": i + 1,
            "heading": heading,
            "narration": narration,
            "search_query": query,
            "image_results": [],
            "current_url_index": -1,
            "auto_image_attempted": False,
            "last_searched_query": ""
        }
        for i, (heading, narration, query)
        in enumerate(content[:count])
    ]


def generate_educational_script(
    topic, level, duration, focus, api_key, model
):

    if not api_key or not api_key.strip():
        return create_offline_script(
            topic, level, duration, focus
        )

    raw = generate_script(
        topic=topic,
        level=level,
        duration=duration,
        focus=focus,
        api_key=api_key.strip(),
        model_name=model,
    )

    raw = raw.strip()

    raw = re.sub(
        r"^\s*```(?:json)?\s*",
        "",
        raw,
        flags=re.IGNORECASE
    )

    raw = re.sub(
        r"\s*```\s*$",
        "",
        raw
    )

    items = json.loads(raw)

    if not isinstance(items, list) or not items:
        raise ValueError(
            "Gemini did not return a valid slide list."
        )

    slides = []

    for item in items:

        if not isinstance(item, dict):
            continue

        narration = str(
            item.get("narration", "")
        ).strip()

        if not narration:
            continue

        slides.append({
            "slide_number": len(slides) + 1,
            "heading": str(
                item.get(
                    "heading",
                    f"Slide {len(slides) + 1}"
                )
            ),
            "narration": narration,
            "search_query": str(
                item.get(
                    "search_query",
                    item.get("image_keyword", topic)
                )
            ),
            "image_results": [],
            "current_url_index": -1,
            "auto_image_attempted": False,
            "last_searched_query": ""
        })

    if not slides:
        raise ValueError(
            "Gemini returned no slides with narration."
        )

    return slides


# -------------------- WIKIMEDIA IMAGE SEARCH --------------------

def scrape_image_urls(query, max_images=20):

    api_url = "https://commons.wikimedia.org/w/api.php"

    params = {
        "action": "query",
        "generator": "search",
        "gsrsearch": query,
        "gsrnamespace": 6,
        "gsrlimit": max_images,
        "prop": "imageinfo",
        "iiprop": "url|extmetadata",
        "iiurlwidth": 1200,
        "format": "json",
    }

    headers = {
        "User-Agent": (
            "AdaptiveLearningVideoCreator/1.0 "
            "(educational project)"
        )
    }

    response = requests.get(
        api_url,
        params=params,
        headers=headers,
        timeout=30
    )

    response.raise_for_status()

    data = response.json()

    if "query" not in data:
        return []

    pages = data["query"].get("pages", {})

    results = []

    for page in pages.values():

        title = page.get("title", "")
        infos = page.get("imageinfo", [])

        if not infos:
            continue

        info = infos[0]

        image_url = (
            info.get("thumburl") or info.get("url")
        )

        if not image_url:
            continue

        meta = info.get("extmetadata", {})

        artist_html = str(
            meta.get("Artist", {}).get(
                "value", "Unknown"
            )
        )

        artist = re.sub(
            r"<[^>]*>", "", artist_html
        )

        artist = re.sub(
            r"\s+", " ", artist
        ).strip()

        description_html = str(
            meta.get("ImageDescription", {}).get(
                "value", ""
            )
        )

        description = re.sub(
            r"<[^>]*>", " ", description_html
        )

        description = re.sub(
            r"\s+", " ", description
        ).strip()

        results.append({
            "url": image_url,
            "title": title,
            "description": description,
            "artist": artist or "Unknown",
            "license": str(
                meta.get("LicenseShortName", {}).get(
                    "value", "Check source page"
                )
            ),
            "page": info.get("descriptionurl", "")
        })

    return results


# -------------------- IMAGE DOWNLOAD --------------------

def download_image(url, save_path):

    try:

        response = requests.get(
            url,
            headers={
                "User-Agent": "AdaptiveLearningVideoCreator/1.0"
            },
            timeout=30
        )

        response.raise_for_status()

        data = BytesIO(response.content)

        with Image.open(data) as image:
            image.verify()

        data.seek(0)

        with Image.open(data) as image:

            image = ImageOps.exif_transpose(image)
            image = image.convert("RGB")

            image.save(
                save_path,
                "JPEG",
                quality=92
            )

        return True

    except Exception as error:

        print(f"Image download failed: {error}")

        if os.path.exists(save_path):
            try:
                os.remove(save_path)
            except OSError:
                pass

        return False


# -------------------- IMAGE SELECTION FOR EACH SLIDE --------------------

def download_image_for_slide(index, force_next=False):

    slide = st.session_state["script_slides"][index]

    query = str(
        slide.get("search_query", "")
    ).strip()

    heading = str(
        slide.get("heading", "")
    ).strip()

    if not query:
        return False

    query_hash = hashlib.md5(
        query.lower().encode("utf-8")
    ).hexdigest()[:10]

    last_query = slide.get("last_searched_query", "")

    had_results = bool(
        slide.get("image_results")
    )

    # Search again if the keyword has changed
    if last_query != query:
        slide["image_results"] = []
        slide["current_url_index"] = -1
        slide["last_searched_query"] = query
        slide.pop("image_path", None)
        had_results = False

    # Search Wikimedia when there are no cached results
    if not had_results:

        search_terms = [
            query,
            heading + " educational diagram",
            heading + " medical illustration"
        ]

        found_results = []
        seen = set()

        for term in search_terms:

            try:

                search_results = scrape_image_urls(
                    term,
                    max_images=20
                )

                for result in search_results:

                    url = result["url"]

                    if url not in seen:
                        seen.add(url)
                        found_results.append(result)

            except Exception as error:

                print(
                    f"Image search failed: {error}"
                )

        # Rank results using meaningful matching words
        stop_words = {
            "the", "and", "for", "with", "from",
            "into", "human", "image", "images",
            "diagram", "illustration", "educational",
            "medical", "anatomy", "picture"
        }

        query_words = {
            word
            for word in re.findall(
                r"[a-zA-Z]+",
                (query + " " + heading).lower()
            )
            if len(word) > 2 and word not in stop_words
        }

        for result in found_results:

            image_text = (
                result.get("title", "") + " " +
                result.get("description", "")
            ).lower()

            image_words = set(
                re.findall(
                    r"[a-zA-Z]+",
                    image_text
                )
            )

            result["relevance"] = len(
                query_words & image_words
            )

        found_results.sort(
            key=lambda item: item["relevance"],
            reverse=True
        )

        slide["image_results"] = [
            result
            for result in found_results
            if result["relevance"] >= 1
        ]

        slide["current_url_index"] = -1

    results = slide.get("image_results", [])

    if not results:
        slide.pop("image_path", None)
        return False

    if force_next and had_results:
        start = (
            slide.get("current_url_index", -1) + 1
        )
    else:
        start = 0

    for result_index in range(start, len(results)):

        result = results[result_index]

        filename = (
            f"downloaded_images/commons_slide_"
            f"{slide['slide_number']}_"
            f"{query_hash}_{result_index}.jpg"
        )

        if os.path.exists(filename):

            try:

                with Image.open(filename) as image:
                    image.verify()

                slide["image_path"] = filename
                slide["current_url_index"] = result_index
                slide["image_credit"] = result

                return True

            except Exception:
                os.remove(filename)

        if download_image(result["url"], filename):

            slide["image_path"] = filename
            slide["current_url_index"] = result_index
            slide["image_credit"] = result

            return True

    slide.pop("image_path", None)

    return False

# -------------------- IMAGE AND SUBTITLE HELPERS --------------------

def create_placeholder_image(text, output_path):

    img = Image.new(
        "RGB",
        (1280, 720),
        (35, 45, 65)
    )

    draw = ImageDraw.Draw(img)

    try:
        font = ImageFont.truetype(
            "arial.ttf",
            48
        )
    except OSError:
        font = ImageFont.load_default()

    lines = text.split("\n")

    total_height = sum(
        draw.textbbox(
            (0, 0),
            line,
            font=font
        )[3] + 20
        for line in lines
    )

    y = (720 - total_height) // 2

    for line in lines:

        bbox = draw.textbbox(
            (0, 0),
            line,
            font=font
        )

        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]

        draw.text(
            ((1280 - width) // 2, y),
            line,
            fill="white",
            font=font
        )

        y += height + 20

    img.save(output_path)

    return output_path


def draw_subtitle_on_image(
    image_path,
    text,
    output_path
):

    image = Image.open(
        image_path
    ).convert("RGB")

    image = ImageOps.fit(
        image,
        (1280, 720)
    )

    overlay = Image.new(
        "RGBA",
        image.size,
        (0, 0, 0, 0)
    )

    draw = ImageDraw.Draw(overlay)

    try:
        font = ImageFont.truetype(
            "arial.ttf",
            30
        )
    except OSError:
        font = ImageFont.load_default()

    words = text.split()

    lines = []
    current = ""

    for word in words:

        test = (
            current + " " + word
            if current else word
        )

        if draw.textbbox(
            (0, 0),
            test,
            font=font
        )[2] > 1100:

            lines.append(current)
            current = word

        else:
            current = test

    if current:
        lines.append(current)

    lines = lines[:4]

    line_heights = [
        draw.textbbox(
            (0, 0),
            line,
            font=font
        )[3]
        for line in lines
    ]

    total_height = (
        sum(line_heights)
        + 15 * (len(lines) - 1)
    )

    banner_height = total_height + 50

    draw.rectangle(
        (0, 720 - banner_height, 1280, 720),
        fill=(0, 0, 0, 190)
    )

    y = 720 - banner_height + 25

    for line, height in zip(
        lines,
        line_heights
    ):

        bbox = draw.textbbox(
            (0, 0),
            line,
            font=font
        )

        width = bbox[2] - bbox[0]

        draw.text(
            ((1280 - width) // 2, y),
            line,
            font=font,
            fill="white"
        )

        y += height + 15

    result = Image.alpha_composite(
        image.convert("RGBA"),
        overlay
    ).convert("RGB")

    result.save(output_path)

    return output_path


# -------------------- BACKGROUND MUSIC --------------------

def get_bg_music(option):

    if option == "No Music":
        return None

    if option == "Sample Background Music":

        music_path = "background_music.mp3"

        if not os.path.exists(music_path):

            try:

                url = (
                    "https://www.soundhelix.com/"
                    "examples/mp3/SoundHelix-Song-1.mp3"
                )

                response = requests.get(
                    url,
                    timeout=30
                )

                response.raise_for_status()

                with open(music_path, "wb") as f:
                    f.write(response.content)

            except Exception as error:

                st.warning(
                    f"Could not download background music: {error}"
                )

                return None

        return music_path

    return None


# -------------------- SIDEBAR SETTINGS --------------------

st.sidebar.title("⚙️ Settings")

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    api_key = st.sidebar.text_input(
        "Gemini API Key",
        type="password",
        help="Leave empty to use the offline script."
    )


model_choice = st.sidebar.selectbox(
    "Gemini Model",
    ["gemini-3.5-flash-lite"]
)


voice_choice = st.sidebar.selectbox(
    "Narration Accent",
    [
        "Indian",
        "British",
        "American",
        "Australian"
    ]
)

voice_map = {
    "Indian": "co.in",
    "British": "co.uk",
    "American": "com",
    "Australian": "com.au",
}

tld = voice_map[voice_choice]


# -------------------- MAIN TITLE --------------------

st.title("🎬 Adaptive Learning Video Creator")

st.write(
    "Create educational videos using AI-generated scripts, "
    "images, narration and subtitles."
)


# -------------------- TABS --------------------

tab1, tab2, tab3 = st.tabs(
    [
        "📝 Step 1: Generate Script",
        "🖼️ Step 2: Edit Slides",
        "🎥 Step 3: Create Video"
    ]
)


# -------------------- STEP 1: SCRIPT GENERATION --------------------

with tab1:

    st.header("Generate Your Learning Script")

    topic = st.text_input(
        "Enter your topic",
        placeholder="Example: How the Human Heart Pumps Blood"
    )

    level = st.slider(
        "Learning Level",
        min_value=1,
        max_value=10,
        value=5
    )

    duration = st.selectbox(
        "Video Duration",
        [
            "1 minute",
            "2 minutes",
            "3 minutes"
        ]
    )

    focus = st.radio(
        "Learning Focus",
        [
            "Concept Explanation",
            "Exam Preparation",
            "Practical Examples"
        ],
        horizontal=True
    )

    if st.button(
        "✨ Generate Script",
        type="primary"
    ):

        if not topic.strip():

            st.warning("Please enter a topic.")

        else:

            with st.spinner(
                "Generating your educational script..."
            ):

                try:

                    slides = generate_educational_script(
                        topic,
                        level,
                        duration,
                        focus,
                        api_key,
                        model_choice
                    )

                    st.session_state["script_slides"] = slides

                    st.session_state["video_topic"] = topic

                    st.session_state["target_duration"] = duration

                    st.session_state["generation_id"] = (
                        st.session_state.get(
                            "generation_id",
                            0
                        ) + 1
                    )

                    st.success(
                        "Script generated successfully!"
                    )

                    st.rerun()

                except Exception as error:

                    st.error(
                        f"Script generation failed: {error}"
                    )

    if st.session_state.get("script_slides"):

        st.subheader("Generated Script")

        for slide in st.session_state["script_slides"]:

            st.markdown(
                f"### Slide {slide['slide_number']}: "
                f"{slide['heading']}"
            )

            st.write(slide["narration"])

# ==========================================
# STEP 2: EDIT SLIDES
# ==========================================

with tab2:
    st.header("🖼️ Edit Your Slides")

    if "script_slides" not in st.session_state or not st.session_state["script_slides"]:
        st.info("Please generate a script in Step 1 first.")

    else:
        slides = st.session_state["script_slides"]

        for i, slide in enumerate(slides):

            st.divider()
            st.subheader(f"Slide {i + 1}")

            # Edit slide heading
            slide["heading"] = st.text_input(
                "Slide Heading",
                value=slide.get("heading", ""),
                key=f"heading_{i}"
            )

            # Edit narration
            slide["narration"] = st.text_area(
                "Narration",
                value=slide.get("narration", ""),
                height=120,
                key=f"narration_{i}"
            )

            # Edit image search keyword
            slide["search_query"] = st.text_input(
                "Image Search Keyword",
                value=slide.get("search_query", slide["heading"]),
                key=f"keyword_{i}"
            )

            # Automatically search for an image.
            # Search again if the keyword has changed.
            if (
                not slide.get("auto_image_attempted", False)
                or slide.get("last_searched_query", "")
                != slide.get("search_query", "").strip()
            ):
                slide["auto_image_attempted"] = True

                with st.spinner(f"Finding an image for Slide {i + 1}..."):
                    success = download_image_for_slide(i)

                if success:
                    st.success("Image found automatically!")
                else:
                    st.warning(
                        "No suitable image found. Try another keyword "
                        "or upload your own image."
                    )

            # Image search buttons
            col1, col2 = st.columns(2)

            with col1:
                if st.button(
                    "🔍 Search / Refresh",
                    key=f"search_{i}"
                ):
                    slide["image_results"] = []
                    slide["current_url_index"] = -1
                    slide["last_searched_query"] = ""
                    slide.pop("image_path", None)

                    with st.spinner("Searching for images..."):
                        success = download_image_for_slide(i)

                    if success:
                        st.success("New image found!")
                    else:
                        st.warning("No image found for this keyword.")

                    st.rerun()

            with col2:
                if st.button(
                    "➡️ Try Next Image",
                    key=f"next_{i}"
                ):
                    with st.spinner("Finding the next image..."):
                        success = download_image_for_slide(
                            i,
                            force_next=True
                        )

                    if success:
                        st.success("Next image selected!")
                    else:
                        st.warning("No more suitable images found.")

                    st.rerun()

            # Display selected image
            image_path = slide.get("image_path")

            if image_path and os.path.exists(image_path):
                st.image(
                    image_path,
                    caption=f"Slide {i + 1} Image",
                    use_container_width=True
                )

                credit = slide.get("image_credit")

                if credit:
                    st.caption(
                        f"Image: {credit.get('title', 'Wikimedia Commons')} "
                        f"| Creator: {credit.get('artist', 'Unknown')} "
                        f"| License: {credit.get('license', 'Unknown')}"
                    )

                    if credit.get("page"):
                        st.markdown(
                            f"[View Original Image]({credit['page']})"
                        )
            else:
                st.info("No image selected for this slide yet.")

            # Upload a custom image
            uploaded_image = st.file_uploader(
                "Or upload your own image",
                type=["jpg", "jpeg", "png"],
                key=f"upload_{i}"
            )

            if uploaded_image is not None:
                try:
                    custom_image = Image.open(uploaded_image).convert("RGB")

                    custom_path = os.path.join(
                        "downloaded_images",
                        f"slide_{slide['slide_number']}_upload.jpg"
                    )

                    custom_image.save(custom_path, "JPEG")

                    slide["image_path"] = custom_path
                    slide.pop("image_credit", None)

                    st.image(
                        custom_image,
                        caption="Uploaded Custom Image",
                        use_container_width=True
                    )

                    st.success("Custom image uploaded successfully!")

                except Exception as e:
                    st.error(f"Unable to process uploaded image: {e}")


# ==========================================
# STEP 3: CREATE VIDEO
# ==========================================

with tab3:
    st.header("🎥 Create Your Educational Video")

    if "script_slides" not in st.session_state or not st.session_state["script_slides"]:
        st.info("Please generate a script in Step 1 first.")

    else:
        slides = st.session_state["script_slides"]

        st.write(
            "Your slides, narration, subtitles and images "
            "will be combined into one educational video."
        )

        # Background music selection
        music_option = st.selectbox(
            "Background Music",
            ["No Music", "Sample Background Music"],
            key="music_option"
        )

        # Optional custom background music
        uploaded_music = st.file_uploader(
            "Upload your own background music (optional)",
            type=["mp3"],
            key="custom_music"
        )

        custom_music_path = None

        if uploaded_music is not None:
            custom_music_path = "custom_background_music.mp3"

            with open(custom_music_path, "wb") as f:
                f.write(uploaded_music.getbuffer())

            st.success("Custom background music uploaded!")

        if st.button("🎬 Generate Video", type="primary"):

            video_clips = []
            audio_clips = []
            music_clip = None
            final_video = None

            progress_bar = st.progress(0)
            status_text = st.empty()

            try:
                total_slides = len(slides)

                # Generate narration and slide clips
                for i, slide in enumerate(slides):

                    status_text.write(
                        f"Processing slide {i + 1} of {total_slides}..."
                    )

                    narration = slide.get("narration", "").strip()

                    if not narration:
                        raise ValueError(
                            f"Slide {i + 1} has no narration."
                        )

                    # Use selected image or create placeholder
                    image_path = slide.get("image_path")

                    if not image_path or not os.path.exists(image_path):
                        image_path = os.path.join(
                            "processed_slides",
                            f"placeholder_{i + 1}.jpg"
                        )

                        create_placeholder_image(
                            slide.get("heading", f"Slide {i + 1}"),
                            image_path
                        )

                    # Generate speech audio
                    audio_path = os.path.join(
                        "slide_audio",
                        f"slide_{i + 1}.mp3"
                    )

                    text_to_speech(
                        narration,
                        filename=audio_path,
                        lang="en",
                        tld=tld
                    )

                    if not os.path.exists(audio_path):
                        raise FileNotFoundError(
                            f"Audio was not generated for Slide {i + 1}."
                        )

                    # Load narration audio
                    audio = AudioFileClip(audio_path)
                    audio_clips.append(audio)

                    # Add subtitles to the slide image
                    subtitle_path = os.path.join(
                        "processed_slides",
                        f"slide_{i + 1}_subtitle.jpg"
                    )

                    draw_subtitle_on_image(
                        image_path,
                        narration,
                        subtitle_path
                    )

                    # Create video clip with narration
                    clip = (
                        ImageClip(subtitle_path)
                        .set_duration(audio.duration)
                        .set_audio(audio)
                    )

                    video_clips.append(clip)

                    progress_bar.progress(
                        int(((i + 1) / total_slides) * 70)
                    )

                # Combine all slide clips
                status_text.write("Combining all slides...")

                final_video = concatenate_videoclips(
                    video_clips,
                    method="compose"
                )

                progress_bar.progress(80)

                # Add background music if selected
                music_path = custom_music_path

                if music_path is None:
                    music_path = get_bg_music(music_option)

                if music_path and os.path.exists(music_path):

                    status_text.write("Adding background music...")

                    music_clip = AudioFileClip(music_path)

                    if music_clip.duration < final_video.duration:
                        music_clip = music_clip.audio_loop(
                            duration=final_video.duration
                        )
                    else:
                        music_clip = music_clip.subclip(
                            0,
                            final_video.duration
                        )

                    # Keep background music quieter than narration
                    music_clip = music_clip.volumex(0.15)

                    if final_video.audio is not None:
                        final_video = final_video.set_audio(
                            CompositeAudioClip([
                                final_video.audio,
                                music_clip
                            ])
                        )
                    else:
                        final_video = final_video.set_audio(music_clip)

                progress_bar.progress(90)

                # Export final video
                status_text.write("Exporting your video...")

                output_path = "personalized_education_video.mp4"

                final_video.write_videofile(
                    output_path,
                    fps=24,
                    codec="libx264",
                    audio_codec="aac",
                    preset="medium"
                )

                progress_bar.progress(100)
                status_text.success("Your video is ready!")

                st.success("🎉 Video generated successfully!")

                # Display video
                st.video(output_path)

                # Download video
                with open(output_path, "rb") as video_file:
                    st.download_button(
                        label="⬇️ Download Your Video",
                        data=video_file,
                        file_name="educational_video.mp4",
                        mime="video/mp4"
                    )

                st.write(
                    f"**Video Duration:** "
                    f"{final_video.duration:.2f} seconds"
                )

            except Exception as e:
                st.error(f"Video generation failed: {e}")

            finally:
                # Close MoviePy resources
                if final_video is not None:
                    try:
                        final_video.close()
                    except Exception:
                        pass

                if music_clip is not None:
                    try:
                        music_clip.close()
                    except Exception:
                        pass

                for clip in video_clips:
                    try:
                        clip.close()
                    except Exception:
                        pass

                for audio in audio_clips:
                    try:
                        audio.close()
                    except Exception:
                        pass
