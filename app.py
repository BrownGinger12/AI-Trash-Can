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

# Global variables for Tkinter UI.
root = None
video_label = None
output_text = None
frame_image = None
trash1_label = None
trash2_label = None
trash1_capacity = 0
trash2_capacity = 0

# Add these globals at the top (after other globals)
pending_trash_action = None  # {'rfid': ..., 'trash_type': ..., 'points': ..., 'bin': ...}
last_trash1_capacity = 0
last_trash2_capacity = 0

# Add these globals after other globals
pause_trash1_ultrasonic = False
pause_trash2_ultrasonic = False

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
        if userData["rewardPoints"] >= abs(points):
            db_resp = add_points_to_user(rfid_value, points)
            if db_resp["statusCode"] == 200:
                print("Points deducted!")

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
    global rfid_value, running, is_scan, trash1_label, trash2_label, trash1_capacity, trash2_capacity
    global last_trash1_capacity, last_trash2_capacity
    global pause_trash1_ultrasonic, pause_trash2_ultrasonic
    # Remove pending_trash_action logic, as point addition is now handled in process_camera

    time.sleep(2)

    try:
        while running:
            if ser.in_waiting > 0:
                data = ser.readline().decode('utf-8', errors='ignore').strip()
                if data.startswith("trash1:"):
                    try:
                        if not pause_trash1_ultrasonic:
                            fullness = data.split(":")[1]
                            raw_capacity = int(''.join(filter(str.isdigit, fullness)))
                            trash1_capacity = raw_capacity
                            if trash1_label:
                                root.after(0, trash1_label.config, {'text': f"Trash Bin 1: {trash1_capacity}%"})
                            last_trash1_capacity = trash1_capacity
                    except Exception as e:
                        print(f"Error parsing trash1 data: '{data}' - {e}")
                elif data.startswith("trash2:"):
                    try:
                        if not pause_trash2_ultrasonic:
                            fullness = data.split(":")[1]
                            raw_capacity = int(''.join(filter(str.isdigit, fullness)))
                            trash2_capacity = raw_capacity
                            if trash2_label:
                                root.after(0, trash2_label.config, {'text': f"Trash Bin 2: {trash2_capacity}%"})
                            last_trash2_capacity = trash2_capacity
                    except Exception as e:
                        print(f"Error parsing trash2 data: '{data}' - {e}")
                elif data == "scan":
                    # Check if either trash bin is at 100% capacity
                    if trash1_capacity >= 100 or trash2_capacity >= 100:
                        print("Cannot scan: One or more trash bins are full!")
                        ser.write("full\n".encode())
                    else:
                        with lock:
                            is_scan = True
                        print("Garbage detected!")
                elif data == "login":
                    # Login: set RFID as current user
                    with lock:
                        if rfid_value != "":
                            print(f"User {rfid_value} already logged in.")
                        else:
                            # Wait for next RFID scan
                            print("Please scan your RFID to login.")
                elif data == "logout":
                    # Logout: clear RFID
                    with lock:
                        if rfid_value != "":
                            print(f"User {rfid_value} logged out.")
                            rfid_value = ""
                        else:
                            print("No user is currently logged in.")
                elif data == "reward1":
                    with lock:
                        current_rfid = rfid_value
                    if current_rfid:
                        reward_user(current_rfid, points=-5, reward_type="reward1", reward_name="pen")
                        with lock:
                            rfid_value = ""  # Logout after redeem
                    else:
                        print("No RFID detected")
                elif data == "reward2":
                    with lock:
                        current_rfid = rfid_value
                    if current_rfid:
                        reward_user(current_rfid, points=-15, reward_type="reward2", reward_name="Highlighter")
                        with lock:
                            rfid_value = ""  # Logout after redeem
                    else:
                        print("No RFID detected")
                elif data == "reward3":
                    with lock:
                        current_rfid = rfid_value
                    if current_rfid:
                        reward_user(current_rfid, points=-20, reward_type="reward3", reward_name="Marker")
                        with lock:
                            rfid_value = ""  # Logout after redeem
                    else:
                        print("No RFID detected")   
                else:
                    # Assume this is an RFID scan
                    with lock:
                        if rfid_value == "":
                            rfid_value = data
                            print(f"RFID Read: {rfid_value} (logged in)")
                        elif rfid_value == data:
                            # Same RFID presented again: treat as logout
                            print(f"User {rfid_value} logged out.")
                            rfid_value = ""
                        else:
                            print(f"RFID {rfid_value} already logged in. Please logout first.")
                
    except Exception as e:
        print(f"RFID Thread Error: {e}")
    finally:
        print("RFID thread stopped.")

