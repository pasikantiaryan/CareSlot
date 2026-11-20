"""
check_careslot.py  -  runs the CareSlot test checklist against a RUNNING API
=============================================================================
Covers every row of handbook Section 9 (T1-T52) plus the extra validation,
business-rule and state checks the checklist implies.

HOW TO USE IT
    1. Stop the server, delete departments.json, doctors.json, patients.json
       and appointments.json, then start the server again:
            uvicorn main:app --reload
    2. In a second terminal (once):   pip install requests
    3. Run:                           python check_careslot.py
       To test a server on another port:  python check_careslot.py http://127.0.0.1:8010
    4. Every line says PASS, FAIL or SKIP. To run it again, repeat from step 1.

Restart tests (T51, T52) cannot run inside one script. Instructions are printed
at the end. The script also checks the JSON files on disk when it can find them
(same folder as this script, or the folder in CARESLOT_DATA_DIR).
"""
import json
import os
import sys
from datetime import date, datetime, timedelta

import requests

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
DATA_DIR = os.environ.get("CARESLOT_DATA_DIR", os.path.dirname(os.path.abspath(__file__)))

# Fixed test clock: the handbook's sample dates. Date-based rules use ?today=.
TEST_TODAY = "2099-12-04"   # the day before the appointment day
APPT_DAY = "2099-12-05"
NEXT_DAY = "2099-12-06"
EARLY_TODAY = "2099-12-01"
PAST_DATE = (date.today() - timedelta(days=1)).isoformat()

passed = 0
failed = 0
skipped = 0


# ------------------------------------------------------------------ helpers
def hdr(role):
    return {} if role is None else {"X-Role": role}


def get(path, role=None, params=None):
    return requests.get(BASE + path, headers=hdr(role), params=params)


def post(path, body=None, role=None, params=None):
    return requests.post(BASE + path, json=body, headers=hdr(role), params=params)


def patch(path, body, role=None):
    return requests.patch(BASE + path, json=body, headers=hdr(role))


def delete(path, role=None):
    return requests.delete(BASE + path, headers=hdr(role))


def data(response):
    try:
        return response.json()
    except ValueError:
        return {}


def new_id(response):
    return data(response).get("id")


def section(title):
    print("\n--- " + title + " ---")


def check(name, response, expected_status, test=None):
    """Compare the status code and, if given, a test on the JSON reply."""
    global passed, failed
    ok = response.status_code == expected_status
    if ok and test is not None:
        try:
            ok = bool(test(response.json()))
        except Exception:
            ok = False
    if ok:
        passed += 1
        print("PASS  " + name)
    else:
        failed += 1
        print("FAIL  " + name + "   (got " + str(response.status_code) +
              ", expected " + str(expected_status) + ")   " + response.text[:150])
    return response


def expect(name, ok, detail=""):
    """A check that is not a single HTTP status: counts, slot lists, file contents."""
    global passed, failed
    if ok:
        passed += 1
        print("PASS  " + name)
    else:
        failed += 1
        print("FAIL  " + name + ("   " + detail if detail else ""))


def skip(name, reason):
    global skipped
    skipped += 1
    print("SKIP  " + name + "   (" + reason + ")")


def grid(start, end):
    """The 30-minute slot times the API should offer between start and end (HH:MM)."""
    current = datetime.strptime(start, "%H:%M")
    stop = datetime.strptime(end, "%H:%M")
    result = []
    while current + timedelta(minutes=30) <= stop:
        result.append(current.strftime("%H:%M"))
        current += timedelta(minutes=30)
    return result


def booking(patient_id, doctor_id, day, time_text, reason="Routine consultation"):
    return {
        "patient_id": patient_id,
        "doctor_id": doctor_id,
        "appointment_date": day,
        "appointment_time": time_text,
        "reason": reason,
    }


def tally(items):
    return {
        "total": len(items),
        "booked": sum(item["status"] == "booked" for item in items),
        "cancelled": sum(item["status"] == "cancelled" for item in items),
        "completed": sum(item["status"] == "completed" for item in items),
    }


# ------------------------------------------------------------ clean start?
section("0. Clean start check")
try:
    starter_departments = get("/departments").json()
    starter_doctors = get("/doctors", params={"only_active": "false"}).json()
    starter_appointments = get("/appointments", "admin").json()
    starter_patient_1 = get("/patients/1", "receptionist").status_code
    starter_patient_2 = get("/patients/2", "receptionist").status_code
    starter_patient_3 = get("/patients/3", "receptionist").status_code
