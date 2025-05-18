import cv2
import threading
import serial
import time
import sys
import requests

from OpenAI.OpenAI_handler import openAi
from Firebase.Firebase_Handler import *

rfid_value = ""
is_scan = False
lock = threading.Lock()
running = True

def reward_user(rfid_value, points=0, reward_type="", reward_name=""):
    response = get_user_points(rfid_value)
    if response["statusCode"] == 200:
        userData = response["userData"]
        if userData["points"] > abs(points):
            db_resp = add_points_to_user(rfid_value, points)
            if db_resp["statusCode"] == 200:
                print("Points added!")

                if "contactNo" in userData:
                    contactNo = userData["contactNo"]
                    url = "https://app.philsms.com/api/v3/sms/send"

                    headers = {
                        "Authorization": "Bearer 1691|Y0sVBhXVG3wOwoSa6qZXCqXC7Pniw0WHVXebXveK",
                        "Content-Type": "application/json",
                        "Accept": "application/json"
                    }

                    data = {
                        "recipient": "639939107132",
                        "sender_id": "PhilSMS",
                        "type": "plain",
                        "message": f"{abs(points)} points is deducted, Thank you for your participation!",
                    }

                    print("Sending SMS to:", contactNo)

                    try:
                        response = requests.post(url, json=data, headers=headers)
                        print("Status Code:", response.status_code)
                        print("Response:", response.text)
                    except requests.exceptions.RequestException as e:
                        print("HTTP Request failed:", e)

                ser.write((reward_type).encode())
        else:
            print("Not enough points to redeem the reward.")        


def read_serial(ser):
    global rfid_value, running, is_scan
    time.sleep(2)

    try:
        while running:
            if ser.in_waiting > 0:
                data = ser.readline().decode('utf-8').strip()
                if data == "scan":
                    with lock:
                        is_scan = True
                    print("Garbage detected!")
                elif data == "reward1":
                    with lock:
                        current_rfid = rfid_value
                    if current_rfid:
                        reward_user(current_rfid, points=-5, reward_type="reward1", reward_name="pen")
                        with lock:
                            rfid_value = ""
                    else:
                        print("No RFID detected")
                elif data == "reward2":
                    with lock:
                        current_rfid = rfid_value
                    if current_rfid:
                        reward_user(current_rfid, points=-5, reward_type="reward1", reward_name="Highlighter")
                        with lock:
                            rfid_value = ""
                    else:
                        print("No RFID detected")
                elif data == "reward3":
                    with lock:
                        current_rfid = rfid_value
                    if current_rfid:
                        reward_user(current_rfid, points=-5, reward_type="reward1", reward_name="Marker")
                        with lock:
                            rfid_value = ""
                    else:
                        print("No RFID detected")   
                else:
                    with lock:
                        rfid_value = data
                    print(f"RFID Read: {rfid_value}")
                
    except Exception as e:
        print(f"RFID Thread Error: {e}")
    finally:
        print("RFID thread stopped.")

def process_camera(ser):
    global rfid_value, running, is_scan
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("Error: Could not open webcam.")
        return

    try:
        while running:
            ret, frame = cap.read()
            if not ret:
                print("Error: Failed to capture frame.")
                break

            cv2.imshow("Webcam Feed", frame)
            key = cv2.waitKey(1) & 0xFF

            with lock:
                scan_garbage = is_scan

            if scan_garbage:
                with lock:
                    current_rfid = rfid_value

                if current_rfid:
                    response = openAi().identify_image(frame)
                    if response:
                        if response == "1":
                            points = 3
                        elif response == "2":
                            points = 5
                        else:
                            points = 0

                        print(f"AI Response: {response}")

                        if points > 0:
                            db_resp = add_points_to_user(current_rfid, points)
                            if db_resp["statusCode"] == 200:
                                print("Points added!")

                                ser.write((response + '\n').encode())

                            else:
                                print(f"DB Error: {db_resp['body']}")
                        else:
                            print("Garbage cannot be identified")
                    else:
                        print("Garbage cannot be identified")
                else:
                    print("No RFID detected")

                with lock:
                    rfid_value = ""
                    is_scan = False


            elif key == ord('q'):
                running = False
                break

    except Exception as e:
        print(f"Camera Thread Error: {e}")
    finally:
        cap.release()
        cv2.destroyAllWindows()
        print("Camera thread stopped.")

if __name__ == "__main__":
    try:
        ser = serial.Serial('COM8', 9600, timeout=1)

        rfid_thread = threading.Thread(target=read_serial, args=(ser,))
        camera_thread = threading.Thread(target=process_camera, args=(ser,))

        rfid_thread.start()
        camera_thread.start()

        rfid_thread.join()
        camera_thread.join()

    except KeyboardInterrupt:
        running = False
        print("\nProgram interrupted. Exiting...")
        sys.exit()
