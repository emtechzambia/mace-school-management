from flask import render_template, redirect, url_for, flash, request, send_file
from flask_login import login_required, current_user
from app.admin import bp
from app.models import User, Course, Session, Report, StaffAttendance
from app.extensions import db
from app.utils import get_lecturer_stats, get_now
from app.email import send_session_notification
from functools import wraps
import pandas as pd
import os
from datetime import datetime, timedelta
from flask import current_app
from sqlalchemy import or_, func, extract
import humanize

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('You do not have permission to access this page')
            return redirect(url_for('auth.index'))
        return f(*args, **kwargs)
    return decorated_function

@bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    active_sessions = Session.query.filter_by(status='ongoing').all()
    pending_sessions = Session.query.filter_by(status='pending').all()
    completed_sessions = Session.query.filter_by(status='completed').all()
    verified_sessions = Session.query.filter_by(status='verified').all()
    
    # Get today's attendance stats
    today = datetime.now().date()
    total_staff = User.query.filter_by(role='lecturer').count()
    
    today_attendance = StaffAttendance.query.filter_by(date=today).all()
    clocked_in_count = len([a for a in today_attendance if a.clock_in])
    clocked_out_count = len([a for a in today_attendance if a.clock_out])
    late_count = len([a for a in today_attendance if a.status == 'late'])
    
    # Get staff currently clocked in
    currently_working = [a for a in today_attendance if a.clock_in and not a.clock_out]
    
    return render_template('admin/dashboard.html', 
                          active_sessions=active_sessions,
                          pending_sessions=pending_sessions,
                          completed_sessions=completed_sessions,
                          verified_sessions=verified_sessions,
                          now=get_now(),
                          User=User,
                          total_staff=total_staff,
                          clocked_in_count=clocked_in_count,
                          clocked_out_count=clocked_out_count,
                          late_count=late_count,
                          currently_working=currently_working)

# User Management Routes
@bp.route('/register_user', methods=['GET', 'POST'])
@login_required
@admin_required
def register_user():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        role = request.form.get('role')
        
        if User.query.filter_by(username=username).first():
            flash('Username already exists')
            return redirect(url_for('admin.register_user'))
        
        if User.query.filter_by(email=email).first():
            flash('Email already exists')
            return redirect(url_for('admin.register_user'))
        
        new_user = User(username=username, email=email, role=role)
        
        # Add lecturer-specific fields if role is lecturer
        if role == 'lecturer':
            employee_number = request.form.get('employee_number')
            department = request.form.get('department')
            first_name = request.form.get('first_name')
            last_name = request.form.get('last_name')
            
            new_user.employee_number = employee_number
            new_user.department = department
            new_user.first_name = first_name
            new_user.last_name = last_name
        
        new_user.set_password(password)
        
        db.session.add(new_user)
        db.session.commit()
        
        flash('User registered successfully')
        return redirect(url_for('admin.manage_users'))
    
    return render_template('admin/register_user.html')

@bp.route('/manage_users')
@login_required
@admin_required
def manage_users():
    # Get filter parameters
    role = request.args.get('role')
    department = request.args.get('department')
    search = request.args.get('search')
    
    # Base query
    query = User.query
    
    # Apply filters
    if role:
        query = query.filter_by(role=role)
    
    if department:
        query = query.filter(User.department.like(f'%{department}%'))
    
    if search:
        query = query.filter(
            or_(
                User.username.like(f'%{search}%'),
                User.email.like(f'%{search}%'),
                User.first_name.like(f'%{search}%'),
                User.last_name.like(f'%{search}%'),
                User.employee_number.like(f'%{search}%')
            )
        )
    
    # Get users
    users = query.all()
    
    return render_template('admin/manage_users.html', users=users)

