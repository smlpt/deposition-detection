import cv2
import numpy as np
import skimage as sk

class ImageProcessor:

    def __init__(self):
        self.prev_ellipse = None
        self.prev_mask = None
        self.alpha = 0.6 # Smoothing factor for the ellipse mask
        self.ellipse_margin = 0.1
    
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
    
    def blend_ellipses(self, current_ellipse, prev_ellipse):
        """Blend ellipse parameters using exponential smoothing"""
        if prev_ellipse is None:
            return current_ellipse
            
        # Unpack ellipse parameters ((x,y), (width,height), angle)
        center_current = np.array(current_ellipse[0])
        size_current = np.array(current_ellipse[1])
        angle_current = current_ellipse[2]
        
        center_prev = np.array(prev_ellipse[0])
        size_prev = np.array(prev_ellipse[1])
        angle_prev = prev_ellipse[2]
        
        # Handle angle wraparound (e.g., 179° -> -179°)
        if abs(angle_current - angle_prev) > 90:
            if angle_current > angle_prev:
                angle_prev += 180
            else:
                angle_current += 180
                
        # Blend parameters
        center_smooth = self.alpha * center_prev + (1 - self.alpha) * center_current
        size_smooth = self.alpha * size_prev + (1 - self.alpha) * size_current
        angle_smooth = self.alpha * angle_prev + (1 - self.alpha) * angle_current
        
        # Normalize angle back to [0, 180)
        angle_smooth = angle_smooth % 180
        
        return (tuple(center_smooth), tuple(size_smooth), angle_smooth)

    def mask_ellipse_contour(self, frame):
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
            if contour_length < 0.4 * w or contour_length > 3 * w:
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
            distance_from_center = np.sqrt((ellipse[0][0] - frame_center[0])**2 +
                                           (ellipse[0][1] - frame_center[1])**2)
            center_weight = 1 - (distance_from_center /
                                 (0.5 * np.sqrt(frame.shape[1]**2 + frame.shape[0]**2)))
            
            # Score the ellipse based on size and aspect ratio
            # Prefer larger ellipses with aspect ratio closer to 1
            base_score = contour_length * (1 - abs(1 - aspect_ratio)) * center_weight

            # Additional temporal consistency scoring
            temporal_score = 1.0
            if self.prev_ellipse is not None:
                # Distance to previous ellipse center
                prev_dist = np.sqrt((ellipse[0][0] - self.prev_ellipse[0][0])**2 + 
                                  (ellipse[0][1] - self.prev_ellipse[0][1])**2)
                dist_weight = np.exp(-prev_dist / (0.2 * w))  # Exponential falloff
                
                # Size similarity
                size_ratio = (ellipse[1][0] * ellipse[1][1]) / (self.prev_ellipse[1][0] * self.prev_ellipse[1][1])
                size_weight = np.exp(-abs(1 - size_ratio))
                
                temporal_score = 0.5 * (dist_weight + size_weight)
            
            score = base_score * (1 + temporal_score)

            if score > best_score:
                best_score = score
                best_ellipse = ellipse
        
        if best_ellipse is None:
            if self.prev_ellipse is not None:
                return self.prev_mask, self.prev_ellipse, self.prev_ellipse, 0
            return None, None, None, None
            

        # Blend the current ellipse with the previous one
        smoothed_ellipse = self.blend_ellipses(best_ellipse, self.prev_ellipse)
        # Creates a smaller ellipse to make masking more robust
        inner_ellipse = (smoothed_ellipse[0], 
                            ((1 - self.ellipse_margin) * smoothed_ellipse[1][0],
                             (1 - self.ellipse_margin) * smoothed_ellipse[1][1]), 
                            smoothed_ellipse[2])
        # Create the mask
        mask = np.zeros(frame.shape[:2], dtype=np.uint8)
        cv2.ellipse(mask, inner_ellipse, 255, -1)

        self.prev_ellipse = smoothed_ellipse
        self.prev_mask = mask.copy()

        return mask, smoothed_ellipse, inner_ellipse, best_score