from camera.camera import PiCamera
from camera.processor import ImageProcessor
from analysis.hsv_analyzer import HSVAnalyzer
from web.server import WebServer
import time
import threading
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def analysis_loop(camera, processor, analyzer):
    while True:
        frame = camera.get_frame()
        if frame is not None:
            analyzer.update(frame, alpha=0.05)
        time.sleep(0.1)  # 10 Hz analysis rate

def main():
    
    # Initialize components
    camera = PiCamera()
    processor = ImageProcessor()
    analyzer = HSVAnalyzer(processor)
    server = WebServer(camera, analyzer)
    server.find_camera_devices()
    # Start camera
    camera.start()
    
    logger.info("Initialized camera, processor, analyser and server.")
    
    # Start analysis loop in a separate thread
    analyzer_thread = threading.Thread(target=analysis_loop, args=(camera, processor, analyzer))
    analyzer_thread.daemon = True
    analyzer_thread.start()
    logger.info("Started the analyzer thread.")

    # Start web server
    server.launch()
    
    # Once we are here, we can assume the server was stopped, so we also stop the camera
    camera.stop()

if __name__ == "__main__":
    logger.info("Starting up...")
    main()
