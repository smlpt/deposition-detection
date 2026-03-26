import serial
import serial.tools.list_ports
import time
import re
import threading
import logging


class SyringeController():
    # NE-1000 serial defaults
    BAUDRATE    = 19200
    BYTESIZE    = serial.EIGHTBITS
    PARITY      = serial.PARITY_NONE
    STOPBITS    = serial.STOPBITS_ONE
    TIMEOUT     = 0.5  # seconds

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.port: str | None = None
        self.serial: serial.Serial | None = None

    def _probe_port(self, port_name: str, timeout: float = 1.0, probe_timeout: float = 0.5) -> bool:
        """Probe a port with a hard wall-clock timeout on the open() call itself."""
        result = [False]  # mutable container so the thread can write to it

        def _attempt():
            try:
                with serial.Serial(
                    port     = port_name,
                    baudrate = self.BAUDRATE,
                    bytesize = self.BYTESIZE,
                    parity   = self.PARITY,
                    stopbits = self.STOPBITS,
                    timeout  = timeout,
                ) as s:
                    s.reset_input_buffer()
                    s.write(b"*\r")
                    time.sleep(0.3)
                    response = s.read_all().decode(errors="replace").strip()

                    if not response:
                        self.logger.debug(f"  {port_name}: no response")
                        return

                    self.logger.debug(f"  {port_name}: got {repr(response)}")
                    result[0] = bool(re.match(r"^\d{2}[SIWA]\??$", response))

            except (serial.SerialException, PermissionError) as e:
                self.logger.debug(f"  {port_name}: could not open — {e}")

        t = threading.Thread(target=_attempt, daemon=True)
        t.start()
        t.join(timeout=probe_timeout)

        if t.is_alive():
            self.logger.debug(f"  {port_name}: timed out after {probe_timeout}s (port hung on open)")

        return result[0]

    def find_and_set_port(self) -> str | None:
            """Scan all ports, probe each one, store the first working port."""
            self.logger.info("Probing COM ports to find syringe pump...")
            for port_info in serial.tools.list_ports.comports():
                name = port_info.device
                self.logger.debug(f"Probing {name} ({port_info.description})…")
                if self._probe_port(name, self.TIMEOUT):
                    self.port = name
                    self.logger.info(f"Syringe pump stored on active port: {self.port}")
                    return self.port
            return None

    def set_port(self, port_name: str) -> bool:
        """Manually specify a port after validating it."""
        if self._probe_port(port_name, self.TIMEOUT):
            self.port = port_name
            return True
        return False
    
    def connect(self) -> bool:
        """Open a persistent connection to the stored port."""
        if not self.port:
            self.logger.info("No port set — call find_and_set_port() or set_port() first.")
            return False
        try:
            self.serial = serial.Serial(
                port     = self.port,
                baudrate = self.BAUDRATE,
                bytesize = self.BYTESIZE,
                parity   = self.PARITY,
                stopbits = self.STOPBITS,
                timeout  = self.TIMEOUT,
            )
            self.logger.info(f"Connected to {self.port}")
            return True
        except serial.SerialException as e:
            self.logger.warning(f"Connection failed: {e}")
            return False

    def disconnect(self):
        if self.serial and self.serial.is_open:
            self.serial.close()
            self.logger.info("Serial port closed.")

    def _send(self, command: str) -> str | None:
            """Send a CR-terminated command; return the pump's response."""
            if not self.serial or not self.serial.is_open:
                self.logger.warning("Not connected.")
                return None
            try:
                self.serial.write(f"{command}\r".encode())
                time.sleep(0.05)                        # give pump time to respond
                response = self.serial.read_all().decode(errors="replace").strip()
                return response
            except serial.SerialException as e:
                self.logger.warning(f"Serial error: {e}")
                return None

    def start(self) -> str | None:
        """Start the pump. Returns next button label, or None if command failed."""
        response = self._send("RUN")
        if self._is_accepted(response):
            self.logger.info("Pump started.")
            return "Stop"
        self.logger.warning(f"Start command rejected: {repr(response)}")
        return None

    def stop(self) -> str | None:
        """Stop the pump. Returns next button label, or None if command failed."""
        response = self._send("STP")
        if self._is_accepted(response):
            self.logger.info("Pump stopped.")
            return "Start"
        self.logger.warning(f"Stop command rejected: {repr(response)}")
        return None
    
    def _is_accepted(self, response: str | None) -> bool:
        """Return True if the pump's response indicates the command was accepted.
        Accepted responses match the normal status format: e.g. '00S', '00I', '00W'
        Error responses contain '?' e.g. '00?NA' (not applicable) or '00?OOR' (out of range)
        """
        if not response:
            return False
        return bool(re.match(r"^\d{2}[SIWA]$", response))

    def set_rate(self, rate: float, unit: str = "MM") -> str | None:
        """
        Set infusion rate.
        unit: MM = mL/min | MH = mL/hr | UM = µL/min | UH = µL/hr
        """
        return self._send(f"RAT {rate:.4f} {unit}")
    
    def beep(self):
        """Make the pump beep."""
        return self._send("BEP")