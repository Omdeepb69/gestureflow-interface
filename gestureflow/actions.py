# gestureflow/actions.py

import logging
import time
import platform
import sys

# Optional imports - wrap in try-except to handle missing installations gracefully
try:
    import pyautogui
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    PYAUTOGUI_AVAILABLE = False
    logging.warning("pyautogui not found. OS control actions will be unavailable.")
except Exception as e:
    # Catch potential platform-specific issues (e.g., on headless Linux)
    PYAUTOGUI_AVAILABLE = False
    logging.warning(f"pyautogui import failed: {e}. OS control actions will be unavailable.")


try:
    import serial
    import serial.tools.list_ports
    PYSERIAL_AVAILABLE = True
except ImportError:
    PYSERIAL_AVAILABLE = False
    logging.warning("pyserial not found. Serial communication actions will be unavailable.")

# Basic logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class ActionHandler:
    """
    Handles the execution of actions based on recognized gestures and configuration.
    Supports OS control via pyautogui and hardware communication via pyserial.
    """

    def __init__(self, config: dict):
        """
        Initializes the ActionHandler.

        Args:
            config (dict): The loaded configuration dictionary containing gesture mappings
                           and settings for pyautogui and pyserial.
        """
        self.config = config
        self.gesture_map = config.get('gestures', {})
        self.serial_connection = None
        self.last_action_time = {} # Track last execution time per gesture to prevent spamming
        self.action_debounce_ms = config.get('action_debounce_ms', 500) # Min ms between same action

        # --- PyAutoGUI Setup ---
        self.pyautogui_enabled = PYAUTOGUI_AVAILABLE and config.get('pyautogui', {}).get('enabled', False)
        if self.pyautogui_enabled:
            try:
                # Configure pyautogui (optional, based on config)
                pyautogui_config = config.get('pyautogui', {})
                pyautogui.PAUSE = pyautogui_config.get('pause_between_actions', 0.1)
                pyautogui.FAILSAFE = pyautogui_config.get('failsafe', True)
                logging.info("PyAutoGUI actions enabled.")
                # Get screen dimensions for potential mouse control mapping
                self.screen_width, self.screen_height = pyautogui.size()
                logging.info(f"Screen dimensions: {self.screen_width}x{self.screen_height}")
                self.mouse_control_active = False
                self.mouse_control_gesture = config.get('mouse_control', {}).get('control_gesture')
                self.mouse_sensitivity = config.get('mouse_control', {}).get('sensitivity', 1.5)
                self.prev_mouse_landmark = None # Store previous landmark for relative movement
            except Exception as e:
                logging.error(f"Failed to configure PyAutoGUI: {e}. Disabling OS control.")
                self.pyautogui_enabled = False
        else:
             if config.get('pyautogui', {}).get('enabled', False):
                 logging.warning("PyAutoGUI is configured to be enabled, but the library is not available or failed to init.")

        # --- PySerial Setup ---
        self.pyserial_enabled = PYSERIAL_AVAILABLE and config.get('serial', {}).get('enabled', False)
        if self.pyserial_enabled:
            try:
                self._init_serial()
            except Exception as e:
                logging.error(f"Failed to initialize serial connection: {e}. Disabling serial actions.")
                self.pyserial_enabled = False
        else:
            if config.get('serial', {}).get('enabled', False):
                 logging.warning("PySerial is configured to be enabled, but the library is not available.")


    def _init_serial(self):
        """Initializes the serial connection based on the configuration."""
        serial_config = self.config.get('serial', {})
        port = serial_config.get('port')
        baudrate = serial_config.get('baudrate', 9600)
        timeout = serial_config.get('timeout', 1)

        if not port or port.lower() == 'auto':
            logging.info("Attempting to auto-detect serial port...")
            ports = serial.tools.list_ports.comports()
            # Simple heuristic: prioritize Arduino/common USB-Serial vendors
            potential_ports = [p for p in ports if 'USB' in p.description or 'ACM' in p.device or 'arduino' in p.description.lower()]
            if not potential_ports:
                 potential_ports = ports # Fallback to any port if specific ones aren't found

            if potential_ports:
                # Try connecting to the first potential port found
                port = potential_ports[0].device
                logging.info(f"Auto-detected port: {port}")
            else:
                raise serial.SerialException("No serial ports detected.")

        try:
            self.serial_connection = serial.Serial(port, baudrate, timeout=timeout)
            time.sleep(2) # Allow time for Arduino/device to reset after connection
            logging.info(f"Serial connection established on {port} at {baudrate} baud.")
        except serial.SerialException as e:
            logging.error(f"Failed to open serial port {port}: {e}")
            self.serial_connection = None
            raise # Re-raise the exception to be caught in __init__

    def _can_execute(self, gesture_name: str) -> bool:
        """Checks if the action for the gesture can be executed based on debounce timer."""
        current_time = time.time() * 1000 # milliseconds
        last_time = self.last_action_time.get(gesture_name, 0)
        if current_time - last_time > self.action_debounce_ms:
            self.last_action_time[gesture_name] = current_time
            return True
        return False

    def execute_action(self, gesture_name: str, landmarks=None):
        """
        Executes the action mapped to the given gesture name.

        Args:
            gesture_name (str): The name of the recognized gesture.
            landmarks (list, optional): The list of detected hand landmarks.
                                        Required for actions like mouse control.
        """
        if not gesture_name or gesture_name == 'NO_HAND':
            # Handle potential mouse control deactivation when no hand/gesture is detected
            if self.pyautogui_enabled and self.mouse_control_active:
                 logging.debug("Deactivating mouse control due to lack of gesture.")
                 self.mouse_control_active = False
                 self.prev_mouse_landmark = None
            return

        action_config = self.gesture_map.get(gesture_name)

        if not action_config:
            # Check if this gesture is meant for mouse control activation/deactivation
            if self.pyautogui_enabled and gesture_name == self.mouse_control_gesture:
                if not self.mouse_control_active:
                    logging.info(f"Activating mouse control with gesture: {gesture_name}")
                    self.mouse_control_active = True
                    self.prev_mouse_landmark = None # Reset previous landmark on activation
            elif self.pyautogui_enabled and self.mouse_control_active:
                # If mouse control is active, but the current gesture isn't the control gesture,
                # potentially deactivate it or handle other gestures if configured.
                # For now, we just keep it active until NO_HAND or the control gesture again?
                # Or maybe deactivate if *any* other *mapped* gesture is detected?
                # Let's deactivate if another mapped gesture occurs.
                # if gesture_name in self.gesture_map: # Check if it's a mapped action gesture
                #    logging.debug(f"Deactivating mouse control due to other action gesture: {gesture_name}")
                #    self.mouse_control_active = False
                #    self.prev_mouse_landmark = None
                pass # Keep mouse control active unless explicitly stopped or another action occurs

            # If mouse control is active, perform mouse movement regardless of other mappings
            if self.pyautogui_enabled and self.mouse_control_active and landmarks:
                self._handle_mouse_movement(landmarks)
                return # Don't process other actions if mouse control is active

            # logging.debug(f"No action configured for gesture: {gesture_name}")
            return # No specific action mapped, and not a mouse control trigger/movement

        # --- Debounce Check ---
        if not self._can_execute(gesture_name):
            # logging.debug(f"Debouncing action for gesture: {gesture_name}")
            return

        action_type = action_config.get('action')
        command = action_config.get('command')

        logging.info(f"Executing action for gesture '{gesture_name}': Type='{action_type}', Command='{command}'")

        try:
            # --- PyAutoGUI Actions ---
            if action_type == 'keyboard' and self.pyautogui_enabled:
                if not command:
                    logging.warning(f"Keyboard action for '{gesture_name}' has no command.")
                    return
                # Simple parsing for hotkeys vs single keys
                keys = command.split('+')
                if len(keys) > 1:
                    pyautogui.hotkey(*keys)
                else:
                    pyautogui.press(keys[0])
                logging.debug(f"Executed keyboard command: {command}")

            elif action_type == 'mouse' and self.pyautogui_enabled:
                if command == 'click':
                    pyautogui.click()
                    logging.debug("Executed mouse click.")
                elif command == 'right_click':
                    pyautogui.rightClick()
                    logging.debug("Executed mouse right click.")
                elif command == 'double_click':
                    pyautogui.doubleClick()
                    logging.debug("Executed mouse double click.")
                elif command == 'scroll_up':
                    amount = action_config.get('amount', 100) # Configurable scroll amount
                    pyautogui.scroll(amount)
                    logging.debug(f"Executed mouse scroll up by {amount}.")
                elif command == 'scroll_down':
                    amount = action_config.get('amount', 100)
                    pyautogui.scroll(-amount) # Negative for down scroll
                    logging.debug(f"Executed mouse scroll down by {amount}.")
                # Add more mouse commands as needed (drag, specific positions, etc.)
                else:
                    logging.warning(f"Unknown mouse command '{command}' for gesture '{gesture_name}'.")

            # --- PySerial Actions ---
            elif action_type == 'serial' and self.pyserial_enabled:
                if not self.serial_connection or not self.serial_connection.is_open:
                    logging.warning("Serial action requested, but connection is not available.")
                    # Optionally try to reconnect?
                    # try: self._init_serial()
                    # except: pass # Ignore reconnect failure here
                    return
                if not command:
                    logging.warning(f"Serial action for '{gesture_name}' has no command.")
                    return

                # Send command, ensuring it ends with a newline for Arduino compatibility
                command_bytes = (command + '\n').encode('utf-8')
                self.serial_connection.write(command_bytes)
                logging.debug(f"Sent serial command: {command}")
                # Optional: Read response?
                # response = self.serial_connection.readline().decode('utf-8').strip()
                # if response: logging.debug(f"Received serial response: {response}")

            # --- Unknown Action Type ---
            elif action_type:
                logging.warning(f"Unsupported action type '{action_type}' for gesture '{gesture_name}'.")

        except Exception as e:
            logging.error(f"Error executing action for gesture '{gesture_name}': {e}")
            # Reset debounce timer in case of error to allow retrying
            if gesture_name in self.last_action_time:
                 del self.last_action_time[gesture_name]
            # Handle specific library errors if needed
            if isinstance(e, pyautogui.PyAutoGUIException):
                logging.error("PyAutoGUI specific error occurred.")
            elif PYSERIAL_AVAILABLE and isinstance(e, serial.SerialException):
                logging.error("Serial communication error occurred. Closing connection.")
                self.close() # Attempt to close faulty connection
                self.pyserial_enabled = False # Disable further serial attempts


    def _handle_mouse_movement(self, landmarks):
        """
        Controls the mouse pointer based on hand landmarks (e.g., index finger tip).
        Uses relative movement based on the change from the previous frame.

        Args:
            landmarks: List of normalized hand landmarks from MediaPipe.
        """
        if not self.pyautogui_enabled or not landmarks or len(landmarks) <= 8:
             # Ensure landmarks are valid and index finger tip (landmark 8) exists
            self.prev_mouse_landmark = None # Reset if landmarks are invalid
            return

        # Use the tip of the index finger (landmark 8) for control
        index_tip = landmarks[8]
        # Landmarks are normalized (0.0 to 1.0). Convert to screen coordinates.
        # Invert Y-axis because landmark Y increases downwards, screen Y increases upwards.
        target_x = int(index_tip.x * self.screen_width)
        target_y = int((1.0 - index_tip.y) * self.screen_height) # Invert Y

        if self.prev_mouse_landmark:
            # Calculate relative movement
            prev_x = int(self.prev_mouse_landmark.x * self.screen_width)
            prev_y = int((1.0 - self.prev_mouse_landmark.y) * self.screen_height)

            # Apply sensitivity factor
            delta_x = int((target_x - prev_x) * self.mouse_sensitivity)
            delta_y = int((target_y - prev_y) * self.mouse_sensitivity)

            # Use moveRel for smoother relative movement
            if abs(delta_x) > 1 or abs(delta_y) > 1: # Add a small threshold to avoid jitter
                pyautogui.moveRel(delta_x, delta_y, duration=0) # Duration 0 for immediate move
                # logging.debug(f"Mouse moveRel: dx={delta_x}, dy={delta_y}")

        # Update previous landmark position for the next frame
        self.prev_mouse_landmark = index_tip

        # Optional: Absolute positioning (can be jittery)
        # pyautogui.moveTo(target_x, target_y, duration=0.1)


    def close(self):
        """Closes any open connections (like serial)."""
        if self.serial_connection and self.serial_connection.is_open:
            try:
                self.serial_connection.close()
                logging.info("Serial connection closed.")
            except Exception as e:
                logging.error(f"Error closing serial connection: {e}")
        self.serial_connection = None

