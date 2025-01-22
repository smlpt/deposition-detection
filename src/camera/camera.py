
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
        self.stored_settings = None
        
        self.logger = logging.getLogger(__name__)

    def get_current_settings(self):
        """Get current camera settings"""
        result = subprocess.run(
            ['v4l2-ctl', '-d', self.device_path, '--get-ctrl=exposure_absolute,white_balance_temperature'],
            capture_output=True, text=True
        )
        
        settings = {}
        for line in result.stdout.splitlines():
            name, value = line.split(":")
            settings[name.strip()] = int(value.strip())
            
        return settings
    
    def apply_settings(self, settings):
        """Apply stored settings to camera"""
        subprocess.run(['v4l2-ctl', '-d', self.device_path, '-c', 'exposure_auto=1'])
        subprocess.run(['v4l2-ctl', '-d', self.device_path, '-c', 
                       f'exposure_absolute={settings["exposure_absolute"]}'])
        
        subprocess.run(['v4l2-ctl', '-d', self.device_path, '-c', 'white_balance_temperature_auto=0'])
        subprocess.run(['v4l2-ctl', '-d', self.device_path, '-c', 
                       f'white_balance_temperature={settings["white_balance_temperature"]}'])
        
    def enable_auto_settings(self):
        """Enable automatic camera adjustments"""
        subprocess.run(['v4l2-ctl', '-d', self.device_path, '-c', 'exposure_auto=3'])
        subprocess.run(['v4l2-ctl', '-d', self.device_path, '-c', 'white_balance_temperature_auto=1'])
        
    def freeze_current_settings(self, frames_to_wait=5):
        """Wait for auto settings to settle and then freeze them"""
        self.enable_auto_settings()
        
        # Wait for specified number of frames
        for _ in range(frames_to_wait):
            with self.lock:
                if self.frame is None:
                    raise RuntimeError("No frames available")
            time.sleep(0.1)
        
        # Capture and store the current settings
        self.stored_settings = self.get_current_settings()
        
        # Apply these settings manually
        self.apply_settings(self.stored_settings)
        
        self.logger.info(f"Camera settings frozen at: {self.stored_settings}")
        return self.stored_settings
        
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
        
        # Start with auto settings enabled
        self.enable_auto_settings()

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
            ret, frame = self.stream.read()
            if ret:
                with self.lock:
                    self.frame = frame
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