def create_fullscreen_camera():
    global root, video_label, output_text, trash1_label, trash2_label, scan_button
    root = tk.Tk()
    root.attributes('-fullscreen', True)
    root.overrideredirect(True)  # Remove window decorations
    root.configure(background='black')

    # Set window size for 5-inch display (800x480)
    root.geometry("800x480")

    # Create main frame
    main_frame = tk.Frame(root, bg='black')
    main_frame.pack(expand=True, fill='both')

    # --- BUTTONS ON THE RIGHT SIDE ---
    right_button_frame = tk.Frame(main_frame, bg='black')
    right_button_frame.pack(side='right', fill='y', padx=5, pady=5)

    scan_button = Button(
        right_button_frame,
        text="Scan",
        font=("Arial", 18, "bold"),  # Larger font
        bg='green',
        fg='white',
        padx=24,  # Wider padding
        pady=18,  # Taller padding
        height=2,  # Button height in text lines
        width=8,   # Button width in characters
        command=on_scan_button
    )
    scan_button.pack(side='top', pady=20, anchor='ne')

    close_button = Button(
        right_button_frame,
        text="Exit",
        font=("Arial", 16),
        command=lambda: [setattr(sys.modules[__name__], 'running', False), root.destroy()],
        bg='red',
        fg='white',
        padx=18,
        pady=12,
        height=2,
        width=8
    )
    close_button.pack(side='top', pady=20, anchor='ne')

    # --- VIDEO FRAME ---
    video_frame = tk.Frame(main_frame, bg='black')
    video_frame.pack(expand=True, padx=5, pady=5, fill='both')
    video_label = Label(video_frame, bg='black')
    video_label.pack(expand=True, fill='both')

    # --- TRASH FULLNESS FRAME ---
    trash_frame = tk.Frame(main_frame, bg='black')
    trash_frame.pack(fill='x', padx=5, pady=2)
    trash1_label = Label(trash_frame, text="Trash Bin 1: 0%", font=("Arial", 12),
                        fg="white", bg="black", padx=5)
    trash1_label.pack(side='left', expand=True)
    trash2_label = Label(trash_frame, text="Trash Bin 2: 0%", font=("Arial", 12),
                        fg="white", bg="black", padx=5)
    trash2_label.pack(side='right', expand=True)

    # --- OUTPUT TEXT AREA ---
    output_frame = tk.Frame(main_frame, bg='black')
    output_frame.pack(fill='x', padx=5, pady=2)
    scrollbar = Scrollbar(output_frame)
    scrollbar.pack(side='right', fill='y')
    output_text = Text(output_frame, height=3, width=50, bg='black', fg='white',
                      font=('Consolas', 9), yscrollcommand=scrollbar.set)
    output_text.pack(side='left', fill='x', expand=True)
    scrollbar.config(command=output_text.yview)

    # Add key binding to exit fullscreen
    root.bind("<Escape>", lambda e: [setattr(sys.modules[__name__], 'running', False), root.destroy()])

def update_camera_frame(frame):
    if video_label and frame is not None:
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = Image.fromarray(frame_rgb)
        frame_image = ImageTk.PhotoImage(image=img)
        video_label.config(image=frame_image)
        video_label.image = frame_image  # Keep a reference!

def update_camera_error_message(msg):
    if output_text:
        output_text.after(0, lambda: output_text.insert(tk.END, f"\n{msg}\n"))
        output_text.after(0, output_text.see, tk.END)

