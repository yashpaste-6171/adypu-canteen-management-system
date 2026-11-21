import os
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-this-secret-key-before-deployment")
    DATABASE = os.path.join(BASE_DIR, "ADYPU Canteen.db")
