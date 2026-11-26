from moviepy.editor import ImageClip, concatenate_videoclips
import os

# Folder where your images are stored
image_folder = r"C:\Users\gowth\OneDrive\Desktop\gow_1stproject\adaptive-learning-video\images"

# Get all JPG images from the folder, sorted alphabetically
image_files = sorted([f for f in os.listdir(image_folder) if f.lower().endswith(".jpg")])

# Check if images are found
if not image_files:
    raise FileNotFoundError("No JPG images found in the folder!")

# Create ImageClips for each image (duration = 2 seconds per image)
clips = [ImageClip(os.path.join(image_folder, img)).set_duration(2) for img in image_files]

# Concatenate all clips
final_video = concatenate_videoclips(clips, method="compose")

# Output video file
output_path = r"C:\Users\gowth\OneDrive\Desktop\gow_1stproject\adaptive-learning-video\output.mp4"
final_video.write_videofile(output_path, fps=24)

print(f"Video created successfully at: {output_path}")
