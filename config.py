import os

class Config:
    SECRET_KEY = os.environ.get('FLASK_SECRET_KEY', 'dev-key-123')
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    UPLOAD_FOLDER = '/tmp/uploads'
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    ALLOWED_EXTENSIONS = {'png'}

    # Email configuration
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = 'noreply@dtfprinting.com'

    # SendGrid configuration
    SENDGRID_API_KEY = os.environ.get('SENDGRID_API_KEY')

    # Production team email
    PRODUCTION_TEAM_EMAIL = os.environ.get('PRODUCTION_TEAM_EMAIL')

    # DTF Printing costs
    COST_PER_SQINCH = 0.02  # Cost per square inch in USD