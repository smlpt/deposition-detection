from collections import deque
from dataclasses import dataclass, field
import time
import logging

@dataclass
class HSVStats:
    h_m: float = 0.0
    s_m: float = 0.0
    v_m: float = 0.0
    h_decay: float = 0.0
    s_decay: float = 0.0
    v_decay: float = 0.0

class HSVAnalyzer:
    
    def __init__(self):
        
        self.logger = logging.getLogger(__name__)
        
        self.hsv_history = []
        self.timestamps = []

        self.ref_stats = None
        self.is_paused = False
        
    def set_reference(self, hsv_stats):
        """Set new reference values and clear history"""
        
        self.logger.info("Set new reference frame.")
        
        self.ref_stats = hsv_stats
        self.clear_history()
    
    def clear_history(self):
        """Clear all historical data"""
        
        self.hsv_history.clear()
        
    def update(self, hsv_stats, alpha):
        """Update with new stats relative to reference frame"""
        
        if self.is_paused:
            return
            
        if self.ref_stats is None:
            self.ref_stats = hsv_stats
        
        relative_stats = HSVStats(
            h_m=hsv_stats['h_m'] - self.ref_stats['h_m'],
            s_m=hsv_stats['s_m'] - self.ref_stats['s_m'],
            v_m=hsv_stats['v_m'] - self.ref_stats['v_m'],
            # Append the actual value on the first frame, otherwise calculate an exponentially decaying average
            h_decay=alpha * (hsv_stats['h_m'] - self.ref_stats['h_m']) + (1 - alpha) * (self.hsv_history[-1].h_decay if self.hsv_history else hsv_stats['h_m'] - self.ref_stats['h_m']),
            s_decay=alpha * (hsv_stats['s_m'] - self.ref_stats['s_m']) + (1 - alpha) * (self.hsv_history[-1].s_decay if self.hsv_history else hsv_stats['s_m'] - self.ref_stats['s_m']),
            v_decay=alpha * (hsv_stats['v_m'] - self.ref_stats['v_m']) + (1 - alpha) * (self.hsv_history[-1].v_decay if self.hsv_history else hsv_stats['v_m'] - self.ref_stats['v_m'])
        )
        
        self.hsv_history.append(relative_stats)
        self.timestamps.append(time.time())
    
    def toggle_pause(self):
        self.is_paused = not self.is_paused
        return "Resume Analysis" if self.is_paused else "Pause Analysis"
        
    def get_history(self):
        return {
            'timestamps': list(self.timestamps),
            'h_means': [stats.h_m for stats in self.hsv_history],
            's_means': [stats.s_m for stats in self.hsv_history],
            'v_means': [stats.v_m for stats in self.hsv_history],
            'h_decay': [stats.h_decay for stats in self.hsv_history],
            's_decay': [stats.s_decay for stats in self.hsv_history],
            'v_decay': [stats.v_decay for stats in self.hsv_history]
        }