except requests.exceptions.ConnectionError:
    print("Cannot reach the server at " + BASE + ". Is it running?")
    sys.exit(1)

if (len(starter_departments) != 3 or len(starter_doctors) != 3 or
        len(starter_appointments) != 0 or starter_patient_1 != 200 or
        starter_patient_2 != 200 or starter_patient_3 != 404):
    print("The data is not a clean start. Stop the server, delete the four JSON files,")
    print("start the server again, then re-run.")
    sys.exit(1)
expect("Clean start: 3 departments, 3 doctors, 2 patients, 0 appointments", True)

# Bookkeeping so the report checks can count what should exist.
alive_departments = {1, 2, 3}
alive_doctors = {1, 2, 3}
alive_patients = {1, 2}

# ================================================================
section("1. Health and browsing, no role needed (T1-T5 and extras)")
check("T1  GET /health -> 200 with status ok", get("/health"), 200,
      lambda d: d["status"] == "ok")
check("T2  GET /departments lists the 3 starter departments", get("/departments"), 200,
      lambda d: len(d) == 3)
check("T3  GET /doctors?department_id=1&speciality=Cardiology -> only doctor 1",
      get("/doctors", params={"department_id": 1, "speciality": "Cardiology"}), 200,
      lambda d: [x["id"] for x in d] == [1])
check("T4  GET /doctors/999 -> 404", get("/doctors/999"), 404)
check("T5  GET /doctors/1/slots for 2099-12-05 -> 8 slots from 09:00 to 12:30", 
      get("/doctors/1/slots", params={"appointment_date": APPT_DAY}), 200,
      lambda d: d["available_slots"] == grid("09:00", "13:00") and len(d["available_slots"]) == 8)
check("    GET /doctors/1 returns the detail", get("/doctors/1"), 200,
      lambda d: d["name"] == "Dr Asha Rao")
check("    GET /doctors speciality filter ignores case (ortho -> doctor 2)",
      get("/doctors", params={"speciality": "ortho"}), 200,
      lambda d: [x["id"] for x in d] == [2])
check("    GET /doctors?department_id=abc -> 422 (bad filter type)",
      get("/doctors", params={"department_id": "abc"}), 422)
check("    GET /doctors/1/slots without appointment_date -> 422",
      get("/doctors/1/slots"), 422)
check("    GET /doctors/1/slots with an impossible date -> 422",
      get("/doctors/1/slots", params={"appointment_date": "2099-13-45"}), 422)
check("    GET /doctors/999/slots -> 404",
      get("/doctors/999/slots", params={"appointment_date": APPT_DAY}), 404)

# ================================================================
section("2. Departments (T6-T10, T46, T48, T49 and extras)")
new_department = {"name": "Neurology", "description": "Brain and nerves"}
check("T6  POST /departments with no X-Role -> 401",
      post("/departments", new_department), 401)
check("T7  POST /departments as patient -> 403",
      post("/departments", new_department, "patient"), 403)
check("    POST /departments as receptionist -> 403 (admin only)",
      post("/departments", new_department, "receptionist"), 403)
check("    POST /departments with X-Role 'Admin' (case-sensitive) -> 401",
      post("/departments", new_department, "Admin"), 401)
r = check("T8  POST /departments as admin -> 201", 
          post("/departments", new_department, "admin"), 201,
          lambda d: d["name"] == "Neurology")
neuro_id = new_id(r)
alive_departments.add(neuro_id)
check("T9  POST /departments duplicate name (any case) -> 409",
      post("/departments", {"name": "neurology"}, "admin"), 409)
check("T10 POST /departments name too short -> 422",
      post("/departments", {"name": "N"}, "admin"), 422)
check("    POST /departments name missing -> 422",
      post("/departments", {"description": "no name"}, "admin"), 422)
check("    PATCH /departments/{id} description as admin -> 200",
      patch(f"/departments/{neuro_id}", {"description": "Brain and spinal cord"}, "admin"), 200,
      lambda d: d["description"] == "Brain and spinal cord")
check("    PATCH /departments as patient -> 403",
      patch(f"/departments/{neuro_id}", {"description": "x"}, "patient"), 403)
check("    PATCH /departments/99 -> 404",
      patch("/departments/99", {"description": "x"}, "admin"), 404)
check("    PATCH /departments to a name already in use -> 409",
      patch(f"/departments/{neuro_id}", {"name": "Cardiology"}, "admin"), 409)
check("T46 DELETE /departments/1 while it has doctors -> 409",
      delete("/departments/1", "admin"), 409)
