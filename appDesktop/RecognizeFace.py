import cv2
import numpy as np
import sqlite3
import os
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QMessageBox, QDesktopWidget
from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtCore import QTimer
from facenet_pytorch import MTCNN, InceptionResnetV1

recognize_face_style = """
QWidget {
    font-family: 'Segoe UI', sans-serif;
    background-color: #f0f4f8;
}

QLabel {
    font-size: 18px;
    color: #00796b;
    margin-bottom: 10px;
}

QLineEdit {
    border: 1px solid #80deea;
    border-radius: 8px;
    padding: 10px;
    font-size: 18px;
    color: #004d40;
    background-color: #ffffff;
}

QLineEdit:focus {
    border: 2px solid #00acc1;
    outline: none;
}

QPushButton {
    font-size: 20px;
    background-color: #00acc1;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 12px;
    margin-top: 10px;
}

QPushButton:hover {
    background-color: #00838f;
}

QPushButton:pressed {
    background-color: #00796b;
}

QMessageBox {
    font-size: 18px;
    background-color: #f0f4f8;
    color: #004d40;
}

QLabel#status_label {
    font-size: 16px;
    color: blue;
}

QVBoxLayout {
    spacing: 10px;
}

QHBoxLayout {
    spacing: 20px;
}
"""


class RecognizeFaceWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Recognize Face')

        # Get screen dimensions and set window size
        screen = QDesktopWidget().screenGeometry()
        window_height = min(800, screen.height() - 100)  # Limit height to screen size
        self.setGeometry(100, 100, 800, window_height)

        # Apply the stylesheet
        self.setStyleSheet(recognize_face_style)

        # Initialize camera and face detection
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            QMessageBox.critical(self, 'Error', 'Could not open camera!')
            return

        # Initialize MTCNN for face detection
        self.mtcnn = MTCNN()

        # Initialize FaceNet for face recognition
        self.facenet = InceptionResnetV1(pretrained='vggface2').eval()

        # Main layout with proper spacing
        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.setContentsMargins(20, 20, 20, 20)

        # Title label
        title_label = QLabel('Face Recognition')
        title_label.setStyleSheet("font-size: 24px; font-weight: bold; color: #00796b; margin-bottom: 20px;")
        layout.addWidget(title_label)

        # Camera feed display
        self.image_label = QLabel()
        self.image_label.setFixedSize(640, 480)
        self.image_label.setStyleSheet("border: 2px solid #80deea; border-radius: 10px; padding: 5px;")
        layout.addWidget(self.image_label)

        # Status label with custom styling
        self.status_label = QLabel('Status: Ready')
        self.status_label.setObjectName("status_label")  # This will apply the #status_label style
        self.status_label.setStyleSheet("""
            QLabel#status_label {
                font-size: 18px;
                color: #00796b;
                padding: 10px;
                background-color: #e0f7fa;
                border-radius: 5px;
                margin-top: 10px;
            }
        """)
        layout.addWidget(self.status_label)

        # Timer for updating camera feed
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(30)

        self.setLayout(layout)

        # Initialize database
        self.db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "FaceBase.db")
        self.known_faces = self.load_database_faces()

    def load_database_faces(self):
        """Load face images, labels, and names from the database and generate embeddings."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("SELECT ID, Name, Image FROM Peoples")
            data = cursor.fetchall()
            conn.close()

            embeddings = []
            labels = []
            names = []  # To store names associated with face IDs

            for user_id, name, image_data in data:
                np_img = np.frombuffer(image_data, np.uint8)
                db_face_image = cv2.imdecode(np_img, cv2.IMREAD_COLOR)  # Load as color image
                if db_face_image is not None:
                    # Detect face and align
                    face = self.mtcnn(db_face_image)
                    if face is not None:
                        # Generate embedding
                        embedding = self.facenet(face.unsqueeze(0)).detach().numpy()
                        embeddings.append(embedding)
                        labels.append(user_id)
                        names.append(name)

            return embeddings, labels, names
        except Exception as e:
            QMessageBox.critical(self, 'Error', f"Failed to load database: {str(e)}")
            return [], [], []

    def update_frame(self):
        ret, frame = self.cap.read()
        if ret:
            # Resize the frame to improve performance
            frame = cv2.resize(frame, (640, 480))

            # Detect faces in the frame
            faces = self.mtcnn.detect(frame)

            if faces[0] is not None:
                for box in faces[0]:
                    x1, y1, x2, y2 = map(int, box)  # Extract and round bounding box coordinates
                    w = x2 - x1
                    h = y2 - y1

                    # Adjust bounding box size and center the face
                    padding = int(0.1 * min(w, h))  # Add padding (10% of the smaller dimension)
                    x1_adj = max(0, x1 - padding)  # Ensure padding doesn't go out of frame
                    y1_adj = max(0, y1 - padding)
                    x2_adj = min(frame.shape[1], x2 + padding)
                    y2_adj = min(frame.shape[0], y2 + padding)

                    # Draw the adjusted bounding box
                    cv2.rectangle(frame,
                                  (x1_adj, y1_adj),
                                  (x2_adj, y2_adj),
                                  (0, 255, 0),
                                  2)

                    # Extract and process the face
                    face_image = frame[y1_adj:y2_adj, x1_adj:x2_adj]
                    face = self.mtcnn(face_image)
                    if face is not None:
                        embedding = self.facenet(face.unsqueeze(0)).detach().numpy()
                        min_distance = float('inf')
                        best_match = None
                        for i, known_embedding in enumerate(self.known_faces[0]):
                            distance = np.linalg.norm(embedding - known_embedding)
                            if distance < min_distance:
                                min_distance = distance
                                best_match = i

                        # Check if the face is recognized
                        if min_distance < 1.0:  # Threshold for face recognition
                            name = self.known_faces[2][best_match]
                        else:
                            name = "Inconnu"  # Unknown face

                        # Display the name
                        cv2.putText(frame, name,
                                    (x1_adj, y1_adj - 10),  # Display above the bounding box
                                    cv2.FONT_HERSHEY_SIMPLEX,
                                    0.8, (0, 255, 0), 2)

            # Convert to RGB for displaying in QLabel
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_frame.shape
            bytes_per_line = ch * w
            qt_image = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
            self.image_label.setPixmap(QPixmap.fromImage(qt_image))

    def closeEvent(self, event):
        self.cap.release()
        event.accept()