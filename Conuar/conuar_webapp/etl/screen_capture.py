import time
import csv
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict

import cv2
import numpy as np

import mss


def is_boolean_true(value) -> bool:
    """Check if a value represents boolean TRUE"""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower().strip() in ('true', '1', 'yes')
    if isinstance(value, (int, float)):
        return value == 1
    return False


def read_csv_last_line(csv_file: Path) -> Optional[Dict]:
    """Read the last non-empty line from CSV file"""
    if not csv_file.exists():
        return None
    
    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            # Read all lines
            lines = f.readlines()
            
            # Find last non-empty line (skip header and empty lines)
            for line in reversed(lines):
                line = line.strip()
                if line and not line.startswith('datetime,'):
                    # Parse CSV line
                    reader = csv.reader([line])
                    row = next(reader)
                    if len(row) >= 9:
                        return {
                            'datetime': row[0],
                            'CicloActivo': row[1],
                            'ReiniciarCiclo': row[2],
                            'AbortarCiclo': row[3],
                            'FinCiclo': row[4],
                            'ID_Control': row[5],
                            'Nombre_Control': row[6],
                            'ID_EC': row[7],
                            'NombreCiclo': row[8]
                        }
    except Exception as e:
        print(f"Error reading CSV: {e}")
    
    return None


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


def monitor_and_record_inspections(fps=15, csv_file_path=None, output_dir=None, check_interval=1.0):
    """
    Monitor CSV file for CicloActivo changes and record screen during inspections.
    
    Args:
        fps: Frames per second for video recording (default: 15)
        csv_file_path: Path to plc_reads_nodered.csv file
        output_dir: Directory to save video files (default: media/inspection_video)
        check_interval: How often to check CSV file in seconds (default: 1.0)
    """
    # Set up CSV file path
    if csv_file_path is None:
        current_dir = Path(__file__).resolve().parent
        csv_file_path = current_dir / "NodeRed" / "plc_reads" / "plc_reads_nodered.csv"
    else:
        csv_file_path = Path(csv_file_path)
    
    if not csv_file_path.exists():
        print(f"ERROR: CSV file not found: {csv_file_path}")
        return
    
    # Set up output directory
    if output_dir is None:
        current_dir = Path(__file__).resolve().parent
        project_root = current_dir.parent
        output_dir = project_root / "media" / "inspection_video"
    
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print("=" * 80)
    print("Inspection Screen Recorder - Sistema Conuar")
    print("=" * 80)
    print(f"Monitoring CSV: {csv_file_path}")
    print(f"Output directory: {output_dir}")
    print(f"Recording FPS: {fps}")
    print(f"Check interval: {check_interval}s")
    print("=" * 80)
    print()
    
    # State tracking
    last_ciclo_activo = False
    is_recording = False
    video_writer = None
    recording_start_time = None
    current_inspection_info = None
    frame_width = None
    frame_height = None
    
    # Screen capture setup
    sct = mss.mss()
    monitor = {"top": 0, "left": 0, "width": 1920, "height": 1080}
    frame_time = 1.0 / fps
    
    print("Waiting for inspection cycle to start (CicloActivo = TRUE)...")
    
    try:
        while True:
            # Check CSV for changes
            last_row = read_csv_last_line(csv_file_path)
            
            if last_row:
                ciclo_activo = is_boolean_true(last_row.get('CicloActivo', ''))
                nombre_ciclo = last_row.get('NombreCiclo', '').strip() or 'UNKNOWN'
                id_ec = last_row.get('ID_EC', '').strip() or 'UNKNOWN'
                id_control = last_row.get('ID_Control', '').strip() or ''
                
                # Detect state change: FALSE -> TRUE (start recording)
                if ciclo_activo and not last_ciclo_activo:
                    print(f"\n>>> Inspection cycle STARTED")
                    print(f"    NombreCiclo: {nombre_ciclo}, ID_EC: {id_ec}")
                    
                    # Generate filename with inspection info
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"inspection_{nombre_ciclo}_{id_ec}_{timestamp}.mov"
                    output_file = output_dir / filename
                    
                    print(f"    Starting recording: {output_file.name}")
                    
                    is_recording = True
                    recording_start_time = time.time()
                    current_inspection_info = {
                        'nombre_ciclo': nombre_ciclo,
                        'id_ec': id_ec,
                        'start_time': recording_start_time,
                        'output_file': output_file
                    }
                    video_writer = None  # Will be initialized on first frame
                
                # Detect state change: TRUE -> FALSE (stop recording)
                elif not ciclo_activo and last_ciclo_activo:
                    print(f"\n>>> Inspection cycle ENDED")
                    if current_inspection_info:
                        print(f"    NombreCiclo: {current_inspection_info['nombre_ciclo']}, ID_EC: {current_inspection_info['id_ec']}")
                    
                    is_recording = False
                    
                    # Stop recording
                    if video_writer is not None:
                        video_writer.release()
                        video_writer = None
                        
                        if current_inspection_info:
                            output_file = current_inspection_info['output_file']
                            if output_file.exists():
                                file_size = output_file.stat().st_size / (1024 * 1024)  # Size in MB
                                duration = time.time() - current_inspection_info['start_time']
                                print(f"    Video saved: {output_file.name}")
                                print(f"    Duration: {duration:.1f}s, Size: {file_size:.2f} MB")
                    
                    current_inspection_info = None
                    print("    Waiting for next inspection cycle...")
                
                last_ciclo_activo = ciclo_activo
            
            # Record frame if recording
            if is_recording:
                last_time = time.time()
                
                # Get screen capture
                img = np.array(sct.grab(monitor))
                img_bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
                
                # Initialize video writer on first frame
                if video_writer is None:
                    frame_height, frame_width = img_bgr.shape[:2]
                    output_file = current_inspection_info['output_file']
                    
                    # Try codecs
                    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
                    video_writer = cv2.VideoWriter(
                        str(output_file),
                        fourcc,
                        fps,
                        (frame_width, frame_height)
                    )
                    
                    if not video_writer.isOpened():
                        # Try alternative codec
                        fourcc = cv2.VideoWriter_fourcc(*'avc1')
                        video_writer = cv2.VideoWriter(
                            str(output_file),
                            fourcc,
                            fps,
                            (frame_width, frame_height)
                        )
                    
                    if not video_writer.isOpened():
                        print(f"ERROR: Could not initialize video writer")
                        is_recording = False
                        video_writer = None
                    else:
                        print(f"    Video writer initialized: {frame_width}x{frame_height} @ {fps} FPS")
                
                # Write frame
                if video_writer is not None:
                    video_writer.write(img_bgr)
                
                # Sleep to maintain FPS
                sleep_time = frame_time - (time.time() - last_time)
                if sleep_time > 0:
                    time.sleep(sleep_time)
            else:
                # Not recording, sleep for check interval
                time.sleep(check_interval)
    
    except KeyboardInterrupt:
        print("\n\nStopping monitor...")
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Clean up if still recording
        if video_writer is not None:
            video_writer.release()
            if current_inspection_info:
                output_file = current_inspection_info['output_file']
                if output_file.exists():
                    file_size = output_file.stat().st_size / (1024 * 1024)
                    print(f"\nFinal video saved: {output_file.name} ({file_size:.2f} MB)")
        
        sct.close()
        print("Monitor stopped.")


if __name__ == "__main__":
    # Monitor CSV and record during inspections
    monitor_and_record_inspections(fps=15, check_interval=1.0)