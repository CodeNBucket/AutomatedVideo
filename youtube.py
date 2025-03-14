import os
import random
import requests
import time
import numpy as np
from moviepy.editor import ImageClip, AudioFileClip, CompositeAudioClip, CompositeVideoClip, concatenate_audioclips, AudioClip
from PIL import Image, ImageDraw, ImageFont
import textwrap
from moviepy.audio.fx.all import volumex  # Import volume adjustment function
import googleapiclient.discovery
import googleapiclient.errors
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import pickle
import random

# Paths
quotes_music_folder = #Your music file path
backgrounds_folder = #Your background image path
tts_output_folder = #Your tts output path
video_output = #Your video output path
quotes_path= # Your quotes txt path
# YouTube API credentials file
CLIENT_SECRETS_FILE = #Your client json path

# Video file path (generated video)
VIDEO_FILE = #Your video output path

# Title and description files
TITLE_FILE = #Your title file path
DESCRIPTION_FILE = #Your description file path

# OAuth 2.0 scopes required for YouTube API
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

# Select a random background image
background_image = random.choice(os.listdir(backgrounds_folder))
background_image_path = os.path.join(backgrounds_folder, background_image)
print("Selected Background Image:", background_image_path)

# Select a random quotes file
quotes_files = [os.path.join(quotes_path, f) for f in os.listdir(quotes_path) if f.endswith('.txt')]
if not quotes_files:
    raise FileNotFoundError("No text files found in the quotes directory.")
quotes_file_path = random.choice(quotes_files)
print("Selected Quotes File:", quotes_file_path)

# Read quotes from the selected file
with open(quotes_file_path, "r", encoding="utf-8") as file:
    quotes = file.readlines()
quotes = [q.strip() for q in quotes if q.strip()]
selected_quotes = random.sample(quotes, 15) if len(quotes) >= 2 else quotes

# Print selected quotes
print("Selected Quotes:")
for quote in selected_quotes:
    print(quote)

# Generate speech using AllTalk API
def generate_tts(quote, filename):
    url = "http://127.0.0.1:7851/api/tts-generate"
    data = {
        "text_input": quote,
        "text_filtering": "standard",
        "character_voice_gen": #Desired voice,
        "narrator_enabled": "false",
        "narrator_voice_gen": #Desired voice,
        "text_not_inside": "character",
        "language": "en",
        "output_file_name": filename,
        "output_file_timestamp": "true",
        "autoplay": "false",
        "autoplay_volume": "0.8"
    }
    response = requests.post(url, data=data)
    if response.status_code == 200:
        result = response.json()
        if result.get("status") == "generate-success":
            return result["output_file_path"]
    return None

# Generate TTS for each quote
tts_files = []
for i, quote in enumerate(selected_quotes):
    filename = f"quote_{i+1}"
    tts_path = generate_tts(quote, filename)
    if tts_path:
        tts_files.append(tts_path)
    time.sleep(2)

if not tts_files:
    raise FileNotFoundError("TTS generation failed. No audio files created.")

# Load and process quotes audio
audio_clips = [AudioFileClip(tts).volumex(1.0) for tts in tts_files]

# Create silence padding between quotes
silence_duration = 3
silence_clip = AudioClip(lambda t: 0, duration=silence_duration, fps=44100)

# Add silence at the start
audio_sequence = [silence_clip]
for i, audio in enumerate(audio_clips):
    audio_sequence.append(audio)
    if i < len(audio_clips) - 1:
        audio_sequence.append(silence_clip)
audio_sequence.append(AudioClip(lambda t: 0, duration=1, fps=44100))  # 1-sec silence at the end

# Merge all quote audio with silence gaps
quotes_audio = concatenate_audioclips(audio_sequence)

# Load background music
music_files = [os.path.join(quotes_music_folder, f) for f in os.listdir(quotes_music_folder) if f.endswith('.mp3') or f.endswith('.wav')]
if not music_files:
    raise FileNotFoundError("No music files found in the quotes_music folder.")

selected_music = random.choice(music_files)
music_clip = AudioFileClip(selected_music).volumex(0.15)  # Lower music volume