check("    DELETE /departments as receptionist -> 403",
      delete(f"/departments/{neuro_id}", "receptionist"), 403)
check("T48 DELETE /departments/99 -> 404", delete("/departments/99", "admin"), 404)
check("T49 DELETE unused department as admin -> 204",
      delete(f"/departments/{neuro_id}", "admin"), 204)
alive_departments.discard(neuro_id)
check("    Department list is back to 3 after the delete",
      get("/departments"), 200, lambda d: len(d) == 3)

# ================================================================
section("3. Doctors (T11, T12, T47 later, and doctor rules)")
doctor_vikram = {"name": "Dr Vikram Das", "speciality": "Orthopaedics", "department_id": 2,
                 "consultation_fee": 450, "working_start": "14:00", "working_end": "16:00"}
doctor_long = {"name": "Dr Long Shift", "speciality": "Cardiology", "department_id": 1,
               "consultation_fee": 600, "working_start": "08:00", "working_end": "14:00"}

check("    POST /doctors with no X-Role -> 401", post("/doctors", doctor_vikram), 401)
check("    POST /doctors as patient -> 403", post("/doctors", doctor_vikram, "patient"), 403)
check("    POST /doctors as receptionist -> 403 (admin only)",
      post("/doctors", doctor_vikram, "receptionist"), 403)
check("T11 POST /doctors with unknown department_id 999 -> 404",
      post("/doctors", {**doctor_vikram, "department_id": 999}, "admin"), 404)
check("T12 POST /doctors with working_start 29:99 -> 422",
      post("/doctors", {**doctor_vikram, "working_start": "29:99"}, "admin"), 422)
check("    POST /doctors with working_end before working_start -> 422",
      post("/doctors", {**doctor_vikram, "working_start": "13:00", "working_end": "09:00"},
           "admin"), 422)
check("    POST /doctors name too short -> 422",
      post("/doctors", {**doctor_vikram, "name": "Dr"}, "admin"), 422)
check("    POST /doctors consultation_fee above limit -> 422",
      post("/doctors", {**doctor_vikram, "consultation_fee": 20000}, "admin"), 422)

r = check("    POST /doctors valid as admin -> 201 (active by default)",
          post("/doctors", doctor_vikram, "admin"), 201,
          lambda d: d["name"] == "Dr Vikram Das" and d["is_active"] is True)
vikram_id = new_id(r)                      # expected 4
alive_doctors.add(vikram_id)
r = check("    POST /doctors second valid doctor as admin -> 201",
          post("/doctors", doctor_long, "admin"), 201)
long_id = new_id(r)                        # expected 5
alive_doctors.add(long_id)

check("    PATCH /doctors/{id} as receptionist -> 403",
      patch(f"/doctors/{vikram_id}", {"consultation_fee": 500}, "receptionist"), 403)
check("    PATCH /doctors/{id} with no X-Role -> 401",
      patch(f"/doctors/{vikram_id}", {"consultation_fee": 500}), 401)
check("    PATCH /doctors/{id} fee as admin -> 200",
      patch(f"/doctors/{vikram_id}", {"consultation_fee": 500}, "admin"), 200,
      lambda d: d["consultation_fee"] == 500)
check("    PATCH /doctors working_start after working_end -> 422",
      patch(f"/doctors/{vikram_id}", {"working_start": "17:00"}, "admin"), 422)
check("    PATCH /doctors with unknown department -> 404",
      patch(f"/doctors/{vikram_id}", {"department_id": 999}, "admin"), 404)
check("    PATCH /doctors/99 -> 404", patch("/doctors/99", {"consultation_fee": 500}, "admin"), 404)
check("    GET /doctors?speciality=cardio finds both Cardiology doctors",
      get("/doctors", params={"speciality": "cardio"}), 200,
      lambda d: sorted(x["id"] for x in d) == [1, long_id])

# Dr Meera Shah (3): deactivate while she has no bookings, then check behaviour.
check("    PATCH /doctors/3 is_active false with no bookings -> 200",
      patch("/doctors/3", {"is_active": False}, "admin"), 200,
      lambda d: d["is_active"] is False)
check("    Inactive doctor is hidden from the default doctor list",
      get("/doctors"), 200, lambda d: 3 not in [x["id"] for x in d])
check("    only_active=false still shows the inactive doctor",
      get("/doctors", params={"only_active": "false"}), 200,
      lambda d: 3 in [x["id"] for x in d] and len(d) == 5)
check("    Inactive doctor has no slots",
      get("/doctors/3/slots", params={"appointment_date": APPT_DAY}), 200,
      lambda d: d["available_slots"] == [])
