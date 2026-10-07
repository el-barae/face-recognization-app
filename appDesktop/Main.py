import sys
import os
import sqlite3
import numpy as np
import cv2
from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QPushButton, QLabel, QWidget, QMessageBox, \
    QFileDialog

import AddToDatabase
import RecognizeFace
import VideoAnalyzer


# Add your style to the app
app_style = """
QWidget {
    font-family: 'Segoe UI', sans-serif;
    background-color: #e0f7fa;
}
QLabel {
    font-size: 20px;
    color: #006064;
}
QPushButton {
    font-size: 20px;  /* Slightly smaller font size for buttons */
    background-color: #00acc1;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 12px 20px;  /* Adjusted padding for better button size */
    margin: 5px 0;
    min-width: 200px;  /* Set a minimum width for buttons */
}
QPushButton:hover {
    background-color: #00838f;
}
QPushButton:pressed {
    background-color: #006064;
}
QMessageBox {
    font-size: 18px;
    background-color: #e0f7fa;
    color: #004d40;
}
"""

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Face Recognition System')
        self.setGeometry(100, 100, 600, 400)

        layout = QVBoxLayout()

        title_label = QLabel('Face Recognition System')
        title_label.setStyleSheet("font-size: 28px; font-weight: bold; color: #006064; margin-bottom: 20px;")
        title_label.setAlignment(Qt.AlignCenter)  # Center-align the title
        layout.addWidget(title_label)

        self.add_button = QPushButton('Add Face to Database')
        self.add_button.clicked.connect(self.open_add_to_database_window)
        layout.addWidget(self.add_button)

        self.recognize_button = QPushButton('Recognize Face')
        self.recognize_button.clicked.connect(self.open_recognize_face_window)
        layout.addWidget(self.recognize_button)

        self.train_button = QPushButton('Train Model')  # New Train Model Button
        self.train_button.clicked.connect(self.train_model)
        layout.addWidget(self.train_button)

        self.analyze_button = QPushButton('Analyze Video')  # New Analyze Video Button
        self.analyze_button.clicked.connect(self.analyze_video)
        layout.addWidget(self.analyze_button)

        self.add_dataset_button = QPushButton('Add folder to Database')  # New Add Dataset Button
        self.add_dataset_button.clicked.connect(self.add_dataset)
        layout.addWidget(self.add_dataset_button)

        self.status_label = QLabel('Status: Ready')  # Status Label for Updates
        layout.addWidget(self.status_label)

        central_widget = QWidget()
        central_widget.setLayout(layout)
        self.setCentralWidget(central_widget)

        # Apply the app style
        self.setStyleSheet(app_style)

    def open_add_to_database_window(self):
        self.add_window = AddToDatabase.AddToDatabaseWindow()
        self.add_window.show()

    def open_recognize_face_window(self):
        self.recognize_window = RecognizeFace.RecognizeFaceWindow()
        self.recognize_window.show()

    def train_model(self):
        """Train the face recognition model using database images."""
        try:
            # Database connection
            db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "FaceBase.db")
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Fetch IDs and images from the database
            cursor.execute("SELECT ID, Image FROM Peoples")
            data = cursor.fetchall()
            conn.close()

            if not data:
                self.status_label.setText("No data available for training")
                QMessageBox.warning(self, 'Error', 'No data available for training!')
                return

            # Prepare training data
            labels = []
            faces = []
            invalid_entries = 0

            for user_id, image_data in data:
                if not image_data:
                    invalid_entries += 1
                    continue
                try:
                    # Decode image
                    np_array = np.frombuffer(image_data, dtype=np.uint8)
                    img = cv2.imdecode(np_array, cv2.IMREAD_GRAYSCALE)
                    if img is None or img.size == 0:
                        invalid_entries += 1
                        continue

                    # Append data for training
                    labels.append(user_id)
                    faces.append(img)
                except Exception as e:
                    invalid_entries += 1
                    print(f"Error decoding image for user ID {user_id}: {str(e)}")

            if not faces:
                self.status_label.setText("No valid images for training")
                QMessageBox.warning(self, 'Error', 'No valid images available for training!')
                return

            # Train face recognizer
            recognizer = cv2.face.LBPHFaceRecognizer_create()
            recognizer.train(faces, np.array(labels))

            # Save the trained model
            model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "face_recognizer.yml")
            recognizer.save(model_path)

            # Update status
            success_message = f"Model trained successfully! {len(faces)} images used, {invalid_entries} invalid entries ignored."
            self.status_label.setText(success_message)
            QMessageBox.information(self, 'Success', success_message)

        except sqlite3.Error as e:
            self.status_label.setText(f"Database error: {str(e)}")
            QMessageBox.critical(self, 'Error', f"Database error: {str(e)}")
        except Exception as e:
            self.status_label.setText(f"Error: {str(e)}")
            QMessageBox.critical(self, 'Error', f"An error occurred: {str(e)}\n{traceback.format_exc()}")


    def analyze_video(self):
        """Analyze a video for face detection and recognition using FaceNet."""
        self.add_window = VideoAnalyzer.VideoAnalyzer()
        self.add_window.show()

    def add_dataset(self):
        """Allows the user to import a folder of images as a dataset."""
        folder = QFileDialog.getExistingDirectory(self, 'Select Dataset Folder')
        if folder:
            try:
                conn = sqlite3.connect("FaceBase.db")
                cursor = conn.cursor()

                for subdir, _, files in os.walk(folder):
                    person_name = os.path.basename(subdir)
                    cursor.execute("""
                                                    DELETE FROM Peoples WHERE ID > 8
                                                """)
                    for file in files:
                        file_path = os.path.join(subdir, file)
                        img = cv2.imread(file_path)
                        if img is not None:
                            # Resize the image for consistency (e.g., 160x160)
                            resized_img = cv2.resize(img, (240, 240))

                            # Use better encoding with minimal compression
                            encode_params = [cv2.IMWRITE_JPEG_QUALITY, 95]  # 95% quality
                            _, img_encoded = cv2.imencode('.jpg', resized_img, encode_params)

                            # Convert encoded image to binary blob
                            img_blob = img_encoded.tobytes()
                            cursor.execute("""
                                INSERT INTO Peoples (Name, Age, Gender, Image) VALUES (?, ?, ?, ?)
                            """, (person_name, None, None, img_blob))

                conn.commit()
                conn.close()
                self.status_label.setText("Dataset imported successfully !")
            except Exception as e:
                self.status_label.setText(f"Error importing dataset: {str(e)}")
                QMessageBox.critical(self, 'Error', f"Failed to import dataset: {str(e)}")


if __name__ == '__main__':
    app = QApplication(sys.argv)

    main_window = MainWindow()
    main_window.show()

    sys.exit(app.exec_())
