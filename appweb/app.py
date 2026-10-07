import base64
import logging
import traceback
from zipfile import ZipFile
from flask import Flask, render_template, Response
import os
from flask_cors import CORS
from werkzeug.utils import secure_filename
import numpy as np
import cv2
import torch
import sqlite3
from PIL import Image as PILImage
from facenet_pytorch import MTCNN, InceptionResnetV1
from flask import jsonify, request
import logging
from functools import lru_cache
import threading
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__, static_folder='static', template_folder='templates')
CORS(app)

mtcnn = MTCNN(keep_all=True)
facenet = InceptionResnetV1(pretrained="vggface2").eval()

# Global variables to store face data
known_faces = {
    "embeddings": [],
    "labels": [],
    "names": []
}

DB_PATH = "./database/FaceBase.db"

@app.route('/')
def index():
    return render_template('index.html')

# Route for add to database page
@app.route('/addToDB')
def add_to_db():
    return render_template('addToDB.html')

# Route for recognize face page
@app.route('/recognize')
def recognize():
    return render_template('recognize.html')

# Route for analyze video page
@app.route('/analyze')
def analyze():
    return render_template('analyze.html')

# Route for dataset page
@app.route('/dataset')
def dataset():
    return render_template('dataset.html')


@app.route('/submit_faces', methods=['POST'])
def submit_faces():
    try:
        # Validate input data
        data = request.json
        print("Received data:", data)
        user_name = data.get("name", "").strip()
        user_age = data.get("age", "").strip()
        user_gender = data.get("gender", "").strip()
        faces = data.get("faces", [])

        if not all([user_name, user_age, user_gender, faces]):
            return jsonify({"message": "All fields and at least one face are required!"}), 400

        try:
            user_age = int(user_age)
        except ValueError:
            return jsonify({"message": "Age must be a valid integer!"}), 400

        # Decode images
        decoded_faces = []
        for face in faces:
            try:
                image_data = base64.b64decode(face.split(",")[1])
                decoded_faces.append(image_data)
            except Exception as e:
                return jsonify({"message": f"Error decoding images: {str(e)}"}), 400

        # Save to the database
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "./database/FaceBase.db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Insert each face into the database
        for img_data in decoded_faces:
            cursor.execute(
                "INSERT INTO Peoples (Name, Age, Gender, Image) VALUES (?, ?, ?, ?)",
                (user_name, user_age, user_gender, img_data)
            )

        conn.commit()
        conn.close()

        return jsonify({"message": "User information and faces saved successfully!"}), 200

    except sqlite3.Error as se:
        return jsonify({"message": f"Database error: {str(se)}"}), 500
    except Exception as e:
        return jsonify({"message": f"An error occurred: {str(e)}"}), 500


# Initialize SocketIO
from flask_socketio import SocketIO, emit

socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')


# Remove the HTTP route and add WebSocket handlers
@socketio.on('connect')
def handle_connect():
    """Handle new WebSocket connections."""
    logger.info(f"Client connected: {request.sid}")


@socketio.on('disconnect')
def handle_disconnect():
    """Handle WebSocket disconnections."""
    logger.info(f"Client disconnected: {request.sid}")


@socketio.on('frame')
def handle_frame(frame_data):
    """Handle incoming video frames over WebSocket."""
    try:
        # Decode base64 frame data
        encoded_data = frame_data.split(',')[1] if ',' in frame_data else frame_data
        nparr = np.frombuffer(base64.b64decode(encoded_data), np.uint8)
        frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if frame is None:
            emit('recognition_result', {'error': 'Invalid image data'})
            return

        # Convert frame to RGB
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Detect faces in the frame
        boxes, _ = mtcnn.detect(frame_rgb)
        if boxes is None or len(boxes) == 0:
            emit('recognition_result', {'faces': []})
            return

        results = []

        # Process each detected face
        for box in boxes:
            x1, y1, x2, y2 = map(int, box)

            # Add padding and adjust bounding box
            w, h = x2 - x1, y2 - y1
            padding = int(0.1 * min(w, h))
            x1, y1 = max(0, x1 - padding), max(0, y1 - padding)
            x2, y2 = min(frame_rgb.shape[1], x2 + padding), min(frame_rgb.shape[0], y2 + padding)

            # Extract the face region
            face_image = frame_rgb[y1:y2, x1:x2]
            if face_image.size == 0:
                continue

            # Generate face embedding
            face_tensor = mtcnn(face_image)
            if face_tensor is None:
                continue

            embedding = facenet(face_tensor.unsqueeze(0)).detach().cpu().numpy()

            # Match the face with known faces
            min_distance = float("inf")
            best_match_index = None

            with cache_lock:
                for i, known_embedding in enumerate(known_faces["embeddings"]):
                    distance = np.linalg.norm(embedding - known_embedding)
                    if distance < min_distance:
                        min_distance = distance
                        best_match_index = i

            # Determine name based on distance
            if min_distance < MATCH_THRESHOLD:
                name = known_faces["names"][best_match_index]
            else:
                name = "Unknown"

            results.append({
                "box": [int(x1), int(y1), int(x2), int(y2)],
                "name": name,
                "confidence": float(1 - min_distance) if min_distance != float("inf") else 0
            })

        # Emit results back to the client
        emit('recognition_result', {'faces': results})

    except Exception as e:
        logger.exception("Error in handle_frame")
        emit('recognition_result', {'error': str(e)})