check("    Booking an inactive doctor -> 409",
      post("/appointments", booking(1, 3, APPT_DAY, "10:00"), "patient"), 409)
check("    PATCH /doctors/3 is_active true again -> 200",
      patch("/doctors/3", {"is_active": True}, "admin"), 200,
      lambda d: d["is_active"] is True)

# ================================================================
section("4. Patients (T13-T19 and extras)")
check("    POST /patients with no X-Role -> 401",
      post("/patients", {"name": "No Role", "phone": "9123456780", "age": 30}), 401)
r = check("T13 POST /patients as patient, valid -> 201",
          post("/patients", {"name": "Sample Patient Three", "phone": "9123456780", "age": 30},
               "patient"), 201,
          lambda d: d["phone"] == "9123456780")
alive_patients.add(new_id(r))              # expected 3
check("T14 POST /patients with phone 123 -> 422",
      post("/patients", {"name": "Bad Phone", "phone": "123", "age": 30}, "patient"), 422)
check("T15 POST /patients with a phone already used -> 409",
      post("/patients", {"name": "Copycat", "phone": "9000000001", "age": 30}, "patient"), 409)
check("    POST /patients phone not starting 6-9 -> 422",
      post("/patients", {"name": "Bad Start", "phone": "5123456789", "age": 30}, "patient"), 422)
check("    POST /patients age 121 -> 422",
      post("/patients", {"name": "Too Old", "phone": "9111111111", "age": 121}, "patient"), 422)
check("    POST /patients name 'A' -> 422",
      post("/patients", {"name": "A", "phone": "9111111112", "age": 30}, "patient"), 422)
r = check("    POST /patients as receptionist -> 201",
          post("/patients", {"name": "Spare Patient", "phone": "9100000999", "age": 40},
               "receptionist"), 201)
spare_id = new_id(r)
alive_patients.add(spare_id)

check("T16 GET /patients/1 as patient -> 403", get("/patients/1", "patient"), 403)
check("    GET /patients/1 with no X-Role -> 401", get("/patients/1"), 401)
check("T17 GET /patients/999 as receptionist -> 404",
      get("/patients/999", "receptionist"), 404)
check("    GET /patients/1 as receptionist -> 200",
      get("/patients/1", "receptionist"), 200, lambda d: d["name"] == "Sample Patient One")
check("T18 PATCH /patients/1 as receptionist, change name -> 200",
      patch("/patients/1", {"name": "Sample Patient Updated"}, "receptionist"), 200,
      lambda d: d["name"] == "Sample Patient Updated")
check("    PATCH /patients/1 to a phone used by another patient -> 409",
      patch("/patients/1", {"phone": "9123456780"}, "receptionist"), 409)
check("    PATCH /patients/1 with phone 123 -> 422",
      patch("/patients/1", {"phone": "123"}, "receptionist"), 422)
check("    PATCH /patients/1 as patient -> 403",
      patch("/patients/1", {"age": 26}, "patient"), 403)
check("    PATCH /patients/99 -> 404",
      patch("/patients/99", {"age": 40}, "receptionist"), 404)
check("    DELETE /patients/1 as receptionist -> 403 (admin only)",
      delete("/patients/1", "receptionist"), 403)

# Nine extra patients, so the daily-limit test can fill one doctor's day.
extras = []
for n in range(1, 10):
    r = post("/patients", {"name": f"Test Patient {n:02d}", "phone": f"91000000{n:02d}", "age": 35},
             "receptionist")
    if r.status_code == 201:
        extras.append(new_id(r))
        alive_patients.add(new_id(r))
expect("Setup: 9 extra test patients created", len(extras) == 9, f"created {len(extras)}")

# ================================================================
section("5. Booking (T20-T28 and booking rules)")
check("T21 POST /appointments with no X-Role -> 401",
      post("/appointments", booking(1, 1, APPT_DAY, "09:00")), 401)
check("T22 POST /appointments with unknown patient_id 999 -> 404",
      post("/appointments", booking(999, 1, APPT_DAY, "09:00"), "patient"), 404)
check("T23 POST /appointments with unknown doctor_id 999 -> 404",
      post("/appointments", booking(1, 999, APPT_DAY, "09:00"), "patient"), 404)
check("T24 POST /appointments in the past -> 400",
      post("/appointments", booking(1, 1, PAST_DATE, "09:00"), "patient"), 400)
check("    POST /appointments with today=2099-12-06 for a 12-05 date -> 400 (test clock)",
      post("/appointments", booking(1, 1, APPT_DAY, "09:00"), "patient",
           params={"today": NEXT_DAY}), 400)
