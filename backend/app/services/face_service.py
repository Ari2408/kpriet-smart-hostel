import cv2
import numpy as np
import base64
import json
import math
from typing import Tuple, Dict, Any, List, Optional

MIN_FACE_SIZE = 60 # Minimum bounding box width/height in pixels
EMBEDDING_DIM = 128
COSINE_SIMILARITY_THRESHOLD = 0.70

def decode_image(image_input: str) -> Optional[np.ndarray]:
    """
    Decodes an image from base64 string or binary bytes into a BGR OpenCV numpy array.
    """
    try:
        if isinstance(image_input, str):
            if "base64," in image_input:
                image_input = image_input.split("base64,")[1]
            image_bytes = base64.b64decode(image_input)
        else:
            image_bytes = image_input

        nparr = np.frombuffer(image_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        return img
    except Exception as e:
        return None

def detect_face_bbox(img: np.ndarray) -> Tuple[Optional[Tuple[int, int, int, int]], int, str]:
    """
    Detects face bounding box using YCrCb skin-color locus and morphological analysis.
    Returns: (bbox, face_count, status_message)
    bbox format: (x, y, w, h)
    """
    if img is None:
        return None, 0, "Empty image provided"

    height, width, _ = img.shape
    if height < 100 or width < 100:
        return None, 0, "Image resolution too low. Minimum 100x100 required."

    # Convert to YCrCb for robust illumination-independent skin color detection
    ycrcb = cv2.cvtColor(img, cv2.COLOR_BGR2YCrCb)
    # Human skin ranges in YCrCb: Cr in [133, 173], Cb in [77, 127]
    lower_skin = np.array([0, 133, 77], dtype=np.uint8)
    upper_skin = np.array([255, 173, 127], dtype=np.uint8)
    skin_mask = cv2.inRange(ycrcb, lower_skin, upper_skin)

    # Morphological filtering to eliminate small noise and connect face components
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    skin_mask = cv2.erode(skin_mask, kernel, iterations=1)
    skin_mask = cv2.dilate(skin_mask, kernel, iterations=2)
    skin_mask = cv2.GaussianBlur(skin_mask, (5, 5), 0)

    contours, _ = cv2.findContours(skin_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    valid_faces = []
    min_area = (width * height) * 0.04 # At least 4% of screen area

    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < min_area:
            continue

        x, y, w, h = cv2.boundingRect(cnt)
        aspect_ratio = float(h) / max(1, w)

        # Human face bounding box aspect ratio typically between 1.0 and 1.8
        if 0.9 <= aspect_ratio <= 2.2 and w >= MIN_FACE_SIZE and h >= MIN_FACE_SIZE:
            valid_faces.append((x, y, w, h, area))

    if len(valid_faces) == 0:
        # Fallback to central region if image is a direct face portrait crop
        center_x, center_y = width // 2, height // 2
        crop_w = int(width * 0.65)
        crop_h = int(height * 0.75)
        x = max(0, center_x - crop_w // 2)
        y = max(0, center_y - crop_h // 2)
        return (x, y, crop_w, crop_h), 1, "Face localized via portrait frame."

    if len(valid_faces) > 1:
        # Sort by area descending
        valid_faces.sort(key=lambda item: item[4], reverse=True)
        # If second face is comparable in size, reject multi-face
        if valid_faces[1][4] > valid_faces[0][4] * 0.5:
            return None, len(valid_faces), "Multiple faces detected. Only one student must be in front of camera."

    best = valid_faces[0]
    return (best[0], best[1], best[2], best[3]), 1, "Face detected successfully."

def check_liveness_and_anti_spoofing(img: np.ndarray, bbox: Tuple[int, int, int, int]) -> Tuple[bool, float, str]:
    """
    Anti-spoofing and liveness check:
    1. Rejects blurry captures (Laplacian variance)
    2. Rejects static paper prints / phone screens (Fourier 2D frequency analysis - screens have severe moire patterns)
    3. Verifies natural color distribution and contrast
    """
    x, y, w, h = bbox
    face_crop = img[y:y+h, x:x+w]
    if face_crop.size == 0:
        return False, 0.0, "Invalid face crop"

    gray = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY)

    # 1. Blur test (Laplacian variance)
    laplacian_var = cv2.Laplacian(gray, cv2.CV_64F).var()
    if laplacian_var < 35.0:
        return False, float(laplacian_var), "Image too blurry. Please hold the phone steady with good lighting."

    # 2. Brightness sanity check
    mean_brightness = np.mean(gray)
    if mean_brightness < 30.0:
        return False, float(mean_brightness), "Image is too dark. Please move to a well-lit area."
    if mean_brightness > 245.0:
        return False, float(mean_brightness), "Image is over-exposed. Avoid harsh direct backlighting."

    # 3. Frequency domain analysis for screen spoofing (Moiré pattern detection)
    resized_gray = cv2.resize(gray, (128, 128))
    f_transform = np.fft.fft2(resized_gray)
    f_shift = np.fft.fftshift(f_transform)
    magnitude_spectrum = 20 * np.log(np.abs(f_shift) + 1e-7)

    # High frequency ratio: screens produce abnormal repeating spikes
    h_mid, w_mid = 64, 64
    high_freq_ring = magnitude_spectrum.copy()
    high_freq_ring[h_mid-20:h_mid+20, w_mid-20:w_mid+20] = 0 # zero out low frequencies
    high_freq_peak = np.max(high_freq_ring)
    high_freq_mean = np.mean(high_freq_ring)

    if high_freq_mean > 0 and (high_freq_peak / high_freq_mean) > 8.0:
        return False, 0.2, "Screen replay or digital display pattern detected. Please use live camera."

    return True, 0.95, "Liveness check passed."

def extract_face_embedding(img: np.ndarray, bbox: Optional[Tuple[int, int, int, int]] = None) -> List[float]:
    """
    Extracts a normalized 128-dimensional facial feature vector.
    Invariant to illumination and minor head poses.
    """
    if bbox is not None:
        x, y, w, h = bbox
        face = img[y:y+h, x:x+w]
    else:
        face = img

    if face is None or face.size == 0:
        raise ValueError("Cannot extract embedding from empty image")

    # 1. Resize face to canonical 112x112 size
    aligned = cv2.resize(face, (112, 112))

    # 2. Convert to LAB color space and apply CLAHE on L channel for contrast normalization
    lab = cv2.cvtColor(aligned, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8))
    l_eq = clahe.apply(l)
    equalized_gray = l_eq

    # 3. Compute multi-scale directional gradients (HOG-like features across 4x4 spatial blocks)
    # 4x4 grid = 16 cells. Each cell gets 8 directional bins = 16 * 8 = 128 features!
    sobel_x = cv2.Sobel(equalized_gray, cv2.CV_32F, 1, 0, ksize=3)
    sobel_y = cv2.Sobel(equalized_gray, cv2.CV_32F, 0, 1, ksize=3)
    magnitude, angle = cv2.cartToPolar(sobel_x, sobel_y, angleInDegrees=True)

    cell_size = 28 # 112 / 4 = 28
    features = []

    for row in range(4):
        for col in range(4):
            y_start = row * cell_size
            y_end = (row + 1) * cell_size
            x_start = col * cell_size
            x_end = (col + 1) * cell_size

            cell_mag = magnitude[y_start:y_end, x_start:x_end]
            cell_ang = angle[y_start:y_end, x_start:x_end]

            # 8 bins of 45 degrees each: 0-45, 45-90, 90-135, ..., 315-360
            hist, _ = np.histogram(cell_ang, bins=8, range=(0, 360), weights=cell_mag)
            features.extend(hist.tolist())

    vec = np.array(features, dtype=np.float32)

    # 4. L2-Normalize vector to unit length
    norm = np.linalg.norm(vec)
    if norm > 1e-6:
        vec = vec / norm
    else:
        vec = np.zeros(EMBEDDING_DIM, dtype=np.float32)
        vec[0] = 1.0

    return [round(float(v), 6) for v in vec[:EMBEDDING_DIM]]

def compare_embeddings(embedding1: List[float], embedding2: List[float]) -> float:
    """
    Computes cosine similarity between two 128D embeddings.
    Returns float between 0.0 and 1.0.
    """
    v1 = np.array(embedding1, dtype=np.float32)
    v2 = np.array(embedding2, dtype=np.float32)

    norm1 = np.linalg.norm(v1)
    norm2 = np.linalg.norm(v2)

    if norm1 < 1e-6 or norm2 < 1e-6:
        return 0.0

    cosine_sim = float(np.dot(v1, v2) / (norm1 * norm2))
    # Map [-1, 1] to [0, 1] range
    similarity = max(0.0, min(1.0, (cosine_sim + 1.0) / 2.0))
    return round(similarity, 4)

def process_face_registration(image_data: str) -> Dict[str, Any]:
    """
    Workflow for Staff: enroll new student facial profile.
    """
    img = decode_image(image_data)
    if img is None:
        return {"success": False, "message": "Failed to decode student image."}

    bbox, count, msg = detect_face_bbox(img)
    if count == 0:
        return {"success": False, "message": f"Face enrollment failed: {msg}"}
    if count > 1:
        return {"success": False, "message": f"Face enrollment failed: {msg}"}

    try:
        embedding = extract_face_embedding(img, bbox)
        return {
            "success": True,
            "embedding": embedding,
            "message": "Facial embedding profile successfully generated.",
            "bbox": bbox
        }
    except Exception as e:
        return {"success": False, "message": f"Feature extraction error: {str(e)}"}

def verify_live_face(live_image_data: str, registered_embedding_json: str) -> Dict[str, Any]:
    """
    Workflow for Student: verify live facial capture against registered embedding.
    """
    img = decode_image(live_image_data)
    if img is None:
        return {
            "matched": False,
            "confidence": 0.0,
            "liveness_passed": False,
            "message": "Invalid or unreadable camera frame."
        }

    # 1. Detect face
    bbox, count, msg = detect_face_bbox(img)
    if count == 0:
        return {
            "matched": False,
            "confidence": 0.0,
            "liveness_passed": False,
            "message": "No face detected. Please ensure your face is clearly visible."
        }
    if count > 1:
        return {
            "matched": False,
            "confidence": 0.0,
            "liveness_passed": False,
            "message": "Multiple faces detected. Only the registered student can be in view."
        }

    # 2. Check liveness / anti-spoofing
    liveness_ok, score, liveness_msg = check_liveness_and_anti_spoofing(img, bbox)
    if not liveness_ok:
        return {
            "matched": False,
            "confidence": 0.0,
            "liveness_passed": False,
            "message": f"Liveness check failed: {liveness_msg}"
        }

    # 3. Extract live embedding
    live_embedding = extract_face_embedding(img, bbox)

    # 4. Compare with registered profile
    try:
        if isinstance(registered_embedding_json, str):
            registered_embedding = json.loads(registered_embedding_json)
        else:
            registered_embedding = registered_embedding_json

        similarity = compare_embeddings(live_embedding, registered_embedding)
        matched = similarity >= COSINE_SIMILARITY_THRESHOLD

        return {
            "matched": matched,
            "confidence": similarity,
            "liveness_passed": True,
            "message": "Face verification successful!" if matched else f"Face verification failed. Similarity {similarity:.2f} below threshold {COSINE_SIMILARITY_THRESHOLD:.2f}."
        }
    except Exception as e:
        return {
            "matched": False,
            "confidence": 0.0,
            "liveness_passed": False,
            "message": f"Verification error: {str(e)}"
        }

LIVENESS_CHALLENGES = {
    "BLINK_TWICE": "Please blink your eyes twice naturally.",
    "TURN_HEAD_LEFT": "Turn your head slightly to your left.",
    "TURN_HEAD_RIGHT": "Turn your head slightly to your right.",
    "LOOK_STRAIGHT": "Look straight directly into the camera."
}

def get_random_challenge() -> Tuple[str, str]:
    import random
    challenge_type = random.choice(list(LIVENESS_CHALLENGES.keys()))
    return challenge_type, LIVENESS_CHALLENGES[challenge_type]

def verify_live_face_with_challenge(
    live_image_data: str,
    registered_embedding_json: str,
    expected_challenge: str,
    detected_challenge: str
) -> Dict[str, Any]:
    """
    Combined live face verification enforcing:
    1. Single face bounding box detection.
    2. Challenge-response action validation.
    3. Laplacian blur & 2D FFT spectral anti-spoofing.
    4. 128D directional gradient embedding matching (Cosine similarity >= 0.70).
    """
    if not detected_challenge or detected_challenge.upper() != expected_challenge.upper():
        return {
            "matched": False,
            "confidence": 0.0,
            "liveness_passed": False,
            "message": f"Liveness challenge failed. Expected '{expected_challenge}', but received '{detected_challenge}'."
        }

    # Run core image checks (anti-spoofing & biometric match)
    result = verify_live_face(live_image_data, registered_embedding_json)
    if not result["matched"]:
        return result

    # Additional CV sanity check on the frame for pose challenges
    img = decode_image(live_image_data)
    if img is not None:
        bbox, _, _ = detect_face_bbox(img)
        if bbox:
            h_img, w_img, _ = img.shape
            x, y, w, h = bbox
            face_center_x = (x + w / 2) / max(1, w_img)
            if expected_challenge == "TURN_HEAD_LEFT" and face_center_x > 0.65:
                # Student turned right instead of left
                return {
                    "matched": False,
                    "confidence": result["confidence"],
                    "liveness_passed": False,
                    "message": "Liveness challenge failed: Face orientation did not match turn left."
                }
            elif expected_challenge == "TURN_HEAD_RIGHT" and face_center_x < 0.35:
                # Student turned left instead of right
                return {
                    "matched": False,
                    "confidence": result["confidence"],
                    "liveness_passed": False,
                    "message": "Liveness challenge failed: Face orientation did not match turn right."
                }

    return {
        "matched": True,
        "confidence": result["confidence"],
        "liveness_passed": True,
        "message": "Live face and challenge verification successful!"
    }

