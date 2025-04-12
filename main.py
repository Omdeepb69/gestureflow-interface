# main.py
# Main application entry point for GestureFlow Interface.

import cv2
import numpy as np
import json
import sys
import os
import time
import mediapipe as mp

# --- Configuration ---
CONFIG_FILE = 'config.json'
DEFAULT_CONFIG = {
    "camera_index": 0,
    "min_detection_confidence": 0.7,
    "min_tracking_confidence": 0.7,
    "gesture_actions": {
        "UNKNOWN": "none",
        "FIST": "print_message:Fist detected!",
        "OPEN_PALM": "print_message:Open Palm detected!",
        "POINTING_UP": "print_message:Pointing Up detected!",
        "THUMBS_UP": "print_message:Thumbs Up detected!",
        "VICTORY": "print_message:Victory detected!"
        # Add more gesture-action mappings here
        # Example: "FIST": "key_press:ctrl+alt+t"
        # Example: "OPEN_PALM": "mouse_click:left"
        # Example: "THUMBS_UP": "serial_write:LED_ON"
    },
    "action_settings": {
        "serial_port": None, # e.g., "COM3" on Windows, "/dev/ttyACM0" on Linux
        "baud_rate": 9600,
        "mouse_sensitivity": 1.0,
        "print_actions": True # Log actions to console
    },
    "visualization": {
        "draw_landmarks": True,
        "draw_bounding_box": False, # Optional: draw bounding box around hand
        "text_color": [255, 255, 255], # White
        "landmark_color": [0, 255, 0], # Green
        "connection_color": [0, 0, 255], # Red
        "font_scale": 1.0,
        "thickness": 2
    }
}

# --- Add project root to Python path ---
# This allows importing modules from the 'gestureflow' directory.
# Assumes 'main.py' is in the project root and 'gestureflow' is a subdirectory.
project_root = os.path.dirname(os.path.abspath(__file__))
gestureflow_path = os.path.join(project_root, 'gestureflow')
if gestureflow_path not in sys.path:
    sys.path.append(project_root)

# --- Import Custom Modules ---
try:
    from gestureflow.detector import GestureDetector
    from gestureflow.classifier import GestureClassifier
    from gestureflow.actions import ActionHandler
except ImportError as e:
    print(f"Error importing GestureFlow modules: {e}")
    print("Please ensure 'gestureflow' directory exists and contains detector.py, classifier.py, and actions.py")
    print(f"Current sys.path: {sys.path}")
    sys.exit(1)

# --- MediaPipe Drawing Utilities ---
mp_drawing = mp.solutions.drawing_utils
mp_hands = mp.solutions.hands

# --- Helper Functions ---
def load_config(config_path):
    """Loads configuration from a JSON file."""
    if not os.path.exists(config_path):
        print(f"Warning: Config file '{config_path}' not found. Using default configuration.")
        # Optionally create a default config file here
        # with open(config_path, 'w') as f:
        #     json.dump(DEFAULT_CONFIG, f, indent=4)
        return DEFAULT_CONFIG
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
            # You might want to add validation here to ensure necessary keys exist
            # Merge with defaults for missing keys if desired
            # For simplicity, we assume the loaded config is sufficient if it loads
            print(f"Configuration loaded from '{config_path}'")
            return config
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON from '{config_path}': {e}")
        print("Using default configuration.")
        return DEFAULT_CONFIG
    except Exception as e:
        print(f"Error loading config file '{config_path}': {e}")
        print("Using default configuration.")
        return DEFAULT_CONFIG