check("    POST /appointments reason too short -> 422",
      post("/appointments", booking(1, 1, APPT_DAY, "09:00", reason="ab"), "patient"), 422)
check("    POST /appointments time 25:00 -> 422",
      post("/appointments", booking(1, 1, APPT_DAY, "25:00"), "patient"), 422)
check("    POST /appointments time with seconds (09:00:30) -> 422",
      post("/appointments", booking(1, 1, APPT_DAY, "09:00:30"), "patient"), 422)
check("    POST /appointments with bad role 'nurse' -> 401",
      post("/appointments", booking(1, 1, APPT_DAY, "09:00"), "nurse"), 401)

r = check("T20 POST /appointments valid future free slot -> 201 with status booked",
          post("/appointments", booking(1, 1, APPT_DAY, "09:00"), "patient"), 201,
          lambda d: d["status"] == "booked" and d["appointment_time"] == "09:00"
          and d["appointment_date"] == APPT_DAY)
id1 = new_id(r)                              # Patient 1, doctor 1, 09:00
check("T25 same doctor, date and time (other patient) -> 409 double booking",
      post("/appointments", booking(2, 1, APPT_DAY, "09:00"), "patient"), 409)
check("T26 same patient, same doctor, same date, different time -> 409",
      post("/appointments", booking(1, 1, APPT_DAY, "10:00"), "patient"), 409)
check("T27 time not on the 30-minute grid (09:15) -> 409",
      post("/appointments", booking(2, 1, APPT_DAY, "09:15"), "patient"), 409)
check("    time outside working hours (13:00 for doctor 1) -> 409",
      post("/appointments", booking(2, 1, APPT_DAY, "13:00"), "patient"), 409)
check("    time before working hours (08:30 for doctor 1) -> 409",
      post("/appointments", booking(2, 1, APPT_DAY, "08:30"), "patient"), 409)
r = check("    Second patient books doctor 1 at 09:30 -> 201",
          post("/appointments", booking(2, 1, APPT_DAY, "09:30"), "patient"), 201)
id2 = new_id(r)                              # Patient 2, doctor 1, 09:30

check("    Booked slots disappear from doctor 1's slot list",
      get("/doctors/1/slots", params={"appointment_date": APPT_DAY}), 200,
      lambda d: "09:00" not in d["available_slots"] and "09:30" not in d["available_slots"]
      and "10:00" in d["available_slots"])
check("    Doctor with active bookings cannot be deactivated -> 409",
      patch("/doctors/1", {"is_active": False}, "admin"), 409)
check("    Doctor 1 still active after the refused deactivation",
      get("/doctors/1"), 200, lambda d: d["is_active"] is True)

# ---- Daily limit (T28): doctor 5 works 08:00-14:00 = 12 slots, cap is 8 ----
section("5b. Daily limit and cancellation freeing a slot (T28 and rules)")
limit_times = ["08:00", "08:30", "09:00", "09:30", "10:00", "10:30", "11:00", "11:30"]
limit_pool = [1, 2, 3] + extras[0:5]        # 8 different patients
ids5 = []
for pid, t in zip(limit_pool, limit_times):
    r = check(f"    Doctor 5 booking: patient {pid} at {t} -> 201",
              post("/appointments", booking(pid, long_id, APPT_DAY, t), "patient"), 201)
    ids5.append(new_id(r))

check("T28 Ninth booking for doctor 5 on the same day (cap 8) -> 409",
      post("/appointments", booking(extras[5], long_id, APPT_DAY, "12:00"), "patient"), 409)
check("    Slot list is empty once the daily cap is reached",
      get("/doctors/5/slots", params={"appointment_date": APPT_DAY}), 200,
      lambda d: d["available_slots"] == [])
check("    Cancel one of doctor 5's bookings before the day -> 200",
      post(f"/appointments/{ids5[0]}/cancel", role="patient", params={"today": TEST_TODAY}), 200,
      lambda d: d["status"] == "cancelled")
check("    Cancelled booking frees the slot: only 08:00 is offered (cap room is 1)",
      get("/doctors/5/slots", params={"appointment_date": APPT_DAY}), 200,
      lambda d: d["available_slots"] == ["08:00"])
check("    Rebooking the freed 08:00 slot -> 201",
      post("/appointments", booking(extras[5], long_id, APPT_DAY, "08:00"), "patient"), 201)
check("    Completed visits still count toward the cap",
      post(f"/appointments/{ids5[1]}/complete", role="receptionist", params={"today": APPT_DAY}), 200,
      lambda d: d["status"] == "completed")
