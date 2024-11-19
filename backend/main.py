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


class Employee(Base):
    __tablename__ = 'employees'
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(255))
    email = Column(String(255))
    access_level = Column(Integer())
    image_path = Column(String(255))
    
    logs = relationship("Log", back_populates="employee")


# Logs table
class Log(Base):
    __tablename__ = 'logs'
    id = Column(Integer, Sequence('log_id_seq'), primary_key=True, nullable=True)
    employee_id = Column(UUID(as_uuid=True), ForeignKey('employees.id'))
    time = Column(DateTime(timezone=True), server_default=func.now())
    status = Column(String(50))
    image_path = Column(String(255))

    employee = relationship("Employee", back_populates="logs")

# Esquema de Pydantic para la respuesta
class EmployeeSchema(BaseModel):
    id: str
    name: str
    email: str
    # image_path: str
    access_level: int

    class Config:
        orm_mode = True



# Create the users and logs tables if they don't exist
Base.metadata.create_all(bind=engine)

# Function to add a log entry
def add_log(employee_id, status, image_path):
    db = SessionLocal()
    new_log = Log(employee_id=employee_id, status=status, image_path=image_path)  # Cambiado a employee_id
    db.add(new_log)
    db.commit()
    db.close()

class EmployeeCreate(BaseModel):
    name: str
    email: str

# Endpoint para listar todos los empleados
@app.get("/api/v1/employee", response_model=List[EmployeeSchema])
async def list_employees():
    """
    Lista todos los empleados registrados en el sistema
    """
    db = SessionLocal()
    employees = db.query(Employee).all()

    # Construir la respuesta con la columna access_level incluida
    return [
        {
            "id": str(emp.id),
            "name": emp.name,
            "email": emp.email,
            "access_level": emp.access_level, 
            "image_path": emp.image_path
        }
        for emp in employees
    ]

@app.post('/api/v1/employee')
async def add_employee(
        name: str = Form(),
        email: str = Form(),
        access_level: str = Form(),
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
    new_employee = Employee(name=name, email=email, access_level=access_level)
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

    transaction_id = str(uuid4())
    image_path = f"./face_img/transactions/{transaction_id}.jpg"
    face_bytes = await face.read()
    with open(image_path, "wb") as f:
        f.write(face_bytes)

    
    target_image = face_recognition.load_image_file(BytesIO(face_bytes))
    target_encoding = face_recognition.face_encodings(target_image)

    if not target_encoding:
        add_log(None, "Face not detected", image_path)
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
                # add_log(employee.id, "Face recognized", image_path)
                # return {"employee_id": str(employee.id)}
                # Validar el nivel de acceso del empleado
                if employee.access_level >= 3:
                    add_log(employee.id, "Face recognized", image_path)
                    return {"employee_id": str(employee.id)}
                else:
                    add_log(employee.id, "Unauthorized access attempt", image_path)
                    raise HTTPException(status_code=403, detail="Acceso no autorizado para el empleado.")

    # Si no se encuentra coincidencia
    add_log(None, "Face not recognized", image_path)
    raise HTTPException(status_code=404, detail="No se encontró coincidencia para el rostro proporcionado.")


@app.get('/api/v1/logs')
def list_logs():
    """
    Lista todos los logs almacenados en la base de datos
    """
    db = SessionLocal()
    logs = db.query(Log).all()

    # Construir la respuesta serializable
    logs_list = [
        {
            "id": log.id,
            "employee_id": log.employee_id,
            "time": log.time.isoformat(),
            "status": log.status,
            "image_path": log.image_path,
        }
        for log in logs
    ]

    db.close()
    return logs_list


# Run the server (adjusted to use the public IP)
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)  # Accessible from public IP: 34.172.135.76:8000
