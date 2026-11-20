"""CareSlot - Hospital Appointment and OPD Scheduling API.

Classroom project only. X-Role is a simulated role header, not authentication.
Use fictional patient records only. Do not use this application for real care.
"""

import json
import os
from datetime import date, datetime, time, timedelta
from typing import Literal

from fastapi import FastAPI, Header, HTTPException, Response
from pydantic import BaseModel, Field


# =====================================================================
# 1. SETTINGS - keep business limits in one place.
# =====================================================================

SLOT_DURATION_MINUTES = 30
MAX_APPOINTMENTS_PER_DOCTOR_PER_DAY = 8
VALID_ROLES = {"patient", "receptionist", "admin"}
APPOINTMENT_STATUSES = {"booked", "cancelled", "completed"}

app = FastAPI(
    title="CareSlot - Hospital Appointment API",
    description=(
        "A beginner-friendly hospital OPD appointment backend. "
        "It demonstrates doctors, patients, departments, appointments, "
        "role checks, scheduling rules, JSON storage and reports. "
        "Use fictional data only; X-Role is a classroom simulation."
    ),
    version="1.0.0",
)

@app.get("/")
def about():
    return {"For Details":"Go to /docs"}
# =====================================================================
# 2. STORAGE - JSON files persist after a server restart.
# =====================================================================

DATA_FOLDER = os.environ.get(
    "CARESLOT_DATA_DIR", os.path.dirname(os.path.abspath(__file__))
)
os.makedirs(DATA_FOLDER, exist_ok=True)

DEPARTMENTS_FILE = os.path.join(DATA_FOLDER, "departments.json")
DOCTORS_FILE = os.path.join(DATA_FOLDER, "doctors.json")
PATIENTS_FILE = os.path.join(DATA_FOLDER, "patients.json")
APPOINTMENTS_FILE = os.path.join(DATA_FOLDER, "appointments.json")

STARTER_DEPARTMENTS = [
    {"id": 1, "name": "Cardiology", "description": "Heart and circulation"},
    {"id": 2, "name": "Orthopaedics", "description": "Bones and joints"},
    {"id": 3, "name": "Dermatology", "description": "Skin and hair"},
]

STARTER_DOCTORS = [
    {
        "id": 1,
        "name": "Dr Asha Rao",
        "speciality": "Cardiology",
        "department_id": 1,
        "consultation_fee": 500,
        "working_start": "09:00",
        "working_end": "13:00",
        "is_active": True,
    },
    {
        "id": 2,
        "name": "Dr Rahul Nair",
        "speciality": "Orthopaedics",
        "department_id": 2,
        "consultation_fee": 400,
        "working_start": "09:00",
        "working_end": "13:00",
        "is_active": True,
    },
    {
        "id": 3,
        "name": "Dr Meera Shah",
        "speciality": "Dermatology",
        "department_id": 3,
        "consultation_fee": 350,
        "working_start": "10:00",
        "working_end": "14:00",
        "is_active": True,
    },
]

STARTER_PATIENTS = [
    {"id": 1, "name": "Sample Patient One", "phone": "9000000001", "age": 25},
    {"id": 2, "name": "Sample Patient Two", "phone": "9000000002", "age": 31},
]

STARTER_APPOINTMENTS = []


def save_data(path: str, data: list[dict]) -> None:
    """Save one list of records to a JSON file."""
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, indent=2, ensure_ascii=False)

def load_data(path: str, starter: list[dict]) -> list[dict]:
    if not os.path.exists(path):
        data = [dict(item) for item in starter]
        save_data(path, data)
        return data

    with open(path, "r", encoding="utf-8") as file:
        data = json.load(file)

    if isinstance(data, list):
        return data

    data = [dict(item) for item in starter]
    save_data(path, data)
    return data


departments = load_data(DEPARTMENTS_FILE, STARTER_DEPARTMENTS)
doctors = load_data(DOCTORS_FILE, STARTER_DOCTORS)
patients = load_data(PATIENTS_FILE, STARTER_PATIENTS)
appointments = load_data(APPOINTMENTS_FILE, STARTER_APPOINTMENTS)