check("    After a completion the cap still holds (slot list stays empty)",
      get("/doctors/5/slots", params={"appointment_date": APPT_DAY}), 200,
      lambda d: d["available_slots"] == [])

# ================================================================
section("6. Appointment lifecycle: cancel, reschedule, complete (T33-T41)")
# Doctor 1, 2099-12-05: id1 (09:00, cancelled below), id2 (09:30, booked).
# Y, X and F are new bookings on the same day for the lifecycle tests.
r = check("    Setup: patient books doctor 1 at 10:00 (Y, to be rescheduled)",
          post("/appointments", booking(extras[6], 1, APPT_DAY, "10:00"), "patient"), 201)
id_y = new_id(r)
r = check("    Setup: patient books doctor 1 at 10:30 (X, for same-day and completion tests)",
          post("/appointments", booking(extras[7], 1, APPT_DAY, "10:30"), "patient"), 201)
id_x = new_id(r)
r = check("    Setup: patient books doctor 1 at 11:00 (F, stays booked)",
          post("/appointments", booking(extras[8], 1, APPT_DAY, "11:00"), "patient"), 201)
id_f = new_id(r)
r = check("    Setup: patient books doctor 1 on 2099-12-06 at 11:00 (Z, the occupied target)",
          post("/appointments", booking(extras[0], 1, NEXT_DAY, "11:00"), "patient"), 201)
id_z = new_id(r)

check("T33 Cancel id1 before the appointment day -> 200",
      post(f"/appointments/{id1}/cancel", role="patient", params={"today": TEST_TODAY}), 200,
      lambda d: d["status"] == "cancelled")
check("T34 Cancel the same appointment again -> 409",
      post(f"/appointments/{id1}/cancel", role="patient", params={"today": TEST_TODAY}), 409)
check("T35 Cancel on the appointment day itself -> 409",
      post(f"/appointments/{id_x}/cancel", role="patient", params={"today": APPT_DAY}), 409)
check("    Cancel after the appointment day -> 409",
      post(f"/appointments/{id_x}/cancel", role="patient", params={"today": NEXT_DAY}), 409)
check("    Cancel with no X-Role -> 401",
      post(f"/appointments/{id_x}/cancel", params={"today": TEST_TODAY}), 401)
check("    Cancel unknown appointment -> 404",
      post("/appointments/999/cancel", role="patient", params={"today": TEST_TODAY}), 404)

check("T36 Reschedule Y to a free future slot (2099-12-06 09:00) -> 200",
      post(f"/appointments/{id_y}/reschedule",
           {"appointment_date": NEXT_DAY, "appointment_time": "09:00"},
           "patient", params={"today": EARLY_TODAY}), 200,
      lambda d: d["appointment_date"] == NEXT_DAY and d["appointment_time"] == "09:00")
check("T37 Reschedule Y to an occupied slot (12-06 11:00, Z is there) -> 409",
      post(f"/appointments/{id_y}/reschedule",
           {"appointment_date": NEXT_DAY, "appointment_time": "11:00"},
           "patient", params={"today": EARLY_TODAY}), 409)
check("    Reschedule to a date in the past -> 400",
      post(f"/appointments/{id_y}/reschedule",
           {"appointment_date": "2099-11-30", "appointment_time": "09:00"},
           "patient", params={"today": EARLY_TODAY}), 400)
check("    Reschedule to a time off the 30-minute grid -> 409",
      post(f"/appointments/{id_y}/reschedule",
           {"appointment_date": NEXT_DAY, "appointment_time": "09:15"},
           "patient", params={"today": EARLY_TODAY}), 409)
check("    Reschedule with a malformed time -> 422",
      post(f"/appointments/{id_y}/reschedule",
           {"appointment_date": NEXT_DAY, "appointment_time": "99:00"},
           "patient", params={"today": EARLY_TODAY}), 422)
check("    Reschedule with no X-Role -> 401",
      post(f"/appointments/{id_y}/reschedule",
           {"appointment_date": NEXT_DAY, "appointment_time": "10:00"},
           params={"today": EARLY_TODAY}), 401)
check("T38 Reschedule a cancelled appointment -> 409",
      post(f"/appointments/{id1}/reschedule",
           {"appointment_date": NEXT_DAY, "appointment_time": "10:00"},
           "patient", params={"today": APPT_DAY}), 409)

check("T39 Complete a future appointment (2099-12-05, today 12-04) -> 409",
      post(f"/appointments/{id_x}/complete", role="receptionist", params={"today": TEST_TODAY}), 409)
