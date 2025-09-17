from collections import deque
from dataclasses import dataclass, field
import datetime, time
import logging
import numpy as np
from .profile_manager import ThresholdProfile

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
        self.inner_ellipse = None
        self.ellipse_score = None
        self.is_ellipse_enabled = True
        self.is_mask_frozen = False
        self.decay_alpha = 0.05

        self.current_smoothed_stats: HSVStats

        self.processor = processor

        self.current_profile: ThresholdProfile = None
        self.is_threshold_exceeded = False

        self.last_threshold_check = time.time()
        
        # Derivative smoothing parameters
        self.derivative_smoothing = False
        self.smoothing_window_size = 5  # Default window size for smoothing
        
    def set_derivative_smoothing(self, enable: bool, window_size: int = 5):
        """Enable/disable derivative smoothing and set window size"""
        self.derivative_smoothing = enable
        self.smoothing_window_size = window_size
        self.logger.debug(f"Derivative smoothing {'enabled' if enable else 'disabled'} with window size {window_size}")

    def set_profile(self, profile: ThresholdProfile):
        """Set active threshold profile"""
        self.current_profile = profile
        self.logger.info(f"Set threshold profile: {profile.name}")

    def check_thresholds(self, stats: HSVStats) -> bool:
        """Check if current values exceed all thresholds in active profile"""
        if not self.current_profile:
            return False
            
        threshold_checks = [
            (self.current_profile.h_decay, stats.h_decay),
            (self.current_profile.s_decay, stats.s_decay),
            (self.current_profile.v_decay, stats.v_decay),
            (self.current_profile.dh, stats.dh),
            (self.current_profile.ds, stats.ds),
            (self.current_profile.dv, stats.dv),
            (self.current_profile.ddh, stats.ddh),
            (self.current_profile.dds, stats.dds),
            (self.current_profile.ddv, stats.ddv)
        ]
    
        # Only check thresholds that are not None
        active_conditions = []
        for threshold, value in threshold_checks:
            if threshold is not None:
                if threshold >= 0:
                    # Positive threshold: trigger when value >= threshold
                    active_conditions.append(value >= threshold)
                else:
                    # Negative threshold: trigger when value <= threshold
                    active_conditions.append(value <= threshold)
        
        # If no thresholds are set, return False
        if not active_conditions:
            return False
        
        return all(active_conditions)
        
    def set_reference(self, frame):
        """Set new reference values from a frame and clear history"""
        self.logger.info("Setting new reference frame.")
        
        # Convert to HSV
        hsv_frame = self.processor.to_hsv(frame)
        
        if self.is_ellipse_enabled:
            # Find ellipse and create mask only if  we didn't freeze the existing one
            if not self.is_mask_frozen:
                self.current_mask, self.current_ellipse, self.inner_ellipse, self.ellipse_score = self.processor.mask_ellipse_contour(frame)
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
        
    def update(self, frame):
        """Update with new frame relative to reference frame"""
        if self.is_paused:
            return
            
        # Convert to HSV
        hsv_frame = self.processor.to_hsv(frame)
        
        if self.is_ellipse_enabled and not self.is_mask_frozen:
            # Update mask
            self.current_mask, self.current_ellipse, self.inner_ellipse, self.ellipse_score = self.processor.mask_ellipse_contour(frame)
        
        # Calculate stats using the mask
        hsv_stats = self.processor.get_hsv_stats(hsv_frame, self.current_mask)
        
        if self.ref_stats is None:
            self.ref_stats = hsv_stats

        # Calculate new decay values
        h_decay = self.decay_alpha * (hsv_stats['h_m'] - self.ref_stats['h_m']) + (1 - self.decay_alpha) * (self.hsv_history[-1].h_decay if self.hsv_history else hsv_stats['h_m'] - self.ref_stats['h_m'])
        s_decay = self.decay_alpha * (hsv_stats['s_m'] - self.ref_stats['s_m']) + (1 - self.decay_alpha) * (self.hsv_history[-1].s_decay if self.hsv_history else hsv_stats['s_m'] - self.ref_stats['s_m'])
        v_decay = self.decay_alpha * (hsv_stats['v_m'] - self.ref_stats['v_m']) + (1 - self.decay_alpha) * (self.hsv_history[-1].v_decay if self.hsv_history else hsv_stats['v_m'] - self.ref_stats['v_m'])
        
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
    
    def toggle_pause(self, state: bool = None):
        """Toggles between paused and resumed states.
        Args:
            state (bool): Optional parameter that can be used to overwrite the toggle with a fixed state."""
        if state is not None:
            self.is_paused = state
        else:
            self.is_paused = not self.is_paused
        return "Resume" if self.is_paused else "Pause"
    
    def freeze_mask(self):
        self.is_mask_frozen = not self.is_mask_frozen
        return "Unfreeze Mask" if self.is_mask_frozen else "Freeze Mask"
    
    def set_ellipse_masking(self, value):
        self.logger.info(f"Ellipse fitting was {'enabled' if value else 'disabled'}.")
        self.is_ellipse_enabled = value
        if not value:
            self.current_ellipse = None
            self.current_mask = None
            
    def _apply_sliding_window_smoothing(self, data, window_size):
        """Apply sliding window smoothing to data using NumPy"""
        if len(data) < window_size:
            return data
        
        # Convert to numpy array
        data_array = np.array(data)
        
        # Create uniform filter kernel
        kernel = np.ones(window_size) / window_size
        
        # Apply convolution with padding
        padded_data = np.pad(data_array, window_size//2, mode='edge')
        smoothed = np.convolve(padded_data, kernel, mode='valid')
    
        return smoothed.tolist()
    
    def get_history(self):
        """Return history with derivative smoothing pipeline applied in post-processing"""
        history = {
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
        
        if self.derivative_smoothing and len(self.hsv_history) > 0:
            # Convert to numpy arrays for efficient processing
            h_decay_array = np.array(history['h_decay'])
            s_decay_array = np.array(history['s_decay'])
            v_decay_array = np.array(history['v_decay'])
            
            # Apply smoothing to decay values first
            smoothed_h_decay = self._apply_sliding_window_smoothing(h_decay_array, self.smoothing_window_size)
            smoothed_s_decay = self._apply_sliding_window_smoothing(s_decay_array, self.smoothing_window_size)
            smoothed_v_decay = self._apply_sliding_window_smoothing(v_decay_array, self.smoothing_window_size)
            
            # Calculate first derivatives from smoothed decay values
            # We need to handle the case where we have less than 2 elements
            if len(smoothed_h_decay) >= 2:
                dH_smoothed = np.diff(smoothed_h_decay, prepend=smoothed_h_decay[0])
                dS_smoothed = np.diff(smoothed_s_decay, prepend=smoothed_s_decay[0])
                dV_smoothed = np.diff(smoothed_v_decay, prepend=smoothed_v_decay[0])
            else:
                dH_smoothed = [0.0] * len(smoothed_h_decay)
                dS_smoothed = [0.0] * len(smoothed_s_decay)
                dV_smoothed = [0.0] * len(smoothed_v_decay)
            
            # Apply smoothing to first derivatives
            if len(dH_smoothed) > 0:
                smoothed_dH = self._apply_sliding_window_smoothing(dH_smoothed, self.smoothing_window_size*2)
                smoothed_dS = self._apply_sliding_window_smoothing(dS_smoothed, self.smoothing_window_size*2)
                smoothed_dV = self._apply_sliding_window_smoothing(dV_smoothed, self.smoothing_window_size*2)
            else:
                smoothed_dH = dH_smoothed
                smoothed_dS = dS_smoothed
                smoothed_dV = dV_smoothed
            
            # Calculate second derivatives from smoothed first derivatives
            if len(smoothed_dH) >= 2:
                ddH_smoothed = np.diff(smoothed_dH, prepend=smoothed_dH[0])
                ddS_smoothed = np.diff(smoothed_dS, prepend=smoothed_dS[0])
                ddV_smoothed = np.diff(smoothed_dV, prepend=smoothed_dV[0])
            else:
                ddH_smoothed = [0.0] * len(smoothed_dH)
                ddS_smoothed = [0.0] * len(smoothed_dS)
                ddV_smoothed = [0.0] * len(smoothed_dV)
            
            # Apply smoothing to second derivatives
            if len(ddH_smoothed) > 0:
                final_ddH = self._apply_sliding_window_smoothing(ddH_smoothed, self.smoothing_window_size*4)
                final_ddS = self._apply_sliding_window_smoothing(ddS_smoothed, self.smoothing_window_size*4)
                final_ddV = self._apply_sliding_window_smoothing(ddV_smoothed, self.smoothing_window_size*4)
            else:
                final_ddH = ddH_smoothed
                final_ddS = ddS_smoothed
                final_ddV = ddV_smoothed
            
            # Update the history with smoothed values
            history['h_decay'] = smoothed_h_decay
            history['s_decay'] = smoothed_s_decay
            history['v_decay'] = smoothed_v_decay
            history['dH'] = smoothed_dH
            history['dS'] = smoothed_dS
            history['dV'] = smoothed_dV
            history['ddH'] = final_ddH
            history['ddS'] = final_ddS
            history['ddV'] = final_ddV

        # Update current smoothed stats with the last entry
        if self.hsv_history:
            # Create HSVStats object from the last smoothed values
            self.current_smoothed_stats = HSVStats(
                h_m=history['h_means'][-1] if history['h_means'] else 0.0,
                s_m=history['s_means'][-1] if history['s_means'] else 0.0,
                v_m=history['v_means'][-1] if history['v_means'] else 0.0,
                h_decay=history['h_decay'][-1] if history['h_decay'] else 0.0,
                s_decay=history['s_decay'][-1] if history['s_decay'] else 0.0,
                v_decay=history['v_decay'][-1] if history['v_decay'] else 0.0,
                dh=history['dH'][-1] if history['dH'] else 0.0,
                ds=history['dS'][-1] if history['dS'] else 0.0,
                dv=history['dV'][-1] if history['dV'] else 0.0,
                ddh=history['ddH'][-1] if history['ddH'] else 0.0,
                dds=history['ddS'][-1] if history['ddS'] else 0.0,
                ddv=history['ddV'][-1] if history['ddV'] else 0.0
            )
            
            # Check thresholds using the smoothed values
            self.is_threshold_exceeded = self.check_thresholds(self.current_smoothed_stats)
        
        return history
    
    def log_timestamp(self):
        """Log the current timestamp"""
        current_time = datetime.datetime.now().strftime('%H:%M:%S.%f')
        if hasattr(self, 'current_smoothed_stats'):
            self.logger.info(
                f"time: {current_time}, "
                f", H (smooth): {self.current_smoothed_stats.h_decay}, "
                f"S (smooth): {self.current_smoothed_stats.s_decay}, "
                f"V (smooth): {self.current_smoothed_stats.v_decay}, "
                f"dH: {self.current_smoothed_stats.dh}, "
                f"dS: {self.current_smoothed_stats.ds}, "
                f"dV: {self.current_smoothed_stats.dv}, "
                f"ddH: {self.current_smoothed_stats.ddh}, "
                f"ddS: {self.current_smoothed_stats.dds}, "
                f"ddV: {self.current_smoothed_stats.ddv}")
        else:
            # Fallback to original logging if current_smoothed_stats doesn't exist
            self.logger.info(
                f"time: {current_time}, "
                f", H (smooth): {self.hsv_history[-1].h_decay if self.hsv_history else 0.0}, "
                f"S (smooth): {self.hsv_history[-1].s_decay if self.hsv_history else 0.0}, "
                f"V (smooth): {self.hsv_history[-1].v_decay if self.hsv_history else 0.0}, "
                f"dH: {self.hsv_history[-1].dh if self.hsv_history else 0.0}, "
                f"dS: {self.hsv_history[-1].ds if self.hsv_history else 0.0}, "
                f"dV: {self.hsv_history[-1].dv if self.hsv_history else 0.0}, "
                f"ddH: {self.hsv_history[-1].ddh if self.hsv_history else 0.0}, "
                f"ddS: {self.hsv_history[-1].dds if self.hsv_history else 0.0}, "
                f"ddV: {self.hsv_history[-1].ddv if self.hsv_history else 0.0}")
