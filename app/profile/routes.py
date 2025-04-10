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
import re

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

@bp.route('/check_face_detection', methods=['POST'])
@login_required
def check_face_detection():
    """Endpoint to verify if a face is detected in the uploaded image before saving"""
    try:
        # Get image data from form
        image_data = request.form.get('image_data')
        if not image_data:
            return jsonify({'success': False, 'message': 'No image data received'})
        
        # Process the image
        image_data = re.sub('^data:image/.+;base64,', '', image_data)
        image_bytes = base64.b64decode(image_data)
        image = Image.open(io.BytesIO(image_bytes))
        
        # Convert to RGB mode (important for face_recognition)
        if image.mode != 'RGB':
            image = image.convert('RGB')
            
        # Convert to numpy array
        image_np = np.array(image)
        
        # Detect faces using face_recognition library
        face_locations = face_recognition.face_locations(image_np)
        
        if not face_locations:
            return jsonify({
                'success': False, 
                'message': 'No face detected. Please ensure your face is visible and centered.'
            })
        
        if len(face_locations) > 1:
            return jsonify({
                'success': False, 
                'message': 'Multiple faces detected. Please ensure only your face is in the frame.'
            })
        
        # Get face location
        face_location = face_locations[0]
        top, right, bottom, left = face_location
        
        # Calculate face size as percentage of image
        face_width = right - left
        face_height = bottom - top
        image_area = image_np.shape[0] * image_np.shape[1]
        face_area = face_width * face_height
        face_percentage = (face_area / image_area) * 100
        
        # Check if face is too small
        if face_percentage < 10:
            return jsonify({
                'success': False, 
                'message': 'Face is too small. Please move closer to the camera.'
            })
        
        # Check if face is centered enough
        center_x = image_np.shape[1] / 2
        center_y = image_np.shape[0] / 2
        face_center_x = (left + right) / 2
        face_center_y = (top + bottom) / 2
        
        x_offset = abs(face_center_x - center_x) / (image_np.shape[1] / 2) * 100
        y_offset = abs(face_center_y - center_y) / (image_np.shape[0] / 2) * 100
        
        if x_offset > 30 or y_offset > 30:
            return jsonify({
                'success': False, 
                'message': 'Face is not centered. Please position your face in the center of the frame.'
            })
        
        # Get face encoding
        face_encodings = face_recognition.face_encodings(image_np, face_locations)
        
        if not face_encodings:
            return jsonify({
                'success': False, 
                'message': 'Could not encode facial features. Please try again with better lighting.'
            })
        
        # Determine quality based on face size
        quality = "Excellent" if face_percentage > 25 else "Good" if face_percentage > 15 else "Acceptable"
        
        return jsonify({
            'success': True,
            'message': 'Face detected successfully',
            'face_location': face_location,
            'quality': quality
        })
        
    except Exception as e:
        print(f"Error in face detection: {str(e)}")
        return jsonify({'success': False, 'message': f'Error processing image: {str(e)}'})

@bp.route('/update_biometric', methods=['POST'])
@login_required
def update_biometric():
    biometric_type = request.form.get('biometric_type', 'face')
    
    if biometric_type == 'face':
        image_data = request.form.get('image_data')
        if not image_data:
            flash('No image captured')
            return redirect(url_for('profile.index'))
        
        try:
            # Process the image
            image_data = re.sub('^data:image/.+;base64,', '', image_data)
            image_bytes = base64.b64decode(image_data)
            image = Image.open(io.BytesIO(image_bytes))
            
            # Convert to RGB mode (important for face_recognition)
            if image.mode != 'RGB':
                image = image.convert('RGB')
                
            # Convert to numpy array
            image_np = np.array(image)
            
            # Detect faces
            face_locations = face_recognition.face_locations(image_np)
            if not face_locations:
                flash('No face detected. Please try again with better lighting and positioning.')
                return redirect(url_for('profile.index'))
            
            # Get face encodings
            face_encodings = face_recognition.face_encodings(image_np, face_locations)
            
            if not face_encodings:
                flash('Could not encode facial features. Please try again with better lighting.')
                return redirect(url_for('profile.index'))
            
            # Update face encoding
            face_encoding_bytes = face_encodings[0].tobytes()
            current_user.set_face_encoding(face_encoding_bytes)
            
            # Set preferred biometric to face if this is the first time registering
            if not current_user.preferred_biometric:
                current_user.preferred_biometric = 'face'
            
            db.session.commit()
            
            flash('Facial biometric data updated successfully')
            
        except Exception as e:
            flash(f'Error processing facial biometric: {str(e)}')
            print(f"Facial biometric error: {str(e)}")
            return redirect(url_for('profile.index'))
    
    elif biometric_type == 'fingerprint':
        fingerprint_data = request.form.get('fingerprint_data')
        if not fingerprint_data:
            flash('No fingerprint data received')
            return redirect(url_for('profile.index'))
        
        # Process the fingerprint data
        fingerprint_bytes = base64.b64decode(fingerprint_data)
        
        # Update fingerprint data
        current_user.set_fingerprint_data(fingerprint_bytes)
        
        # Set preferred biometric to fingerprint if this is the first time registering
        if not current_user.preferred_biometric:
            current_user.preferred_biometric = 'fingerprint'
        
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

