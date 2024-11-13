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
        self.logger = logging.getLogger(__name__)
        
    def toggle_pause(self):
        return self.analyzer.toggle_pause()
    
    def set_new_reference(self):
        frame = self.camera.get_frame()
        if frame is not None:
            hsv_frame = ImageProcessor.to_hsv(frame)
            stats = ImageProcessor.get_hsv_stats(hsv_frame)
            self.analyzer.set_reference(stats)
        
    def create_plots(self):
        with self.lock:
            history = self.analyzer.get_history()
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(y=history['h_means'], name='Measured Hue',        line=dict(color="#c8d6ae", dash="dash")))
        fig.add_trace(go.Scatter(y=history['s_means'], name='Measured Saturation', line=dict(color="#b9cdeb", dash="dash")))
        fig.add_trace(go.Scatter(y=history['v_means'], name='Measured Value',      line=dict(color="#ebb9cd", dash="dash")))
        fig.add_trace(go.Scatter(y=history['h_decay'], name="Averaged Hue",        line=dict(color="#7aaa28")))
        fig.add_trace(go.Scatter(y=history['s_decay'], name="Averaged Saturation", line=dict(color="#398dbe")))
        fig.add_trace(go.Scatter(y=history['v_decay'], name="Averaged Value",      line=dict(color="#be398d")))
        
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