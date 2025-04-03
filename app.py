import cv2
from OpenAI.OpenAI_handler import openAi
from Firebase.Firebase_Handler import *

cap = cv2.VideoCapture(0)

rfid = "12345"

if not cap.isOpened():
    print("Error: Could not open webcam.")
    exit()

while True:
    ret, frame = cap.read()

    if not ret:
        print("Error: Failed to capture frame.")
        break

    
    cv2.imshow("Webcam Feed", frame)

    if cv2.waitKey(1) & 0xFF == ord('s'):
        if rfid:
            response = openAi().identify_image(frame)
            if response:

                if response == "1":
                    points_to_add = 3
                elif response == "2":
                    points_to_add = 5
                else:
                    points_to_add = 0

                print(response)

                if points_to_add != 0:
                    db_resp = add_points_to_user(rfid, points_to_add)

                    if db_resp["statusCode"] == 200:
                        print("Points added!")
                    else:
                        print("An error occured")
                else:
                    print("Garbage cannot be identified")

            else:
                print("Garbage cannot be identified")
        
        else:
            print("rfid is empty")


    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
