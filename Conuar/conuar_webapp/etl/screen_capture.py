import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

import mss


def capture_screen_with_recording(fps=15, max_duration=5, output_dir=None):
    """
    Capture screen and record as video file.
    
    Args:
        fps: Frames per second for video recording (default: 15)
        max_duration: Maximum recording duration in seconds (default: 5)
        output_dir: Directory to save video files (default: media/inspection_video)
    """
    # Set up output directory
    if output_dir is None:
        # Get the project root (parent of etl directory)
        current_dir = Path(__file__).resolve().parent
        project_root = current_dir.parent
        output_dir = project_root / "media" / "inspection_video"
    
    # Create output directory if it doesn't exist
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate filename with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = output_dir / f"screen_capture_{timestamp}.mov"
    
    print(f"Recording will be saved to: {output_file}")
    print(f"Recording duration: {max_duration} seconds at {fps} FPS")
    
    # Video writer setup
    video_writer = None
    frame_width = None
    frame_height = None
    
    # Track recording start time
    recording_start_time = None
    
    with mss.mss() as sct:
        # Part of the screen to capture
        monitor = {"top": 0, "left": 0, "width": 1920, "height": 1080}
        
        # Calculate frame time based on FPS
        frame_time = 1.0 / fps

        while True:
            last_time = time.time()

            # Get raw pixels from the screen, save it to a Numpy array
            img = np.array(sct.grab(monitor))

            # Convert BGRA to BGR for video encoding (OpenCV VideoWriter needs BGR)
            img_bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            
            # Initialize video writer on first frame
            if video_writer is None:
                recording_start_time = time.time()
                frame_height, frame_width = img_bgr.shape[:2]
                # Use 'mp4v' codec for .mov files (widely supported)
                fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                video_writer = cv2.VideoWriter(
                    str(output_file),
                    fourcc,
                    fps,
                    (frame_width, frame_height)
                )
                if not video_writer.isOpened():
                    print(f"ERROR: Could not open video writer for {output_file}")
                    print("Trying alternative codec...")
                    # Try alternative codec
                    fourcc = cv2.VideoWriter_fourcc(*'avc1')
                    video_writer = cv2.VideoWriter(
                        str(output_file),
                        fourcc,
                        fps,
                        (frame_width, frame_height)
                    )
                    if not video_writer.isOpened():
                        print("ERROR: Could not initialize video writer with any codec")
                        video_writer = None
                        break

            # Write frame to video
            if video_writer is not None:
                video_writer.write(img_bgr)

            # Check if maximum duration has been reached
            if recording_start_time is not None:
                elapsed_time = time.time() - recording_start_time
                if elapsed_time >= max_duration:
                    print(f"\nMaximum recording duration ({max_duration}s) reached. Stopping...")
                    break
            
            # Sleep to maintain target FPS
            sleep_time = frame_time - (time.time() - last_time)
            if sleep_time > 0:
                time.sleep(sleep_time)

    # Clean up video writer
    if video_writer is not None:
        video_writer.release()
        print(f"\nVideo saved successfully: {output_file}")
        file_size = output_file.stat().st_size / (1024 * 1024)  # Size in MB
        print(f"File size: {file_size:.2f} MB")


if __name__ == "__main__":
    # Default FPS is 15, max duration is 5 seconds
    capture_screen_with_recording(fps=15, max_duration=5)