from flask import render_template, redirect, url_for, flash, request, session
from flask_login import login_user, logout_user, login_required, current_user
from app.auth import bp
from app.models import User
from app.extensions import db
import face_recognition
from PIL import Image
import io
import base64
import numpy as np
from datetime import timedelta

@bp.route('/')
def index():
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('admin.dashboard'))
        elif current_user.role == 'lecturer':
            return redirect(url_for('lecturer.dashboard'))
        elif current_user.role == 'class_rep':
            return redirect(url_for('class_rep.dashboard'))
    return render_template('auth/index.html')

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('auth.index'))
        
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember_me = 'remember_me' in request.form
        
        # Validate input
        if not username or not password:
            flash('Please enter both username and password')
            return redirect(url_for('auth.login'))
        
        # Find user
        user = User.query.filter_by(username=username).first()
        
        # Check if user exists and password is correct
        if not user:
            flash('Invalid username or password')
            return redirect(url_for('auth.login'))
            
        if not user.check_password(password):
            flash('Invalid username or password')
            return redirect(url_for('auth.login'))
        
        # Login successful, set remember me duration if selected
        login_user(user, remember=remember_me, duration=timedelta(days=30) if remember_me else None)
        
        # Store original destination if any
        next_page = request.args.get('next')
        
        # Redirect to biometric verification
        if not next_page or not next_page.startswith('/'):
            next_page = url_for('auth.biometric_verification')
            
        # Store next page in session for after biometric verification
        session['next_after_biometric'] = next_page
        
        return redirect(url_for('auth.biometric_verification'))
    
    return render_template('auth/login.html')

@bp.route('/biometric_verification', methods=['GET', 'POST'])
@login_required
def biometric_verification():
    if request.method == 'POST':
        biometric_type = request.form.get('biometric_type', 'face')
        
        if biometric_type == 'face':
            image_data = request.form.get('image_data')
            if not image_data:
                flash('No image captured')
                return redirect(url_for('auth.biometric_verification'))
            
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
                return redirect(url_for('auth.biometric_verification'))
            
            # Get face encodings
            face_encodings = face_recognition.face_encodings(image_np, face_locations)
            
            # Get stored encoding for current user
            stored_encoding = current_user.get_face_encoding()
            
            if stored_encoding is None:
                # First time login, store the encoding
                current_user.set_face_encoding(face_encodings[0].tobytes())
                db.session.commit()
                flash('Facial biometric data registered successfully!')
                
                # Redirect to next page or default dashboard
                next_page = session.pop('next_after_biometric', None)
                if not next_page:
                    next_page = url_for('auth.index')
                return redirect(next_page)
            else:
                # Compare with stored encoding
                matches = face_recognition.compare_faces([stored_encoding], face_encodings[0])
                if matches[0]:
                    flash('Facial biometric verification successful!')
                    
                    # Redirect to next page or default dashboard
                    next_page = session.pop('next_after_biometric', None)
                    if not next_page:
                        next_page = url_for('auth.index')
                    return redirect(next_page)
                else:
                    flash('Facial biometric verification failed. Please try again.')
                    return redirect(url_for('auth.biometric_verification'))
        
        elif biometric_type == 'fingerprint':
            fingerprint_data = request.form.get('fingerprint_data')
            if not fingerprint_data:
                flash('No fingerprint data received')
                return redirect(url_for('auth.biometric_verification'))
            
            # Process the fingerprint data
            fingerprint_bytes = base64.b64decode(fingerprint_data)
            
            # Get stored fingerprint data for current user
            stored_fingerprint = current_user.get_fingerprint_data()
            
            if stored_fingerprint is None:
                # First time login, store the fingerprint data
                current_user.set_fingerprint_data(fingerprint_bytes)
                db.session.commit()
                flash('Fingerprint data registered successfully!')
                
                # Redirect to next page or default dashboard
                next_page = session.pop('next_after_biometric', None)
                if not next_page:
                    next_page = url_for('auth.index')
                return redirect(next_page)
            else:
                # In a real implementation, this would involve proper fingerprint matching
                # For this simulation, we'll just assume it's a match (since we're simulating the scanner)
                flash('Fingerprint verification successful!')
                
                # Redirect to next page or default dashboard
                next_page = session.pop('next_after_biometric', None)
                if not next_page:
                    next_page = url_for('auth.index')
                return redirect(next_page)
    
    return render_template('auth/biometric_verification.html')

@bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out successfully')
    return redirect(url_for('auth.index'))