check("    Patient cannot complete a visit -> 403",
      post(f"/appointments/{id_z}/complete", role="patient", params={"today": APPT_DAY}), 403)
check("T40 Complete an appointment on its own day -> 200 status completed",
      post(f"/appointments/{id_x}/complete", role="receptionist", params={"today": APPT_DAY}), 200,
      lambda d: d["status"] == "completed")
check("T41 Complete the same appointment again -> 409",
      post(f"/appointments/{id_x}/complete", role="receptionist", params={"today": APPT_DAY}), 409)
check("    Cancel a completed appointment -> 409 (final state)",
      post(f"/appointments/{id_x}/cancel", role="patient", params={"today": TEST_TODAY}), 409)
check("    Reschedule a completed appointment -> 409 (final state)",
      post(f"/appointments/{id_x}/reschedule",
           {"appointment_date": NEXT_DAY, "appointment_time": "12:00"},
           "patient", params={"today": TEST_TODAY}), 409)
check("    Complete a cancelled appointment -> 409",
      post(f"/appointments/{id1}/complete", role="receptionist", params={"today": APPT_DAY}), 409)

check("    Doctor 1 slots after the lifecycle: 09:00 and 10:00 free; 09:30, 10:30, 11:00 taken",
      get("/doctors/1/slots", params={"appointment_date": APPT_DAY}), 200,
      lambda d: "09:00" in d["available_slots"] and "10:00" in d["available_slots"]
      and "09:30" not in d["available_slots"] and "10:30" not in d["available_slots"]
      and "11:00" not in d["available_slots"])

# ================================================================
section("7. Appointment lookup and listing (T29-T32 and extras)")
check("T29 GET /appointments/999 as patient -> 404",
      get("/appointments/999", "patient"), 404)
check("    GET /appointments/{id} as patient -> 200",
      get(f"/appointments/{id_x}", "patient"), 200, lambda d: d["status"] == "completed")
check("    GET /appointments/{id} with no X-Role -> 401",
      get(f"/appointments/{id_x}"), 401)
check("T30 GET /appointments?status=booked&appointment_date=2099-12-05 -> both filters work",
      get("/appointments", "receptionist",
          params={"status": "booked", "appointment_date": APPT_DAY}), 200,
      lambda d: all(a["status"] == "booked" and a["appointment_date"] == APPT_DAY for a in d)
      and id2 in [a["id"] for a in d] and id_f in [a["id"] for a in d]
      and id1 not in [a["id"] for a in d] and id_x not in [a["id"] for a in d]
      and len(d) == 9)
check("T31 GET /appointments?status=invalid as admin -> 422",
      get("/appointments", "admin", params={"status": "invalid"}), 422)
check("T32 GET /appointments as patient -> 403",
      get("/appointments", "patient"), 403)
check("    GET /appointments with no X-Role -> 401", get("/appointments"), 401)
check("    GET /appointments with a malformed date -> 422",
      get("/appointments", "receptionist", params={"appointment_date": "not-a-date"}), 422)

# ================================================================
section("8. Deletion protection and allowed deletes (T19, T46-T50 and extras)")
check("T19 DELETE /patients/1 with appointment history -> 409",
      delete("/patients/1", "admin"), 409)
check("    DELETE /patients as receptionist -> 403 (admin only)",
      delete(f"/patients/{spare_id}", "receptionist"), 403)
check("    DELETE /patients/99 as admin -> 404", delete("/patients/99", "admin"), 404)
check("    DELETE /patients/{id} with no history as admin -> 204",
      delete(f"/patients/{spare_id}", "admin"), 204)
alive_patients.discard(spare_id)
check("    Deleted patient is gone -> 404", get(f"/patients/{spare_id}", "receptionist"), 404)

check("T47 DELETE /doctors/1 with appointment history -> 409",
      delete("/doctors/1", "admin"), 409)
check("    DELETE /doctors as receptionist -> 403",
      delete(f"/doctors/{vikram_id}", "receptionist"), 403)
check("    DELETE /doctors/99 as admin -> 404", delete("/doctors/99", "admin"), 404)
check("T50 DELETE unused doctor (Dr Vikram, no appointments) as admin -> 204",
      delete(f"/doctors/{vikram_id}", "admin"), 204)
alive_doctors.discard(vikram_id)
check("    Deleted doctor is gone -> 404", get(f"/doctors/{vikram_id}"), 404)

