# Automated Langmuir Deposition Detection

## Overview 

This project aims to create an easy to use interface for monitoring and controlling the injection process of ink onto a liquid surface and to turn off the injection once the saturation point is reached. The idea is to observe relative HSV time series data (hue, saturation, brightness/value) to find the point of saturation. The reference frame should be captured before the injection starts.

The interface consists of a webserver that currently performs the following tasks:
- capture a real-time webcam or Raspberry Pi camera feed
- perform edge detection and temporally stable ellipse fitting to find the region of interest: in our case this is a cylindrical container
- capture a reference frame and calculate the (smoothed) relative HSV data for each subsequently captured frame (and their first and second derivatives)

The user interface exposes the following functionality:
- select the camera device to use
- change the amount of temporal smoothing applied to the masking ellipse
- set a masking margin (range 0-1) to discard color changes at the border of the ellipse
- select which of the captured and calculated timeseries to plot (individual: raw HSV, smoothed HSV, first and second derivatives)
- select the history size to plot
- select threshold profiles from the file `profiles.csv`. Threshold conditions in the CSV file can be sparsely populated. If all threshold conditions are met, alert the user visually with a popup. This uses the smoothed values for threshold checking, not the raw values that could fluctuate a lot
- set an alpha value for decay smoothing. This is a destructive operation and only changes for data points collected after the value was updated
- set a sliding window smoothing range that is applied to the already smoothed data. First derivatives use this factor x2, second derivatives use x4
- record the currently streamed frames into a video that will be saved to `./recordings`
- load a previously recorded video that will replace the current camera stream. After the video finishes, the analysis is paused, and the user can switch back to the camera stream.

> [!Important]
> Manual exposure and white balance values were only tested on a Raspberry Pi Ubuntu system with a Logitech C920. Other devices are currently not supported for manual exposure control.

> [!Note]
> **This is a work in progress. There will be bugs. Some things will not work as intended. Feel free to poke around in the code and submit a PR if you want to help fix things.**

![Screenshot of the WebUI](webui_screenshot.jpg)
*Screenshot of the Gradio-based Web UI.*

## Installation on a desktop computer/laptop

1. Clone this project with `git clone https://github.com/smlpt/deposition-detection`
2. Ensure that a webcam is connected to your computer
3. On Windows: launch `launch_server_windows.bat` to launch the server. This will also automatically set up a virtual environment with the required packages on first launch.
On Linux, make the shell script executable by running `chmod +x run_project.sh` and then launch `./launch_server_linux.sh`.
4. Open `http://localhost:7860/` in a browser to access the interface
5. To stop the server, hit the "close" button in the GUI, or press Ctrl+C in the console.

## Installation on a Raspberry Pi

1. Clone this project with `git clone https://github.com/smlpt/deposition-detection`
2. Ensure that either a webcam or the Raspberry Pi camera is connected to your Raspberry Pi
3. Make the shell script executable by running `chmod +x run_project.sh` and then launch `./launch_server_linux.sh`. This will also automatically set up a virtual environment with the required packages on first launch.
4. Open `http://<raspberry-pi-ip>:7860` in a browser to access the interface. To find the IP address of the Raspberry Pi, you either have to go looking in your Router, or you connect a display and a keyboard and find the IP via `ifconfig`.
5. To stop the server, hit the "close" button in the GUI, or press Ctrl+C in the console.

## Changelog

### v0.4 Recording, Loading, Smoothing
- Allow the user to record videos
- Load existing videos and stream them instead of the camera feed
- Expose more parameters to the UI (decay smoothing, sliding window smoothing, temporal ellipse smoothing factor, ellipse margin)
- Apply sliding window smoothing to the recorded values and to the first and second derivatives
- Timestamp logging and threshold checking now use the smoothed values
- Hid the manual exposure controls for now, as they were only available in Linux and for Logitch C920 webcams

### v0.3 Thresholds
- Adds a profile.csv file to load sparse threshold data for different materials (filled with dummy data right now)
- Plot thresholds with the corresponding timeseries
- Monitor threshold conditions and alert the user when all conditions are met
- Adds an inner ellipse 90% the size of the original ellipse. This inner ellipse is used for calculations to prevent minor pixel shifts/errors around the mask contour
- Adds a log button that outputs the values of the current timestamp for all existing timeseries

### v0.2 Stable Masking and Derivatives
- Masks are now temporarily stable by adding the distance to the previous detection to the score function
- Masks transition smoothly between frames
- Calculate first and second derivatives of each H/S/V channel
- Dropdown to select which channels to plot

### v0.1 Initial release
- Real-time webcam capturing
- Edge detection and basic ellipse fitting
- HSV plotting for relative changes
- Export to CSV
- Manual exposure/WB settings


## FAQ

### I don't see any file open/save dialogs!
Makre sure your browser allows pop-ups.

### Where are my recorded videos?
Check in the `./recordings` folder.
