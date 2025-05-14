import cv2
import mediapipe as mp
import numpy as np

# Configura la URL RTSP de tu cámara IP
#RTSP_URL = "rtsp://admin:admin@172.16.2.223:554/rtsp/streaming?channel=01&subtype=0"
RTSP_URL = "rtsp://admin:Bolidec0@172.16.2.222:80/rtsp/streaming?channel=01&subtype=0"
cap = cv2.VideoCapture(RTSP_URL)

# Opcional: reducir buffering (si hay mucho delay)
cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

# Inicializar detección de rostros con mediapipe con configuración mejorada
mp_face_detection = mp.solutions.face_detection
# Aumentar la confianza mínima para mejorar la precisión
face_detection = mp_face_detection.FaceDetection(
    min_detection_confidence=0.5,  # Reducir para detectar rostros más lejanos
    model_selection=1  # Usar modelo de rango completo (0 para cerca, 1 para hasta 5m)
)

# Lista de trackers activos
trackers = []

# Cada cierto número de frames volvemos a detectar para actualizar las caras
frame_count = 0
DETECT_EVERY_N_FRAMES = 10  # Reducido para actualizar más frecuentemente

# Parámetros para mejorar la detección
MAX_FACES = 50  # Aumentar el número máximo de caras a detectar
MIN_FACE_SIZE = 10  # Tamaño mínimo de cara en píxeles

# Para estabilización de detecciones
previous_faces = []
STABILITY_FRAMES = 3

while True:
    ret, frame = cap.read()
    if not ret:
        break
        
    # Opcional: redimensionar para mejorar rendimiento
    height, width = frame.shape[:2]
    frame = cv2.resize(frame, (int(width * 0.75), int(height * 0.75)))
    
    # Opcional: mejorar contraste para ayudar en la detección
    frame = cv2.convertScaleAbs(frame, alpha=1.2, beta=10)
    
    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    # Redetectar cada N frames (por si hay nuevas caras o se pierde alguna)
    if frame_count % DETECT_EVERY_N_FRAMES == 0:
        results = face_detection.process(frame_rgb)
        current_faces = []
        
        if results.detections:
            for detection in results.detections:
                bboxC = detection.location_data.relative_bounding_box
                ih, iw, _ = frame.shape
                x = int(bboxC.xmin * iw)
                y = int(bboxC.ymin * ih)
                w = int(bboxC.width * iw)
                h = int(bboxC.height * ih)
                
                # Filtrar caras muy pequeñas (posibles falsos positivos)
                if w < MIN_FACE_SIZE or h < MIN_FACE_SIZE:
                    continue
                    
                # Guardar las caras detectadas
                current_faces.append((x, y, w, h))
        
        # Actualizar historial de caras para estabilidad
        previous_faces.append(current_faces)
        if len(previous_faces) > STABILITY_FRAMES:
            previous_faces.pop(0)
            
        # Reiniciar trackers
        trackers = []
        
        # Usar solo caras que aparecen en múltiples frames para estabilidad
        if len(previous_faces) >= 2:
            stable_faces = []
            for face in current_faces:
                x1, y1, w1, h1 = face
                is_stable = False
                
                # Verificar si la cara aparece en frames anteriores
                for prev_frame_faces in previous_faces[:-1]:  # Excluir el frame actual
                    for prev_face in prev_frame_faces:
                        x2, y2, w2, h2 = prev_face
                        # Calcular solapamiento
                        overlap_x = max(0, min(x1+w1, x2+w2) - max(x1, x2))
                        overlap_y = max(0, min(y1+h1, y2+h2) - max(y1, y2))
                        if overlap_x > 0 and overlap_y > 0:
                            is_stable = True
                            break
                    if is_stable:
                        break
                
                if is_stable or len(previous_faces) < STABILITY_FRAMES:
                    stable_faces.append(face)
                    
            # Crear trackers para caras estables
            for x, y, w, h in stable_faces[:MAX_FACES]:  # Limitar número de caras
                tracker = cv2.TrackerCSRT_create()
                tracker.init(frame, (x, y, w, h))
                trackers.append(tracker)
                
                # Dibujar rectángulo para caras recién detectadas
                cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
    else:
        # Actualizar todos los trackers
        new_trackers = []
        for tracker in trackers:
            success, bbox = tracker.update(frame)
            if success:
                x, y, w, h = map(int, bbox)
                cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
                new_trackers.append(tracker)

        trackers = new_trackers  # Elimina los que fallaron

    # Mostrar número de caras detectadas
    cv2.putText(frame, f"Caras: {len(trackers)}", (10, 30), 
                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                
    frame_count += 1
    cv2.imshow("Detección de Rostros Mejorada", frame)

    if cv2.waitKey(1) & 0xFF == 27:
        break

cap.release()
cv2.destroyAllWindows()