def save_departments() -> None:
    save_data(DEPARTMENTS_FILE, departments)


def save_doctors() -> None:
    save_data(DOCTORS_FILE, doctors)


def save_patients() -> None:
    save_data(PATIENTS_FILE, patients)


def save_appointments() -> None:
    save_data(APPOINTMENTS_FILE, appointments)


# =====================================================================
# 3. PYDANTIC MODELS - input models validate requests; output models shape replies.
# =====================================================================

class DepartmentIn(BaseModel):
    name: str = Field(min_length=2, max_length=60, examples=["Neurology"])
    description: str = Field(default="", max_length=200, examples=["Brain and nerves"])


class DepartmentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=60)
    description: str | None = Field(default=None, max_length=200)


class DepartmentOut(BaseModel):
    id: int
    name: str
    description: str


class DoctorIn(BaseModel):
    name: str = Field(min_length=3, max_length=80, examples=["Dr Kavya Iyer"])
    speciality: str = Field(min_length=2, max_length=60, examples=["Neurology"])
    department_id: int = Field(gt=0, examples=[1])
    consultation_fee: int = Field(ge=0, le=10000, examples=[450])
    working_start: str = Field(default="09:00", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    working_end: str = Field(default="13:00", pattern=r"^([01]\d|2[0-3]):[0-5]\d$")


class DoctorUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=3, max_length=80)
    speciality: str | None = Field(default=None, min_length=2, max_length=60)
    department_id: int | None = Field(default=None, gt=0)
    consultation_fee: int | None = Field(default=None, ge=0, le=10000)
    working_start: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    working_end: str | None = Field(default=None, pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    is_active: bool | None = Field(default=None)


class DoctorOut(BaseModel):
    id: int
    name: str
    speciality: str
    department_id: int
    consultation_fee: int
    working_start: str
    working_end: str
    is_active: bool


class PatientIn(BaseModel):
    name: str = Field(min_length=2, max_length=70, examples=["Ananya Rao"])
    phone: str = Field(pattern=r"^[6-9][0-9]{9}$", examples=["9876543210"])
    age: int = Field(ge=0, le=120, examples=[22])


class PatientUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=70)
    phone: str | None = Field(default=None, pattern=r"^[6-9][0-9]{9}$")
    age: int | None = Field(default=None, ge=0, le=120)


class PatientOut(BaseModel):
    id: int
    name: str
    phone: str
    age: int


class AppointmentIn(BaseModel):
    patient_id: int = Field(gt=0, examples=[1])
    doctor_id: int = Field(gt=0, examples=[1])
    appointment_date: date = Field(examples=["2026-12-05"])
    appointment_time: time = Field(examples=["09:30"])
    reason: str = Field(min_length=3, max_length=250, examples=["Routine consultation"])


class RescheduleIn(BaseModel):
    appointment_date: date = Field(examples=["2026-12-06"])
    appointment_time: time = Field(examples=["10:00"])


class AppointmentOut(BaseModel):
    id: int
    patient_id: int
    doctor_id: int
    appointment_date: str
    appointment_time: str
    reason: str
    status: Literal["booked", "cancelled", "completed"]
    created_on: str


# =====================================================================
# 4. HELPERS - shared checks are written once and reused by endpoints.
# =====================================================================


def check_role(x_role: str | None, allowed: list[str]) -> None:
    """Return 401 for missing/unknown role; 403 for a known but blocked role."""
    if x_role.strip().lower() not in VALID_ROLES:
        raise HTTPException(
            status_code=401,
            detail="Send X-Role with patient, receptionist or admin",
        )
    if x_role.strip().lower() not in allowed:
        raise HTTPException(
            status_code=403,
            detail=f"The role '{x_role}' is not allowed to do this",
        )


def next_id(items: list[dict]) -> int:
    return max([item["id"] for item in items], default=0) + 1


def find_record(items: list[dict], record_id: int, label: str) -> dict:
    for item in items:
        if item["id"] == record_id:
            return item
    raise HTTPException(status_code=404, detail=f"{label} not found")


