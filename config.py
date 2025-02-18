import os

class Config:
    SECRET_KEY = os.environ.get('FLASK_SECRET_KEY', 'dev-key-123')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = '/tmp/uploads'
    MAX_CONTENT_LENGTH = 536870912  # 512MB max file size (in bytes)
    MAX_FILE_SIZE = 524288000  # 500MB max individual file size (in bytes)
    REQUEST_TIMEOUT = 1200  # 20 minutes timeout for large uploads
    ALLOWED_EXTENSIONS = {'png'}

    # Proxy settings
    PROXY_FIX = True
    PREFERRED_URL_SCHEME = 'https'

    # File upload settings
    MAX_CONTENT_LENGTH_STR = '512MB'  # For display purposes
    MAX_FILE_SIZE_STR = '500MB'  # For display purposes

    # Email configuration
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = 'info@appareldecorating.net'  

    # SendGrid configuration
    SENDGRID_API_KEY = os.environ.get('SENDGRID_API_KEY')

    # Production team email
    PRODUCTION_TEAM_EMAIL = ['greg.stitchscreen@gmail.com', 'rickey.stitchscreen@gmail.com']

    # DTF Printing costs
    COST_PER_SQINCH = 0.02  # Cost per square inch in USD