def process_camera(ser):
    global rfid_value, running, is_scan, trash1_capacity, trash2_capacity, scan_button
    global last_trash1_capacity, last_trash2_capacity
    global pause_trash1_ultrasonic, pause_trash2_ultrasonic
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        print("Error: Could not open webcam.")
        update_camera_error_message("Error: Could not open webcam. Please check connection.")
        return

    # Set camera resolution to match display
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 480)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 270)

    try:
        while running:
            ret, frame = cap.read()
            if not ret:
                print("Error: Failed to capture frame.")
                update_camera_error_message("Error: Failed to capture frame. Camera disconnected.")
                break

            # Rotate frame 180 degrees by flipping both horizontally and vertically
            frame = cv2.flip(frame, -1)
            frame = cv2.resize(frame, (480, 270))
            root.after(0, update_camera_frame, frame)

            with lock:
                scan_garbage = is_scan

            if scan_garbage:
                with lock:
                    current_rfid = rfid_value

                if current_rfid:
                    print("Scanning trash... Please wait.")
                    if output_text:
                        output_text.after(0, lambda: output_text.insert(tk.END, "\nScanning trash... Please wait.\n"))
                        output_text.after(0, output_text.see, tk.END)
                    # Freeze for 3 seconds (show scanning, update camera)
                    scan_start_time = time.time()
                    last_frame = frame
                    while time.time() - scan_start_time < 3 and running:
                        ret, frame = cap.read()
                        if ret:
                            frame = cv2.flip(frame, -1)
                            frame = cv2.resize(frame, (480, 270))
                            root.after(0, update_camera_frame, frame)
                            last_frame = frame
                        time.sleep(0.03)

                    response = openAi().identify_image(last_frame)
                    if response:
                        if response == "1":
                            points = 3
                            bin_num = 1
                        elif response == "2":
                            points = 5
                            bin_num = 2
                        else:
                            points = 0
                            bin_num = None

                        print(f"AI Response: {response}")

                        if response and points > 0 and bin_num:
                            # --- PAUSE ultrasonic 1s before open, store value ---
                            if bin_num == 1:
                                pause_trash1_ultrasonic = True
                            else:
                                pause_trash2_ultrasonic = True

                            time.sleep(1)
                            if bin_num == 1:
                                before_open = trash1_capacity
                            else:
                                before_open = trash2_capacity

                            # --- RESUME ultrasonic, open servo, store value 1s after open ---
                            if bin_num == 1:
                                pause_trash1_ultrasonic = False
                            else:
                                pause_trash2_ultrasonic = False

                            try:
                                ser.write((str(response) + '\n').encode())
                                print(f"Servo triggered for Bin {bin_num}")
                            except Exception as e:
                                print(f"Servo error: {e}")

                            time.sleep(1)
                            if bin_num == 1:
                                after_open = trash1_capacity
                            else:
                                after_open = trash2_capacity

                            # Prompt user to throw trash
                            print("Please throw your trash now.")
                            if output_text:
                                output_text.after(0, lambda: output_text.insert(tk.END, "\nPlease throw your trash now.\n"))
                                output_text.after(0, output_text.see, tk.END)

                            # Wait for user to throw (total open time minus 2s already used)
                            time.sleep(0.5)  # Example: open total 2.5s before close

                            # --- PAUSE ultrasonic 1s before close, store value ---
                            if bin_num == 1:
                                pause_trash1_ultrasonic = True
                            else:
                                pause_trash2_ultrasonic = True

                            time.sleep(1)
                            if bin_num == 1:
                                before_close = trash1_capacity
                            else:
                                before_close = trash2_capacity

                            # --- RESUME ultrasonic, close servo, store value 1s after close ---
                            if bin_num == 1:
                                pause_trash1_ultrasonic = False
                            else:
                                pause_trash2_ultrasonic = False

                            try:
                                ser.write(b"close\n")
                            except Exception as e:
                                print(f"Servo close error: {e}")

                            time.sleep(1)
                            if bin_num == 1:
                                after_close = trash1_capacity
                            else:
                                after_close = trash2_capacity

                            # --- Compare before_close and after_close ---
                            if after_close > before_close:
                                print(f"Throw detected in Bin {bin_num}. Adding {points} points.")
                                db_resp = add_points_to_user(current_rfid, points)
                                if db_resp["statusCode"] == 200:
                                    print("Points added!")
                                    if output_text:
                                        output_text.after(0, lambda: output_text.insert(tk.END, f"\nPoints added!\n"))
                                        output_text.after(0, output_text.see, tk.END)
                                else:
                                    print(f"DB Error: {db_resp['body']}")
                                    show_db_error(db_resp['body'])
                            else:
                                print("No trash detected after servo closed. No points added.")
                                if output_text:
                                    output_text.after(0, lambda: output_text.insert(tk.END, "\nNo trash detected after servo closed. No points added.\n"))
                                    output_text.after(0, output_text.see, tk.END)
                        elif not response:
                            print("Selected trash bin is full")
                        else:
                            print("Garbage cannot be identified")
                    else:
                        print("Garbage cannot be identified")
                else:
                    print("No RFID detected")

                with lock:
                    is_scan = False
                if scan_button:
                    scan_button.config(state='normal')

            time.sleep(0.03)  # ~30 FPS

    except Exception as e:
        print(f"Camera Thread Error: {e}")
    finally:
        cap.release()
        print("Camera thread stopped.")

def create_gui():
    create_fullscreen_camera()

def on_scan_button():
    global is_scan, scan_button
    with lock:
        is_scan = True
    if scan_button:
        scan_button.config(state='disabled')

def show_db_error(msg):
    if output_text:
        output_text.after(0, lambda: output_text.insert(tk.END, f"\nDB Error: {msg}\n"))
        output_text.after(0, output_text.see, tk.END)

# --- Ultrasonic filtering helpers ---
def get_filtered_capacity(current_capacity, last_capacity, history, threshold=20, window=5):
    """
    Smooths ultrasonic readings:
    - Ignores sudden spikes (likely servo noise)
    - Returns median of last N readings
    """
    # Ignore sudden spikes
    if abs(current_capacity - last_capacity) > threshold:
        current_capacity = last_capacity
    # Maintain a rolling window of readings
    history.append(current_capacity)
    if len(history) > window:
        history.pop(0)
    # Return median for robustness
    sorted_hist = sorted(history)
    median = sorted_hist[len(sorted_hist)//2]
    return median

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
