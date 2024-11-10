from fastapi import FastAPI, HTTPException, UploadFile, File, Depends, Form
from uuid import uuid4
import cv2
import numpy as np
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import create_engine, Column, Integer, String, Sequence, LargeBinary, DateTime, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.sql import func
import os
import face_recognition
from pydantic import BaseModel
from sqlalchemy.orm import Session
from io import BytesIO
from typing import List

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


class Employee(Base):
    __tablename__ = 'employees'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(255))
    email = Column(String(255))
    image_path = Column(String(255))


# Logs table
class Log(Base):
    __tablename__ = 'logs'
    id = Column(Integer, Sequence('log_id_seq'), primary_key=True)
    user_id = Column(Integer, ForeignKey('users.id'))
    time = Column(DateTime(timezone=True), server_default=func.now())
    status = Column(String(50))
    user = relationship("User", back_populates="logs")

# Esquema de Pydantic para la respuesta
class EmployeeSchema(BaseModel):
    id: str
    name: str
    email: str
    # image_path: str

    class Config:
        orm_mode = True



# Create the users and logs tables if they don't exist
Base.metadata.create_all(bind=engine)

# Function to add a log entry
def add_log(user, status):
    db = SessionLocal()
    new_log = Log(user=user, status=status)
    db.add(new_log)
    db.commit()
    db.close()

class EmployeeCreate(BaseModel):
    name: str
    email: str

# Endpoint para listar todos los empleados
@app.get("/api/v1/employee", response_model=List[EmployeeSchema])
async def list_employees():
    db = SessionLocal()
    employees = db.query(Employee).all()
    # Convierte cada id a string para evitar problemas de serialización
    return [{"id": str(emp.id), "name": emp.name, "email": emp.email, "image_path": emp.image_path} for emp in
            employees]

@app.post('/api/v1/employee')
async def add_employee(
        name: str = Form(),
        email: str = Form(),
        face: UploadFile = File(),
        # db: Session = Depends(SessionLocal)
):
    """
    Permite crear un nuevo empleado que sea reconocido por el sistema
    :param name: Nombre del empleado
    :param email: Correo del empleado
    :param face: Imagen con el rostro autorizado
    :return:
    """
    db = SessionLocal()
    # Validar que el archivo sea una imagen JPG
    if face.content_type != 'image/jpeg':
        raise HTTPException(status_code=400, detail="La imagen debe estar en formato JPG")

    # Verificar si el empleado ya existe por su email
    existing_employee = db.query(Employee).filter(Employee.email == email).first()
    if existing_employee:
        raise HTTPException(status_code=409, detail="El empleado ya existe")

    # Crear el nuevo empleado y asignar la ruta de la imagen
    new_employee = Employee(name=name, email=email)
    db.add(new_employee)
    db.commit()  # Esto es necesario para que el id del empleado sea generado
    db.refresh(new_employee)

    # Guardar la imagen en el directorio especificado
    image_path = f"./face_img/{new_employee.id}.jpg"
    with open(image_path, "wb") as image_file:
        image_file.write(await face.read())

    # Actualizar el path de la imagen en la base de datos
    new_employee.image_path = image_path
    db.add(new_employee)
    db.commit()

    return {
        "status": "success",
        "id": new_employee.id,
    }


@app.post('/api/v1/search_face')
async def search_face(
        face: UploadFile = File(),
):
    """
    Busca un rostro vs los previamente autorizados
    :param face: Rostro a identificar en jpg
    :return:
    """

    # Verifica que el archivo sea una imagen JPG
    if face.content_type != 'image/jpeg':
        raise HTTPException(status_code=400, detail="La imagen debe estar en formato JPG")

    # Lee el contenido de la imagen en memoria y conviértelo en un objeto compatible
    face_bytes = await face.read()
    target_image = face_recognition.load_image_file(BytesIO(face_bytes))
    target_encoding = face_recognition.face_encodings(target_image)

    if not target_encoding:
        raise HTTPException(status_code=400, detail="No se detectó ningún rostro en la imagen proporcionada.")

    target_encoding = target_encoding[0]  # Extrae el primer rostro encontrado

    db = SessionLocal()

    # Recorre cada registro en la base de datos para comparar la imagen cargada
    for employee in db.query(Employee).all():
        image_path = f"./face_img/{employee.id}.jpg"

        # Verifica si el archivo de imagen existe
        if os.path.exists(image_path):
            # Carga la imagen del empleado
            employee_image = face_recognition.load_image_file(image_path)
            employee_encodings = face_recognition.face_encodings(employee_image)

            # Si no hay codificaciones en la imagen almacenada, la omite
            if not employee_encodings:
                continue

            # Compara la imagen enviada con la del empleado
            if face_recognition.compare_faces([employee_encodings[0]], target_encoding, tolerance=0.6)[0]:
                return {"employee_id": str(employee.id)}

    # Si no se encuentra coincidencia
    raise HTTPException(status_code=404, detail="No se encontró coincidencia para el rostro proporcionado.")



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
