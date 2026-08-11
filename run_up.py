from app import app, db
from flask_migrate import upgrade
with app.app_context():
    upgrade()
print("Veritabanı başarıyla güncellendi!")
