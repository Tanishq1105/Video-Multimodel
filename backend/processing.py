import os
import time
import google.generativeai as genai
from flask import current_app
from .models import Video
from .extensions import db
import logging
from .utils import generate_with_retry # This import was inside the function, moving it up for consistency

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def process_video(video_id, app_context):
    """
    Background task to process video:
    1. Upload to Gemini
    2. Wait for processing
    3. Generate Transcript
    """
    # Use context manager for cleaner handling
    with app_context:
        try:
            print(f"Starting processing for video {video_id}")
            video = Video.query.get(video_id)
            if not video:
                print(f"Video {video_id} not found")
                return

            video.status = "processing"
            db.session.commit()

            # Configure Gemini
            api_key = os.getenv("GOOGLE_API_KEY")
            if not api_key:
                print("GOOGLE_API_KEY not found")
                video.status = "failed"
                db.session.commit()
                return
                
            genai.configure(api_key=api_key)

            # 1. Upload to Gemini
            print(f"Uploading {video.filename} to Gemini...")
            
            video_path = None
            temp_file = False
            
            if video.s3_key:
                # Download from S3
                s3_bucket = os.getenv('AWS_BUCKET_NAME')
                if s3_bucket:
                    from .utils import download_from_s3
                    import tempfile
                    
                    # Create temp file
                    fd, temp_path = tempfile.mkstemp(suffix=os.path.splitext(video.filename)[1])
                    os.close(fd)
                    
                    print(f"Downloading from S3 to {temp_path}...")
                    if download_from_s3(s3_bucket, video.s3_key, temp_path):
                        video_path = temp_path
                        temp_file = True
                    else:
                        print("Failed to download from S3")
                        video.status = "failed"
                        db.session.commit()
                        return
            
            if not video_path:
                # Fallback to local
                video_path = os.path.join(current_app.root_path, video.file_path) if video.file_path else None
            
            if not video_path or not os.path.exists(video_path):
                print(f"File not found at {video_path}")
                video.status = "failed"
                db.session.commit()
                return
            
            try:
                upload_file = genai.upload_file(path=video_path, display_name=video.title)
                video.gemini_file_uri = upload_file.uri
                video.gemini_file_name = upload_file.name
                db.session.commit()
            except Exception as e:
                print(f"Gemini upload failed: {e}")
                video.status = "failed"
                db.session.commit()
                return
            finally:
                # Clean up temp file
                if temp_file and video_path and os.path.exists(video_path):
                    os.remove(video_path)

            # 2. Wait for Processing
            print("Waiting for Gemini processing...")
            while upload_file.state.name == "PROCESSING":
                time.sleep(5)
                upload_file = genai.get_file(upload_file.name)
                
            if upload_file.state.name == "FAILED":
                print("Gemini processing failed")
                video.status = "failed"
                db.session.commit()
                return

            # 3. Generate Transcript (Summary)
            print("Generating transcript/summary...")
            model = genai.GenerativeModel('gemini-2.0-flash')
            
            try:
                response = generate_with_retry(
                    model, 
                    [upload_file, "Generate a detailed transcript of this video with timestamps."],
                    retries=5,
                    initial_delay=5
                )
                video.transcript = response.text
                video.status = "completed"
                db.session.commit()
                print(f"Video {video_id} processing completed.")
                
            except Exception as e:
                print(f"Transcript generation failed: {e}")
                video.status = "failed"
                db.session.commit()

        except Exception as e:
            print(f"Unexpected error in process_video: {e}")
            # Try to update status if possible
            try:
                video = Video.query.get(video_id)
                if video:
                    video.status = "failed"
                    db.session.commit()
            except:
                pass
