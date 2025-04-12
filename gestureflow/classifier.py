```python
# -*- coding: utf-8 -*-
"""
GestureFlow Interface: Hand Gesture Classifier

This module defines the GestureClassifier class responsible for identifying
predefined hand gestures based on the geometric properties of hand landmarks
detected by MediaPipe.
"""

import math
import numpy as np
from typing import List, Optional, Any

# --- Project-Level Library Imports ---
# These libraries are essential for the overall GestureFlow project,
# though not all are directly used within this specific classifier file.
# import cv2
# import mediapipe as mp
# import pyautogui # Optional: For OS control actions
# import serial    # Optional: For hardware communication (e.g., Arduino)
# --- End Project-Level Imports ---


class GestureClassifier:
    """
    Classifies hand gestures based on the spatial arrangement of landmarks.

    Uses geometric heuristics (distances, angles, relative positions)
    to distinguish between predefined gestures like FIST, OPEN_PALM, etc.
    """

    # Define landmark indices for clarity (using MediaPipe Hand convention)
    WRIST = 0
    THUMB_CMC = 1
    THUMB_MCP = 2
    THUMB_IP = 3
    THUMB_TIP = 4
    INDEX_MCP = 5
    INDEX_PIP = 6
    INDEX_DIP = 7
    INDEX_TIP = 8
    MIDDLE_MCP = 9
    MIDDLE_PIP = 10
    MIDDLE_DIP = 11
    MIDDLE_TIP = 12
    RING_MCP = 13
    RING_PIP = 14
    RING_DIP = 15
    RING_TIP = 16
    PINKY_MCP = 17
    PINKY_PIP = 18
    PINKY_DIP = 19
    PINKY_TIP = 20

    # Finger definitions for easier iteration
    FINGERS = {
        "THUMB": [THUMB_TIP, THUMB_IP, THUMB_MCP, THUMB_CMC],
        "INDEX": [INDEX_TIP, INDEX_DIP, INDEX_PIP, INDEX_MCP],
        "MIDDLE": [MIDDLE_TIP, MIDDLE_DIP, MIDDLE_PIP, MIDDLE_MCP],
        "RING": [RING_TIP, RING_DIP, RING_PIP, RING_MCP],
        "PINKY": [PINKY_TIP, PINKY_DIP, PINKY_PIP, PINKY_MCP],
    }
    FINGER_TIPS = [THUMB_TIP, INDEX_TIP, MIDDLE_TIP, RING_TIP, PINKY_TIP]
    FINGER_PIPS = [THUMB_IP, INDEX_PIP, MIDDLE_PIP, RING_PIP, PINKY_PIP] # Note: THUMB_IP is equivalent PIP for thumb
    FINGER_MCPS = [THUMB_MCP, INDEX_MCP, MIDDLE_MCP, RING_MCP, PINKY_MCP]

    def __init__(self, thresholds: Optional[dict] = None):
        """
        Initializes the GestureClassifier.

        Args:
            thresholds (Optional[dict]): A dictionary to override default
                                         detection thresholds. If None, defaults
                                         are used.
        """
        self.thresholds = thresholds if thresholds else self._default_thresholds()
        # Pre-calculate or store any static data if needed

    def _default_thresholds(self) -> dict:
        """
        Defines default thresholds for various gesture detection heuristics.
        These values may require tuning based on performance and specific camera setup.
        """
        return {
            # Factor for comparing tip-MCP vs PIP-MCP distance for extension
            "FINGER_EXTEND_FACTOR": 1.6,
            # Factor for comparing tip-MCP vs PIP-MCP distance for curling
            "FINGER_CURL_FACTOR": 1.0, # Tip closer to MCP than PIP is from MCP implies curl
             # Max distance factor (tip to wrist / wrist to middle MCP) for fist
            "FIST_MAX_TIP_WRIST_FACTOR": 0.6,
            # Min distance factor (thumb tip to index MCP / index MCP to pinky MCP) for thumb abduction in open palm
            "OPEN_PALM_THUMB_ABDUCTION_FACTOR": 0.7,
            # Min Y-coord diff factor (tip.y vs mcp.y / wrist-mcp distance) for thumbs up
            "THUMBS_UP_Y_FACTOR": -0.1, # Thumb tip should be significantly above MCP (negative Y direction in image coords)
            # Max distance factor for curled fingers in specific gestures (pointing, victory, thumbs up)
            "CURL_MAX_TIP_MCP_FACTOR": 1.2, # Allow slightly more tolerance than strict curl
        }

    def _get_landmark(self, landmarks: List[Any], index: int) -> Optional[Any]:
        """Safely retrieves a landmark object by its index."""
        if landmarks and 0 <= index < len(landmarks):
            # Assuming landmarks are objects with x, y, z attributes
            if hasattr(landmarks[index], 'x') and \
               hasattr(landmarks[index], 'y') and \
               hasattr(landmarks[index], 'z'):
                return landmarks[index]
        return None

    def _calculate_distance(self, p1: Any, p2: Any) -> float:
        """
        Calculates the Euclidean distance between two landmark points.
        Assumes landmarks have 'x', 'y', 'z' attributes.
        Returns float('inf') if either point is invalid.
        """
        if p1 is None or p2 is None:
            return float('inf')
        try:
            return math.sqrt((p1.x - p2.x)**2 + (p1.y - p2.y)**2 + (p1.z - p2.z)**2)
        except AttributeError:
            # Handle cases where landmarks might not have x, y, z (e.g., visibility check failed)
            return float('inf')
        except Exception as e:
            print(f"Error calculating distance: {e}")
            return float('inf')

    def _is_finger_extended(self, landmarks: List[Any], tip_idx: int, pip_idx: int, mcp_idx: int) -> bool:
        """
        Checks if a finger is extended based on relative distances.
        Compares distance from tip to MCP vs distance from PIP to MCP.
        """
        tip = self._get_landmark(landmarks, tip_idx)
        pip = self._get_landmark(landmarks, pip_idx)
        mcp = self._get_landmark(landmarks, mcp_idx)

        if not all([tip, pip, mcp]):
            return False # Cannot determine state if landmarks are missing

        dist_tip_mcp = self._calculate_distance(tip, mcp)
        dist_pip_mcp = self._calculate_distance(pip, mcp)

        # Avoid division by zero or near-zero, indicates unreliable landmark data
        if dist_pip_mcp < 1e-6:
            return False

        # Finger is extended if the tip is significantly farther from the MCP than the PIP is.
        extend_factor = self.thresholds.get("FINGER_EXTEND_FACTOR", 1.6)
        return (dist_tip_mcp / dist_pip_mcp) > extend_factor

    def _is_finger_curled(self, landmarks: List[Any], tip_idx: int, pip_idx: int, mcp_idx: int) -> bool:
        """
        Checks if a finger is curled based on relative distances.
        Compares distance from tip to MCP vs distance from PIP to MCP.
        """
        tip = self._get_landmark(landmarks, tip_idx)
        pip = self._get_landmark(landmarks, pip_idx)
        mcp = self._get_landmark(landmarks, mcp_idx)

        if not all([tip, pip, mcp]):
            return False # Cannot determine state

        dist_tip_mcp = self._calculate_distance(tip, mcp)
        dist_pip_mcp = self._calculate_distance(pip, mcp)

        if dist_pip_mcp < 1e-6:
            # If PIP and MCP are very close, check if tip is also very close
            return dist_tip_mcp < 0.05 # Use a small absolute threshold (needs tuning)

        # Finger is curled if the tip is closer to the MCP than the PIP is (or not significantly farther).
        curl_factor = self.thresholds.get("FINGER_CURL_FACTOR", 1.0)
        return (dist_tip_mcp / dist_pip_mcp) < curl_factor

    # --- Specific Gesture Logic ---

    def _is_fist(self, landmarks: List[Any]) -> bool:
        """Checks if the hand configuration resembles a fist."""
        wrist = self._get_landmark(landmarks, self.WRIST)
        middle_mcp = self._get_landmark(landmarks, self.MIDDLE_MCP)
        if not wrist or not middle_mcp: return False

        # Reference distance: wrist to middle finger MCP
        ref_dist = self._calculate_distance(wrist, middle_mcp)
        if ref_dist < 1e-6: return False # Avoid division by zero

        # Check if all non-thumb fingertips are close to the wrist/palm center
        max_dist_factor = self.thresholds.get("FIST_MAX_TIP_WRIST_FACTOR", 0.6)
        all_fingers_close = True
        for tip_idx in [self.INDEX