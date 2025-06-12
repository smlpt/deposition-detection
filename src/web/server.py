import os
import gradio as gr
import plotly.graph_objects as go
from threading import Lock
import logging
import time
from threading import Lock, Event, Thread
import cv2
import numpy as np
import pandas as pd

from camera.camera import PiCamera
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
        self.cameras = None
        self.camera_names = None
        self.selected_channels = ["H (smooth)", "S (smooth)", "V (smooth)"]  # Default color channels for dropdown
        
    def toggle_pause(self):
        return self.analyzer.toggle_pause()
    
    def freeze_mask(self):
        return self.analyzer.freeze_mask()
    
    def set_new_reference(self):
    
        frame = self.camera.get_frame()
        if frame is not None:
            self.analyzer.set_reference(frame)
            
    def update_history_window(self, new_window):
        """Update the history window size (in seconds)"""
        self.history_window = int(new_window)
        
    def set_ellipse_fitting(self, value):
        self.analyzer.set_ellipse_masking(value)
        
    def switch_camera(self, device_name):
        """Handle camera switch from dropdown"""
        # Extract device index from the name (e.g., "Camera 0" -> 0)
        device_index = int(device_name.split()[-1])
        self.camera.switch_camera(device_index)
        return None  # Return None to clear the current frame while switching
    
    def find_camera_devices(self):
        # Get list of available cameras
        self.cameras = self.camera.list_cameras()
        self.camera_names = [f"Camera {cam['index']}" for cam in self.cameras]
        
    def create_plots(self):
        with self.lock:
            history = self.analyzer.get_history()
            
        samples_per_second = 10
        window_size = int(self.history_window * samples_per_second)
        
        def get_recent(data):
            return data[-window_size:] if len(data) > window_size else data
        
        fig = go.Figure()
        for choice in self.selected_channels:
            match choice:
                case "H (raw)":
                    fig.add_trace(go.Scatter(y=get_recent(history['h_means']), name='Measured H', line=dict(color="#c8d6ae", dash="dash")))
                case "S (raw)":
                    fig.add_trace(go.Scatter(y=get_recent(history['s_means']), name='Measured S', line=dict(color="#b9cdeb", dash="dash")))
                case "V (raw)":
                    fig.add_trace(go.Scatter(y=get_recent(history['v_means']), name='Measured V', line=dict(color="#ebb9cd", dash="dash")))
                case "H (smooth)":
                    fig.add_trace(go.Scatter(y=get_recent(history['h_decay']), name='Smooth H', line=dict(color="#95d02f")))
                case "S (smooth)":
                    fig.add_trace(go.Scatter(y=get_recent(history['s_decay']), name='Smooth S', line=dict(color="#43a7e1")))
                case "V (smooth)":
                    fig.add_trace(go.Scatter(y=get_recent(history['v_decay']), name='Smooth V', line=dict(color="#e443a9")))
                case "dH":
                    fig.add_trace(go.Scatter(y=get_recent(history['dH']), name='dH', line=dict(color="#729a27")))
                case "dS":
                    fig.add_trace(go.Scatter(y=get_recent(history['dS']), name='dS', line=dict(color="#2f6e9d")))
                case "dV":
                    fig.add_trace(go.Scatter(y=get_recent(history['dV']), name='dV', line=dict(color="#9c2f6c")))
                case "ddH":
                    fig.add_trace(go.Scatter(y=get_recent(history['ddH']), name='ddH', line=dict(color="#445e17")))
                case "ddS":
                    fig.add_trace(go.Scatter(y=get_recent(history['ddS']), name='ddS', line=dict(color="#1a3f66")))
                case "ddV":
                    fig.add_trace(go.Scatter(y=get_recent(history['ddV']), name='ddV', line=dict(color="#661a3f")))


        fig.update_layout(
            title=f"Relative HSV Changes (Last {self.history_window} seconds)",
            xaxis_title="Samples",
            yaxis_title="Value",
            legend=dict(yanchor="bottom", orientation="h", y=1)
        )
        
        return fig
    
    def export_csv(self):
        with self.lock:
            history = self.analyzer.get_history()
            
        if history.size == 0:
            gr.Warning("No data to export", 4)
            return
        samples_per_second = 10
        window_size = int(self.history_window * samples_per_second)
        
        def get_recent(data):
            return data[-window_size:] if len(data) > window_size else data
        
            # Get recent data
        timestamps = get_recent(history['timestamps'])
        h_means = get_recent(history['h_means'])
        s_means = get_recent(history['s_means'])
        v_means = get_recent(history['v_means'])
        h_decay = get_recent(history['h_decay'])
        s_decay = get_recent(history['s_decay'])
        v_decay = get_recent(history['v_decay'])
        d_h = get_recent(history['dH'])
        d_s = get_recent(history['dS'])
        d_v = get_recent(history['dV'])
        dd_h = get_recent(history['ddH'])
        dd_s = get_recent(history['ddS'])
        dd_v = get_recent(history['ddV'])

        try:
            import tkinter as tk
            from tkinter import filedialog
            import csv
            from datetime import datetime
            
            # Create root window and hide it
            root = tk.Tk()
            root.withdraw()
            
            # Open file dialog
            file_path = filedialog.asksaveasfilename(
                defaultextension='.csv',
                filetypes=[('CSV files', '*.csv')],
                title='Export HSV Data'
            )
            
            if file_path:
                with open(file_path, 'w', newline='') as csvfile:
                    writer = csv.writer(csvfile)
                    # Write header
                    writer.writerow(['Timestamp', 
                                'H_Measured', 'S_Measured', 'V_Measured',
                                'H_Averaged', 'S_Averaged', 'V_Averaged',
                                "dH", "dS", "dV",
                                "ddH", "ddS", "ddV"])
                    
                    # Write data rows
                    for i in range(len(h_means)):
                        writer.writerow([timestamps[i],
                                    h_means[i], s_means[i], v_means[i],
                                    h_decay[i], s_decay[i], v_decay[i],
                                    d_h[i], d_s[i], d_v[i],
                                    dd_h[i], dd_s[i], dd_v[i]])  
                        
                gr.Info(f"Exported CSV to {file_path}", 4)
                
        except Exception as e:
            print(f"Error exporting CSV: {str(e)}")
            gr.Warning("Error exporting CSV", 4)
        
    def show_frame(self):
        frame = self.camera.get_frame()
        if frame is not None:
            if self.analyzer.current_ellipse is not None:
                # Draw the ellipse on the frame
                cv2.ellipse(frame, self.analyzer.current_ellipse, (0, 255, 0), 2)
                cv2.ellipse(frame, self.analyzer.inner_ellipse, (50, 255, 50), 1)
                # Add the score to the frame
                try:
                    text = f"Ellipse Score: {self.analyzer.ellipse_score:.2f}"
                except:
                    self.logger.info(f"Found illegal score: {self.analyzer.ellipse_score}")
                cv2.putText(frame, text, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (36, 255, 12), 2)

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
        
        with gr.Blocks(theme=gr.themes.Soft()) as demo:
            with gr.Row():
                gr.Plot(self.create_plots, every=0.1, scale=2, show_label=False)
                frame = gr.Image(self.show_frame, every=0.03, scale=1, show_label=False)
            with gr.Row():
                pause_btn = gr.Button("Pause Analysis")
                ref_btn = gr.Button("Set New Reference")
                freeze_btn = gr.Button("Freeze Mask")
                export_btn = gr.Button("Export CSV")
                close_btn = gr.Button("Close")
                camera_select = gr.Dropdown(
                    choices=self.camera_names,
                    value=self.camera_names[0] if self.camera_names else None,
                    label="Select Camera"
                )
                toggle_ellipse = gr.Checkbox(True, label="Enable ellipsoid masking")
                toggle_ellipse.change(fn=self.set_ellipse_fitting, inputs=[toggle_ellipse])
                
                history_size = gr.Number(60, label="History in seconds", precision=0, minimum=0, maximum=1800)
                history_size.change(fn=self.update_history_window, inputs=[history_size])
                
                manual_exposure = gr.Checkbox(False, label="Manual Exposure")
                exposure_val = gr.Number(
                    value=0, 
                    label="Exposure Correction", 
                    precision=0,
                    minimum=-4,
                    maximum=4,
                    step=1
                )
                wb_val = gr.Number(
                    value=4000,
                    label="White Balance Temperature (K)",
                    precision=0,
                    minimum=2800,
                    maximum=7500,
                    step=100
                )

                dropdown = gr.Dropdown(
                    ["H (raw)", "S (raw)", "V (raw)", "H (smooth)", "S (smooth)", "V (smooth)",
                     "dH", "dS", "dV", "ddH", "ddS", "ddV"],
                    label="Channels", scale=1, show_label=True, multiselect=True, value=self.selected_channels)
                
                def update_selected_channels(selected):
                    self.selected_channels = selected

                dropdown.change(
                    fn=update_selected_channels,
                    inputs=[dropdown]
                )

            def update_camera_settings(manual, exp, wb):
                if manual:
                    self.camera.exposure_index = np.clip(exp + 4, 0, 9)
                    self.camera.wb = np.clip(wb, 2800, 7500)
                    self.camera.apply_settings()
                else:
                    self.camera.enable_auto_settings()
                
            manual_exposure.change(
                fn=update_camera_settings,
                inputs=[manual_exposure, exposure_val, wb_val]
            )
            exposure_val.change(
                fn=update_camera_settings,
                inputs=[manual_exposure, exposure_val, wb_val]
            )
            wb_val.change(
                fn=update_camera_settings, 
                inputs=[manual_exposure, exposure_val, wb_val]
            )
                
            camera_select.change(
                fn=self.switch_camera,
                inputs=[camera_select],
                outputs=[frame]
            )
            freeze_btn.click(self.freeze_mask, outputs=freeze_btn)
            pause_btn.click(self.toggle_pause, outputs=pause_btn)
            ref_btn.click(self.set_new_reference)
            export_btn.click(self.export_csv)
            close_btn.click(self.shutdown)
            
        # self.should_stop = True
        demo.launch(server_name='0.0.0.0', show_api=False)