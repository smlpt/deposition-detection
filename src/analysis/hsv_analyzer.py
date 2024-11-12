from collections import deque
import time

class HSVAnalyzer:
    def __init__(self, history_size=100):
        self.history_size = history_size
        self.h_means = deque(maxlen=history_size)
        self.s_means = deque(maxlen=history_size)
        self.v_means = deque(maxlen=history_size)
        self.timestamps = deque(maxlen=history_size)
        
    def update(self, hsv_stats):
        self.h_means.append(hsv_stats['h_mean'])
        self.s_means.append(hsv_stats['s_mean'])
        self.v_means.append(hsv_stats['v_mean'])
        self.timestamps.append(time.time())
        
    def get_history(self):
        return {
            'timestamps': list(self.timestamps),
            'h_means': list(self.h_means),
            's_means': list(self.s_means),
            'v_means': list(self.v_means)
        }
