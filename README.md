# Automated Langmuir Deposition Detection

## Overview 

This project aims to create an easy to use interface for monitoring and controlling the injection process of ink onto a liquid surface and to turn off the injection once the saturation point is reached. The idea is to observe relative HSV time series data (hue, saturation, brightness/value) to find the point of saturation. The reference frame should be captured before the injection starts.

The interface consists of a webserver that currently performs the following tasks:
- capture a real-time webcam or Raspberry Pi camera feed
- perform edge detection and ellipsoid fitting to find the region of interest: in our case this is a cylindrical fluid container
- capture a reference frame and calculate the relative HSV data for each subsequently captured frame
- plot the HSV history in a user defined range

> **This is a work in progress. There will be bugs. Some things will not work as intended. Feel free to poke around in the code and submit a PR if you want to help fix things.**

## Installation on a desktop computer/laptop

1. Clone this project with `git clone https://github.com/smlpt/deposition-detection`
2. Create a virtual Python environment somewhere on your file system, activate it and install the project dependencies from `requirements.txt` with `pip install -r requirements.txt`
3. Ensure that a webcam is connected to your computer
4. `cd` into the project `src` and run `python main.py`
5. Open `http://localhost:7860/` in a browser to access the interface

## Installation on a Raspberry Pi

> This part needs more testing and might not work yet

1. Clone this project with `git clone https://github.com/smlpt/deposition-detection`
2. Create a virtual Python environment somewhere on your file system, activate it and install the project dependencies from `requirements.txt` with `pip install -r requirements.txt`
3. Ensure that either a webcam or the Raspberry Pi camera is connected to your Raspberry Pi
4. `cd` into the project and run `python main.py`
5. Open `http://<raspberry-pi-ip>:7860` in a browser to access the interface. To find the IP address of the Raspberry Pi, you either have to go looking in your Router, or you connect a display and a keyboard and find the IP via `ifconfig`.