# Ensure background music matches the duration of quotes audio
if music_clip.duration < quotes_audio.duration:
    loop_count = int(quotes_audio.duration // music_clip.duration) + 1
    music_clip = concatenate_audioclips([music_clip] * loop_count)  # Loop music if it's too short

music_clip = music_clip.set_duration(quotes_audio.duration).audio_fadein(3).audio_fadeout(3)

# Merge music and quotes
merged_audio = CompositeAudioClip([quotes_audio, music_clip])

# Load and resize background image
image = Image.open(background_image_path)
width, height = image.size
scale_factor = 720 / height
new_width = int(width * scale_factor)
new_height = int(height * scale_factor)
image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

# Create image clip with merged audio
img_clip = ImageClip(np.array(image)).set_duration(quotes_audio.duration).set_audio(merged_audio).fadein(2).fadeout(2)

# Function to format quote text
def format_quote_text(quote, max_line_length=50):
    if "-" in quote:
        text_part, author_part = quote.rsplit("-", 1)
    else:
        text_part, author_part = quote, None
    text_lines = textwrap.wrap(text_part, width=max_line_length)
    author_lines = textwrap.wrap(author_part.strip(), width=max_line_length) if author_part else None
    return text_lines, author_lines

# Function to create text images
def create_text_image(text, font_path, font_size, image_size):
    img = Image.new("RGBA", image_size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype(font_path, font_size)
    text_width = draw.textbbox((0, 0), text, font=font)[2]  # Get text width
    x_position = (image_size[0] - text_width) // 2
    draw.text((x_position, 0), text, font=font, fill="white")
    return img

# Function to remove used quotes from the selected file
def remove_used_quotes(file_path, used_quotes):
    with open(file_path, "r", encoding="utf-8") as file:
        lines = [line.strip() for line in file.readlines() if line.strip()]

    # Remove used quotes
    remaining_lines = [line for line in lines if line not in used_quotes]

    with open(file_path, "w", encoding="utf-8") as file:
        file.writelines("\n".join(remaining_lines) + "\n")  # Ensure the file is properly formatted

    print(f"🗑️ Removed used quotes from: {file_path}")



# Add text overlay for quotes
text_clips = []
current_time = 3  # Start after 3-second silence
for i, (quote, tts_file) in enumerate(zip(selected_quotes, tts_files)):
    text_lines, author_lines = format_quote_text(quote)
    audio_duration = AudioFileClip(tts_file).duration
    start_y = (new_height - len(text_lines) * 50) // 2

    # Display Quote
    for j, line in enumerate(text_lines):
        text_img = create_text_image(line, #your desired font, 50, (new_width, 60))
        text_clip = ImageClip(np.array(text_img)).set_duration(audio_duration + 1).set_start(current_time - 1).set_position(("center", start_y + j * 50)).crossfadein(1).crossfadeout(1)
        text_clips.append(text_clip)

    # Display Author Name
    if author_lines:
        author_start_y = start_y + (len(text_lines) * 50) + 20
        for j, line in enumerate(author_lines):
            author_img = create_text_image(line,#your desired font, 35, (new_width, 60))
            author_clip = ImageClip(np.array(author_img)).set_duration(audio_duration + 1).set_start(current_time - 1).set_position(("center", author_start_y + j * 40)).crossfadein(1).crossfadeout(1)
            text_clips.append(author_clip)

    current_time += audio_duration + 3  # Move to next quote

# Compile video
video = CompositeVideoClip([img_clip] + text_clips)

video.write_videofile(video_output, codec="libx264", fps=30, audio_codec="aac", bitrate="8000k")

# Function to wait for file creation
def wait_for_file(file_path, timeout=300, check_interval=5):
    """
    Wait for the given file to be created, checking every `check_interval` seconds,
    up to a `timeout` limit.
    """
    elapsed_time = 0
    while not os.path.exists(file_path):
        if elapsed_time >= timeout:
            print(f"⚠️ Timeout reached! Video file '{file_path}' was not created.")
            return False
        print(f"⏳ Waiting for video file to be created... ({elapsed_time}s)")
        time.sleep(check_interval)
        elapsed_time += check_interval
    return True

# Wait for the video file to be fully created before uploading
if wait_for_file(video_output):
    print("✅ Video created successfully at:", video_output)
    os.remove(background_image_path)
    remove_used_quotes(quotes_file_path, selected_quotes)

else:
    print("❌ Video creation failed. Skipping upload.")





# Authenticate & get YouTube API client
def get_authenticated_service():
    creds = None
    if os.path.exists("token.pickle"):
        with open("token.pickle", "rb") as token:
            creds = pickle.load(token)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.pickle", "wb") as token:
            pickle.dump(creds, token)

    return googleapiclient.discovery.build("youtube", "v3", credentials=creds)

# Function to get a random line from a file and remove it
def get_random_line_and_remove(file_path):
    with open(file_path, "r", encoding="utf-8") as file:
        lines = [line.strip() for line in file.readlines() if line.strip()]  # Remove empty lines

    if not lines:
        print(f"⚠️ {file_path} is empty!")
        return None

    selected_line = random.choice(lines)
    print(f"🔹 Selected from {file_path}: {selected_line}")

    # Remove the selected line
    lines = [line for line in lines if line != selected_line]

    with open(file_path, "w", encoding="utf-8") as file:
        file.writelines("\n".join(lines) + "\n")  # Ensure the file is properly formatted

    return selected_line

# Upload video to YouTube
def upload_video():
    youtube = get_authenticated_service()

    title = get_random_line_and_remove(TITLE_FILE)
    description = get_random_line_and_remove(DESCRIPTION_FILE)

    if not title or not description:
        print("⚠️ No valid title or description found. Skipping upload.")
        return

    request = youtube.videos().insert(
        part="snippet,status",
        body={
            "snippet": {
                "title": title,
                "description": description,
                "tags": ["motivation", "quotes", "daily inspiration"],
                "categoryId": "22",  # "22" is the category for People & Blogs
            },
            "status": {
                "privacyStatus": "public"  # Options: public, private, unlisted
            },
        },
        media_body=googleapiclient.http.MediaFileUpload(VIDEO_FILE, chunksize=-1, resumable=True),
    )

    response = request.execute()
    print(f"✅ Video uploaded successfully! Watch here: https://www.youtube.com/watch?v={response['id']}")

if __name__ == "__main__":
    upload_video()
