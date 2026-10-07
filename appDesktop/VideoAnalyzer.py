import cv2
import os
from PyQt5.QtWidgets import QFileDialog, QMessageBox, QWidget, QLabel, QVBoxLayout, QPushButton


class VideoAnalyzer(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Traffic Video Object Detection")

        layout = QVBoxLayout()

        # Status label
        self.status_label = QLabel("Ready to analyze video...")
        layout.addWidget(self.status_label)

        # Analyze button
        self.analyze_button = QPushButton("Analyze Video")
        self.analyze_button.clicked.connect(self.analyze_video)
        layout.addWidget(self.analyze_button)

        self.setLayout(layout)

        # Load pre-trained cascade for detecting people
        self.haarcascade_path = cv2.data.haarcascades + "haarcascade_fullbody.xml"
        if not os.path.exists(self.haarcascade_path):
            QMessageBox.critical(self, 'Error', 'Haar cascade file not found. Ensure OpenCV is installed correctly.')
            self.close()

        self.cascade = cv2.CascadeClassifier(self.haarcascade_path)

    def analyze_video(self):
        """Analyze a video for object detection."""
        try:
            # Open a file dialog to select the video
            video_path, _ = QFileDialog.getOpenFileName(self, 'Select Video', '', 'Video Files (*.mp4 *.avi *.mov)')
            if not video_path:
                self.status_label.setText("No video selected")
                return

            # Open the video file
            cap = cv2.VideoCapture(video_path)
            if not cap.isOpened():
                QMessageBox.critical(self, 'Error', 'Unable to open the video file')
                return

            # Analyze video frames
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break

                # Convert frame to grayscale
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

                # Detect people in the frame
                detections = self.cascade.detectMultiScale(
                    gray,
                    scaleFactor=1.1,
                    minNeighbors=3,
                    minSize=(50, 50)
                )

                # Draw bounding boxes around detections
                for (x, y, w, h) in detections:
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                    label = "Person"
                    cv2.putText(frame, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

                # Display the frame
                cv2.imshow("Video Analysis", frame)

                # Break loop if 'q' is pressed
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

            # Cleanup
            cap.release()
            cv2.destroyAllWindows()

            self.status_label.setText("Video analysis completed")
            QMessageBox.information(self, 'Success', 'Video analysis completed!')

        except Exception as e:
            self.status_label.setText(f"Error: {str(e)}")
            QMessageBox.critical(self, 'Error', f'An error occurred: {str(e)}')