# Face Recognition System Initialization

# Configuration Parameters
MIN_FACE_SIZE = 60
CACHE_MAXSIZE = 1000
DB_BATCH_SIZE = 100
THREAD_POOL_WORKERS = min(8, os.cpu_count() or 4)
DOWNSCALE_FACTOR = 0.5
MATCH_THRESHOLD = 0.75  # Increased threshold for face recognition confidence

# Logging Configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("FaceRecognition")

# Model Initialization
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
mtcnn = MTCNN(
    device=device,
    select_largest=False,
    post_process=False,
    min_face_size=MIN_FACE_SIZE,
)
facenet = InceptionResnetV1(pretrained="vggface2").eval().to(device)

# Global Known Faces Cache
known_faces = {"embeddings": [], "labels": [], "names": []}
cache_lock = threading.Lock()

# Thread Pool Executor
executor = ThreadPoolExecutor(max_workers=THREAD_POOL_WORKERS)

@lru_cache(maxsize=CACHE_MAXSIZE)
def compute_embedding(face_tensor):
    """Compute and cache embeddings for a face tensor."""
    with torch.no_grad():
        return facenet(face_tensor.unsqueeze(0)).cpu().numpy()[0]

def load_database_faces(batch_size=DB_BATCH_SIZE):
    """Load face data from database and populate cache."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT ID, Name, Image FROM Peoples")
        data = cursor.fetchall()
        conn.close()

        if not data:
            logger.warning("No faces found in the database.")
            return [], [], []

        embeddings, labels, names = [], [], []

        def process_batch(batch):
            """Process a single batch of database records."""
            results = []
            for user_id, name, image_data in batch:
                try:
                    np_img = np.frombuffer(image_data, np.uint8)
                    db_face_image = cv2.imdecode(np_img, cv2.IMREAD_COLOR)
                    if db_face_image is None:
                        logger.warning(f"Invalid image for user {user_id}.")
                        continue

                    db_face_image = cv2.cvtColor(db_face_image, cv2.COLOR_BGR2RGB)
                    face_tensor = mtcnn(db_face_image)
                    if face_tensor is not None:
                        embedding = compute_embedding(face_tensor)
                        results.append((embedding, user_id, name))
                except Exception as e:
                    logger.error(f"Error processing face for user {user_id}: {e}")
            return results

        for i in range(0, len(data), batch_size):
            batch = data[i : i + batch_size]
            batch_results = executor.map(process_batch, [batch])
            for result in batch_results:
                for embedding, user_id, name in result:
                    embeddings.append(embedding)
                    labels.append(user_id)
                    names.append(name)

        logger.info(f"Loaded {len(embeddings)} faces from database.")
        return embeddings, labels, names
    except Exception as e:
        logger.error(f"Database loading error: {e}")
        return [], [], []

def update_known_faces():
    """Refresh the global known faces cache."""
    embeddings, labels, names = load_database_faces()
    with cache_lock:
        known_faces["embeddings"] = embeddings
        known_faces["labels"] = labels
        known_faces["names"] = names
    logger.info("Known faces cache updated.")

# Initial Cache Update
logger.info("Initializing known faces cache...")
update_known_faces()
logger.info("Known faces cache initialized.")

@app.route("/recognize-frame", methods=["POST"])
def recognize_frame():
    """Optimized API for face recognition in video frames."""
    try:
        # Check if the request contains frame data
        if "frame" not in request.files:
            return jsonify({"error": "No frame data provided"}), 400

        # Decode the frame
        frame_data = request.files["frame"].read()
        np_frame = np.frombuffer(frame_data, np.uint8)
        frame = cv2.imdecode(np_frame, cv2.IMREAD_COLOR)
        if frame is None:
            return jsonify({"error": "Invalid image data"}), 400

        # Convert frame to RGB
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Detect faces in the frame
        boxes, _ = mtcnn.detect(frame_rgb)
        if boxes is None or len(boxes) == 0:
            return jsonify([])  # No faces detected

        results = []

        # Process each detected face
        for box in boxes:
            x1, y1, x2, y2 = map(int, box)

            # Add padding and adjust bounding box
            w, h = x2 - x1, y2 - y1
            padding = int(0.1 * min(w, h))
            x1, y1 = max(0, x1 - padding), max(0, y1 - padding)
            x2, y2 = min(frame_rgb.shape[1], x2 + padding), min(frame_rgb.shape[0], y2 + padding)

            # Extract the face region
            face_image = frame_rgb[y1:y2, x1:x2]
            if face_image.size == 0:
                continue

            # Generate face embedding
            face_tensor = mtcnn(face_image)
            if face_tensor is None:
                continue

            embedding = facenet(face_tensor.unsqueeze(0)).detach().cpu().numpy()

            # Match the face with known faces
            min_distance = float("inf")
            best_match_index = None
            for i, known_embedding in enumerate(known_faces["embeddings"]):
                distance = np.linalg.norm(embedding - known_embedding)
                if distance < min_distance:
                    min_distance = distance
                    best_match_index = i

            # Determine name based on distance
            if min_distance < MATCH_THRESHOLD:  # Recognition threshold increased
                name = known_faces["names"][best_match_index]
            else:
                name = "Unknown"

            results.append({"box": [x1, y1, x2, y2], "name": name})

        return jsonify(results)

    except Exception as e:
        logger.exception("Error in recognize_frame")
        return jsonify({"error": "Internal server error"}), 500





@app.route('/train-model', methods=['POST'])
def train_model():
    """Train the face recognition model using database images."""
    try:
        # Database connection
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "./database/FaceBase.db")
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Fetch IDs and images from the database
        cursor.execute("UPDATE Peoples SET Name = 'El Barae' WHERE ID BETWEEN 25 AND 75")
        cursor.execute("SELECT ID, Image FROM Peoples")
        data = cursor.fetchall()
        conn.close()

        if not data:
            return jsonify({
                'error': 'No data available for training',
                'status': 'failed'
            }), 400

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
            return jsonify({
                'error': 'No valid images for training',
                'status': 'failed',
                'invalid_entries': invalid_entries
            }), 400

        # Train face recognizer
        recognizer = cv2.face.LBPHFaceRecognizer_create()
        recognizer.train(faces, np.array(labels))

        # Save the trained model
        model_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "face_recognizer.yml")
        recognizer.save(model_path)

        # Return success response
        return jsonify({
            'status': 'success',
            'message': 'Model trained successfully',
            'details': {
                'images_used': len(faces),
                'invalid_entries': invalid_entries,
                'model_path': model_path
            }
        }), 200

    except sqlite3.Error as e:
        return jsonify({
            'error': f'Database error: {str(e)}',
            'status': 'failed'
        }), 500
    except Exception as e:
        return jsonify({
            'error': 'An unexpected error occurred',
            'status': 'failed',
            'details': str(e),
            'traceback': traceback.format_exc()
        }), 500


@app.route('/stream-video', methods=['POST'])
def upload_video():
    global video_path

    if 'video' not in request.files:
        return jsonify({'error': 'No video file provided'}), 400

    video = request.files['video']
    video_path = os.path.join("uploads", video.filename)
    os.makedirs("uploads", exist_ok=True)
    video.save(video_path)

    return jsonify({'message': 'Video uploaded successfully'}), 200


@app.route('/stream-video', methods=['GET'])
def stream_video():
    global video_path

    if not video_path or not os.path.exists(video_path):
        return jsonify({'error': 'No video uploaded for streaming'}), 400

    def generate_frames():
        try:
            cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_fullbody.xml")
            cap = cv2.VideoCapture(video_path)

            if not cap.isOpened():
                raise Exception("Unable to open video file.")

            while True:
                ret, frame = cap.read()
                if not ret:
                    break

                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                detections = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=3, minSize=(50, 50))

                for (x, y, w, h) in detections:
                    cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

                _, buffer = cv2.imencode('.jpg', frame)
                yield (b'--frame\r\n'
                       b'Content-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

            cap.release()
            os.remove(video_path)
        except Exception as e:
            print(f"Error: {e}")

    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')


UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route('/add_dataset', methods=['POST'])
def add_dataset():
    if 'dataset' not in request.files:
        return jsonify({'message': 'No file uploaded'}), 400

    file = request.files['dataset']
    if not file.filename.endswith('.zip'):
        return jsonify({'message': 'Invalid file type. Please upload a zip file.'}), 400

    zip_path = os.path.join(UPLOAD_FOLDER, secure_filename(file.filename))
    file.save(zip_path)

    try:
        with ZipFile(zip_path, 'r') as zip_ref:
            extract_folder = os.path.join(UPLOAD_FOLDER, 'extracted')
            zip_ref.extractall(extract_folder)

        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        for root, _, files in os.walk(extract_folder):
            person_name = os.path.basename(root)
            for filename in files:
                file_path = os.path.join(root, filename)
                img = cv2.imread(file_path)
                if img is not None:
                    resized_img = cv2.resize(img, (240, 240))
                    _, img_encoded = cv2.imencode('.jpg', resized_img, [cv2.IMWRITE_JPEG_QUALITY, 95])
                    img_blob = img_encoded.tobytes()
                    cursor.execute("""
                        INSERT INTO Peoples (Name, Age, Gender, Image) VALUES (?, ?, ?, ?)
                    """, (person_name, None, None, img_blob))

        conn.commit()
        conn.close()
        os.remove(zip_path)
        return jsonify({'message': 'Dataset imported successfully!'})
    except Exception as e:
        return jsonify({'message': f"Error importing dataset: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(debug=True)
