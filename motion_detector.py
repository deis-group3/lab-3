"""
Motion Detection Module for Autonomous Vehicle Convoy System
Implements collision detection using background subtraction and motion detection
Integrates with LCM messaging for convoy communication
"""
import cv2
import numpy as np
import time
import threading
import argparse
from datetime import datetime
import lcm
import sys
import os

# Add the generated LCM bindings to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'lcm_generated'))

# Import generated LCM message types
from convoy import heartbeat_t, warning_t, mode_t, status_t

class MotionDetector:
    def __init__(self, camera_id=0, threshold=25, min_area=500, vehicle_id=1):
        """
        Initialize motion detector
        
        Args:
            camera_id: Camera device ID
            threshold: Motion detection threshold
            min_area: Minimum contour area to consider as motion
            vehicle_id: Unique identifier for this vehicle
        """
        self.camera_id = camera_id
        self.threshold = threshold
        self.min_area = min_area
        self.vehicle_id = vehicle_id
        
        # Camera and background subtraction
        self.cap = None
        self.background_subtractor = cv2.createBackgroundSubtractorMOG2(
            detectShadows=True
        )
        
        # State variables
        self.driving_mode = 0  # 0: single, 1: head convoy, 2: in convoy
        self.motion_detected = False
        self.brake_lights_on = False
        self.running = False
        
        # LCM communication - use UDP with TTL=0 for localhost only
        self.lcm = lcm.LCM("udpm://239.255.76.67:7667?ttl=0")
        self.lcm.subscribe("WARNING", self._handle_warning_message)
        self.lcm.subscribe("MODE", self._handle_mode_message)
        
        # Threading
        self.detection_thread = None
        self.heartbeat_thread = None
        self.lcm_thread = None
        
        # Logging
        self.log_messages = []
        
    def initialize_camera(self):
        """Initialize camera capture"""
        self.cap = cv2.VideoCapture(self.camera_id)
        if not self.cap.isOpened():
            raise RuntimeError(f"Cannot open camera {self.camera_id}")
        
        # Set camera properties
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.cap.set(cv2.CAP_PROP_FPS, 30)
        
        print(f"Camera {self.camera_id} initialized")
        
    def detect_motion(self, frame):
        """
        Detect motion in frame using background subtraction
        
        Args:
            frame: Current camera frame
            
        Returns:
            bool: True if motion detected above threshold
        """
        # Apply background subtractor
        fg_mask = self.background_subtractor.apply(frame)
        
        # Remove noise
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN, kernel)
        
        # Find contours
        contours, _ = cv2.findContours(
            fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
        )
        
        # Check if any contour is large enough
        motion_detected = False
        for contour in contours:
            if cv2.contourArea(contour) > self.min_area:
                motion_detected = True
                break
                
        return motion_detected, fg_mask
        
    def process_frame(self):
        """Main frame processing loop"""
        while self.running:
            ret, frame = self.cap.read()
            if not ret:
                print("Failed to read frame")
                break
                
            # Detect motion
            motion_detected, fg_mask = self.detect_motion(frame)
            self.motion_detected = motion_detected
            
            # Handle different driving modes
            self.handle_driving_mode()
            
            # Display frame (optional, for debugging)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
            time.sleep(0.033)  # ~30 FPS
            
    def handle_driving_mode(self):
        """Handle actions based on current driving mode and motion detection"""
        current_time = time.time()
        
        if self.driving_mode == 0:  # Single vehicle driving
            if self.motion_detected:
                self.turn_on_brake_lights()
                self.log_event("Mode 0: Object detected, brake lights ON")
            else:
                self.turn_off_brake_lights()
                
        elif self.driving_mode == 1:  # Head in convoy
            if self.motion_detected:
                self.turn_on_brake_lights()
                self.send_warning_message(current_time)
                self.log_event("Mode 1: Object detected, brake lights ON, warning sent")
            else:
                self.turn_off_brake_lights()
                
        elif self.driving_mode == 2:  # In convoy
            # Brake lights controlled by warning messages from head vehicle
            pass
            
    def turn_on_brake_lights(self):
        """Simulate turning on brake lights"""
        if not self.brake_lights_on:
            self.brake_lights_on = True
            print(f"[{datetime.now().strftime('%H:%M:%S')}] BRAKE LIGHTS ON")
            
    def turn_off_brake_lights(self):
        """Simulate turning off brake lights"""
        if self.brake_lights_on:
            self.brake_lights_on = False
            print(f"[{datetime.now().strftime('%H:%M:%S')}] BRAKE LIGHTS OFF")
            
    def send_heartbeat(self):
        """Send heartbeat message every second for convoy modes"""
        while self.running:
            if self.driving_mode in [1, 2]:
                current_time = int(time.time() * 1000000)  # Convert to microseconds
                heartbeat = heartbeat_t()
                heartbeat.timestamp = current_time
                heartbeat.vehicle_id = self.vehicle_id
                
                self.lcm.publish("HEARTBEAT", heartbeat.encode())
                self.log_event(f"Heartbeat sent from vehicle {self.vehicle_id}: {current_time}")
                
            time.sleep(1.0)
            
    def send_warning_message(self, timestamp, description="Motion detected"):
        """Send warning message to convoy"""
        warning = warning_t()
        warning.timestamp = int(timestamp * 1000000)  # Convert to microseconds
        warning.vehicle_id = self.vehicle_id
        warning.danger_detected = True
        warning.description = description
        
        self.lcm.publish("WARNING", warning.encode())
        self.log_event(f"Warning message sent from vehicle {self.vehicle_id}: {timestamp}")
        
    def handle_warning_message(self, timestamp):
        """Handle received warning message (for mode 2)"""
        if self.driving_mode == 2:
            self.turn_on_brake_lights()
            # Repeat warning message
            self.send_warning_message(timestamp, "Warning relayed")
            self.log_event(f"Warning received and repeated: {timestamp}")
    
    def _handle_warning_message(self, channel, data):
        """LCM handler for warning messages"""
        try:
            msg = warning_t.decode(data)
            if msg.vehicle_id != self.vehicle_id:  # Don't handle our own messages
                timestamp = msg.timestamp / 1000000.0  # Convert back to seconds
                self.log_event(f"Received warning from vehicle {msg.vehicle_id}: {msg.description}")
                if self.driving_mode == 2:
                    self.handle_warning_message(timestamp)
        except Exception as e:
            self.log_event(f"Error handling warning message: {e}")
    
    def _handle_mode_message(self, channel, data):
        """LCM handler for mode change messages"""
        try:
            msg = mode_t.decode(data)
            if msg.vehicle_id != self.vehicle_id:  # Don't handle our own messages
                self.log_event(f"Vehicle {msg.vehicle_id} changed mode to {msg.mode}: {msg.mode_description}")
        except Exception as e:
            self.log_event(f"Error handling mode message: {e}")
            
    def set_driving_mode(self, mode):
        """Set driving mode"""
        if mode in [0, 1, 2]:
            old_mode = self.driving_mode
            self.driving_mode = mode
            
            # Send mode change message
            mode_names = ["Single Vehicle", "Head in Convoy", "In Convoy"]
            mode_msg = mode_t()
            mode_msg.timestamp = int(time.time() * 1000000)
            mode_msg.vehicle_id = self.vehicle_id
            mode_msg.mode = mode
            mode_msg.mode_description = mode_names[mode]
            
            self.lcm.publish("MODE", mode_msg.encode())
            
            self.log_event(f"Driving mode changed from {old_mode} to {mode} ({mode_names[mode]})")
            print(f"Driving mode set to: {mode} ({mode_names[mode]})")
        else:
            print(f"Invalid driving mode: {mode}")
            
    def log_event(self, message):
        """Log events with timestamp"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
        log_entry = f"[{timestamp}] {message}"
        self.log_messages.append(log_entry)
        print(log_entry)
        

    def _lcm_handler_loop(self):
        """LCM message handling loop"""
        while self.running:
            try:
                # Handle LCM messages with timeout
                self.lcm.handle_timeout(100)  # 100ms timeout
            except Exception as e:
                if self.running:  # Only log if we're still running
                    self.log_event(f"LCM handler error: {e}")
    
    def send_status_message(self):
        """Send comprehensive status message"""
        status = status_t()
        status.timestamp = int(time.time() * 1000000)
        status.vehicle_id = self.vehicle_id
        status.driving_mode = self.driving_mode
        status.motion_detected = self.motion_detected
        status.brake_lights_on = self.brake_lights_on
        status.system_running = self.running
        status.status_message = f"Vehicle {self.vehicle_id} operational"
        
        self.lcm.publish("STATUS", status.encode())
        self.log_event(f"Status message sent from vehicle {self.vehicle_id}")

    def start(self):
        """Start the motion detection system"""
        try:
            self.initialize_camera()
            self.running = True
            
            # Start detection thread
            self.detection_thread = threading.Thread(target=self.process_frame)
            self.detection_thread.start()
            
            # Start heartbeat thread
            self.heartbeat_thread = threading.Thread(target=self.send_heartbeat)
            self.heartbeat_thread.start()
            
            # Start LCM handler thread
            self.lcm_thread = threading.Thread(target=self._lcm_handler_loop)
            self.lcm_thread.start()
            
            print(f"Motion detection system started for vehicle {self.vehicle_id}")
            print("Commands:")
            print("  0, 1, 2: Set driving mode")
            print("  s: Show status")
            print("  l: Show logs")
            print("  st: Send status message")
            print("  w: Simulate warning (for testing)")
            print("  q: Quit")
            
            # Command loop
            while self.running:
                try:
                    cmd = input().strip().lower()
                    if cmd == 'q':
                        break
                    elif cmd in ['0', '1', '2']:
                        self.set_driving_mode(int(cmd))
                    elif cmd == 's':
                        self.show_status()
                    elif cmd == 'l':
                        self.show_logs()
                    elif cmd == 'st':
                        self.send_status_message()
                    elif cmd == 'w':  # Simulate warning for testing
                        self.send_warning_message(time.time(), "Manual test warning")
                except KeyboardInterrupt:
                    break
                    
        except Exception as e:
            print(f"Error: {e}")
        finally:
            self.stop()
            
    def show_status(self):
        """Show current system status"""
        mode_names = ["Single Vehicle", "Head in Convoy", "In Convoy"]
        print(f"\n=== Status ===")
        print(f"Driving Mode: {self.driving_mode} ({mode_names[self.driving_mode]})")
        print(f"Motion Detected: {self.motion_detected}")
        print(f"Brake Lights: {'ON' if self.brake_lights_on else 'OFF'}")
        print(f"System Running: {self.running}")
        print()
        
    def show_logs(self):
        """Show recent log messages"""
        print(f"\n=== Recent Logs ===")
        for log in self.log_messages[-10:]:  # Show last 10 logs
            print(log)
        print()
        
    def stop(self):
        """Stop the motion detection system"""
        self.running = False
        
        if self.detection_thread and self.detection_thread.is_alive():
            self.detection_thread.join()
            
        if self.heartbeat_thread and self.heartbeat_thread.is_alive():
            self.heartbeat_thread.join()
            
        if self.lcm_thread and self.lcm_thread.is_alive():
            self.lcm_thread.join()
            
        if self.cap:
            self.cap.release()
            
        cv2.destroyAllWindows()
        print("Motion detection system stopped")

def main():
    parser = argparse.ArgumentParser(description='Motion Detection for Convoy System')
    parser.add_argument('--camera', type=int, default=0, help='Camera device ID')
    parser.add_argument('--threshold', type=int, default=25, help='Motion detection threshold')
    parser.add_argument('--min-area', type=int, default=500, help='Minimum contour area')
    parser.add_argument('--mode', type=int, choices=[0, 1, 2], default=0, help='Initial driving mode')
    parser.add_argument('--vehicle-id', type=int, default=1, help='Unique vehicle identifier')
    
    args = parser.parse_args()
    
    detector = MotionDetector(
        camera_id=args.camera,
        threshold=args.threshold,
        min_area=args.min_area,
        vehicle_id=args.vehicle_id
    )
    
    detector.set_driving_mode(args.mode)
    detector.start()

if __name__ == "__main__":
    main()