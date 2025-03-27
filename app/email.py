from flask import current_app, render_template
from flask_mail import Message
from threading import Thread
from app.extensions import mail

def send_async_email(app, msg):
    with app.app_context():
        mail.send(msg)

def send_email(subject, sender, recipients, text_body, html_body):
    msg = Message(subject, sender=sender, recipients=recipients)
    msg.body = text_body
    msg.html = html_body
    
    # Send email asynchronously
    Thread(target=send_async_email,
           args=(current_app._get_current_object(), msg)).start()

def send_session_notification(session, action):
    """
    Send email notification about session status changes
    
    Args:
        session: The session object
        action: String describing the action (started, ended, verified)
    """
    if action == 'started':
        subject = f'Session Started: {session.course.code}'
        template = 'email/session_started.html'
    elif action == 'ended':
        subject = f'Session Ended: {session.course.code}'
        template = 'email/session_ended.html'
    elif action == 'verified':
        subject = f'Session Verified: {session.course.code}'
        template = 'email/session_verified.html'
    else:
        return
    
    # Get recipients based on action
    recipients = []
    
    # Admin always gets notified
    from app.models import User
    admins = User.query.filter_by(role='admin').all()
    for admin in admins:
        recipients.append(admin.email)
    
    # For started/ended sessions, notify class reps
    if action in ['started', 'ended']:
        class_reps = User.query.filter_by(role='class_rep').all()
        for rep in class_reps:
            recipients.append(rep.email)
    
    # For verified sessions, notify the lecturer
    if action == 'verified':
        lecturer = User.query.get(session.lecturer_id)
        recipients.append(lecturer.email)
    
    # Send the email
    send_email(
        subject=subject,
        sender=current_app.config['MAIL_DEFAULT_SENDER'],
        recipients=recipients,
        text_body=render_template(f'{template}.txt', session=session),
        html_body=render_template(template, session=session)
    )

