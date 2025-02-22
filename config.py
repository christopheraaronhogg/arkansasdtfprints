import os

class Config:
    SECRET_KEY = os.environ.get('FLASK_SECRET_KEY', 'dev-key-123')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'postgresql://neondb_owner:npg_dB0gsHM7KDuI@ep-cold-glade-a54esyy3.us-east-2.aws.neon.tech/neondb?sslmode=require')
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

    # Database Configuration
    POSTGRES_CONFIG = {
        'database': os.environ.get('PGDATABASE', 'neondb'),
        'user': os.environ.get('PGUSER', 'neondb_owner'),
        'password': os.environ.get('PGPASSWORD', 'npg_dB0gsHM7KDuI'),
        'host': os.environ.get('PGHOST', 'ep-cold-glade-a54esyy3.us-east-2.aws.neon.tech'),
        'port': os.environ.get('PGPORT', '5432')
    }

    # Object Storage Configuration
    OBJECT_STORAGE_BUCKET_ID = 'replit-objstore-c3fb67d8-cc58-4f6a-8303-0ada7212ebd1'