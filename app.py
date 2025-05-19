import cv2
import threading
import serial
import time
import sys
import requests
import tkinter as tk
from tkinter import Label, Button, Text, Scrollbar
from PIL import Image, ImageTk
import io

from OpenAI.OpenAI_handler import openAi
from Firebase.Firebase_Handler import *

rfid_value = ""
is_scan = False
lock = threading.Lock()
running = True

# Global variables for Tkinter UI
root = None
video_label = None
output_text = None
frame_image = None
trash1_label = None
trash2_label = None

# Redirect print to label   
class PrintRedirect(io.StringIO):
    def write(self, s):
        if output_text:
            output_text.after(0, self._write_to_text, s)
        sys.__stdout__.write(s)
    
    def _write_to_text(self, s):
        output_text.insert(tk.END, s)
        output_text.see(tk.END)  # Auto-scroll to bottom

sys.stdout = PrintRedirect()

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
                        "recipient": contactNo,
                        "sender_id": "PhilSMS",
                        "type": "plain",
                        "message": f"{abs(points)} points is deducted, Thank you for your participation!",
                    }

                    print("Sending SMS to:", contactNo)

                    try:
                        response = requests.post(url, json=data, headers=headers)
                        print("Message Sent")
                    except requests.exceptions.RequestException as e:
                        print("Message failed")

                ser.write((reward_type).encode())
        else:
            print("Not enough points to redeem the reward.")        


def read_serial(ser):
    global rfid_value, running, is_scan, trash1_label, trash2_label
    time.sleep(2)

    try:
        while running:
            if ser.in_waiting > 0:
                data = ser.readline().decode('utf-8').strip()
                if data.startswith("trash1:"):
                    fullness = data.split(":")[1]
                    if trash1_label:
                        root.after(0, trash1_label.config, {'text': f"Trash Bin 1: {fullness}"})
                elif data.startswith("trash2:"):
                    fullness = data.split(":")[1]
                    if trash2_label:
                        root.after(0, trash2_label.config, {'text': f"Trash Bin 2: {fullness}"})
                elif data == "scan":
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
                        reward_user(current_rfid, points=-15, reward_type="reward2", reward_name="Highlighter")
                        with lock:
                            rfid_value = ""
                    else:
                        print("No RFID detected")
                elif data == "reward3":
                    with lock:
                        current_rfid = rfid_value
                    if current_rfid:
                        reward_user(current_rfid, points=-20, reward_type="reward3", reward_name="Marker")
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

def create_fullscreen_camera():
    global root, video_label, output_text, trash1_label, trash2_label
    root = tk.Tk()
    root.attributes('-fullscreen', True)
    root.configure(background='black')

    # Set window size for 5-inch display (800x480)
    root.geometry("800x480")

    # Create main frame
    main_frame = tk.Frame(root, bg='black')
    main_frame.pack(expand=True, fill='both')

    # Create video label with border
    video_frame = tk.Frame(main_frame, bg='white', bd=1, relief='solid')
    video_frame.pack(expand=True, padx=10, pady=10)
    
    video_label = Label(video_frame, bg='black')
    video_label.pack(expand=True, padx=1, pady=1)

    # Create trash fullness frame
    trash_frame = tk.Frame(main_frame, bg='black')
    trash_frame.pack(fill='x', padx=10, pady=2)

    # Create labels for trash fullness
    trash1_label = Label(trash_frame, text="Trash Bin 1: 0%", font=("Arial", 12),
                        fg="white", bg="black", padx=5)
    trash1_label.pack(side='left', expand=True)

    trash2_label = Label(trash_frame, text="Trash Bin 2: 0%", font=("Arial", 12),
                        fg="white", bg="black", padx=5)
    trash2_label.pack(side='right', expand=True)

    # Create output text area with scrollbar
    output_frame = tk.Frame(main_frame, bg='black')
    output_frame.pack(fill='x', padx=10, pady=2)

    # Scrollbar for output text
    scrollbar = Scrollbar(output_frame)
    scrollbar.pack(side='right', fill='y')

    # Output text area
    output_text = Text(output_frame, height=4, width=50, bg='black', fg='white',
                      font=('Consolas', 9), yscrollcommand=scrollbar.set)
    output_text.pack(side='left', fill='x', expand=True)
    scrollbar.config(command=output_text.yview)

    # Create status frame at the bottom
    status_frame = tk.Frame(main_frame, bg='black')
    status_frame.pack(fill='x', pady=2)

    # Close button
    close_button = Button(status_frame, text="Exit", font=("Arial", 10),
                         command=lambda: [setattr(sys.modules[__name__], 'running', False), root.destroy()],
                         bg='red', fg='white', padx=5, pady=2)
    close_button.pack(side='right', padx=10)

    # Add key binding to exit fullscreen
    root.bind("<Escape>", lambda e: [setattr(sys.modules[__name__], 'running', False), root.destroy()])

def update_camera_frame(frame):
    if video_label and frame is not None:
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(frame_rgb)
        frame_image = ImageTk.PhotoImage(image=img)
        video_label.config(image=frame_image)
        video_label.image = frame_image  # Keep a reference!

def process_camera(ser):
    global rfid_value, running, is_scan
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("Error: Could not open webcam.")
        return

    # Set camera resolution to match display
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 360)

    try:
        while running:
            ret, frame = cap.read()
            if not ret:
                print("Error: Failed to capture frame.")
                break

            # Resize frame to fit display
            frame = cv2.resize(frame, (640, 360))

            # Update the frame in the main thread
            root.after(0, update_camera_frame, frame)

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

            time.sleep(0.03)  # ~30 FPS

    except Exception as e:
        print(f"Camera Thread Error: {e}")
    finally:
        cap.release()
        print("Camera thread stopped.")

def create_gui():
    create_fullscreen_camera()

if __name__ == "__main__":
    try:
        ser = serial.Serial('/dev/ttyACM0', 9600, timeout=1)
        create_fullscreen_camera()

        # Start the camera and RFID threads
        rfid_thread = threading.Thread(target=read_serial, args=(ser,))
        camera_thread = threading.Thread(target=process_camera, args=(ser,))

        rfid_thread.start()
        camera_thread.start()

        # Run the main loop in the main thread
        root.mainloop()

        # After mainloop ends, wait for threads to finish
        running = False
        rfid_thread.join()
        camera_thread.join()

    except KeyboardInterrupt:
        running = False
        print("\nProgram interrupted. Exiting...")
        sys.exit()
    finally:
        if 'ser' in locals():
            ser.close()
