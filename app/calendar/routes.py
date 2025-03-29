from flask import render_template, jsonify, request
from flask_login import login_required, current_user
from app.calendar import bp
from app.models import Session, User
from datetime import datetime, timedelta

@bp.route('/')
@login_required
def index():
   return render_template('calendar/index.html')

@bp.route('/events')
@login_required
def events():
   # Get start and end dates from query parameters or use default (current month)
   start_date = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
   end_date = (start_date.replace(month=start_date.month+1) if start_date.month < 12 
               else start_date.replace(year=start_date.year+1, month=1)) - timedelta(seconds=1)
   
   # Get status filter if provided
   status_filter = request.args.get('status', 'all')
   
   # Query sessions based on user role
   if current_user.role == 'admin':
       sessions = Session.query.filter(
           ((Session.start_time >= start_date) & (Session.start_time <= end_date)) |
           (Session.start_time == None)  # Include pending sessions
       ).all()
   elif current_user.role == 'lecturer':
       sessions = Session.query.filter_by(lecturer_id=current_user.id).filter(
           ((Session.start_time >= start_date) & (Session.start_time <= end_date)) |
           (Session.start_time == None)  # Include pending sessions
       ).all()
   elif current_user.role == 'class_rep':
       sessions = Session.query.filter(
           ((Session.start_time >= start_date) & (Session.start_time <= end_date)) |
           (Session.status == 'completed')  # Include completed sessions for verification
       ).all()
   
   # Apply status filter if not 'all'
   if status_filter != 'all':
       sessions = [s for s in sessions if s.status == status_filter]
   
   # Format sessions for calendar
   events = []
   for session in sessions:
       # Determine event color based on status
       if session.status == 'pending':
           color = '#ffc107'  # warning/yellow
       elif session.status == 'ongoing':
           color = '#0d6efd'  # primary/blue
       elif session.status == 'completed':
           color = '#6c757d'  # secondary/gray
       elif session.status == 'verified':
           color = '#198754'  # success/green
       
       # Determine event title and time
       course_name = f"{session.course.code} - {session.course.name}"
       lecturer_name = User.query.get(session.lecturer_id).username
       
       if session.start_time and session.end_time:
           start = session.start_time.isoformat()
           end = session.end_time.isoformat()
           title = f"{course_name} ({lecturer_name})"
       elif session.start_time:
           start = session.start_time.isoformat()
           end = (session.start_time + timedelta(hours=1)).isoformat()  # Assume 1 hour for ongoing sessions
           title = f"{course_name} ({lecturer_name}) - Ongoing"
       else:
           # For pending sessions, use a placeholder date (today)
           today = datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)
           start = today.isoformat()
           end = (today + timedelta(hours=1)).isoformat()
           title = f"{course_name} ({lecturer_name}) - Pending"
       
       events.append({
           'id': session.session_id,
           'title': title,
           'start': start,
           'end': end,
           'backgroundColor': color,
           'borderColor': color,
           'textColor': '#fff',
           'extendedProps': {
               'status': session.status,
               'classroom': session.classroom,
               'course': course_name,
               'lecturer': lecturer_name
           }
       })
   
   return jsonify(events)

