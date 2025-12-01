
# TODO This is only needed if using a logitech webcam
import os
import subprocess
os.environ["OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS"] = "0"

import cv2
from threading import Thread, Lock
import time
import logging
import warnings
import ids_peak.ids_peak as ids_peak
import ids_peak_ipl.ids_peak_ipl as ids_ipl
import ids_peak.ids_peak_ipl_extension as ids_ipl_extension

class PiCamera:
    def __init__(self, device_index=0):
        self.device_index = device_index
        self.stream = None
        self.lock = Lock()
        self.frame = None
        self._stopped = False
        self.device_path = f"/dev/video{device_index}"
        self.use_ids = False
        self.mem_ptr = None
        self.mem_id = None
        self.sensor_width = None
        self.sensor_height = None
        self.ids_devices = None
        self.ids_device_nodemap = None
        self.exposure_index = 1
        # This range of exposures is suitable for a Logitech C920 webcam
        self.exposures = [5, 10, 20, 39, 78, 156, 312, 625, 1250, 2047]
        self.wb = 4000
        self.logger = logging.getLogger(__name__)
        self.is_recording = False
        self.video_writer = None
        self.is_stream_video = False
        self.video_reader: cv2.VideoCapture = None
        self.video_frame_count = -1
        self.current_frame_idx = 0
        self.pause_callback = None
    
    def apply_settings(self):
        """Apply stored exposure and white balance to camera"""
        self.logger.debug("Applying camera settings: exposure=%d, white_balance=%d", self.exposure_index, self.wb)
        subprocess.run(['v4l2-ctl', '-d', self.device_path, '-c', 'auto_exposure=1'])
        subprocess.run(['v4l2-ctl', '-d', self.device_path, '-c', 'exposure_dynamic_framerate=0'])
        subprocess.run(['v4l2-ctl', '-d', self.device_path, '-c', 'gain=0'])
        subprocess.run(['v4l2-ctl', '-d', self.device_path, '-c', f'exposure_time_absolute={self.exposures[self.exposure_index]}'])
        subprocess.run(['v4l2-ctl', '-d', self.device_path, '-c', 'white_balance_automatic=0'])
        subprocess.run(['v4l2-ctl', '-d', self.device_path, '-c', f'white_balance_temperature={self.wb}'])
        
    def enable_auto_settings(self):
        """Enable automatic camera adjustments"""
        subprocess.run(['v4l2-ctl', '-d', self.device_path, '-c', 'auto_exposure=3'])
        subprocess.run(['v4l2-ctl', '-d', self.device_path, '-c', 'white_balance_automatic=1'])
        subprocess.run(['v4l2-ctl', '-d', self.device_path, '-c', 'exposure_dynamic_framerate=1'])
        
    def list_cameras(self):
        """List all available camera devices"""
        self.logger.info("Creating a list of available camera devices...")
        self.logger.info("(The following OpenCV warnings can safely be ignored)")
        camera_list = []

        # Find IDS camera
        ids_peak.Library.Initialize()
        device_manager = ids_peak.DeviceManager.Instance()
        device_manager.Update()
        self.ids_devices = device_manager.Devices()

        if self.ids_devices.count > 0:
            # Append IDS to camera list and return immediately
            camera_list.append({"index": 0, "name": "IDS Camera"})
            self.use_ids = True
            return camera_list

        for i in range(10):  # Check first 10 indexes if no IDS camera is found
            self.logger.debug(f"trying out cam {i}")
            
            cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
            if cap.isOpened():
                ret, cam = cap.read()
                if ret is not None and cam is not None:
                    camera_list.append({"index": i, "name": f"Camera {i}"})
                cap.release()
        return camera_list
        
    def start(self):
        """Start capture from specified device"""
        self._stopped = False

        if self.use_ids:
            self.logger.info("Using IDS camera")
            device = self.ids_devices[0].OpenDevice(ids_peak.DeviceAccessType_Control)
            print("Opened Device: " + device.DisplayName())
            
            self.ids_device_nodemap = device.RemoteDevice().NodeMaps()[0]
            self.ids_device_nodemap.FindNode("TriggerSelector").SetCurrentEntry("ExposureStart")
            self.ids_device_nodemap.FindNode("TriggerSource").SetCurrentEntry("Software")
            self.ids_device_nodemap.FindNode("TriggerMode").SetCurrentEntry("On")

            self.stream = device.DataStreams()[0].OpenDataStream()

            payload_size = self.ids_device_nodemap.FindNode("PayloadSize").Value()
            for i in range(self.stream.NumBuffersAnnouncedMinRequired()):
                buffer = self.stream.AllocAndAnnounceBuffer(payload_size)
                self.stream.QueueBuffer(buffer)
                
            self.stream.StartAcquisition()
            self.ids_device_nodemap.FindNode("AcquisitionStart").Execute()
            self.ids_device_nodemap.FindNode("AcquisitionStart").WaitUntilDone()

            Thread(target=self._capture_loop_ids, daemon=True).start()
            self.logger.info("Started IDS camera thread")
            return
        else:
            self.stream = cv2.VideoCapture(self.device_index)
            if not self.stream.isOpened():
                raise RuntimeError(f"Failed to open camera at index {self.device_index}")        
            Thread(target=self._capture_loop, daemon=True).start()
            self.logger.info(f"Started camera thread for device {self.device_index}")

    def switch_camera(self, new_index):
        """Switch to a different camera device"""
        self.stop()
        self.device_index = new_index
        if self.use_ids:
            # For IDS, device_path is not used
            self.logger.info("Switching to IDS camera (index ignored)")
        else:
            self.device_path = f"/dev/video{new_index}"
        self.stored_settings = None  # Reset stored settings
        self.start()
    
    def _capture_loop(self):
        """Default capture loop for webcam devices. Will stream video if `self.is_stream_video` is set."""
        while not self._stopped:
            # Take the frame either from camera or from a video file
            ret, frame = self.video_reader.read() if self.is_stream_video else self.stream.read()
            if ret:
                with self.lock:
                    self.frame = frame
                    if self.is_stream_video:
                        self.current_frame_idx += 1
                    if self.video_frame_count == self.current_frame_idx and self.pause_callback is not None:
                        self.pause_callback()
                # Record frames to file is the flag is set
                if getattr(self, 'is_recording', False):
                    self.video_writer.write(frame)
            time.sleep(0.03)  # ~30 FPS

    def _capture_loop_ids(self):
        """Special capture loop for IDS devices. Will stream video if `self.is_stream_video` is set."""
        while not self._stopped:
            self.ids_device_nodemap.FindNode("TriggerSoftware").Execute()
            buffer = self.stream.WaitForFinishedBuffer(100)

            # convert to RGB
            raw_image = ids_ipl_extension.BufferToImage(buffer)
            color_image = raw_image.ConvertTo(ids_ipl.PixelFormatName_RGB8)
            self.stream.QueueBuffer(buffer)
            # We need to construct a tuple here 
            
            ret, frame = self.video_reader.read() if self.is_stream_video else (not color_image.Empty(), color_image.get_numpy())

            if ret:
                with self.lock:
                    self.frame = frame
                    if self.is_stream_video:
                        self.current_frame_idx += 1
                    if self.video_frame_count == self.current_frame_idx and self.pause_callback is not None:
                        self.pause_callback()
                # Record frames to file is the flag is set
                if getattr(self, 'is_recording', False):
                    self.video_writer.write(frame)
            time.sleep(0.03)
            
    def get_frame(self):
        with self.lock:
            return self.frame.copy() if self.frame is not None else None
            
    def stop(self):
        self.logger.info(f"Stopped camera {self.device_index}")
        self._stopped = True
        if self.use_ids:
            ids_peak.Library.Close()
            self.ids_device_nodemap = None
            self.ids_devices = None
        else:
            if self.stream is not None:
                self.stream.release()
                self.stream = None

    def start_recording(self, filename):
        # Ensure the recordings directory exists
        recordings_dir = os.path.join(os.getcwd(), "recordings")
        os.makedirs(recordings_dir, exist_ok=True)
        filepath = os.path.join(recordings_dir, filename)

        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        self.video_writer = cv2.VideoWriter(filepath, fourcc, 20.0, (self.frame.shape[1], self.frame.shape[0]), isColor=True)
        if not self.video_writer.isOpened():
            self.logger.error(f"Failed to open VideoWriter for {filepath}")
            return False
        self.is_recording = True
        self.logger.info(f"Started recording to {filepath}")
        return True

    def stop_recording(self):
        if hasattr(self, 'video_writer') and self.video_writer is not None:
            self.video_writer.release()
            self.is_recording = False
            self.logger.info("Stopped recording.")
            
    def reset_video_reader(self):
        self.is_stream_video = False
        self.video_reader.release()
        self.video_reader = None
        self.current_frame_idx = 0