def find_department(department_id: int) -> dict:
    return find_record(departments, department_id, "Department")


def find_department_by_name(name: str) -> dict:
    """Case-insensitive department lookup, e.g. 'cardiology' finds 'Cardiology'."""
    wanted = name.strip().lower()
    for department in departments:
        if department["name"].lower() == wanted:
            return department
    raise HTTPException(status_code=404, detail="Department not found")


def find_doctor(doctor_id: int) -> dict:
    return find_record(doctors, doctor_id, "Doctor")


def find_patient(patient_id: int) -> dict:
    return find_record(patients, patient_id, "Patient")


def find_appointment(appointment_id: int) -> dict:
    return find_record(appointments, appointment_id, "Appointment")


def effective_today(today: date | None) -> date:
    """Optional today=... is a classroom test clock for date-based rules."""
    return today if today is not None else date.today()


def appointment_sort_key(item: dict) -> tuple[str, str]:
    """Sort appointments by date first, then by time."""
    return (item["appointment_date"], item["appointment_time"])


def validate_working_hours(start_text: str, end_text: str) -> None:
    start = time.fromisoformat(start_text)
    end = time.fromisoformat(end_text)
    if start >= end:
        raise HTTPException(
            status_code=422,
            detail="working_end must be later than working_start",
        )


def booked_appointments_for_doctor(
    doctor_id: int, target_date: date, exclude_appointment_id: int | None = None
) -> list[dict]:
    result = []
    for appointment in appointments:
        if (
            appointment["doctor_id"] == doctor_id
            and appointment["appointment_date"] == target_date.isoformat()
            and appointment["status"] in ("booked", "completed")
            and appointment["id"] != exclude_appointment_id
        ):
            result.append(appointment)
    return result


def patient_has_doctor_booking(
    patient_id: int,
    doctor_id: int,
    target_date: date,
    exclude_appointment_id: int | None = None,
) -> bool:
    for appointment in appointments:
        if (
            appointment["patient_id"] == patient_id
            and appointment["doctor_id"] == doctor_id
            and appointment["appointment_date"] == target_date.isoformat()
            and appointment["status"] == "booked"
            and appointment["id"] != exclude_appointment_id
        ):
            return True
    return False


def available_slots(
    doctor: dict,
    target_date: date,
    today: date,
    exclude_appointment_id: int | None = None,
) -> list[str]:
    """Build 30-minute slots from the doctor's working hours and remove booked ones."""
    if not doctor["is_active"] or target_date < today:
        return []

    already_booked = booked_appointments_for_doctor(
        doctor["id"], target_date, exclude_appointment_id
    )
    if len(already_booked) >= MAX_APPOINTMENTS_PER_DOCTOR_PER_DAY:
        return []

    start = datetime.combine(target_date, time.fromisoformat(doctor["working_start"]))
    end = datetime.combine(target_date, time.fromisoformat(doctor["working_end"]))
    slot_length = timedelta(minutes=SLOT_DURATION_MINUTES)
    result = []

    while start + slot_length <= end:
        slot_text = start.strftime("%H:%M")
        occupied = any(
            item["appointment_time"] == slot_text for item in already_booked
        )
        is_past_time_today = (
            target_date == today
            and today == date.today()
            and start.time() <= datetime.now().time().replace(second=0, microsecond=0)
        )
        if (
            not occupied
            and not is_past_time_today
            and len(already_booked) + len(result) < MAX_APPOINTMENTS_PER_DOCTOR_PER_DAY
        ):
            result.append(slot_text)
        start += slot_length

    return result


