from camera.camera import Camera
from camera.processor import ImageProcessor
from analysis.hsv_analyzer import HSVAnalyzer
from web.server import WebServer
import time
import threading
import logging
import sys
import asyncio
import os
import cProfile
import pstats

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def analysis_loop(camera, processor, analyzer):
    while True:
        frame = camera.get_frame()
        if frame is not None:
            analyzer.update(frame)
        time.sleep(0.1)  # 10 Hz analysis rate

def main():

    print(f"Using Python location {sys.executable}")
    
    if os.name == "nt":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        logger.info("Applied Windows-specific asyncio event loop fix.")
    
    # Initialize components
    camera = Camera()
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
    # camera.stop()

if __name__ == "__main__":
    logger.info("Starting up...")
    prof = cProfile.Profile()
    prof.run('main()')
    prof.dump_stats('output.prof')
    stream = open('output.txt', 'w')
    stats = pstats.Stats('output.prof', stream=stream)
    stats.sort_stats('cumtime')
    stats.print_stats()