def draw_visualization(frame, hand_landmarks, gesture, config):
    """Draws landmarks and gesture text on the frame."""
    vis_config = config.get('visualization', DEFAULT_CONFIG['visualization'])
    text_color = tuple(vis_config.get('text_color', [255, 255, 255]))
    landmark_color = tuple(vis_config.get('landmark_color', [0, 255, 0]))
    connection_color = tuple(vis_config.get('connection_color', [0, 0, 255]))
    font_scale = vis_config.get('font_scale', 1.0)
    thickness = vis_config.get('thickness', 2)
    draw_landmarks_flag = vis_config.get('draw_landmarks', True)
    draw_bbox_flag = vis_config.get('draw_bounding_box', False)

    # Draw landmarks and connections
    if hand_landmarks and draw_landmarks_flag:
        mp_drawing.draw_landmarks(
            frame,
            hand_landmarks,
            mp_hands.HAND_CONNECTIONS,
            mp_drawing.DrawingSpec(color=landmark_color, thickness=thickness, circle_radius=thickness),
            mp_drawing.DrawingSpec(color=connection_color, thickness=thickness, circle_radius=thickness)
        )

        # Optional: Draw bounding box
        if draw_bbox_flag:
            h, w, _ = frame.shape
            x_coords = [lm.x * w for lm in hand_landmarks.landmark]
            y_coords = [lm.y * h for lm in hand_landmarks.landmark]
            if x_coords and y_coords:
                x_min, x_max = int(min(x_coords)), int(max(x_coords))
                y_min, y_max = int(min(y_coords)), int(max(y_coords))
                padding = 20 # Add some padding
                cv2.rectangle(frame, (x_min - padding, y_min - padding),
                              (x_max + padding, y_max + padding), landmark_color, thickness)

    # Display the recognized gesture
    if gesture and gesture != "UNKNOWN":
        cv2.putText(frame, f"Gesture: {gesture}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, font_scale, text_color, thickness, cv2.LINE_AA)
    elif hand_landmarks:
         cv2.putText(frame, "Gesture: UNKNOWN", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, font_scale, text_color, thickness, cv2.LINE_AA)

    return frame

# --- Main Application ---
def main():
    """Main application function."""
    print("Starting GestureFlow Interface...")

    # 1. Load Configuration
    config = load_config(CONFIG_FILE)

    # 2. Initialization
    try:
        # Webcam
        camera_index = config.get('camera_index', DEFAULT_CONFIG['camera_index'])
        cap = cv2.VideoCapture(camera_index)
        if not cap.isOpened():
            print(f"Error: Could not open webcam with index {camera_index}.")
            sys.exit(1)
        print(f"Webcam {camera_index} opened successfully.")

        # Gesture Detector
        detector = GestureDetector(
            min_detection_confidence=config.get('min_detection_confidence', DEFAULT_CONFIG['min_detection_confidence']),
            min_tracking_confidence=config.get('min_tracking_confidence', DEFAULT_CONFIG['min_tracking_confidence'])
        )
        print("GestureDetector initialized.")

        # Gesture Classifier
        # Pass any necessary classification parameters from config if needed
        classifier = GestureClassifier()
        print("GestureClassifier initialized.")

        # Action Handler
        action_handler = ActionHandler(config)
        print("ActionHandler initialized.")

    except Exception as e:
        print(f"Initialization failed: {e}")
        if 'cap' in locals() and cap.isOpened():
            cap.release()
        sys.exit(1)

    # --- Main Loop ---
    print("Starting main loop... Press 'q' to quit.")
    last_gesture = None
    gesture_start_time = None
    debounce_time = 0.3 # Seconds to wait before repeating an action for the same gesture

    try:
        while True:
            # Read frame
            success, frame = cap.read()
            if not success:
                print("Error: Failed to read frame from webcam.")
                time.sleep(1) # Wait a bit before retrying
                continue

            # Flip the frame horizontally for a later selfie-view display
            # Also convert the BGR image to RGB before processing
            frame = cv2.flip(frame, 1)
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # Process the frame
            rgb_frame.flags.writeable = False # Optimize performance
            results = detector.detect(rgb_frame)
            rgb_frame.flags.writeable = True

            # Convert back to BGR for OpenCV display
            bgr_frame = cv2.cvtColor(rgb_frame, cv2.COLOR_RGB2BGR)

            recognized_gesture = "UNKNOWN"
            hand_landmarks = None

            # Check if hands were detected
            if results.multi_hand_landmarks:
                # For simplicity, process only the first detected hand
                hand_landmarks = results.multi_hand_landmarks[0]

                # Classify gesture
                recognized_gesture = classifier.classify(hand_landmarks)

                # Execute action (with debounce)
                current_time = time.time()
                if recognized_gesture != "UNKNOWN":
                    if recognized_gesture != last_gesture or \
                       (gesture_start_time is None or current_time - gesture_start_time > debounce_time):
                        action_handler.execute(recognized_gesture, hand_landmarks, frame.shape) # Pass landmarks and frame shape if needed by actions
                        last_gesture = recognized_gesture
                        gesture_start_time = current_time
                else:
                    # Reset if gesture is lost or becomes unknown
                    last_gesture = "UNKNOWN"
                    gesture_start_time = None


            # Visualization
            visualized_frame = draw_visualization(bgr_frame, hand_landmarks, recognized_gesture, config)

            # Display frame
            cv2.imshow('GestureFlow Interface', visualized_frame)

            # Exit condition
            if cv2.waitKey(5) & 0xFF == ord('q'):
                print("Exit key 'q' pressed. Shutting down.")
                break

    except KeyboardInterrupt:
        print("Keyboard interrupt received. Shutting down.")
    except Exception as e:
        print(f"An error occurred during the main loop: {e}")
    finally:
        # Cleanup
        print("Releasing resources...")
        if cap.isOpened():
            cap.release()
        cv2.destroyAllWindows()
        action_handler.cleanup() # Allow action handler to release resources (e.g., serial port)
        print("GestureFlow Interface stopped.")

if __name__ == "__main__":
    main()