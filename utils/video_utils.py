from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips

def create_video_with_audio(image_folder, audio_path, output_path="final_video.mp4"):
    # List of images in order
    image_files = ["egg.jpg", "larva.jpg", "pupa.jpg", "butterfly.jpg"]

    # Load audio
    total_audio = AudioFileClip(audio_path)

    # Divide time equally for each image
    per_image_duration = total_audio.duration / len(image_files)

    clips = []
    for img in image_files:
        img_path = f"{image_folder}/{img}"
        clip = ImageClip(img_path).set_duration(per_image_duration)
        clips.append(clip)

    # Combine all images into one video
    video = concatenate_videoclips(clips, method="compose")
    video = video.set_audio(total_audio)

    # Export video
    video.write_videofile(output_path, fps=24)
