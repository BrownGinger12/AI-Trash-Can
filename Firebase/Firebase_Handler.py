import firebase_admin
from firebase_admin import credentials, db
import os
from dotenv import load_dotenv

load_dotenv()

cred = credentials.Certificate("Firebase/key.json")
firebase_admin.initialize_app(cred, {
    'databaseURL': os.getenv("DATABASE_URL")
})

def add_points_to_user(user_id: str, points_to_add: int):
    try:
        ref = db.reference(f"/users/{user_id}")  

        current_points = ref.get()

        if current_points:
            data = { "points": current_points["points"] + points_to_add}
        else:
            data = { "points": points_to_add}

        response = ref.set(data)

        return {"statusCode": 200, "body": response}
    
    except Exception as e:
        return {"statusCode": 500, "body": e}
