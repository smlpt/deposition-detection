import os
import gradio as gr
import plotly.graph_objects as go
from threading import Lock
import logging
import time
from threading import Lock, Event, Thread
import cv2

from camera.processor import ImageProcessor

class WebServer:
    def __init__(self, camera, analyzer):
        self.camera = camera
        self.analyzer = analyzer
        self.lock = Lock()
        self.update_event = Event()
        self.should_stop = False
        self.history_window = 60 # default is a minute
        self.logger = logging.getLogger(__name__)
        
    def toggle_pause(self):
        return self.analyzer.toggle_pause()
    
    def set_new_reference(self):
        frame = self.camera.get_frame()
        if frame is not None:
            hsv_frame = ImageProcessor.to_hsv(frame)
            stats = ImageProcessor.get_hsv_stats(hsv_frame)
            self.analyzer.set_reference(stats)
            
    def update_history_window(self, new_window):
        """Update the history window size (in seconds)"""
        self.history_window = int(new_window)
        
    def create_plots(self):
        with self.lock:
            history = self.analyzer.get_history()
            
        samples_per_second = 10
        window_size = int(self.history_window * samples_per_second)
        
        def get_recent(data):
            return data[-window_size:] if len(data) > window_size else data
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(y=get_recent(history['h_means']), name='Measured H', line=dict(color="#c8d6ae", dash="dash")))
        fig.add_trace(go.Scatter(y=get_recent(history['s_means']), name='Measured S', line=dict(color="#b9cdeb", dash="dash")))
        fig.add_trace(go.Scatter(y=get_recent(history['v_means']), name='Measured V', line=dict(color="#ebb9cd", dash="dash")))
        fig.add_trace(go.Scatter(y=get_recent(history['h_decay']), name="Averaged H", line=dict(color="#7aaa28")))
        fig.add_trace(go.Scatter(y=get_recent(history['s_decay']), name="Averaged S", line=dict(color="#398dbe")))
        fig.add_trace(go.Scatter(y=get_recent(history['v_decay']), name="Averaged V", line=dict(color="#be398d")))
        
        fig.update_layout(
            title=f"HSV Values (Last {self.history_window} seconds)",
            xaxis_title="Samples",
            yaxis_title="Value"
        )
        
        return fig
        
    def show_frame(self):
            frame = self.camera.get_frame()
            if frame is not None:
                return cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            else:
                return None
            
    def shutdown(self):
        self.should_stop = True
        time.sleep(0.5) # time for threads to clean up
        os._exit(0)
            
    def launch(self):
        self.logger.info("Launching webserver...")
        self.set_new_reference()
        with gr.Blocks() as demo:
            with gr.Row():
                gr.Plot(self.create_plots, every=0.1)
            with gr.Row():
                history_size = gr.Number(20, label="History in seconds", precision=0, minimum=1, maximum=300)
                history_size.change(fn=self.update_history_window, inputs=[history_size])
            with gr.Row():
                frame = gr.Image(self.show_frame, every=0.01)
            with gr.Row():
                pause_btn = gr.Button("Pause Analysis")
                ref_btn = gr.Button("Set New Reference")
                close_btn = gr.Button("Close")
                
            pause_btn.click(self.toggle_pause, outputs=pause_btn)
            ref_btn.click(self.set_new_reference)
            close_btn.click(self.shutdown)
            
        # self.should_stop = True
        demo.launch(server_name='localhost', show_api=False)