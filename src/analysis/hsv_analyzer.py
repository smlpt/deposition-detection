from collections import deque
from dataclasses import dataclass, field
import datetime
import logging

from camera.processor import ImageProcessor

@dataclass
class HSVStats:
    h_m: float = 0.0 # Raw values
    s_m: float = 0.0
    v_m: float = 0.0
    h_decay: float = 0.0 # Smooth values
    s_decay: float = 0.0
    v_decay: float = 0.0
    dh: float = 0.0  # First derivatives
    ds: float = 0.0
    dv: float = 0.0
    ddh: float = 0.0  # Second derivatives
    dds: float = 0.0
    ddv: float = 0.0

class HSVAnalyzer:
    
    def __init__(self, processor: ImageProcessor):
        
        self.logger = logging.getLogger(__name__)
        
        self.hsv_history = []
        self.timestamps = []

        self.ref_stats = None
        """Reference values for the first frame"""

        self.is_paused = False
        
        self.current_mask = None
        self.current_ellipse = None
        self.ellipse_score = None
        self.is_ellipse_enabled = True
        self.is_mask_frozen = False

        self.processor = processor
        
    def set_reference(self, frame):
        """Set new reference values from a frame and clear history"""
        self.logger.info("Setting new reference frame.")
        
        # Convert to HSV
        hsv_frame = self.processor.to_hsv(frame)
        
        if self.is_ellipse_enabled:
            # Find ellipse and create mask only if  we didn't freeze the existing one
            if not self.is_mask_frozen:
                self.current_mask, self.current_ellipse, self.ellipse_score = self.processor.mask_ellipse_contour(frame)
        else:
            self.current_mask = None
            self.current_ellipse = None
        
        # Calculate stats using the mask
        self.ref_stats = self.processor.get_hsv_stats(hsv_frame, self.current_mask)
        self.clear_history()
        
        if self.current_ellipse is not None:
            self.logger.info(f"Found reference ellipse at {self.current_ellipse[0]} with size {self.current_ellipse[1]}")
        
    def clear_history(self):
        """Clear all historical data"""
        
        self.hsv_history.clear()
        
    def update(self, frame, alpha):
        """Update with new frame relative to reference frame"""
        if self.is_paused:
            return
            
        # Convert to HSV
        hsv_frame = self.processor.to_hsv(frame)
        
        if self.is_ellipse_enabled and not self.is_mask_frozen:
            # Update mask
            self.current_mask, self.current_ellipse, self.ellipse_score = self.processor.mask_ellipse_contour(frame)
        
        # Calculate stats using the mask
        hsv_stats = self.processor.get_hsv_stats(hsv_frame, self.current_mask)
        
        if self.ref_stats is None:
            self.ref_stats = hsv_stats

        # Calculate new decay values
        h_decay = alpha * (hsv_stats['h_m'] - self.ref_stats['h_m']) + (1 - alpha) * (self.hsv_history[-1].h_decay if self.hsv_history else hsv_stats['h_m'] - self.ref_stats['h_m'])
        s_decay = alpha * (hsv_stats['s_m'] - self.ref_stats['s_m']) + (1 - alpha) * (self.hsv_history[-1].s_decay if self.hsv_history else hsv_stats['s_m'] - self.ref_stats['s_m'])
        v_decay = alpha * (hsv_stats['v_m'] - self.ref_stats['v_m']) + (1 - alpha) * (self.hsv_history[-1].v_decay if self.hsv_history else hsv_stats['v_m'] - self.ref_stats['v_m'])
        
        # Calculate derivatives
        if self.hsv_history:
            prev = self.hsv_history[-1]
            dh = h_decay - prev.h_decay
            ds = s_decay - prev.s_decay
            dv = v_decay - prev.v_decay
            ddh = dh - prev.dh if prev.dh != 0.0 else 0.0
            dds = ds - prev.ds if prev.ds != 0.0 else 0.0
            ddv = dv - prev.dv if prev.dv != 0.0 else 0.0
        else:
            dh = ds = dv = ddh = dds = ddv = 0.0

        relative_stats = HSVStats(
            h_m=hsv_stats['h_m'] - self.ref_stats['h_m'],
            s_m=hsv_stats['s_m'] - self.ref_stats['s_m'],
            v_m=hsv_stats['v_m'] - self.ref_stats['v_m'],
            h_decay=h_decay,
            s_decay=s_decay,
            v_decay=v_decay,
            dh=dh,
            ds=ds,
            dv=dv,
            ddh=ddh,
            dds=dds,
            ddv=ddv
        )
        
        self.hsv_history.append(relative_stats)
        self.timestamps.append(datetime.datetime.now().strftime('%H:%M:%S.%f'))
    
    def toggle_pause(self):
        self.is_paused = not self.is_paused
        return "Resume Analysis" if self.is_paused else "Pause Analysis"
    
    def freeze_mask(self):
        self.is_mask_frozen = not self.is_mask_frozen
        return "Unfreeze Mask" if self.is_mask_frozen else "Freeze Mask"
    
    def set_ellipse_masking(self, value):
        self.logger.info(f"Ellipse fitting was {'enabled' if value else 'disabled'}.")
        self.is_ellipse_enabled = value
        if not value:
            self.current_ellipse = None
            self.current_mask = None
            
    def get_history(self):
        return {
            'timestamps': list(self.timestamps),
            'h_means': [stats.h_m for stats in self.hsv_history],
            's_means': [stats.s_m for stats in self.hsv_history],
            'v_means': [stats.v_m for stats in self.hsv_history],
            'h_decay': [stats.h_decay for stats in self.hsv_history],
            's_decay': [stats.s_decay for stats in self.hsv_history],
            'v_decay': [stats.v_decay for stats in self.hsv_history],
            'dH': [stats.dh for stats in self.hsv_history],
            'dS': [stats.ds for stats in self.hsv_history],
            'dV': [stats.dv for stats in self.hsv_history],
            'ddH': [stats.ddh for stats in self.hsv_history],
            'ddS': [stats.dds for stats in self.hsv_history],
            'ddV': [stats.ddv for stats in self.hsv_history]
        }
