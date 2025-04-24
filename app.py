import cv2
import threading
import serial
import time
import sys

from OpenAI.OpenAI_handler import openAi
from Firebase.Firebase_Handler import *

rfid_value = ""
is_scan = False
lock = threading.Lock()
running = True

def read_rfid(ser):
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
        ser = serial.Serial('/dev/ttyACM0', 9600, timeout=1)

        rfid_thread = threading.Thread(target=read_rfid, args=(ser,))
        camera_thread = threading.Thread(target=process_camera, args=(ser,))

        rfid_thread.start()
        camera_thread.start()

        rfid_thread.join()
        camera_thread.join()

    except KeyboardInterrupt:
        running = False
        print("\nProgram interrupted. Exiting...")
        sys.exit()
