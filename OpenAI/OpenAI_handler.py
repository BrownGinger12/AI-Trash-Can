import base64
from openai import OpenAI
from dotenv import load_dotenv
import cv2
import os

load_dotenv()

def encode_image(frame):
    _, buffer = cv2.imencode(".jpg", frame)  # Convert frame to JPEG format
    return base64.b64encode(buffer).decode("utf-8") 


class openAi:
    def __init__(self):
        key = os.getenv("OPENAI_API_KEY")
        self.client = OpenAI(api_key = key)

    def identify_image(self, image):
        base64_image = encode_image(image)

        response = self.client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are an AI that identifies garbage. Output '1' if it's a plastic bottle and '2' if it's metal."},
                {"role": "user", "content": [
                    {"type": "text", "text": "Identify the garbage in the image."},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}},
                ]},
            ],
            max_tokens=10
        )

        return response.choices[0].message.content
