from collections import deque
import time
import logging

class HSVAnalyzer:
    
    def __init__(self, history_size=100):
        
        self.logger = logging.getLogger(__name__)
        self.history_size = history_size
        self.h_means = deque(maxlen=history_size)
        self.s_means = deque(maxlen=history_size)
        self.v_means = deque(maxlen=history_size)
                
        self.h_decay = deque(maxlen=history_size)
        self.s_decay = deque(maxlen=history_size)
        self.v_decay = deque(maxlen=history_size)
        
        self.timestamps = deque(maxlen=history_size)

        self.reference_stats = None
        self.is_paused = False
        
    def set_reference(self, hsv_stats):
        """Set new reference values and clear history"""
        
        self.logger.info("Set new reference frame.")
        
        self.reference_stats = hsv_stats
        self.clear_history()
        
        
    
    def clear_history(self):
        """Clear all historical data"""
        
        for s in [self.h_means, self.s_means, self.v_means, self.h_decay, self.s_decay, self.v_decay, self.timestamps]:
            s.clear()
        
    def update(self, hsv_stats, alpha):
        """Update with new stats relative to reference frame"""
        
        if self.is_paused:
            return
            
        if self.reference_stats is None:
            self.reference_stats = hsv_stats
        
        self.h_means.append(hsv_stats['h_mean'] - self.reference_stats['h_mean'])
        self.s_means.append(hsv_stats['s_mean'] - self.reference_stats['s_mean'])
        self.v_means.append(hsv_stats['v_mean'] - self.reference_stats['v_mean'])
        self.timestamps.append(time.time())
        
        
        # Append the actual value on the first frame, otherwise calculate an exponentially decaying average
        if len(self.h_means) == 1:
            self.h_decay.append(self.h_means[-1])
            self.s_decay.append(self.s_means[-1])
            self.v_decay.append(self.v_means[-1])
        else:
            self.h_decay.append( alpha * (hsv_stats['h_mean'] - self.reference_stats['h_mean']) + (1 - alpha) * self.h_decay[-1] )
            self.s_decay.append( alpha * (hsv_stats['s_mean'] - self.reference_stats['s_mean']) + (1 - alpha) * self.s_decay[-1] )
            self.v_decay.append( alpha * (hsv_stats['v_mean'] - self.reference_stats['v_mean']) + (1 - alpha) * self.v_decay[-1] )
    
    def toggle_pause(self):
        self.is_paused = not self.is_paused
        return "Resume Analysis" if self.is_paused else "Pause Analysis"
        
    def get_history(self):
        return {
            'timestamps': list(self.timestamps),
            'h_means': list(self.h_means),
            's_means': list(self.s_means),
            'v_means': list(self.v_means),
            'h_decay': list(self.h_decay),
            's_decay': list(self.s_decay),
            'v_decay': list(self.v_decay)
        }
