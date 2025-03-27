from flask import render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app.biometric import bp
from app.models import User, BiometricLog
from app.extensions import db
from app.utils import get_now
from datetime import datetime
import json
import os
import base64
from app.biometric.device import get_device, CaptureResult
from app.biometric.utils import extract_features, create_template, encode_template, decode_template, compare_templates

@bp.route('/enroll', methods=['GET', 'POST'])
@login_required
def enroll():
    """Enroll a user's fingerprint"""
    if request.method == 'POST':
        fingerprint_data = request.form.get('fingerprint_data')
        finger_position = request.form.get('finger_position', 'right_index')
        
        if not fingerprint_data:
            flash('No fingerprint data received')
            return redirect(url_for('biometric.enroll'))
        
        # Process the fingerprint data
        try:
            # Store the fingerprint template
            if finger_position == 'right_index':
                current_user.fingerprint_right_index = fingerprint_data
            elif finger_position == 'right_thumb':
                current_user.fingerprint_right_thumb = fingerprint_data
            elif finger_position == 'left_index':
                current_user.fingerprint_left_index = fingerprint_data
            elif finger_position == 'left_thumb':
                current_user.fingerprint_left_thumb = fingerprint_data
            
            # Log the enrollment
            log = BiometricLog(
                user_id=current_user.id,
                action='enroll',
                finger_position=finger_position,
                status='success',
                ip_address=request.remote_addr,
                device_info=request.user_agent.string
            )
            db.session.add(log)
            db.session.commit()
            
            flash(f'Fingerprint for {finger_position.replace("_", " ")} enrolled successfully')
            return redirect(url_for('profile.index'))
            
        except Exception as e:
            flash(f'Error enrolling fingerprint: {str(e)}')
            return redirect(url_for('biometric.enroll'))
    
    return render_template('biometric/enroll.html')

# Update the verify endpoint to use real template comparison
@bp.route('/verify', methods=['POST'])
@login_required
def verify():
    """Verify a fingerprint for clock-in/out"""
    fingerprint_data = request.form.get('fingerprint_data')
    action = request.form.get('action')  # 'clock_in' or 'clock_out'
    
    if not fingerprint_data:
        return jsonify({'success': False, 'message': 'No fingerprint data received'})
    
    # Decode the received fingerprint data
    try:
        captured_template = decode_template(fingerprint_data)
        if not captured_template:
            return jsonify({'success': False, 'message': 'Invalid fingerprint data'})
    except Exception as e:
        return jsonify({'success': False, 'message': f'Error processing fingerprint data: {str(e)}'})
    
    # Check if the user has enrolled fingerprints
    enrolled_templates = []
    if current_user.fingerprint_right_index:
        enrolled_templates.append(decode_template(current_user.fingerprint_right_index))
    if current_user.fingerprint_right_thumb:
        enrolled_templates.append(decode_template(current_user.fingerprint_right_thumb))
    if current_user.fingerprint_left_index:
        enrolled_templates.append(decode_template(current_user.fingerprint_left_index))
    if current_user.fingerprint_left_thumb:
        enrolled_templates.append(decode_template(current_user.fingerprint_left_thumb))
    
    if not enrolled_templates:
        return jsonify({'success': False, 'message': 'No enrolled fingerprints found'})
    
    # Compare with enrolled templates
    device = get_device()
    best_match_score = 0
    is_match = False
    
    for template in enrolled_templates:
        if template:
            match, score = device.compare_templates(captured_template, template)
            if match and score > best_match_score:
                is_match = True
                best_match_score = score
    
    if not is_match:
        return jsonify({
            'success': False, 
            'message': 'Fingerprint verification failed. No matching fingerprint found.',
            'score': best_match_score
        })
    
    # Log the verification attempt
    log = BiometricLog(
        user_id=current_user.id,
        action=f'verify_{action}',
        status='success',
        ip_address=request.remote_addr,
        device_info=request.user_agent.string,
        details=json.dumps({
            'match_score': best_match_score,
            'verification_time': datetime.now().isoformat()
        })
    )
    db.session.add(log)
    db.session.commit()
    
    return jsonify({
        'success': True, 
        'message': 'Fingerprint verified successfully',
        'score': best_match_score
    })

@bp.route('/status')
@login_required
def status():
    """Check if the fingerprint reader is connected"""
    device = get_device()
    
    # Try to connect to the device if not already connected
    if not device.is_connected():
        success, message = device.connect()
        if not success:
            return jsonify({
                'connected': False,
                'message': message,
                'status': 'disconnected'
            })
    
    # Get device status
    status_info = device.get_status()
    return jsonify(status_info)

# Update the capture endpoint to use the real device implementation
@bp.route('/capture', methods=['POST'])
@login_required
def capture():
    """Capture a fingerprint from the device"""
    device = get_device()
    
    # Check if device is connected
    if not device.is_connected():
        success, message = device.connect()
        if not success:
            return jsonify({
                'success': False,
                'message': 'Device not connected. ' + message
            })
    
    # Capture fingerprint
    result, fingerprint_data, quality = device.capture_fingerprint()
    
    if result != CaptureResult.SUCCESS:
        return jsonify({
            'success': False,
            'message': f'Capture failed: {result.name}',
            'quality': quality
        })
    
    # Encode for transmission
    encoded_data = encode_template(fingerprint_data)
    
    return jsonify({
        'success': True,
        'message': 'Fingerprint captured successfully',
        'data': encoded_data,
        'quality': quality
    })

@bp.route('/logs')
@login_required
def logs():
    """View biometric logs for the current user"""
    user_logs = BiometricLog.query.filter_by(user_id=current_user.id).order_by(BiometricLog.timestamp.desc()).all()
    return render_template('biometric/logs.html', logs=user_logs)

@bp.route('/test-device')
@login_required
def test_device():
    """Test the fingerprint device connection"""
    device = get_device()
    
    # Try to connect to the device
    success, message = device.connect()
    
    if success:
        status_info = device.get_status()
        return render_template('biometric/test_device.html', 
                              connected=True, 
                              message=message,
                              device_info=status_info['device_info'])
    else:
        return render_template('biometric/test_device.html', 
                              connected=False, 
                              message=message)