# Example Usage (for testing purposes, typically instantiated by the main application)
if __name__ == '__main__':
    print("Testing ActionHandler...")

    # Sample configuration
    test_config = {
        "gestures": {
            "FIST": {"action": "keyboard", "command": "ctrl+alt+t"}, # Example: Open terminal on Linux
            "OPEN_PALM": {"action": "mouse", "command": "click"},
            "THUMBS_UP": {"action": "serial", "command": "LED_ON"},
            "THUMBS_DOWN": {"action": "serial", "command": "LED_OFF"},
            "POINTING_INDEX": {"action": "mouse", "command": "scroll_up", "amount": 50},
            "VICTORY": {"action": "keyboard", "command": "win"}, # Example: Open Start menu on Windows
        },
        "serial": {
            "enabled": True,
            "port": "auto",  # Or specify directly e.g., "COM3" or "/dev/ttyACM0"
            "baudrate": 9600,
            "timeout": 1
        },
        "pyautogui": {
            "enabled": True,
            "pause_between_actions": 0.1,
            "failsafe": True
        },
        "action_debounce_ms": 300 # Only allow actions every 300ms
    }

    # --- Platform specific adjustments for testing ---
    if platform.system() == "Windows":
        test_config["gestures"]["FIST"] = {"action": "keyboard", "command": "win+r"} # Run dialog
    elif platform.system() == "Darwin": # macOS
         test_config["gestures"]["FIST"] = {"action": "keyboard", "command": "command+space"} # Spotlight
         test_config["gestures"]["VICTORY"] = {"action": "keyboard", "command": "command"} # Command key press

    # --- Initialize Action Handler ---
    action_handler = ActionHandler(test_config)

    # --- Simulate Gesture Recognition ---
    print("\nSimulating gestures (check output/effects):")

    if action_handler.pyautogui_enabled:
        print("Testing PyAutoGUI - FIST (e.g., open terminal/run)...")
        action_handler.execute_action("FIST")
        time.sleep(2)

        print("Testing PyAutoGUI - OPEN_PALM (click)...")
        # Move mouse slightly first so click has an effect
        try: pyautogui.moveRel(20, 0, duration=0.2)
        except NameError: pass # pyautogui might not be imported
        action_handler.execute_action("OPEN_PALM")
        time.sleep(1)

        print("Testing PyAutoGUI - POINTING_INDEX (scroll up)...")
        action_handler.execute_action("POINTING_INDEX")
        time.sleep(1)

        print("Testing PyAutoGUI - VICTORY (e.g., Win/Cmd key)...")
        action_handler.execute_action("VICTORY")
        time.sleep(1)

        print("Testing Debounce (rapid OPEN_PALM clicks - only first should work)...")
        action_handler.execute_action("OPEN_PALM") # Should work
        time.sleep(0.1)
        action_handler.execute_action("OPEN_PALM") # Should be debounced
        time.sleep(0.1)
        action_handler.execute_action("OPEN_PALM") # Should be debounced
        time.sleep(0.5) # Wait longer than debounce
        action_handler.execute_action("OPEN_PALM") # Should work again
        time.sleep(1)


    if action_handler.pyserial_enabled and action_handler.serial_connection:
        print("Testing PySerial - THUMBS_UP (LED_ON)...")
        action_handler.execute_action("THUMBS_UP")
        time.sleep(1) # Give time for serial device to react

        print("Testing PySerial - THUMBS_DOWN (LED_OFF)...")
        action_handler.execute_action("THUMBS_DOWN")
        time.sleep(1)
    elif test_config.get("serial", {}).get("enabled"):
         print("Serial configured but connection failed or library unavailable. Skipping serial tests.")

    print("\nTesting unknown gesture...")
    action_handler.execute_action("UNKNOWN_GESTURE") # Should do nothing silently

    print("\nTesting gesture with no command...")
    test_config["gestures"]["NEW_GESTURE"] = {"action": "keyboard"} # Missing command
    action_handler.config = test_config # Update handler's config view
    action_handler.gesture_map = test_config.get('gestures', {})
    action_handler.execute_action("NEW_GESTURE") # Should log warning

    # --- Cleanup ---
    print("\nClosing connections...")
    action_handler.close()

    print("\nActionHandler test finished.")