def validate_new_appointment(
    patient_id: int,
    doctor: dict,
    target_date: date,
    target_time: time,
    today: date,
    exclude_appointment_id: int | None = None,
) -> None:
    if target_date < today:
        raise HTTPException(status_code=400, detail="Cannot book an appointment in the past")
    if target_time.second != 0 or target_time.microsecond != 0:
        raise HTTPException(
            status_code=422,
            detail="Appointment time must be entered to the nearest minute",
        )
    if (
        target_date == today
        and today == date.today()
        and target_time <= datetime.now().time().replace(second=0, microsecond=0)
    ):
        raise HTTPException(status_code=400, detail="Cannot book a time that has already passed")
    if not doctor["is_active"]:
        raise HTTPException(status_code=409, detail="This doctor is not accepting appointments")
    if patient_has_doctor_booking(
        patient_id, doctor["id"], target_date, exclude_appointment_id
    ):
        raise HTTPException(
            status_code=409,
            detail="A patient may have only one active appointment with the same doctor per day",
        )

    slot_text = target_time.strftime("%H:%M")
    slots = available_slots(
        doctor, target_date, today, exclude_appointment_id
    )
    if slot_text not in slots:
        raise HTTPException(
            status_code=409,
            detail="That slot is unavailable; check the doctor's available slots",
        )


# =====================================================================
# 5. ENDPOINTS - one function per API route.
# =====================================================================

# ----- System -----

@app.get("/health", tags=["system"], summary="Check whether the API is running")
def health():
    return {"status": "ok", "application": "CareSlot"}


# ----- Departments (M1) -----

@app.get("/departments", response_model=list[DepartmentOut], tags=["departments"])
def list_departments():
    return departments


@app.post(
    "/departments",
    status_code=201,
    response_model=DepartmentOut,
    tags=["departments"],
)
def add_department(
    body: DepartmentIn, x_role: str | None = Header(default=None)
):
    check_role(x_role, ["admin"])
    for department in departments:
        if department["name"].lower() == body.name.lower():
            raise HTTPException(status_code=409, detail="Department already exists")
    department = {
        "id": next_id(departments),
        "name": body.name,
        "description": body.description,
    }
    departments.append(department)
    save_departments()
    return department


@app.patch(
    "/departments/{department_id}",
    response_model=DepartmentOut,
    tags=["departments"],
)
def update_department(
    department_id: int,
    body: DepartmentUpdate,
    x_role: str | None = Header(default=None),
):
    check_role(x_role, ["admin"])
    department = find_department(department_id)
    changes = body.model_dump(exclude_none=True)
    if "name" in changes:
        for other in departments:
            if other["id"] != department_id and other["name"].lower() == changes["name"].lower():
                raise HTTPException(status_code=409, detail="Department name already exists")
    department.update(changes)
    save_departments()
    return department


@app.delete(
    "/departments/{department_id}", status_code=204, tags=["departments"]
)
def delete_department(
    department_id: int, x_role: str | None = Header(default=None)
):
    check_role(x_role, ["admin"])
    department = find_department(department_id)
    if any(doctor["department_id"] == department_id for doctor in doctors):
        raise HTTPException(status_code=409, detail="Department still has doctors")
    departments.remove(department)
    save_departments()
    return Response(status_code=204)


# ----- Doctors (M2) -----

@app.get("/doctors", response_model=list[DoctorOut], tags=["doctors"])
def list_doctors(
    department_id: int | None = None,
    speciality: str | None = None,
    only_active: bool = True,
):
    """List doctors; department_id and speciality are query-parameter filters."""
    result = []
    for doctor in doctors:
        if department_id is not None and doctor["department_id"] != department_id:
            continue
        if speciality is not None and speciality.lower() not in doctor["speciality"].lower():
            continue
        if only_active and not doctor["is_active"]:
            continue
        result.append(doctor)
    return result


@app.get("/doctors/{doctor_id}", response_model=DoctorOut, tags=["doctors"])
def get_doctor(doctor_id: int):
    return find_doctor(doctor_id)


@app.get("/doctors/{doctor_id}/slots", tags=["doctors"])
def get_doctor_slots(
    doctor_id: int,
    appointment_date: date,
    today: date | None = None,
):
    doctor = find_doctor(doctor_id)
    selected_day = effective_today(today)
    return {
        "doctor_id": doctor_id,
        "doctor_name": doctor["name"],
        "appointment_date": appointment_date.isoformat(),
        "slot_duration_minutes": SLOT_DURATION_MINUTES,
        "available_slots": available_slots(doctor, appointment_date, selected_day),
    }


