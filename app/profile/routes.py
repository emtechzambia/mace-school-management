from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app.profile import bp
from app.models import User
from app.extensions import db
from PIL import Image
import face_recognition
import io
import base64
import numpy as np

@bp.route('/')
@login_required
def index():
    return render_template('profile/index.html')

@bp.route('/update', methods=['POST'])
@login_required
def update():
    email = request.form.get('email')
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    # Validate email
    if email and email != current_user.email:
        if User.query.filter_by(email=email).first():
            flash('Email already exists')
            return redirect(url_for('profile.index'))
        current_user.email = email
    
    # Update lecturer-specific fields if applicable
    if current_user.role == 'lecturer':
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        employee_number = request.form.get('employee_number')
        department = request.form.get('department')
        
        if first_name:
            current_user.first_name = first_name
        
        if last_name:
            current_user.last_name = last_name
        
        if employee_number:
            current_user.employee_number = employee_number
        
        if department:
            current_user.department = department
    
    # Validate password change
    if current_password and new_password and confirm_password:
        if not current_user.check_password(current_password):
            flash('Current password is incorrect')
            return redirect(url_for('profile.index'))
        
        if new_password != confirm_password:
            flash('New passwords do not match')
            return redirect(url_for('profile.index'))
        
        current_user.set_password(new_password)
        flash('Password updated successfully')
    
    db.session.commit()
    flash('Profile updated successfully')
    return redirect(url_for('profile.index'))

@bp.route('/update_biometric', methods=['POST'])
@login_required
def update_biometric():
    biometric_type = request.form.get('biometric_type', 'face')
    
    if biometric_type == 'face':
        image_data = request.form.get('image_data')
        if not image_data:
            flash('No image captured')
            return redirect(url_for('profile.index'))
        
        # Process the image
        image_data = image_data.split(',')[1]
        image = Image.open(io.BytesIO(base64.b64decode(image_data)))
        image_np = np.array(image)
        
        # Convert RGB to BGR (for OpenCV)
        image_np = image_np[:, :, ::-1]
        
        # Detect faces
        face_locations = face_recognition.face_locations(image_np)
        if not face_locations:
            flash('No face detected. Please try again.')
            return redirect(url_for('profile.index'))
        
        # Get face encodings
        face_encodings = face_recognition.face_encodings(image_np, face_locations)
        
        # Update face encoding
        current_user.set_face_encoding(face_encodings[0].tobytes())
        db.session.commit()
        
        flash('Facial biometric data updated successfully')
    
    elif biometric_type == 'fingerprint':
        fingerprint_data = request.form.get('fingerprint_data')
        if not fingerprint_data:
            flash('No fingerprint data received')
            return redirect(url_for('profile.index'))
        
        # Process the fingerprint data
        # In a real implementation, this would involve proper fingerprint processing
        # For this simulation, we'll just store the raw data
        fingerprint_bytes = base64.b64decode(fingerprint_data)
        
        # Update fingerprint data
        current_user.set_fingerprint_data(fingerprint_bytes)
        db.session.commit()
        
        flash('Fingerprint biometric data updated successfully')
    
    return redirect(url_for('profile.index'))

@bp.route('/update_biometric_preference', methods=['POST'])
@login_required
def update_biometric_preference():
    preferred_biometric = request.form.get('preferred_biometric')
    
    if preferred_biometric in ['face', 'fingerprint']:
        current_user.preferred_biometric = preferred_biometric
        db.session.commit()
        flash('Biometric preference updated successfully')
    
    # Handle AJAX requests from the biometric verification page
    if request.is_json:
        preferred_biometric = request.json.get('preferred_biometric')
        if preferred_biometric in ['face', 'fingerprint']:
            current_user.preferred_biometric = preferred_biometric
            db.session.commit()
            return jsonify({'success': True})
        return jsonify({'success': False, 'error': 'Invalid biometric type'})
    
    return redirect(url_for('profile.index'))

