from flask import render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.class_rep import bp
from app.models import Session
from app.extensions import db
from app.utils import get_now
from app.email import send_session_notification
from functools import wraps

def class_rep_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'class_rep':
            flash('You do not have permission to access this page')
            return redirect(url_for('auth.index'))
        return f(*args, **kwargs)
    return decorated_function

@bp.route('/dashboard')
@login_required
@class_rep_required
def dashboard():
    active_sessions = Session.query.filter_by(status='ongoing').all()
    completed_sessions = Session.query.filter_by(status='completed').all()
    
    return render_template('class_rep/dashboard.html',
                          active_sessions=active_sessions,
                          completed_sessions=completed_sessions,
                          now=get_now())

@bp.route('/verify_session/<session_id>', methods=['POST'])
@login_required
@class_rep_required
def verify_session(session_id):
    session_obj = Session.query.filter_by(session_id=session_id).first()
    if not session_obj:
        flash('Session not found')
        return redirect(url_for('class_rep.dashboard'))
    
    signature = request.form.get('signature')
    if not signature:
        flash('Signature is required')
        return redirect(url_for('class_rep.dashboard'))
    
    session_obj.status = 'verified'
    session_obj.verified_by = current_user.id
    session_obj.rep_signature = signature
    db.session.commit()
    
    # Send email notification
    send_session_notification(session_obj, 'verified')
    
    flash('Session verified successfully')
    return redirect(url_for('class_rep.dashboard'))

