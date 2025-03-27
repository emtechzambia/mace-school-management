from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app.lecturer import bp
from app.models import Session, StaffAttendance, BiometricLog
from app.extensions import db
from app.utils import get_now
from app.email import send_session_notification
from datetime import datetime
from functools import wraps
import json

def lecturer_required(f):
   @wraps(f)
   def decorated_function(*args, **kwargs):
       if not current_user.is_authenticated or current_user.role != 'lecturer':
           flash('You do not have permission to access this page')
           return redirect(url_for('auth.index'))
       return f(*args, **kwargs)
   return decorated_function

@bp.route('/dashboard')
@login_required
@lecturer_required
def dashboard():
   my_sessions = Session.query.filter_by(lecturer_id=current_user.id).all()
   upcoming_sessions = [s for s in my_sessions if s.status == 'pending']
   active_sessions = [s for s in my_sessions if s.status == 'ongoing']
   completed_sessions = [s for s in my_sessions if s.status in ['completed', 'verified']]
   
   # Get today's attendance record
   today_attendance = current_user.get_today_attendance()
   
   return render_template('lecturer/dashboard.html',
                         upcoming_sessions=upcoming_sessions,
                         active_sessions=active_sessions,
                         completed_sessions=completed_sessions,
                         today_attendance=today_attendance,
                         now=get_now())

@bp.route('/start_session/<session_id>', methods=['POST'])
@login_required
@lecturer_required
def start_session(session_id):
   session_obj = Session.query.filter_by(session_id=session_id).first()
   if not session_obj:
       flash('Session not found')
       return redirect(url_for('lecturer.dashboard'))
   
   if session_obj.lecturer_id != current_user.id:
       flash('You are not assigned to this session')
       return redirect(url_for('lecturer.dashboard'))
   
   session_obj.start_time = datetime.now()
   session_obj.status = 'ongoing'
   db.session.commit()
   
   # Send email notification
   send_session_notification(session_obj, 'started')
   
   flash('Session started successfully')
   return redirect(url_for('lecturer.dashboard'))

@bp.route('/end_session/<session_id>', methods=['POST'])
@login_required
@lecturer_required
def end_session(session_id):
   session_obj = Session.query.filter_by(session_id=session_id).first()
   if not session_obj:
       flash('Session not found')
       return redirect(url_for('lecturer.dashboard'))
   
   if session_obj.lecturer_id != current_user.id:
       flash('You are not assigned to this session')
       return redirect(url_for('lecturer.dashboard'))
   
   signature = request.form.get('signature')
   if not signature:
       flash('Signature is required')
       return redirect(url_for('lecturer.dashboard'))
   
   session_obj.end_time = datetime.now()
   session_obj.status = 'completed'
   session_obj.lecturer_signature = signature
   db.session.commit()
   
   # Send email notification
   send_session_notification(session_obj, 'ended')
   
   flash('Session ended successfully')
   return redirect(url_for('lecturer.dashboard'))

@bp.route('/clock-in', methods=['POST'])
@login_required
@lecturer_required
def clock_in():
   # Check if already clocked in today
   today_attendance = current_user.get_today_attendance()
   
   if today_attendance and today_attendance.clock_in:
       flash('You have already clocked in today')
       return redirect(url_for('lecturer.dashboard'))
   
   # Verify fingerprint
   fingerprint_verified = request.form.get('fingerprint_verified') == 'true'
   
   if not fingerprint_verified:
       flash('Biometric verification is required for clock-in')
       return redirect(url_for('lecturer.dashboard'))
   
   # Get location from form if provided
   location = request.form.get('location', 'On Campus')
   
   # Create new attendance record or update existing
   if not today_attendance:
       today_attendance = StaffAttendance(
           staff_id=current_user.id,
           date=datetime.now().date(),
           clock_in=datetime.now(),
           location=location,
           clock_in_verified=True,
           clock_in_ip=request.remote_addr,
           clock_in_device=request.user_agent.string
       )
       db.session.add(today_attendance)
   else:
       today_attendance.clock_in = datetime.now()
       today_attendance.location = location
       today_attendance.clock_in_verified = True
       today_attendance.clock_in_ip = request.remote_addr
       today_attendance.clock_in_device = request.user_agent.string
   
   # Check if late
   if datetime.now().time() > StaffAttendance.LATE_THRESHOLD:
       today_attendance.status = 'late'
   
   # Log the biometric verification
   log = BiometricLog(
       user_id=current_user.id,
       action='clock_in',
       status='success',
       ip_address=request.remote_addr,
       device_info=request.user_agent.string,
       details=json.dumps({
           'location': location,
           'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
           'verified': True
       })
   )
   db.session.add(log)
   
   db.session.commit()
   flash('You have successfully clocked in')
   return redirect(url_for('lecturer.dashboard'))