@app.post("/doctors", status_code=201, response_model=DoctorOut, tags=["doctors"])
def add_doctor(body: DoctorIn, x_role: str | None = Header(default=None)):
    check_role(x_role, ["admin"])
    find_department(body.department_id)
    validate_working_hours(body.working_start, body.working_end)
    doctor = {
        "id": next_id(doctors),
        "name": body.name,
        "speciality": body.speciality,
        "department_id": body.department_id,
        "consultation_fee": body.consultation_fee,
        "working_start": body.working_start,
        "working_end": body.working_end,
        "is_active": True,
    }
    doctors.append(doctor)
    save_doctors()
    return doctor


@app.patch("/doctors/{doctor_id}", response_model=DoctorOut, tags=["doctors"])
def update_doctor(
    doctor_id: int,
    body: DoctorUpdate,
    x_role: str | None = Header(default=None),
):
    check_role(x_role, ["admin"])
    doctor = find_doctor(doctor_id)
    changes = body.model_dump(exclude_none=True)
    if "department_id" in changes:
        find_department(changes["department_id"])

    start_text = changes.get("working_start", doctor["working_start"])
    end_text = changes.get("working_end", doctor["working_end"])
    validate_working_hours(start_text, end_text)

    if changes.get("is_active") is False:
        has_bookings = any(
            item["doctor_id"] == doctor_id and item["status"] == "booked"
            for item in appointments
        )
        if has_bookings:
            raise HTTPException(status_code=409, detail="Doctor has active appointments")

    doctor.update(changes)
    save_doctors()
    return doctor


@app.delete("/doctors/{doctor_id}", status_code=204, tags=["doctors"])
def delete_doctor(doctor_id: int, x_role: str | None = Header(default=None)):
    check_role(x_role, ["admin"])
    doctor = find_doctor(doctor_id)
    if any(item["doctor_id"] == doctor_id for item in appointments):
        raise HTTPException(status_code=409, detail="Doctor has appointment history")
    doctors.remove(doctor)
    save_doctors()
    return Response(status_code=204)


# ----- Patients (M3) -----

@app.post("/patients", status_code=201, response_model=PatientOut, tags=["patients"])
def add_patient(body: PatientIn, x_role: str | None = Header(default=None)):
    check_role(x_role, ["patient", "receptionist", "admin"])
    phone = body.phone
    if any(item["phone"] == phone for item in patients):
        raise HTTPException(status_code=409, detail="Phone number is already registered")
    patient = {
        "id": next_id(patients),
        "name": body.name,
        "phone": phone,
        "age": body.age,
    }
    patients.append(patient)
    save_patients()
    return patient


@app.get("/patients/{patient_id}", response_model=PatientOut, tags=["patients"])
def get_patient(
    patient_id: int, x_role: str | None = Header(default=None)
):
    check_role(x_role, ["receptionist", "admin"])
    return find_patient(patient_id)


@app.patch("/patients/{patient_id}", response_model=PatientOut, tags=["patients"])
def update_patient(
    patient_id: int,
    body: PatientUpdate,
    x_role: str | None = Header(default=None),
):
    check_role(x_role, ["receptionist", "admin"])
    patient = find_patient(patient_id)
    changes = body.model_dump(exclude_none=True)
    if "phone" in changes:
        for other in patients:
            if other["id"] != patient_id and other["phone"] == changes["phone"]:
                raise HTTPException(status_code=409, detail="Phone number is already registered")
    patient.update(changes)
    save_patients()
    return patient


@app.delete("/patients/{patient_id}", status_code=204, tags=["patients"])
def delete_patient(
    patient_id: int, x_role: str | None = Header(default=None)
):
    check_role(x_role, ["admin"])
    patient = find_patient(patient_id)
    if any(item["patient_id"] == patient_id for item in appointments):
        raise HTTPException(status_code=409, detail="Patient has appointment history")
    patients.remove(patient)
    save_patients()
    return Response(status_code=204)


# ----- Appointments: booking and listing (M4) -----

