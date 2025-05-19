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
            data = { "rewardPoints": current_points["rewardPoints"] + points_to_add}
        else:
            data = { "rewardPoints": points_to_add}

        response = ref.update(data)

        return {"statusCode": 200, "body": response}
    
    except Exception as e:
        return {"statusCode": 500, "body": e}


def get_user_points(user_id: str):
    try:
        ref = db.reference(f"/users/{user_id}")
        user_data = ref.get()

        if user_data:
            return {"statusCode": 200, "userData": user_data}
        else:
            return {"statusCode": 404, "body": "User not found"}
    
    except Exception as e:
        return {"statusCode": 500, "body": e}