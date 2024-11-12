import gradio as gr
import plotly.graph_objects as go
from threading import Lock
import logging
import time
from threading import Lock, Event, Thread

class WebServer:
    def __init__(self, camera, analyzer):
        self.camera = camera
        self.analyzer = analyzer
        self.lock = Lock()
        self.update_event = Event()
        self.should_stop = False
        self.logger = logging.getLogger(__name__)
        
    def create_plots(self):
        with self.lock:
            history = self.analyzer.get_history()
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(y=history['h_means'], name='Hue'))
        fig.add_trace(go.Scatter(y=history['s_means'], name='Saturation'))
        fig.add_trace(go.Scatter(y=history['v_means'], name='Value'))
        
        return fig
        
    def show_frame(self):
            frame = self.camera.get_frame()
            if frame is not None:
                return frame
            else:
                return None
            
    def launch(self):
        self.logger.info("Launching webserver...")
        with gr.Blocks() as demo:
            with gr.Row():
                gr.Plot(self.create_plots, every=1)
            with gr.Row():
                frame = gr.Image(self.show_frame)
            
        self.should_stop = True
        demo.launch(server_name='localhost', show_api=False)