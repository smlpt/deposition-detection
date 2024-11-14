import cv2
import numpy as np
import skimage as sk

class ImageProcessor:
    
    @staticmethod
    def to_hsv(frame):
        return cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    
    @staticmethod
    def get_hsv_stats(hsv_frame, mask=None):
        """Calculate HSV statistics, optionally using a mask"""
        h, s, v = cv2.split(hsv_frame)
        
        # If mask is provided, apply it to each channel
        if mask is not None:
            h = cv2.bitwise_and(h, h, mask=mask)
            s = cv2.bitwise_and(s, s, mask=mask)
            v = cv2.bitwise_and(v, v, mask=mask)
            
            # Calculate means only for non-zero mask areas
            h_mean = np.mean(h[mask > 0])
            s_mean = np.mean(s[mask > 0])
            v_mean = np.mean(v[mask > 0])
           
        else:
            h_mean = np.mean(h)
            s_mean = np.mean(s)
            v_mean = np.mean(v)
            
        return {
            'h_m': h_mean,
            's_m': s_mean,
            'v_m': v_mean,
        }

    @staticmethod
    def mask_ellipse_contour(frame):
        """Find the most prominent ellipse in the image and create a mask.
        Returns both the mask and the ellipse parameters if found, or (None, None) if no suitable ellipse is found."""
        
        # Convert to grayscale if needed
        if len(frame.shape) == 3:
            bw = sk.color.rgb2gray(frame)
        else:
            bw = frame.copy()
            
        # Normalize intensity
        p2, p98 = np.percentile(bw, (2, 98))
        bw = sk.exposure.rescale_intensity(bw, in_range=(p2, p98))
        
        # Edge detection
        edges = sk.feature.canny(bw, 3)
        binary = sk.util.img_as_ubyte(edges)
        
        # Find contours
        contours, hierarchy = cv2.findContours(binary, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)
        
        w = frame.shape[1]
        best_ellipse = None
        best_score = 0
        
        for contour in contours:
            # Skip if contour is too small or too large
            contour_length = cv2.arcLength(contour, False)
            if contour_length < 0.4 * w or contour_length > 1.5 * w:
                continue
                
            # Need at least 5 points to fit an ellipse
            if len(contour) < 5:
                continue
                
            try:
                ellipse = cv2.fitEllipse(contour)
            except cv2.error:
                continue
                
            # ellipse[1] gives a pair of major and minor axis. Skip all ellipsoids with too narrow aspect ratio
            aspect_ratio = ellipse[1][0] / ellipse[1][1]
            if aspect_ratio < 0.5:
                continue
                
            # Compute a center-weighted score
            frame_center = (frame.shape[1] // 2, frame.shape[0] // 2) # this is floor division
            distance_from_center = np.sqrt((ellipse[0][0] - frame_center[0])**2 + (ellipse[0][1] - frame_center[1])**2)
            center_weight = 1 - (distance_from_center / (0.5 * np.sqrt(frame.shape[1]**2 + frame.shape[0]**2)))
            
            # Score the ellipse based on size and aspect ratio
            # Prefer larger ellipses with aspect ratio closer to 1
            score = contour_length * (1 - abs(1 - aspect_ratio)) * center_weight
            
            if score > best_score:
                best_score = score
                best_ellipse = ellipse
        
        if best_ellipse is None:
            return None, None, None
            
        # Create the mask
        mask = np.zeros(frame.shape[:2], dtype=np.uint8)
        cv2.ellipse(mask, best_ellipse, 255, -1)
        
        return mask, best_ellipse, best_score