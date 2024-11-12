import cv2
import numpy as np

class ImageProcessor:
    @staticmethod
    def to_hsv(frame):
        return cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    
    @staticmethod
    def get_hsv_stats(hsv_frame):
        h, s, v = cv2.split(hsv_frame)
        return {
            'h_mean': np.mean(h),
            'h_std': np.std(h),
            's_mean': np.mean(s),
            's_std': np.std(s),
            'v_mean': np.mean(v),
            'v_std': np.std(v)
        }
