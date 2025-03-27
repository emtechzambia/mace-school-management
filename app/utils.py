from datetime import datetime
from app.models import User, Session
from app.extensions import db

def get_lecturer_stats():
    """Get statistics for all lecturers with verified sessions"""
    verified_sessions = Session.query.filter_by(status='verified').all()
    
    # Group by lecturer
    lecturer_stats = {}
    for session in verified_sessions:
        lecturer_id = session.lecturer_id
        if lecturer_id not in lecturer_stats:
            lecturer = User.query.get(lecturer_id)
            lecturer_stats[lecturer_id] = {
                'name': lecturer.get_full_name(),
                'total_sessions': 0,
                'total_minutes': 0
            }
        
        lecturer_stats[lecturer_id]['total_sessions'] += 1
        lecturer_stats[lecturer_id]['total_minutes'] += session.duration_minutes()
    
    return lecturer_stats

def get_now():
    """Get current datetime"""
    return datetime.now()

