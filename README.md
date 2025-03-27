# School Management System

A comprehensive system for tracking lecture attendance, managing class sessions, and ensuring accountability through biometric authentication and e-signature verification.

## Features

- **Biometric Authentication**: Secure access with facial recognition technology
- **Session Tracking**: Monitor lecture start and end times accurately
- **E-Signature Verification**: Class representatives verify session details
- **Role-Based Access**: Different permissions for admin, lecturers, and class reps
- **Comprehensive Reports**: Generate detailed reports on lecturer attendance
- **Real-time Dashboard**: Monitor ongoing classes and session status
- **Calendar View**: Visual representation of all sessions
- **Email Notifications**: Automatic notifications for session status changes
- **Export Functionality**: Export reports in various formats (CSV, Excel, JSON)

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/school-management-system.git
cd school-management-system
```

### Set up a local SMTP debugging server using Python's built-in `smtpd` module.
This way, you can test email functionality without actually sending emails.



1. **First, modify your .env file to use local SMTP server settings:**

````properties
# Email Configuration
MAIL_SERVER=localhost
MAIL_PORT=1025
MAIL_USE_TLS=false
MAIL_USERNAME=
MAIL_PASSWORD=
MAIL_DEFAULT_SENDER=test@localhost
````

2. **Create a test email route:**

````python
from flask import Blueprint
from flask_mail import Message
from app import mail

test_bp = Blueprint('test', __name__)

@test_bp.route('/test-email')
def test_email():
    msg = Message('Test Email',
                  sender='test@localhost',
                  recipients=['recipient@localhost'],
                  body='This is a test email from the School Management System')
    mail.send(msg)
    return 'Email sent to debug server!'
````

3. **Start the local SMTP debugging server**

Open a new terminal and run:
```bash
python3 -m smtpd -n -c DebuggingServer localhost:1025
```

4. **Test sending an email**

Using curl or your browser:
```bash
curl http://localhost:5000/test-email
```

