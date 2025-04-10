from app.extensions import db, login_manager
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, time, timedelta
import uuid
import numpy as np
import os

@login_manager.user_loader
def load_user(user_id):
   return User.query.get(int(user_id))

class User(db.Model, UserMixin):
   id = db.Column(db.Integer, primary_key=True)
   username = db.Column(db.String(80), unique=True, nullable=False)
   email = db.Column(db.String(120), unique=True, nullable=False)
   password_hash = db.Column(db.String(128))
   role = db.Column(db.String(20), nullable=False)  # admin, lecturer, class_rep
   face_encoding = db.Column(db.LargeBinary, nullable=True)
   fingerprint_data = db.Column(db.LargeBinary, nullable=True)
   preferred_biometric = db.Column(db.String(20), default='face')  # face, fingerprint
   sessions = db.relationship('Session', backref='lecturer', lazy=True, foreign_keys='Session.lecturer_id')
   verified_sessions = db.relationship('Session', backref='verifier', lazy=True, foreign_keys='Session.verified_by')
   assigned_sessions = db.relationship('Session', backref='class_rep', lazy=True, foreign_keys='Session.class_rep_id')
   attendance_records = db.relationship('StaffAttendance', backref='staff', lazy=True)
   
   # Additional fields for lecturers
   employee_number = db.Column(db.String(20), nullable=True)
   first_name = db.Column(db.String(50), nullable=True)
   last_name = db.Column(db.String(50), nullable=True)
   department = db.Column(db.String(100), nullable=True)
   
   def set_password(self, password):
       self.password_hash = generate_password_hash(password)
       
   def check_password(self, password):
       return check_password_hash(self.password_hash, password)
   
   def set_face_encoding(self, encoding):
       """Store facial encoding as binary data
       
       Args:
           encoding: Either bytes or numpy array of face encoding
       """
       try:
           if encoding is None:
               self.face_encoding = None
               return
               
           # Convert numpy array to bytes if needed
           if isinstance(encoding, np.ndarray):
               self.face_encoding = encoding.tobytes()
           else:
               # Assume it's already bytes
               self.face_encoding = encoding
               
           # Verify we can read it back (validates format)
           test_read = self.get_face_encoding()
           if test_read is None:
               print("Warning: Stored face encoding cannot be read back")
       except Exception as e:
           print(f"Error setting face encoding: {str(e)}")
           self.face_encoding = None
       
   def get_face_encoding(self):
       """Retrieve facial encoding as numpy array"""
       if not self.face_encoding:
           return None
       
       try:
           # Convert bytes to numpy array
           encoding_np = np.frombuffer(self.face_encoding, dtype=np.float64)
           
           # Verify shape/size is reasonable for face_recognition
           # Most face_recognition models produce 128-dimensional feature vectors
           if len(encoding_np) < 50 or len(encoding_np) > 200:
               print(f"Warning: Face encoding has unusual dimensions: {len(encoding_np)}")
               
           return encoding_np
       except Exception as e:
           print(f"Error decoding face encoding: {str(e)}")
           return None
   
   def verify_face(self, face_encoding, tolerance=0.6):
       """Verify if the given face encoding matches the stored one
       
       Args:
           face_encoding: Numpy array of the face to verify
           tolerance: Threshold for face comparison (lower is stricter)
           
       Returns:
           tuple: (is_match, distance) or (False, None) if no encoding stored
       """
       import face_recognition
       
       stored_encoding = self.get_face_encoding()
       
       if stored_encoding is None:
           return False, None
           
       try:
           # Ensure both encodings have compatible shapes
           if len(stored_encoding) != len(face_encoding):
               print(f"Warning: Encoding length mismatch. Stored: {len(stored_encoding)}, New: {len(face_encoding)}")
               
               # Try to use the smaller length
               min_len = min(len(stored_encoding), len(face_encoding))
               stored_encoding = stored_encoding[:min_len]
               face_encoding = face_encoding[:min_len]
           
           # Calculate distance and match
           face_distance = face_recognition.face_distance([stored_encoding], face_encoding)[0]
           is_match = face_distance <= tolerance
           
           return is_match, face_distance
       except Exception as e:
           print(f"Error during face verification: {str(e)}")
           return False, None
   
   def set_fingerprint_data(self, data):
       self.fingerprint_data = data
       
   def get_fingerprint_data(self):
       if self.fingerprint_data:
           return np.frombuffer(self.fingerprint_data, dtype=np.float64)
       return None
       
   def get_full_name(self):
       if self.first_name and self.last_name:
           return f"{self.first_name} {self.last_name}"
       return self.username
   
   def get_today_attendance(self):
       """Get today's attendance record for the staff member"""
       today = datetime.now().date()
       return StaffAttendance.query.filter_by(
           staff_id=self.id,
           date=today
       ).first()
   
   def is_clocked_in(self):
       """Check if the staff member is currently clocked in"""
       attendance = self.get_today_attendance()
       return attendance and attendance.clock_in and not attendance.clock_out

