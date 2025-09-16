
# TODO This is only needed if using a logitech webcam
import os
import subprocess
os.environ["OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS"] = "0"

import cv2
from threading import Thread, Lock
import time
import logging
import warnings

class PiCamera:
    def __init__(self, device_index=0):
        self.device_index = device_index
        self.stream = None
        self.lock = Lock()
        self.frame = None
        self._stopped = False
        self.device_path = f"/dev/video{device_index}"
        self.exposure_index = 1
        # This range of exposures is suitable for a Logitech C920 webcam
        self.exposures = [5, 10, 20, 39, 78, 156, 312, 625, 1250, 2047]
        self.wb = 4000
        self.logger = logging.getLogger(__name__)
        self.is_recording = False
        self.video_writer = None
        self.is_stream_video = False
        self.video_reader: cv2.VideoCapture = None
        self.video_frame_count = -1
        self.current_frame_idx = 0
        self.pause_callback = None
    
    def apply_settings(self):
        """Apply stored exposure and white balance to camera"""
        self.logger.debug("Applying camera settings: exposure=%d, white_balance=%d", self.exposure_index, self.wb)
        subprocess.run(['v4l2-ctl', '-d', self.device_path, '-c', 'auto_exposure=1'])
        subprocess.run(['v4l2-ctl', '-d', self.device_path, '-c', 'exposure_dynamic_framerate=0'])
        subprocess.run(['v4l2-ctl', '-d', self.device_path, '-c', 'gain=0'])
        subprocess.run(['v4l2-ctl', '-d', self.device_path, '-c', f'exposure_time_absolute={self.exposures[self.exposure_index]}'])
        subprocess.run(['v4l2-ctl', '-d', self.device_path, '-c', 'white_balance_automatic=0'])
        subprocess.run(['v4l2-ctl', '-d', self.device_path, '-c', f'white_balance_temperature={self.wb}'])
        
    def enable_auto_settings(self):
        """Enable automatic camera adjustments"""
        subprocess.run(['v4l2-ctl', '-d', self.device_path, '-c', 'auto_exposure=3'])
        subprocess.run(['v4l2-ctl', '-d', self.device_path, '-c', 'white_balance_automatic=1'])
        subprocess.run(['v4l2-ctl', '-d', self.device_path, '-c', 'exposure_dynamic_framerate=1'])
        
    def list_cameras(self):
        """List all available camera devices"""
        self.logger.info("Creating a list of available camera devices...")
        self.logger.info("(The following OpenCV warnings can safely be ignored)")
        camera_list = []
        for i in range(10):  # Check first 10 indexes
            self.logger.debug(f"trying out cam {i}")
            
            cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
            if cap.isOpened():
                ret, cam = cap.read()
                if ret is not None and cam is not None:
                    camera_list.append({"index": i, "name": f"Camera {i}"})
                cap.release()
        return camera_list
        
    def start(self):
        """Start capture from specified device"""
        self._stopped = False
        self.stream = cv2.VideoCapture(self.device_index)
        if not self.stream.isOpened():
            raise RuntimeError(f"Failed to open camera at index {self.device_index}")
        
        Thread(target=self._capture_loop, daemon=True).start()
        self.logger.info(f"Started camera thread for device {self.device_index}")

    def switch_camera(self, new_index):
        """Switch to a different camera device"""
        self.stop()
        self.device_index = new_index
        self.device_path = f"/dev/video{new_index}"
        self.stored_settings = None  # Reset stored settings
        self.start()    
    
    def _capture_loop(self):
        while not self._stopped:
            # Take the frame either from camera or from a video file
            ret, frame = self.video_reader.read() if self.is_stream_video else self.stream.read()
            if ret:
                with self.lock:
                    self.frame = frame
                    if self.is_stream_video:
                        self.current_frame_idx += 1
                    if self.video_frame_count == self.current_frame_idx and self.pause_callback is not None:
                        self.pause_callback()
                # Record frames to file is the flag is set
                if getattr(self, 'is_recording', False):
                    self.video_writer.write(frame)
            time.sleep(0.03)  # ~30 FPS
            
    def get_frame(self):
        with self.lock:
            return self.frame.copy() if self.frame is not None else None
            
    def stop(self):
        self.logger.info(f"Stopped camera {self.device_index}")
        self._stopped = True
        if self.stream is not None:
            self.stream.release()
            self.stream = None

    def start_recording(self, filename):
        # Ensure the recordings directory exists
        recordings_dir = os.path.join(os.getcwd(), "recordings")
        os.makedirs(recordings_dir, exist_ok=True)
        filepath = os.path.join(recordings_dir, filename)

        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        self.video_writer = cv2.VideoWriter(filepath, fourcc, 20.0, (self.frame.shape[1], self.frame.shape[0]), isColor=True)
        if not self.video_writer.isOpened():
            self.logger.error(f"Failed to open VideoWriter for {filepath}")
            return False
        self.is_recording = True
        self.logger.info(f"Started recording to {filepath}")
        return True

    def stop_recording(self):
        if hasattr(self, 'video_writer') and self.video_writer is not None:
            self.video_writer.release()
            self.is_recording = False
            self.logger.info("Stopped recording.")
            
    def reset_video_reader(self):
        self.is_stream_video = False
        self.video_reader.release()
        self.video_reader = None
        self.current_frame_idx = 0