@bp.route('/clock-out', methods=['POST'])
@login_required
@lecturer_required
def clock_out():
   # Check if clocked in today
   today_attendance = current_user.get_today_attendance()
   
   if not today_attendance or not today_attendance.clock_in:
       flash('You need to clock in before you can clock out')
       return redirect(url_for('lecturer.dashboard'))
   
   if today_attendance.clock_out:
       flash('You have already clocked out today')
       return redirect(url_for('lecturer.dashboard'))
   
   # Verify fingerprint
   fingerprint_verified = request.form.get('fingerprint_verified') == 'true'
   
   if not fingerprint_verified:
       flash('Biometric verification is required for clock-out')
       return redirect(url_for('lecturer.dashboard'))
   
   # Update attendance record
   today_attendance.clock_out = datetime.now()
   today_attendance.clock_out_verified = True
   today_attendance.clock_out_ip = request.remote_addr
   today_attendance.clock_out_device = request.user_agent.string
   
   # Check if half-day (less than 4 hours)
   work_duration = today_attendance.get_work_duration()
   if work_duration < 4:
       today_attendance.status = 'half-day'
   
   # Log the biometric verification
   log = BiometricLog(
       user_id=current_user.id,
       action='clock_out',
       status='success',
       ip_address=request.remote_addr,
       device_info=request.user_agent.string,
       details=json.dumps({
           'time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
           'work_duration': work_duration,
           'verified': True
       })
   )
   db.session.add(log)
   
   db.session.commit()
   flash('You have successfully clocked out')
   return redirect(url_for('lecturer.dashboard'))

@bp.route('/attendance-history')
@login_required
@lecturer_required
def attendance_history():
   # Get filter parameters
   month = request.args.get('month')
   year = request.args.get('year')
   status = request.args.get('status')
   
   # Base query
   query = StaffAttendance.query.filter_by(staff_id=current_user.id)
   
   # Apply filters
   if month and year:
       start_date = datetime.strptime(f'{year}-{month}-01', '%Y-%m-%d').date()
       if month == '12':
           end_date = datetime.strptime(f'{int(year)+1}-01-01', '%Y-%m-%d').date()
       else:
           end_date = datetime.strptime(f'{year}-{int(month)+1}-01', '%Y-%m-%d').date()
       
       query = query.filter(StaffAttendance.date >= start_date, StaffAttendance.date < end_date)
   elif year:
       start_date = datetime.strptime(f'{year}-01-01', '%Y-%m-%d').date()
       end_date = datetime.strptime(f'{int(year)+1}-01-01', '%Y-%m-%d').date()
       query = query.filter(StaffAttendance.date >= start_date, StaffAttendance.date < end_date)
   
   if status:
       query = query.filter_by(status=status)
   
   # Order by date (newest first)
   attendance_records = query.order_by(StaffAttendance.date.desc()).all()
   
   # Calculate statistics
   total_days = len(attendance_records)
   present_days = sum(1 for record in attendance_records if record.status == 'present')
   late_days = sum(1 for record in attendance_records if record.status == 'late')
   absent_days = sum(1 for record in attendance_records if record.status == 'absent')
   half_days = sum(1 for record in attendance_records if record.status == 'half-day')
   
   # Calculate total work hours
   total_hours = sum(record.get_work_duration() for record in attendance_records)
   
   return render_template('lecturer/attendance_history.html',
                         attendance_records=attendance_records,
                         total_days=total_days,
                         present_days=present_days,
                         late_days=late_days,
                         absent_days=absent_days,
                         half_days=half_days,
                         total_hours=total_hours)