@app.post(
    "/appointments",
    status_code=201,
    response_model=AppointmentOut,
    tags=["appointments"],
)
def book_appointment(
    body: AppointmentIn,
    x_role: str | None = Header(default=None),
    today: date | None = None,
):
    check_role(x_role, ["patient", "receptionist", "admin"])
    find_patient(body.patient_id)
    doctor = find_doctor(body.doctor_id)
    selected_day = effective_today(today)
    validate_new_appointment(
        body.patient_id,
        doctor,
        body.appointment_date,
        body.appointment_time,
        selected_day,
    )

    appointment = {
        "id": next_id(appointments),
        "patient_id": body.patient_id,
        "doctor_id": body.doctor_id,
        "appointment_date": body.appointment_date.isoformat(),
        "appointment_time": body.appointment_time.strftime("%H:%M"),
        "reason": body.reason,
        "status": "booked",
        "created_on": date.today().isoformat(),
    }
    appointments.append(appointment)
    save_appointments()
    return appointment


@app.get(
    "/appointments/{appointment_id}",
    response_model=AppointmentOut,
    tags=["appointments"],
)
def get_appointment(
    appointment_id: int, x_role: str | None = Header(default=None)
):
    check_role(x_role, ["patient", "receptionist", "admin"])
    return find_appointment(appointment_id)


@app.get(
    "/appointments", response_model=list[AppointmentOut], tags=["appointments"]
)
def list_appointments(
    status: Literal["booked", "cancelled", "completed"] | None = None,
    appointment_date: date | None = None,
    x_role: str | None = Header(default=None),
):
    check_role(x_role, ["receptionist", "admin"])
    result = []
    for appointment in appointments:
        if status is not None and appointment["status"] != status:
            continue
        if (
            appointment_date is not None
            and appointment["appointment_date"] != appointment_date.isoformat()
        ):
            continue
        result.append(appointment)
    return result


# ----- Appointment lifecycle: cancel, reschedule, complete (M5) -----

@app.post(
    "/appointments/{appointment_id}/cancel",
    response_model=AppointmentOut,
    tags=["appointments"],
)
def cancel_appointment(
    appointment_id: int,
    x_role: str | None = Header(default=None),
    today: date | None = None,
):
    check_role(x_role, ["patient", "receptionist", "admin"])
    appointment = find_appointment(appointment_id)
    selected_day = effective_today(today)
    if appointment["status"] != "booked":
        raise HTTPException(status_code=409, detail="Only a booked appointment can be cancelled")
    appointment_day = date.fromisoformat(appointment["appointment_date"])
    if appointment_day <= selected_day:
        raise HTTPException(
            status_code=409,
            detail="Cancellation is allowed only before the appointment day",
        )
    appointment["status"] = "cancelled"
    save_appointments()
    return appointment


@app.post(
    "/appointments/{appointment_id}/reschedule",
    response_model=AppointmentOut,
    tags=["appointments"],
)
def reschedule_appointment(
    appointment_id: int,
    body: RescheduleIn,
    x_role: str | None = Header(default=None),
    today: date | None = None,
):
    check_role(x_role, ["patient", "receptionist", "admin"])
    appointment = find_appointment(appointment_id)
    selected_day = effective_today(today)

    if appointment["status"] != "booked":
        raise HTTPException(status_code=409, detail="Only a booked appointment can be rescheduled")
    old_day = date.fromisoformat(appointment["appointment_date"])
    if old_day <= selected_day:
        raise HTTPException(status_code=409, detail="Past or same-day appointments cannot be rescheduled")

    doctor = find_doctor(appointment["doctor_id"])
    validate_new_appointment(
        appointment["patient_id"],
        doctor,
        body.appointment_date,
        body.appointment_time,
        selected_day,
        exclude_appointment_id=appointment_id,
    )

    appointment["appointment_date"] = body.appointment_date.isoformat()
    appointment["appointment_time"] = body.appointment_time.strftime("%H:%M")
    save_appointments()
    return appointment


