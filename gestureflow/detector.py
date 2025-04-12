# gestureflow/detector.py

import cv2
import mediapipe as mp
import numpy as np
from typing import List, Optional, Tuple, Any

class HandDetector:
    """
    Detects hands and extracts landmarks from image frames using MediaPipe Hands.
    """

    def __init__(self,
                 static_image_mode: bool = False,
                 max_num_hands: int = 2,
                 model_complexity: int = 1,
                 min_detection_confidence: float = 0.5,
                 min_tracking_confidence: float = 0.5):
        """
        Initializes the HandDetector.

        Args:
            static_image_mode: Whether to treat the input images as a batch of static
                               and possibly unrelated images, or a video stream.
            max_num_hands: Maximum number of hands to detect.
            model_complexity: Complexity of the hand landmark model (0 or 1).
            min_detection_confidence: Minimum confidence value ([0.0, 1.0]) for hand
                                      detection to be considered successful.
            min_tracking_confidence: Minimum confidence value ([0.0, 1.0]) for the
                                     hand landmarks to be considered tracked successfully.
        """
        self.static_image_mode = static_image_mode
        self.max_num_hands = max_num_hands
        self.model_complexity = model_complexity
        self.min_detection_confidence = min_detection_confidence
        self.min_tracking_confidence = min_tracking_confidence

        # Initialize MediaPipe Hands
        self.mp_hands = mp.solutions.hands
        try:
            self.hands = self.mp_hands.Hands(
                static_image_mode=self.static_image_mode,
                max_num_hands=self.max_num_hands,
                model_complexity=self.model_complexity,
                min_detection_confidence=self.min_detection_confidence,
                min_tracking_confidence=self.min_tracking_confidence
            )
        except Exception as e:
            print(f"Error initializing MediaPipe Hands: {e}")
            # Depending on the desired behavior, you might want to raise the exception
            # or handle it in a way that allows the application to continue degraded.
            self.hands = None # Indicate initialization failure

        self.mp_drawing = mp.solutions.drawing_utils
        self.mp_drawing_styles = mp.solutions.drawing_styles


    def process_frame(self, frame: np.ndarray) -> Tuple[List[Any], Optional[Any]]:
        """
        Processes a single image frame to detect hands and landmarks.

        Args:
            frame: The input image frame (in BGR format).

        Returns:
            A tuple containing:
            - A list of detected hand landmarks. Each element in the list corresponds
              to a detected hand and contains its landmarks. Returns an empty list
              if no hands are detected or if initialization failed.
            - The raw results object from MediaPipe Hands processing. Returns None
              if initialization failed or processing failed.
        """
        if self.hands is None:
            print("Error: Hand detector was not initialized successfully.")
            return [], None

        # Convert the BGR image to RGB
        try:
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        except cv2.error as e:
            print(f"Error converting frame color space: {e}")
            return [], None

        # To improve performance, optionally mark the image as not writeable to
        # pass by reference.
        rgb_frame.flags.writeable = False

        # Process the frame and find hands
        try:
            results = self.hands.process(rgb_frame)
        except Exception as e:
            print(f"Error processing frame with MediaPipe Hands: {e}")
            # Ensure frame is writeable again even if processing fails
            rgb_frame.flags.writeable = True
            return [], None

        # Allow writing to the frame again
        rgb_frame.flags.writeable = True # Although we don't modify rgb_frame here, good practice

        detected_hands_landmarks = []
        if results.multi_hand_landmarks:
            # Extract landmarks for each detected hand
            for hand_landmarks in results.multi_hand_landmarks:
                detected_hands_landmarks.append(hand_landmarks)

        return detected_hands_landmarks, results

    def draw_landmarks(self, frame: np.ndarray, results: Any) -> np.ndarray:
        """
        Draws the detected hand landmarks and connections on the frame.

        Args:
            frame: The image frame (in BGR format) to draw on.
            results: The raw results object from MediaPipe Hands processing
                     (obtained from process_frame).

        Returns:
            The frame with landmarks drawn.
        """
        if results and results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                # Draw landmarks
                self.mp_drawing.draw_landmarks(
                    frame,
                    hand_landmarks,
                    self.mp_hands.HAND_CONNECTIONS,
                    self.mp_drawing_styles.get_default_hand_landmarks_style(),
                    self.mp_drawing_styles.get_default_hand_connections_style())
        return frame

    def close(self):
        """
        Releases MediaPipe Hands resources.
        """
        if hasattr(self, 'hands') and self.hands:
            self.hands.close()
            print("MediaPipe Hands resources released.")


# Example Usage (can be run standalone for testing)
if __name__ == '__main__':
    detector = HandDetector(max_num_hands=2, min_detection_confidence=0.7)

    # Use webcam
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("Error: Could not open webcam.")
        exit()

    print("Starting webcam feed. Press 'q' to quit.")

    while True:
        success, frame = cap.read()
        if not success:
            print("Ignoring empty camera frame.")
            continue

        # Flip the frame horizontally for a later selfie-view display
        # and convert the BGR image to RGB.
        frame = cv2.flip(frame, 1)

        # Process the frame
        landmarks_list, results = detector.process_frame(frame)

        # Draw landmarks on the frame
        annotated_frame = detector.draw_landmarks(frame.copy(), results) # Draw on a copy

        # Display handedness and landmark count (example of using results)
        if results and results.multi_handedness:
             for idx, hand_handedness in enumerate(results.multi_handedness):
                 handedness = hand_handedness.classification[0].label
                 score = hand_handedness.classification[0].score
                 cv2.putText(annotated_frame, f'{handedness} ({score:.2f})',
                             (10, 30 + idx * 30), cv2.FONT_HERSHEY_SIMPLEX,
                             0.7, (0, 255, 0), 2)

        if landmarks_list:
            num_hands = len(landmarks_list)
            # print(f"Detected {num_hands} hand(s).")
            # You could access specific landmarks like:
            # first_hand_wrist = landmarks_list[0].landmark[detector.mp_hands.HandLandmark.WRIST]
            # print(f"First hand wrist coords: ({first_hand_wrist.x}, {first_hand_wrist.y})")
            pass # Placeholder for further processing

        # Display the resulting frame
        cv2.imshow('GestureFlow - Hand Detection Test', annotated_frame)

        # Exit loop if 'q' is pressed
        if cv2.waitKey(5) & 0xFF == ord('q'):
            break

    # Release resources
    detector.close()
    cap.release()
    cv2.destroyAllWindows()
    print("Webcam feed stopped and resources released.")