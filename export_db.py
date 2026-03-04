from app import create_app
from models import db
from sqlalchemy import text

app = create_app()
with app.app_context():
    # List all tables in current database
    
    # Check teachers count
    from models import Teacher
    count = Teacher.query.count()
    print(f"\nTeachers in current database: {count}")
    