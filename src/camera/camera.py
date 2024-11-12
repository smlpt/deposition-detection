import cv2
from threading import Thread, Lock
import time
import logging

class PiCamera:
    def __init__(self):
        self.stream = cv2.VideoCapture(0)
        self.lock = Lock()
        self.frame = None
        self._stopped = False
        
        self.logger = logging.getLogger(__name__)
        
    def start(self):
        Thread(target=self._capture_loop, daemon=True).start()
        self.logger.info("Started camera thread.")
        
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
        self.logger.info("Stopped the camera.")
        self._stopped = True
        self.stream.release()