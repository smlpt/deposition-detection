import ids_peak.ids_peak as ids_peak
import ids_peak_ipl.ids_peak_ipl as ids_ipl
import ids_peak.ids_peak_ipl_extension as ids_ipl_extension
import cv2
import numpy as np

def main():
    # Initialize IDS Peak library
    ids_peak.Library.Initialize()
    
    try:
        # Find and open camera
        device_manager = ids_peak.DeviceManager.Instance()
        device_manager.Update()
        
        if len(device_manager.Devices()) == 0:
            print("No camera found!")
            return
        
        device = device_manager.Devices()[0].OpenDevice(ids_peak.DeviceAccessType_Control)
        print(f"Opened: {device.DisplayName()}")
        
        nodemap = device.RemoteDevice().NodeMaps()[0]
        
        # Configure camera for continuous acquisition
        nodemap.FindNode("AcquisitionMode").SetCurrentEntry("Continuous")
        
        # Use the native Bayer format - we'll debayer in software
        pixel_format_node = nodemap.FindNode("PixelFormat")
        current_format = pixel_format_node.CurrentEntry().SymbolicValue()
        print(f"Camera pixel format: {current_format}")

        print(nodemap.FindNode("ExposureTime").Value())
        
        # Software white balance gains (applied after debayering)
        # ADJUST THESE VALUES based on your lighting conditions
        red_gain = 1.7   # Increase if image is too cyan/green
        blue_gain = 1.8  # Increase if image is too yellow/green
        # print(f"Software white balance gains: Red={red_gain:.2f}, Blue={blue_gain:.2f}")
        
        # Open datastream and prepare buffers
        datastream = device.DataStreams()[0].OpenDataStream()
        payload_size = nodemap.FindNode("PayloadSize").Value()
        
        # Allocate buffers
        num_buffers = datastream.NumBuffersAnnouncedMinRequired()
        for i in range(num_buffers):
            buffer = datastream.AllocAndAnnounceBuffer(payload_size)
            datastream.QueueBuffer(buffer)
        
        # Start acquisition
        datastream.StartAcquisition()
        nodemap.FindNode("AcquisitionStart").Execute()
        nodemap.FindNode("AcquisitionStart").WaitUntilDone()
        
        print("Streaming... Press 'q' to quit")

        frame_count = 0

        lookUpTable = np.empty((1,256), np.uint8)
        for i in range(256):
            lookUpTable[0,i] = np.clip(pow(i / 255.0, 0.6) * 255.0, 0, 255)
        
        # Main loop
        while True:
            # Get frame
            buffer = datastream.WaitForFinishedBuffer(1000)
            
            # Convert to numpy array
            raw_image = ids_ipl_extension.BufferToImage(buffer)
            
            # Debayer and convert to RGB8
            # The IPL library handles the Bayer demosaicing automatically
            rgb_image = raw_image.ConvertTo(ids_ipl.PixelFormatName_RGB8)
            
            # Get numpy array (RGB format)
            frame = rgb_image.get_numpy_3D()
            frame = cv2.resize(frame, None, fx=0.2, fy=0.2, interpolation=cv2.INTER_AREA)
            frame = frame.astype(np.float32)

            # calculate WB every 5th frame and then mix it into the existing WB gains
            if frame_count % 5 == 0:
                avg_r = np.mean(frame[:, :, 0])
                avg_g = np.mean(frame[:, :, 1])
                avg_b = np.mean(frame[:, :, 2])

                red_gain = 0.8 * red_gain + 0.2 * (avg_g / avg_r)
                blue_gain = 0.8 * blue_gain + 0.2 * (avg_g / avg_b)

            # Apply software white balance correction
            # frame = frame.astype(np.float32)
            frame[:, :, 0] *= red_gain   # Red channel
            frame[:, :, 2] *= blue_gain  # Blue channel
            frame = np.clip(frame, 0, 255).astype(np.uint8)

            frame = cv2.LUT(frame, lookUpTable)
            
            # Convert RGB to BGR for OpenCV display
            frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
         
            # Queue buffer back for reuse
            datastream.QueueBuffer(buffer)
            
            # Display
            cv2.imshow('IDS Camera Stream', frame_bgr)

            frame_count += 1

            # Check for keyboard input
            key = cv2.waitKey(1) & 0xFF
        
            if key == ord('q'):
                break
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Cleanup
        try:
            nodemap.FindNode("AcquisitionStop").Execute()
            datastream.StopAcquisition()
            datastream.Flush(ids_peak.DataStreamFlushMode_DiscardAll)
            
            # Revoke buffers
            for buffer in datastream.AnnouncedBuffers():
                datastream.RevokeBuffer(buffer)
            
        except:
            pass
        
        cv2.destroyAllWindows()
        ids_peak.Library.Close()
        print("Cleanup complete")

if __name__ == "__main__":
    main()