@app.post(
    "/appointments/{appointment_id}/complete",
    response_model=AppointmentOut,
    tags=["appointments"],
)
def complete_appointment(
    appointment_id: int,
    x_role: str | None = Header(default=None),
    today: date | None = None,
):
    check_role(x_role, ["receptionist", "admin"])
    appointment = find_appointment(appointment_id)
    selected_day = effective_today(today)
    if appointment["status"] != "booked":
        raise HTTPException(status_code=409, detail="Only a booked appointment can be completed")
    appointment_day = date.fromisoformat(appointment["appointment_date"])
    if appointment_day > selected_day:
        raise HTTPException(status_code=409, detail="A future appointment cannot be completed")
    appointment["status"] = "completed"
    save_appointments()
    return appointment


# ----- Reports (M6) -----

@app.get("/stats", tags=["reports"], summary="Overall hospital appointment summary")
def overall_stats(x_role: str | None = Header(default=None)):
    check_role(x_role, ["receptionist", "admin"])
    counts = {status: 0 for status in APPOINTMENT_STATUSES}
    for appointment in appointments:
        counts[appointment["status"]] += 1
    return {
        "department_count": len(departments),
        "doctor_count": len(doctors),
        "patient_count": len(patients),
        "appointment_count": len(appointments),
        "appointment_status_counts": counts,
    }


@app.get("/stats/doctors", tags=["reports"], summary="Appointment counts for every doctor")
def doctor_stats(x_role: str | None = Header(default=None)):
    check_role(x_role, ["admin"])
    result = []
    for doctor in doctors:
        matching = [item for item in appointments if item["doctor_id"] == doctor["id"]]
        result.append(
            {
                "doctor_id": doctor["id"],
                "doctor_name": doctor["name"],
                "total_appointments": len(matching),
                "booked": sum(item["status"] == "booked" for item in matching),
                "cancelled": sum(item["status"] == "cancelled" for item in matching),
                "completed": sum(item["status"] == "completed" for item in matching),
            }
        )
    return result


@app.get("/stats/daily", tags=["reports"], summary="Appointment counts for one date")
def daily_stats(
    appointment_date: date,
    x_role: str | None = Header(default=None),
):
    check_role(x_role, ["receptionist", "admin"])
    matching = [
        item for item in appointments
        if item["appointment_date"] == appointment_date.isoformat()
    ]
    return {
        "appointment_date": appointment_date.isoformat(),
        "total": len(matching),
        "booked": sum(item["status"] == "booked" for item in matching),
        "cancelled": sum(item["status"] == "cancelled" for item in matching),
        "completed": sum(item["status"] == "completed" for item in matching),
    }


@app.get(
    "/stats/doctors/{doctor_id}",
    tags=["reports"],
    summary="Appointment counts for one doctor",
)
def single_doctor_stats(doctor_id: int, x_role: str | None = Header(default=None)):
    check_role(x_role, ["admin"])
    doctor = find_doctor(doctor_id)
    matching = [item for item in appointments if item["doctor_id"] == doctor_id]
    return {
        "doctor_id": doctor["id"],
        "doctor_name": doctor["name"],
        "speciality": doctor["speciality"],
        "is_active": doctor["is_active"],
        "total_appointments": len(matching),
        "booked": sum(item["status"] == "booked" for item in matching),
        "cancelled": sum(item["status"] == "cancelled" for item in matching),
        "completed": sum(item["status"] == "completed" for item in matching),
    }


@app.get("/stats/patients", tags=["reports"], summary="Appointment counts for every patient")
def patient_stats(x_role: str | None = Header(default=None)):
    check_role(x_role, ["receptionist", "admin"])
    result = []
    for patient in patients:
        matching = [item for item in appointments if item["patient_id"] == patient["id"]]
        result.append(
            {
                "patient_id": patient["id"],
                "patient_name": patient["name"],
                "total_appointments": len(matching),
                "booked": sum(item["status"] == "booked" for item in matching),
                "cancelled": sum(item["status"] == "cancelled" for item in matching),
                "completed": sum(item["status"] == "completed" for item in matching),
            }
        )
    return result