@bp.route('/edit_user/<int:user_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_user(user_id):
    user = User.query.get_or_404(user_id)
    
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        role = request.form.get('role')
        password = request.form.get('password')
        
        # Check if username already exists for another user
        existing_user = User.query.filter_by(username=username).first()
        if existing_user and existing_user.id != user.id:
            flash('Username already exists')
            return redirect(url_for('admin.edit_user', user_id=user.id))
        
        # Check if email already exists for another user
        existing_user = User.query.filter_by(email=email).first()
        if existing_user and existing_user.id != user.id:
            flash('Email already exists')
            return redirect(url_for('admin.edit_user', user_id=user.id))
        
        # Update user details
        user.username = username
        user.email = email
        user.role = role
        
        # Update password if provided
        if password:
            user.set_password(password)
        
        # Update lecturer-specific fields if role is lecturer
        if role == 'lecturer':
            user.employee_number = request.form.get('employee_number')
            user.department = request.form.get('department')
            user.first_name = request.form.get('first_name')
            user.last_name = request.form.get('last_name')
        
        db.session.commit()
        flash('User updated successfully')
        return redirect(url_for('admin.manage_users'))
    
    return render_template('admin/edit_user.html', user=user)

@bp.route('/delete_user/<int:user_id>', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    user = User.query.get_or_404(user_id)
    
    # Check if user is the current user
    if user.id == current_user.id:
        flash('You cannot delete your own account')
        return redirect(url_for('admin.manage_users'))
    
    # Delete user
    db.session.delete(user)
    db.session.commit()
    
    flash('User deleted successfully')
    return redirect(url_for('admin.manage_users'))

# Course Management Routes
@bp.route('/register_course', methods=['GET', 'POST'])
@login_required
@admin_required
def register_course():
    if request.method == 'POST':
        code = request.form.get('code')
        name = request.form.get('name')
        
        if Course.query.filter_by(code=code).first():
            flash('Course code already exists')
            return redirect(url_for('admin.register_course'))
        
        new_course = Course(code=code, name=name)
        
        db.session.add(new_course)
        db.session.commit()
        
        flash('Course registered successfully')
        return redirect(url_for('admin.manage_courses'))
    
    return render_template('admin/register_course.html')

@bp.route('/manage_courses')
@login_required
@admin_required
def manage_courses():
    # Get filter parameters
    search = request.args.get('search')
    
    # Base query
    query = Course.query
    
    # Apply filters
    if search:
        query = query.filter(
            or_(
                Course.code.like(f'%{search}%'),
                Course.name.like(f'%{search}%')
            )
        )
    
    # Get courses
    courses = query.all()
    
    return render_template('admin/manage_courses.html', courses=courses)

@bp.route('/edit_course/<int:course_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_course(course_id):
    course = Course.query.get_or_404(course_id)
    
    if request.method == 'POST':
        code = request.form.get('code')
        name = request.form.get('name')
        
        # Check if course code already exists for another course
        existing_course = Course.query.filter_by(code=code).first()
        if existing_course and existing_course.id != course.id:
            flash('Course code already exists')
            return redirect(url_for('admin.edit_course', course_id=course.id))
        
        # Update course details
        course.code = code
        course.name = name
        
        db.session.commit()
        flash('Course updated successfully')
        return redirect(url_for('admin.manage_courses'))
    
    return render_template('admin/edit_course.html', course=course)

@bp.route('/delete_course/<int:course_id>', methods=['POST'])
@login_required
@admin_required
def delete_course(course_id):
    course = Course.query.get_or_404(course_id)
    
    # Delete associated sessions
    Session.query.filter_by(course_id=course.id).delete()
    
    # Delete course
    db.session.delete(course)
    db.session.commit()
    
    flash('Course deleted successfully')
    return redirect(url_for('admin.manage_courses'))

# Session Management Routes
@bp.route('/create_session', methods=['GET', 'POST'])
@login_required
@admin_required
def create_session():
    if request.method == 'POST':
        course_id = request.form.get('course_id')
        lecturer_id = request.form.get('lecturer_id')
        classroom = request.form.get('classroom')
        
        new_session = Session(
            course_id=course_id,
            lecturer_id=lecturer_id,
            classroom=classroom,
            status='pending'
        )
        
        db.session.add(new_session)
        db.session.commit()
        
        flash('Session created successfully')
        return redirect(url_for('admin.manage_sessions'))
    
    courses = Course.query.all()
    lecturers = User.query.filter_by(role='lecturer').all()
    
    return render_template('admin/create_session.html', courses=courses, lecturers=lecturers)

@bp.route('/manage_sessions')
@login_required
@admin_required
def manage_sessions():
    # Get filter parameters
    status = request.args.get('status')
    course_id = request.args.get('course_id')
    lecturer_id = request.args.get('lecturer_id')
    date = request.args.get('date')
    
    # Base query
    query = Session.query
    
    # Apply filters
    if status:
        query = query.filter_by(status=status)
    
    if course_id:
        query = query.filter_by(course_id=int(course_id))
    
    if lecturer_id:
        query = query.filter_by(lecturer_id=int(lecturer_id))
    
    if date:
        # Filter sessions on the specified date
        date_obj = datetime.strptime(date, '%Y-%m-%d')
        next_date = date_obj.replace(hour=23, minute=59, second=59)
        query = query.filter(
            (Session.start_time >= date_obj) & (Session.start_time <= next_date)
        )
    
    # Get sessions
    sessions = query.all()
    
    # Get courses and lecturers for filter dropdowns
    courses = Course.query.all()
    lecturers = User.query.filter_by(role='lecturer').all()
    
    return render_template('admin/manage_sessions.html', 
                          sessions=sessions, 
                          courses=courses, 
                          lecturers=lecturers)

@bp.route('/edit_session/<int:session_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def edit_session(session_id):
    session = Session.query.get_or_404(session_id)
    
    if request.method == 'POST':
        course_id = request.form.get('course_id')
        lecturer_id = request.form.get('lecturer_id')
        classroom = request.form.get('classroom')
        status = request.form.get('status')
        start_time = request.form.get('start_time')
        end_time = request.form.get('end_time')
        
        # Update session details
        session.course_id = course_id
        session.lecturer_id = lecturer_id
        session.classroom = classroom
        session.status = status
        
        # Update start time if provided
        if start_time:
            session.start_time = datetime.strptime(start_time, '%Y-%m-%dT%H:%M')
        else:
            session.start_time = None
        
        # Update end time if provided
        if end_time:
            session.end_time = datetime.strptime(end_time, '%Y-%m-%dT%H:%M')
        else:
            session.end_time = None
        
        db.session.commit()
        flash('Session updated successfully')
        return redirect(url_for('admin.manage_sessions'))
    
    courses = Course.query.all()
    lecturers = User.query.filter_by(role='lecturer').all()
    
    return render_template('admin/edit_session.html', 
                          session=session, 
                          courses=courses, 
                          lecturers=lecturers)

@bp.route('/delete_session/<int:session_id>', methods=['POST'])
@login_required
@admin_required
def delete_session(session_id):
    session = Session.query.get_or_404(session_id)
    
    # Delete session
    db.session.delete(session)
    db.session.commit()
    
    flash('Session deleted successfully')
    return redirect(url_for('admin.manage_sessions'))

@bp.route('/reports')
@login_required
@admin_required
def reports():
    lecturer_stats = get_lecturer_stats()
    saved_reports = Report.query.order_by(Report.created_at.desc()).all()
    return render_template('admin/reports.html', 
                          lecturer_stats=lecturer_stats, 
                          User=User,
                          saved_reports=saved_reports)

@bp.route('/export_reports/<format>')
@login_required
@admin_required
def export_reports(format):
    lecturer_stats = get_lecturer_stats()
    
    # Convert to DataFrame
    data = []
    for lecturer_id, stats in lecturer_stats.items():
        lecturer = User.query.get(lecturer_id)
        data.append({
            'Lecturer': stats['name'],
            'Employee Number': lecturer.employee_number or 'N/A',
            'Department': lecturer.department or 'N/A',
            'Total Sessions': stats['total_sessions'],
            'Total Hours': round(stats['total_minutes'] / 60, 1),
            'Average Session Duration (minutes)': round(stats['total_minutes'] / stats['total_sessions']) if stats['total_sessions'] > 0 else 0
        })
    
    df = pd.DataFrame(data)
    
    # Generate filename with timestamp and more descriptive name
    current_date = datetime.now().strftime('%Y-%m-%d')
    timestamp = datetime.now().strftime('%H%M%S')
    
    # Set the correct file extension based on format
    if format == 'excel':
        file_extension = 'xlsx'
        mimetype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        format_name = 'Excel'
    elif format == 'csv':
        file_extension = 'csv'
        mimetype = 'text/csv'
        format_name = 'CSV'
    elif format == 'json':
        file_extension = 'json'
        mimetype = 'application/json'
        format_name = 'JSON'
    else:
        flash('Invalid export format')
        return redirect(url_for('admin.reports'))
    
    filename = f'staff_attendance_report_{current_date}_{timestamp}.{file_extension}'
    
    # Ensure export directory exists
    export_folder = current_app.config['EXPORT_FOLDER']
    os.makedirs(export_folder, exist_ok=True)
    
    filepath = os.path.join(export_folder, filename)
    
    # Export based on format
    try:
        if format == 'csv':
            df.to_csv(filepath, index=False)
        elif format == 'excel':
            # Explicitly specify the engine for Excel export
            df.to_excel(filepath, index=False, engine='openpyxl')
        elif format == 'json':
            df.to_json(filepath, orient='records')
        
        # Get file size
        file_size = os.path.getsize(filepath)
        
        # Create report record in database
        report = Report(
            title=f'Staff Attendance Report ({format_name})',
            filename=filename,
            filepath=filepath,
            format=format,
            file_size=file_size,
            description=f'Staff attendance report generated on {current_date}',
            created_by=current_user.id
        )
        
        db.session.add(report)
        db.session.commit()
        
        flash(f'Report exported successfully and saved to database')
        return send_file(filepath, mimetype=mimetype, as_attachment=True, download_name=filename)
    except Exception as e:
        flash(f'Error exporting report: {str(e)}')
        current_app.logger.error(f"Export error: {str(e)}")
        return redirect(url_for('admin.reports'))

@bp.route('/manage_reports')
@login_required
@admin_required
def manage_reports():
    # Get filter parameters
    format_filter = request.args.get('format')
    date_filter = request.args.get('date')
    
    # Base query
    query = Report.query
    
    # Apply filters
    if format_filter:
        query = query.filter_by(format=format_filter)
    
    if date_filter:
        date_obj = datetime.strptime(date_filter, '%Y-%m-%d')
        next_date = date_obj.replace(hour=23, minute=59, second=59)
        query = query.filter(
            (Report.created_at >= date_obj) & (Report.created_at <= next_date)
        )
    
    # Get reports ordered by creation date (newest first)
    reports = query.order_by(Report.created_at.desc()).all()
    
    return render_template('admin/manage_reports.html', reports=reports)

@bp.route('/download_report/<int:report_id>')
@login_required
@admin_required
def download_report(report_id):
    report = Report.query.get_or_404(report_id)
    
    if not os.path.exists(report.filepath):
        flash('Report file not found')
        return redirect(url_for('admin.manage_reports'))
    
    # Determine MIME type based on format
    if report.format == 'excel':
        mimetype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    elif report.format == 'csv':
        mimetype = 'text/csv'
    elif report.format == 'json':
        mimetype = 'application/json'
    else:
        mimetype = 'application/octet-stream'
    
    return send_file(report.filepath, mimetype=mimetype, as_attachment=True, download_name=report.filename)

@bp.route('/delete_report/<int:report_id>', methods=['POST'])
@login_required
@admin_required
def delete_report(report_id):
    report = Report.query.get_or_404(report_id)
    
    # Delete the physical file
    report.delete_file()
    
    # Delete the database record
    db.session.delete(report)
    db.session.commit()
    
    flash('Report deleted successfully')
    return redirect(url_for('admin.manage_reports'))

@bp.route('/staff-attendance')
@login_required
@admin_required
def staff_attendance():
    # Get filter parameters
    staff_id = request.args.get('staff_id')
    department = request.args.get('department')
    status = request.args.get('status')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    
    # Base query
    query = StaffAttendance.query
    
    # Apply filters
    if staff_id:
        query = query.filter_by(staff_id=int(staff_id))
    
    if status:
        query = query.filter_by(status=status)
    
    if department:
        # Join with User to filter by department
        query = query.join(User).filter(User.department.like(f'%{department}%'))
    
    if date_from:
        date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
        query = query.filter(StaffAttendance.date >= date_from_obj)
    
    if date_to:
        date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
        query = query.filter(StaffAttendance.date <= date_to_obj)
    
    # Get attendance records ordered by date (newest first)
    attendance_records = query.order_by(StaffAttendance.date.desc()).all()
    
    # Get staff for filter dropdown
    staff = User.query.filter_by(role='lecturer').all()
    
    # Calculate statistics
    total_records = len(attendance_records)
    present_count = sum(1 for record in attendance_records if record.status == 'present')
    late_count = sum(1 for record in attendance_records if record.status == 'late')
    absent_count = sum(1 for record in attendance_records if record.status == 'absent')
    half_day_count = sum(1 for record in attendance_records if record.status == 'half-day')
    
    return render_template('admin/staff_attendance.html',
                          attendance_records=attendance_records,
                          staff=staff,
                          total_records=total_records,
                          present_count=present_count,
                          late_count=late_count,
                          absent_count=absent_count,
                          half_day_count=half_day_count)

@bp.route('/mark-attendance', methods=['GET', 'POST'])
@login_required
@admin_required
def mark_attendance():
    if request.method == 'POST':
        staff_id = request.form.get('staff_id')
        date_str = request.form.get('date')
        status = request.form.get('status')
        clock_in_str = request.form.get('clock_in')
        clock_out_str = request.form.get('clock_out')
        notes = request.form.get('notes')
        
        # Parse date and times
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        
        # Check if record already exists
        existing_record = StaffAttendance.query.filter_by(
            staff_id=staff_id,
            date=date_obj
        ).first()
        
        if existing_record:
            # Update existing record
            existing_record.status = status
            
            if clock_in_str:
                clock_in_time = datetime.strptime(clock_in_str, '%H:%M').time()
                existing_record.clock_in = datetime.combine(date_obj, clock_in_time)
            else:
                existing_record.clock_in = None
                
            if clock_out_str:
                clock_out_time = datetime.strptime(clock_out_str, '%H:%M').time()
                existing_record.clock_out = datetime.combine(date_obj, clock_out_time)
            else:
                existing_record.clock_out = None
                
            existing_record.notes = notes
            
            flash('Attendance record updated successfully')
        else:
            # Create new record
            new_record = StaffAttendance(
                staff_id=staff_id,
                date=date_obj,
                status=status,
                notes=notes
            )
            
            if clock_in_str:
                clock_in_time = datetime.strptime(clock_in_str, '%H:%M').time()
                new_record.clock_in = datetime.combine(date_obj, clock_in_time)
                
            if clock_out_str:
                clock_out_time = datetime.strptime(clock_out_str, '%H:%M').time()
                new_record.clock_out = datetime.combine(date_obj, clock_out_time)
            
            db.session.add(new_record)
            flash('Attendance record created successfully')
        
        db.session.commit()
        return redirect(url_for('admin.staff_attendance'))
    
    # Get staff for dropdown
    staff = User.query.filter_by(role='lecturer').all()
    
    return render_template('admin/mark_attendance.html', staff=staff)

@bp.route('/export-attendance/<format>')
@login_required
@admin_required
def export_attendance(format):
    # Get filter parameters (same as staff_attendance route)
    staff_id = request.args.get('staff_id')
    department = request.args.get('department')
    status = request.args.get('status')
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    
    # Base query
    query = StaffAttendance.query
    
    # Apply filters
    if staff_id:
        query = query.filter_by(staff_id=int(staff_id))
    
    if status:
        query = query.filter_by(status=status)
    
    if department:
        query = query.join(User).filter(User.department.like(f'%{department}%'))
    
    if date_from:
        date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
        query = query.filter(StaffAttendance.date >= date_from_obj)
    
    if date_to:
        date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
        query = query.filter(StaffAttendance.date <= date_to_obj)
    
    # Get attendance records
    attendance_records = query.order_by(StaffAttendance.date.desc()).all()
    
    # Convert to DataFrame
    data = []
    for record in attendance_records:
        staff = User.query.get(record.staff_id)
        data.append({
            'Date': record.date.strftime('%Y-%m-%d'),
            'Staff Name': staff.get_full_name(),
            'Employee Number': staff.employee_number or 'N/A',
            'Department': staff.department or 'N/A',
            'Clock In': record.clock_in.strftime('%H:%M:%S') if record.clock_in else 'N/A',
            'Clock Out': record.clock_out.strftime('%H:%M:%S') if record.clock_out else 'N/A',
            'Status': record.status.capitalize(),
            'Work Duration (hours)': round(record.get_work_duration(), 2) if record.clock_in else 0,
            'Notes': record.notes or ''
        })
    
    df = pd.DataFrame(data)
    
    # Generate filename with timestamp
    current_date = datetime.now().strftime('%Y-%m-%d')
    timestamp = datetime.now().strftime('%H%M%S')
    
    # Set the correct file extension based on format
    if format == 'excel':
        file_extension = 'xlsx'
        mimetype = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        format_name = 'Excel'
    elif format == 'csv':
        file_extension = 'csv'
        mimetype = 'text/csv'
        format_name = 'CSV'
    elif format == 'json':
        file_extension = 'json'
        mimetype = 'application/json'
        format_name = 'JSON'
    else:
        flash('Invalid export format')
        return redirect(url_for('admin.staff_attendance'))
    
    filename = f'staff_attendance_log_{current_date}_{timestamp}.{file_extension}'
    
    # Ensure export directory exists
    export_folder = current_app.config['EXPORT_FOLDER']
    os.makedirs(export_folder, exist_ok=True)
    
    filepath = os.path.join(export_folder, filename)
    
    # Export based on format
    try:
        if format == 'csv':
            df.to_csv(filepath, index=False)
        elif format == 'excel':
            df.to_excel(filepath, index=False, engine='openpyxl')
        elif format == 'json':
            df.to_json(filepath, orient='records')
        
        # Get file size
        file_size = os.path.getsize(filepath)
        
        # Create report record in database
        report = Report(
            title=f'Staff Attendance Log ({format_name})',
            filename=filename,
            filepath=filepath,
            format=format,
            file_size=file_size,
            description=f'Staff attendance log generated on {current_date}',
            created_by=current_user.id
        )
        
        db.session.add(report)
        db.session.commit()
        
        flash(f'Attendance log exported successfully and saved to database')
        return send_file(filepath, mimetype=mimetype, as_attachment=True, download_name=filename)
    except Exception as e:
        flash(f'Error exporting attendance log: {str(e)}')
        current_app.logger.error(f"Export error: {str(e)}")
        return redirect(url_for('admin.staff_attendance'))