# ================================================================
section("9. Overall reports (T42-T45 and report checks)")
all_appointments = get("/appointments", "admin").json()
expect("Setup: full appointment list is readable by admin", isinstance(all_appointments, list))

check("T42 GET /stats as patient -> 403", get("/stats", "patient"), 403)
check("    GET /stats with no X-Role -> 401", get("/stats"), 401)
doctors_now = get("/doctors", params={"only_active": "false"}).json()
check("T43 GET /stats as receptionist -> counts match the stored records",
      get("/stats", "receptionist"), 200,
      lambda d: d["appointment_count"] == len(all_appointments)
      and d["appointment_status_counts"] == {
          "booked": tally(all_appointments)["booked"],
          "cancelled": tally(all_appointments)["cancelled"],
          "completed": tally(all_appointments)["completed"]}
      and d["department_count"] == len(alive_departments)
      and d["doctor_count"] == len(doctors_now)
      and d["patient_count"] == len(alive_patients))

check("T44 GET /stats/doctors as admin -> one row per doctor, counts match",
      get("/stats/doctors", "admin"), 200,
      lambda d: len(d) == len(doctors_now) and all(
          row["total_appointments"] == tally([a for a in all_appointments
                                              if a["doctor_id"] == row["doctor_id"]])["total"]
          and row["booked"] == tally([a for a in all_appointments
                                      if a["doctor_id"] == row["doctor_id"]])["booked"]
          and row["cancelled"] == tally([a for a in all_appointments
                                         if a["doctor_id"] == row["doctor_id"]])["cancelled"]
          and row["completed"] == tally([a for a in all_appointments
                                         if a["doctor_id"] == row["doctor_id"]])["completed"]
          for row in d))
check("    GET /stats/doctors as receptionist -> 403 (admin only)",
      get("/stats/doctors", "receptionist"), 403)

day_items = [a for a in all_appointments if a["appointment_date"] == APPT_DAY]
day_counts = tally(day_items)
check("T45 GET /stats/daily?appointment_date=2099-12-05 -> counts for that day",
      get("/stats/daily", "receptionist", params={"appointment_date": APPT_DAY}), 200,
      lambda d: d["total"] == day_counts["total"] and d["booked"] == day_counts["booked"]
      and d["cancelled"] == day_counts["cancelled"] and d["completed"] == day_counts["completed"])
check("    GET /stats/daily as patient -> 403",
      get("/stats/daily", "patient", params={"appointment_date": APPT_DAY}), 403)
check("    GET /stats/daily without a date -> 422",
      get("/stats/daily", "receptionist"), 422)

# ================================================================
section("10. Files on disk, for persistence (T51 and T52 need a manual restart)")
file_checks = [
    ("departments.json", lambda: len(get("/departments").json()), len(alive_departments)),
    ("doctors.json", lambda: len(get("/doctors", params={"only_active": "false"}).json()),
     len(alive_doctors)),
    ("patients.json", lambda: len(alive_patients), len(alive_patients)),
    ("appointments.json", lambda: len(get("/appointments", "admin").json()),
     len(all_appointments)),
]
for file_name, api_count, expected_count in file_checks:
    path = os.path.join(DATA_DIR, file_name)
    if not os.path.exists(path):
        skip(f"{file_name} record count matches the API", f"not found in {DATA_DIR}")
        continue
    try:
        with open(path, "r", encoding="utf-8") as handle:
            stored = json.load(handle)
        expect(f"{file_name} holds the same number of records the API shows",
               isinstance(stored, list) and len(stored) == expected_count == api_count(),
               f"file has {len(stored) if isinstance(stored, list) else 'bad'} records")
    except (ValueError, OSError) as error:
        expect(f"{file_name} is readable JSON", False, str(error))

# ================================================================
print("\n--- 11. Final deletion-safety check ---")
check("    DELETE /departments/2 (Orthopaedics still has doctors? doctor 2 yes) -> 409",
      delete("/departments/2", "admin"), 409)

print("\nPassed: " + str(passed) + "   Failed: " + str(failed) + "   Skipped: " + str(skipped))
print("\nManual restart tests still to do:")
print(" T51  Stop the server (Ctrl+C), start it again WITHOUT deleting the JSON files,")
print("      then check GET /appointments and GET /doctors/1/slots?appointment_date=2099-12-05.")
print("      The same records and slots should appear.")
print(" T52  Copy the folder, put invalid text in the copy's doctors.json, run the server")
print("      from that copy (CARESLOT_DATA_DIR=<copy folder>). The server should start, and")
print("      doctors.json should be restored from starter data.")
sys.exit(1 if failed > 0 else 0)