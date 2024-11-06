from fastapi import FastAPI, File, UploadFile
import cv2
import numpy as np
from sqlalchemy import create_engine, Column, Integer, String, Sequence, LargeBinary, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.sql import func
import os
import face_recognition

# Initialize FastAPI app
app = FastAPI()

# Database connection
DATABASE_URL = "postgresql://user:password@db:5432/logs_db"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Users table
class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, Sequence('user_id_seq'), primary_key=True)
    name = Column(String(255))
    email = Column(String(255), unique=True)
    image = Column(LargeBinary)
    logs = relationship("Log", back_populates="user")

# Logs table
class Log(Base):
    __tablename__ = 'logs'
    id = Column(Integer, Sequence('log_id_seq'), primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    time = Column(DateTime(timezone=True), server_default=func.now())
    status = Column(String(50))
    user = relationship("User", back_populates="logs")

# Create the users and logs tables if they don't exist
Base.metadata.create_all(bind=engine)

# Function to add a log entry
def add_log(user, status):
    db = SessionLocal()
    new_log = Log(user=user, status=status)
    db.add(new_log)
    db.commit()
    db.close()

@app.post("/analyze/")
async def analyze_image(file: UploadFile = File(...)):
    # Read image from the uploaded file
    image_bytes = await file.read()
    np_image = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(np_image, cv2.IMREAD_COLOR)

    # Convert to RGB for face recognition
    rgb_img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

    # Encode the uploaded image
    uploaded_image_encoding = face_recognition.face_encodings(rgb_img)
    if len(uploaded_image_encoding) == 0:
        add_log(None, "Access denied: No face detected in uploaded image.")
        return {"result": "denied"}

    uploaded_image_encoding = uploaded_image_encoding[0]

    # Compare with images in the users table
    db = SessionLocal()
    users = db.query(User).all()
    for user in users:
        user_image = np.frombuffer(user.image, np.uint8)
        user_img = cv2.imdecode(user_image, cv2.IMREAD_COLOR)
        user_rgb_img = cv2.cvtColor(user_img, cv2.COLOR_BGR2RGB)
        user_image_encoding = face_recognition.face_encodings(user_rgb_img)

        if len(user_image_encoding) > 0:
            user_image_encoding = user_image_encoding[0]
            matches = face_recognition.compare_faces([user_image_encoding], uploaded_image_encoding)
            if matches[0]:
                add_log(user, "Access approved")
                db.close()
                return {"result": "approved"}

    db.close()
    add_log(None, "Access denied: No matching face found.")
    return {"result": "denied"}

# Run the server (adjusted to use the public IP)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)  # Accessible from public IP: 34.172.135.76:8000
