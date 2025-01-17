
import os
import base64
import openai
from openai import OpenAI
import pyaudio
import logging
import cv2


# camera
cam_port = 0
cam = cv2.VideoCapture(cam_port) 
width = 640
height = 480
cam.set(cv2.CAP_PROP_FRAME_WIDTH, width)
cam.set(cv2.CAP_PROP_FRAME_HEIGHT, height)

openai.api_key = os.environ['OPENAI_API_KEY']

client = OpenAI(
  api_key=os.environ['OPENAI_API_KEY'],  # this is also the default, it can be omitted
)


# Open the image file and encode it as a base64 string
def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode("utf-8")

def ask_openai(prompt, imagedata):
    logging.info(f"Asking OpenAI with prompt: {prompt}")
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": [
                {"type": "text", "text": f"{prompt}"},
                {"type": "image_url", "image_url": {
                    "url": f"data:image/png;base64,{imagedata}"}
                }
            ]}
        ],
        temperature=0.0,
    )
    return response.choices[0].message.content



def main():
 
    prompt = "Describe the following image."# What color is the sweater?"

    # -,image = cam.read() # read frame from webcam
    # cv2.imwrite("camview.jpg", image) #save image

    # convert image to base64
    IMAGE_PATH = "camview.jpg"
    # _, buffer = cv2.imencode('.jpg', encode_image(IMAGE_PATH))
    # image_base64 = base64.b64encode(buffer).decode('utf-8')

    response = ask_openai(prompt, encode_image(IMAGE_PATH))

    print(response)



if __name__ == "__main__":
    main()