class Course(db.Model):
   id = db.Column(db.Integer, primary_key=True)
   code = db.Column(db.String(20), unique=True, nullable=False)
   name = db.Column(db.String(100), nullable=False)
   sessions = db.relationship('Session', backref='course', lazy=True)

class Session(db.Model):
   id = db.Column(db.Integer, primary_key=True)
   session_id = db.Column(db.String(36), unique=True, default=lambda: str(uuid.uuid4()))
   course_id = db.Column(db.Integer, db.ForeignKey('course.id'), nullable=False)
   lecturer_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
   class_rep_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
   start_time = db.Column(db.DateTime, nullable=True)
   end_time = db.Column(db.DateTime, nullable=True)
   status = db.Column(db.String(20), default='pending')  # pending, ongoing, completed, verified
   classroom = db.Column(db.String(50), nullable=False)
   verified_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
   lecturer_signature = db.Column(db.Text, nullable=True)
   rep_signature = db.Column(db.Text, nullable=True)
   
   def duration_minutes(self):
       if self.start_time and self.end_time:
           delta = self.end_time - self.start_time
           return delta.total_seconds() / 60
       return 0

class Report(db.Model):
   id = db.Column(db.Integer, primary_key=True)
   title = db.Column(db.String(200), nullable=False)
   filename = db.Column(db.String(255), nullable=False)
   filepath = db.Column(db.String(255), nullable=False)
   format = db.Column(db.String(20), nullable=False)  # csv, xlsx, json
   created_at = db.Column(db.DateTime, default=datetime.now)
   file_size = db.Column(db.Integer, nullable=False)  # Size in bytes
   description = db.Column(db.Text, nullable=True)
   created_by = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
   
   # Relationship with the user who created the report
   user = db.relationship('User', backref='reports')
   
   def get_formatted_size(self):
       """Return human-readable file size"""
       size = self.file_size
       for unit in ['B', 'KB', 'MB', 'GB']:
           if size < 1024 or unit == 'GB':
               return f"{size:.2f} {unit}"
           size /= 1024
   
   def delete_file(self):
       """Delete the physical file from the filesystem"""
       if os.path.exists(self.filepath):
           os.remove(self.filepath)
           return True
       return False

class StaffAttendance(db.Model):
   id = db.Column(db.Integer, primary_key=True)
   staff_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
   date = db.Column(db.Date, nullable=False, default=datetime.now().date)
   clock_in = db.Column(db.DateTime, nullable=True)
   clock_out = db.Column(db.DateTime, nullable=True)
   status = db.Column(db.String(20), default='present')  # present, absent, late, half-day
   notes = db.Column(db.Text, nullable=True)
   location = db.Column(db.String(100), nullable=True)
   
   # Define standard work hours
   WORK_START_TIME = time(8, 0)  # 8:00 AM
   WORK_END_TIME = time(17, 0)   # 5:00 PM
   LATE_THRESHOLD = time(8, 30)  # 8:30 AM
   
   def __init__(self, **kwargs):
       super(StaffAttendance, self).__init__(**kwargs)
       # Set status based on clock-in time
       if self.clock_in:
           if self.clock_in.time() > self.LATE_THRESHOLD:
               self.status = 'late'
   
   def get_work_duration(self):
       """Calculate the duration of work in hours"""
       if not self.clock_in:
           return 0
       
       end_time = self.clock_out or datetime.now()
       delta = end_time - self.clock_in
       return round(delta.total_seconds() / 3600, 2)  # Convert to hours
   
   def is_late(self):
       """Check if the staff member was late"""
       return self.clock_in and self.clock_in.time() > self.LATE_THRESHOLD
   
   def is_early_departure(self):
       """Check if the staff member left early"""
       return self.clock_out and self.clock_out.time() < self.WORK_END_TIME
   
   def get_status_badge(self):
       """Return a Bootstrap badge class based on status"""
       if self.status == 'present':
           return 'bg-success'
       elif self.status == 'late':
           return 'bg-warning text-dark'
       elif self.status == 'absent':
           return 'bg-danger'
       elif self.status == 'half-day':
           return 'bg-info'
       return 'bg-secondary'

