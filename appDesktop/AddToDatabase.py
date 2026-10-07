import traceback

from PyQt5.QtGui import QImage, QPixmap
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QLineEdit,
    QPushButton, QMessageBox, QHBoxLayout, QDesktopWidget,
    QScrollArea
)
from PyQt5.QtCore import Qt, QTimer
import cv2
import sqlite3
import os

# Style remains the same as in your original code
add_to_database_style = """
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


class AddToDatabaseWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Add User to Database')

        # Get screen dimensions and set window size
        screen = QDesktopWidget().screenGeometry()
        window_height = min(800, screen.height() - 100)  # Limit height to screen size
        self.setGeometry(100, 100, 1000, window_height)
        self.setStyleSheet(add_to_database_style)

        # Initialize camera and face detection
        self.cap = cv2.VideoCapture(0)
        if not self.cap.isOpened():
            QMessageBox.critical(self, 'Error', 'Could not open camera!')
            return

        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        )

        # Create main horizontal layout
        main_layout = QHBoxLayout()

        # Left side - Input fields
        left_widget = QWidget()
        left_layout = QVBoxLayout()

        # Create a scroll area for input fields
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        # Container for input fields
        input_container = QWidget()
        input_layout = QVBoxLayout()

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText('Enter User Name')
        input_layout.addWidget(self.create_input_group("Name", self.name_input))

        self.age_input = QLineEdit()
        self.age_input.setPlaceholderText('Enter User Age')
        input_layout.addWidget(self.create_input_group("Age", self.age_input))

        self.gender_input = QLineEdit()
        self.gender_input.setPlaceholderText('Enter User Gender')
        input_layout.addWidget(self.create_input_group("Gender", self.gender_input))

        input_container.setLayout(input_layout)
        scroll_area.setWidget(input_container)
        left_layout.addWidget(scroll_area)
        left_widget.setLayout(left_layout)

        # Right side - Camera feed and buttons
        right_widget = QWidget()
        right_layout = QVBoxLayout()

        # Camera feed
        self.image_label = QLabel()
        self.image_label.setFixedSize(640, 480)
        right_layout.addWidget(self.image_label)

        # Buttons
        buttons_layout = QVBoxLayout()
        self.auto_capture_button = QPushButton('Start Auto-Capture')
        self.auto_capture_button.clicked.connect(self.toggle_auto_capture)
        buttons_layout.addWidget(self.auto_capture_button)

        self.submit_button = QPushButton('Submit to Database')
        self.submit_button.clicked.connect(self.submit_to_database)
        self.submit_button.setEnabled(False)
        buttons_layout.addWidget(self.submit_button)

        # Status label
        self.status_label = QLabel()
        self.status_label.setObjectName("status_label")
        buttons_layout.addWidget(self.status_label)

        right_layout.addLayout(buttons_layout)
        right_widget.setLayout(right_layout)

        # Add left and right widgets to main layout
        main_layout.addWidget(left_widget, 1)  # 1 is the stretch factor
        main_layout.addWidget(right_widget, 2)  # 2 is the stretch factor

        self.setLayout(main_layout)

        # Timer for updating camera feed
        self.timer = QTimer()
        self.timer.timeout.connect(self.update_frame)
        self.timer.start(30)

        # Variables for auto-capture
        self.captured_faces = []
        self.max_captures = 100
        self.auto_capture_active = False

        # Initialize database
        self.init_database()

    def init_database(self):
        """Initialize the database and create tables if they don't exist"""
        try:
            # Define the database path
            db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "FaceBase.db")
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Create the Peoples table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS Peoples (
                    ID INTEGER PRIMARY KEY AUTOINCREMENT,
                    Name TEXT NOT NULL,
                    Age INTEGER,
                    Gender TEXT,
                    Image BLOB
                )
            """)

            conn.commit()
            self.status_label.setText("Database initialized successfully")
        except sqlite3.Error as e:
            self.status_label.setText(f"Database initialization error: {str(e)}")
            QMessageBox.critical(self, 'Error', f'SQLite error: {str(e)}')
        except Exception as e:
            self.status_label.setText(f"Unexpected error: {str(e)}")
            QMessageBox.critical(self, 'Error', f'Failed to initialize database: {str(e)}')
        finally:
            if conn:
                conn.close()

    def create_input_group(self, label_text, input_field):
        group_layout = QVBoxLayout()
        label = QLabel(label_text)
        group_layout.addWidget(label)
        group_layout.addWidget(input_field)
        container = QWidget()
        container.setLayout(group_layout)
        return container

    def update_frame(self):
        ret, frame = self.cap.read()
        if ret:
            # Convert frame to grayscale for face detection
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = self.face_cascade.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30)
            )

            # Draw rectangle around detected faces
            for (x, y, w, h) in faces:
                cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

            # Auto-capture faces if enabled
            if self.auto_capture_active and len(self.captured_faces) < self.max_captures:
                if len(faces) > 0:
                    (x, y, w, h) = faces[0]  # Take the first detected face
                    face_image = frame[y:y + h, x:x + w]
                    self.captured_faces.append(face_image)
                    self.status_label.setText(f"Auto-captured {len(self.captured_faces)} of {self.max_captures} faces")

                    if len(self.captured_faces) >= self.max_captures:
                        self.auto_capture_active = False  # Stop auto-capture
                        self.auto_capture_button.setText("Start Auto-Capture")
                        self.submit_button.setEnabled(True)  # Enable submit button
                        QMessageBox.information(self, 'Success', '50 faces captured successfully!')

            # Convert frame to QImage for display
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_frame.shape
            bytes_per_line = ch * w
            qt_image = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
            self.image_label.setPixmap(QPixmap.fromImage(qt_image))

    def toggle_auto_capture(self):
        """Toggle auto-capture on/off"""
        if not self.auto_capture_active:
            self.auto_capture_active = True
            self.auto_capture_button.setText("Stop Auto-Capture")
            self.captured_faces.clear()  # Clear previous captures
            self.status_label.setText("Auto-capture started...")
        else:
            self.auto_capture_active = False
            self.auto_capture_button.setText("Start Auto-Capture")
            self.status_label.setText("Auto-capture stopped.")

    def submit_to_database(self):
        if not self.captured_faces:
            self.status_label.setText("No faces captured")
            QMessageBox.warning(self, 'Error', 'Please capture faces first!')
            return

        try:
            # Validate input fields
            user_name = self.name_input.text().strip()
            user_age = self.age_input.text().strip()
            user_gender = self.gender_input.text().strip()

            if not all([user_name, user_age, user_gender]):
                self.status_label.setText("All fields are required")
                QMessageBox.warning(self, 'Error', 'All fields are required!')
                return

            user_age = int(user_age)

            # Convert images to bytes and prepare data
            encoded_images = []
            for face in self.captured_faces:
                ret, buffer = cv2.imencode('.jpg', face)
                if ret:
                    encoded_images.append(buffer.tobytes())
                else:
                    print("Failed to encode image.")

            # Save to database
            db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "FaceBase.db")
            print(f"Database path: {db_path}")

            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # Check if the table exists
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='Peoples'")
            table_exists = cursor.fetchone()
            if not table_exists:
                print("Table 'Peoples' does not exist. Creating it.")
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS Peoples (
                        ID INTEGER PRIMARY KEY AUTOINCREMENT,
                        Name TEXT NOT NULL,
                        Age INTEGER,
                        Gender TEXT,
                        Image BLOB
                    )
                """)
                conn.commit()

            # Insert each face image into the database
            for img_data in encoded_images:
                print(f"Inserting image data of size: {len(img_data)} bytes")
                cursor.execute(
                    "INSERT INTO Peoples (Name, Age, Gender, Image) VALUES (?, ?, ?, ?)",
                    (user_name, user_age, user_gender, img_data)
                )
                print("Insertion successful.")

            conn.commit()
            print("Changes committed to the database.")

            QMessageBox.information(self, 'Success', 'User information saved to database!')
            self.clear_fields()
            self.captured_faces.clear()  # Clear captured faces after submission

        except ValueError:
            self.status_label.setText("Invalid Age format")
            QMessageBox.warning(self, 'Error', 'Age must be a valid integer!')
        except sqlite3.Error as se:
            self.status_label.setText(f"Database error: {str(se)}")
            QMessageBox.critical(self, 'Error', f'Database error: {str(se)}')
        except Exception as e:
            self.status_label.setText(f"Error: {str(e)}")
            QMessageBox.critical(self, 'Error', f'An error occurred: {str(e)}\n{traceback.format_exc()}')
        finally:
            if conn:
                conn.close()
                print("Database connection closed.")

    def clear_fields(self):
        self.name_input.clear()
        self.age_input.clear()
        self.gender_input.clear()
        self.captured_faces = []
        self.submit_button.setEnabled(False)
        self.status_label.setText("Fields cleared")

    def closeEvent(self, event):
        self.cap.release()
        event.accept()

        # # Step 2: Copy data from the old table to the new table
        # cursor.execute("""
        #     INSERT INTO Peoples_new (Name, Age, Gender, Image)
        #     SELECT Name, Age, Gender, Image FROM Peoples
        # """)
        #
        # # Step 3: Drop the old table
        # cursor.execute("DROP TABLE Peoples")
        #
        # # Step 4: Rename the new table to the original table name
        # cursor.execute("ALTER TABLE Peoples_new RENAME TO Peoples")

        # Create the FaceImages table for storing multiple face captures
        # cursor.execute("""
        #     CREATE TABLE IF NOT EXISTS FaceImages (
        #         ImageID INTEGER PRIMARY KEY AUTOINCREMENT,
        #         UserID INTEGER NOT NULL,
        #         Image BLOB NOT NULL,
        #         FOREIGN KEY (UserID) REFERENCES Peoples(ID) ON DELETE CASCADE
        #     )
        # """)