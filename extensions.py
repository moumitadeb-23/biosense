from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect

# Database ORM instance
db = SQLAlchemy()

# User session manager
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "Please authenticate to access the requested scientific analytics."
login_manager.login_message_category = "info"

# Cross-Site Request Forgery (CSRF) Protection
csrf = CSRFProtect()
