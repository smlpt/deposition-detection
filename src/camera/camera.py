
# TODO This is only needed if using a logitech webcam
import os
import subprocess
os.environ["OPENCV_VIDEOIO_MSMF_ENABLE_HW_TRANSFORMS"] = "0"

import numpy as np
import cv2
from threading import Thread, Lock
import time
import logging
import warnings
import ids_peak.ids_peak as ids_peak
import ids_peak_ipl.ids_peak_ipl as ids_ipl
import ids_peak.ids_peak_ipl_extension as ids_ipl_extension
from timeit import default_timer as timer

class Camera:
    def __init__(self, device_index=0):
        self.device_index = device_index
        self.stream = None
        self.lock = Lock()
        self.frame = None
        self.raw_frame = None # Needed for calculating the white balance
        self.frame_ready = False
        self._stopped = False
        self.device_path = f"/dev/video{device_index}"
        self.use_ids = False
        self.sensor_width = None
        self.sensor_height = None
        self.ids_devices = None
        self.ids_device_nodemap = None
  
        self.wb = 4000
        self.logger = logging.getLogger(__name__)
        self.is_recording = False
        self.video_writer = None
        self.is_stream_from_file = False
        self.video_reader: cv2.VideoCapture = None
        self.video_frame_count = -1
        self.current_frame_idx = 0
        self.pause_callback = None
        self.camera_list = []
        self.lut = np.empty((1,256), np.uint8)
        self.exposure = 1
        self.gamma = 1.0
        self.red_gain = 1.7
        self.blue_gain = 1.8

    @property
    def exposure(self):
        return self._exposure
    
    @exposure.setter
    def exposure(self, value):
        self._exposure = value
        # IDS takes exposure in microseconds and we want to scale exposure quadratically for ease of use
        correct_expo = self.calculate_ids_exposure(value)
        
        if self.ids_device_nodemap is not None:
            self.ids_device_nodemap.FindNode("ExposureTime").SetValue(correct_expo)

    def calculate_ids_exposure(self, value: float):
        """We provide the user with a convenient conversion between the range 0-20 and a quadratic
        increase in actual exposure value """
        return value**2 * 1000

    def build_gamma_LUT(self, gamma: float = 1.0):
        """(Re)constructs a lookup table for nonlinear gamma conversion of a frame."""
        self.lut = np.empty((1,256), np.uint8)
        for i in range(256):
            self.lut[0,i] = np.clip(pow(i / 255.0, gamma) * 255.0, 0, 255)

    def calculate_WB(self, frame = None) -> tuple:
        """Takes in a frame and returns the red and blue gains for a grey world."""
        if frame == None:
            frame = self.raw_frame

        frame = frame.astype(np.float32)
        avg_r = np.mean(frame[:, :, 0])
        avg_g = np.mean(frame[:, :, 1])
        avg_b = np.mean(frame[:, :, 2])

        self.red_gain = avg_g / avg_r
        self.blue_gain = avg_g / avg_b
        self.logger.info(" Calculated new white balance from frame.")
        return (float(self.red_gain), float(self.blue_gain))

         
    def list_cameras(self):
        """List all available camera devices"""
        self.logger.info("Creating a list of available camera devices...")
        self.logger.info("(The following OpenCV warnings can safely be ignored)")
        self.camera_list = []

        # Find IDS camera
        try:
            ids_peak.Library.Initialize()
            device_manager = ids_peak.DeviceManager.Instance()
            device_manager.Update()
            self.ids_devices = device_manager.Devices()

            if len(self.ids_devices) > 0:
                # Append IDS to camera list and return immediately
                for index, ids_cam in enumerate(self.ids_devices):
                    self.camera_list.append({"index": index, "name": f"IDS {ids_cam.ModelName()}"})
                self.use_ids = True
        except:
            self.use_ids = False
            self.logger.warning("Failed to initialize IDS camera devices. Maybe incorrect IDS peak & driver installation?" \
            "Resorting to webcam devices only.")

        webcam_count = len(self.ids_devices)
        # Check first 5 indexes
        for i in range(5):
            self.logger.debug(f"trying out cam {i}")
            
            cap = cv2.VideoCapture(i, cv2.CAP_DSHOW)
            if cap.isOpened():
                ret, cam = cap.read()
                if ret is not None and cam is not None:
                    # Assign sequential index after IDS cameras
                    self.logger.info(f"Found webcam {i}")
                    self.camera_list.append({"index": webcam_count, "name": f"Webcam {i}"})
                    webcam_count += 1
                cap.release()
        return self.camera_list
        
    def start(self):
        """Start capture from specified device"""
        self._stopped = False
        self.build_gamma_LUT(1.0)
        if self.use_ids:
            self.logger.info("Using IDS camera")
            Thread(target=self._capture_loop, daemon=True).start()
            self.logger.info("Started camera thread")
            return
        else:
            actual_index = self._get_actual_webcam_index()
            self.stream = cv2.VideoCapture(actual_index)
            if not self.stream.isOpened():
                raise RuntimeError(f"Failed to open camera at index {actual_index}")        
            Thread(target=self._capture_loop, daemon=True).start()
            self.logger.info(f"Started camera thread for device {actual_index}")

    def _get_actual_webcam_index(self):
        """Get the actual OpenCV device index for a webcam"""
        camera_name = self.get_camera_name(self.device_index)
        if camera_name.startswith("Webcam"):
            # Extract the original index from the name
            return int(camera_name.split()[-1])
        return self.device_index

    def switch_camera(self, new_index):
        """Switch to a different camera device"""
        self.stop()
        self.device_index = new_index
        camera_name: str = self.get_camera_name(new_index)
        self.use_ids = camera_name.startswith("IDS")
        
        if not self.use_ids:
            self.device_path = f"/dev/video{new_index}"
        self.stored_settings = None  # Reset stored settings
        self.start()

    def get_camera_name(self, index: int = None) -> str:
        """Returns the string of a specified camera index.
        Uses the currently active device index if no index is specified."""
        if index == None:
            index = self.device_index
        return next(cam["name"] for cam in self.camera_list if cam["index"] == index)
    
    def wait_for_frame(self, timeout=5.0):
        """Wait for a valid frame to be available. Returns True if successful, False on timeout."""
        start_time = time.time()
        while not self.frame_ready and (time.time() - start_time) < timeout:
            time.sleep(0.05)
        return self.frame_ready
    
    def _capture_loop(self):
        """Capture loop for webcam and IDS devices.
        Will stream video from file if `self.is_stream_from_file` is set."""
        
        if self.use_ids:
            ids_peak.Library.Initialize()
            device = self.ids_devices[self.device_index].OpenDevice(ids_peak.DeviceAccessType_Control)
            print("Opened Device: " + device.DisplayName())
            
            self.ids_device_nodemap = device.RemoteDevice().NodeMaps()[0]
            self.ids_device_nodemap.FindNode("AcquisitionMode").SetCurrentEntry("Continuous")
            
            def set_ids_expo():
                time.sleep(2)  # Wait for camera to stabilize
                try:
                    ids_expo = self.ids_device_nodemap.FindNode("ExposureTime").Value()
                    calculated_expo = np.sqrt(ids_expo / 1000.0)
                    self._exposure = calculated_expo  # Set internal value
                    self.logger.info(f"Initial IDS exposure: {calculated_expo:.2f}")
                except Exception as e:
                    self.logger.error(f"Failed to read initial exposure: {e}")
            
            Thread(target=set_ids_expo).start()

            self.stream = device.DataStreams()[0].OpenDataStream()

            payload_size = self.ids_device_nodemap.FindNode("PayloadSize").Value()
            num_buffers = self.stream.NumBuffersAnnouncedMinRequired()

            for i in range(num_buffers):
                buffer = self.stream.AllocAndAnnounceBuffer(payload_size)
                self.stream.QueueBuffer(buffer)  # Queue immediately for reuse
                
            self.stream.StartAcquisition()
            self.ids_device_nodemap.FindNode("AcquisitionStart").Execute()
            self.ids_device_nodemap.FindNode("AcquisitionStart").WaitUntilDone()

        self.logger.info(f" Started capture loop with device {self.device_index}: {self.get_camera_name()}")

        base_width = 600

        while not self._stopped:
        
            if self.use_ids and isinstance(self.stream, ids_peak.DataStream) and not self.is_stream_from_file:
                
                buffer = self.stream.WaitForFinishedBuffer(1000)
                raw_image = ids_ipl_extension.BufferToImage(buffer)

                # Queue self.ids_buffer back for reuse
                self.stream.QueueBuffer(buffer)

                # Convert to RGB8 if needed
                if raw_image.PixelFormat() != ids_ipl.PixelFormatName_RGB8:
                    rgb_image = raw_image.ConvertTo(ids_ipl.PixelFormatName_RGB8)
                else:
                    rgb_image = raw_image
                
                # Get numpy array and convert RGB to BGR for OpenCV
                frame = rgb_image.get_numpy_3D()
                

                ratio = frame.shape[0] / frame.shape[1]
                # Always resize
                frame = cv2.resize(frame, (int(base_width), int(ratio * base_width)), interpolation=cv2.INTER_AREA)
                self.raw_frame = frame

                # Gain and white balance stuff
                frame = frame.astype(np.float32)
                frame[:, :, 0] *= self.red_gain   # Red channel
                frame[:, :, 2] *= self.blue_gain  # Blue channel
                
                frame = np.clip(frame, 0, 255).astype(np.uint8)
                # Adjust gamma
                frame = cv2.LUT(frame, self.lut)

                frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

                with self.lock:
                    self.frame = frame_bgr
                    self.frame_ready = True

                # Record frames to file if the flag is set
                if getattr(self, 'is_recording', False):
                    self.video_writer.write(frame)

            else:
                # Take the frame either from camera or from a video file
                if self.is_stream_from_file:
                    ret, frame = self.video_reader.read()
                else:
                    # Check if stream is valid before reading
                    if self.stream is not None and isinstance(self.stream, cv2.VideoCapture):
                        ret, frame = self.stream.read()
                    else:
                        # Stream is not valid, skip this iteration
                        ret = False
                        frame = None
                        
                if ret:
                    with self.lock:
                        self.frame = frame
                        self.frame_ready = True
                        if self.is_stream_from_file:
                            self.current_frame_idx += 1
                        if self.video_frame_count == self.current_frame_idx and self.pause_callback is not None:
                            self.pause_callback()
                    # Record frames to file if the flag is set
                    if getattr(self, 'is_recording', False):
                        self.video_writer.write(frame)
                else:
                    # Only print warning if we're not in file streaming mode
                    if not self.is_stream_from_file:
                        print("failed to load frame")

            time.sleep(0.03)  # ~30 FPS
            
    def get_frame(self):
        with self.lock:
            return self.frame.copy() if self.frame is not None else None
            
    def stop(self):
        self.logger.info(f"Stopped camera {self.device_index}")
        self._stopped = True
        self.frame_ready = False
        if self.use_ids:
            try:
                self.ids_device_nodemap.FindNode("AcquisitionStop").Execute()
                self.stream.StopAcquisition()
                self.stream.Flush(ids_peak.DataStreamFlushMode_DiscardAll)
                # Revoke buffers
                for buffer in self.stream.AnnouncedBuffers():
                    self.stream.RevokeBuffer(buffer)
            except:
                self.logger.warning("Failed to clean up IDS device and acqusition stream!")
            ids_peak.Library.Close()
            self.ids_device_nodemap = None
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
        self.is_stream_from_file = False
        self.frame_ready = False
        if self.video_reader is not None:
            self.video_reader.release()
            self.video_reader = None
        self.current_frame_idx = 0
