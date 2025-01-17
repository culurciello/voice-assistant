
import os
import sys
import base64
import time
import pyttsx3
import torch
import openai
from openai import OpenAI
import yaml
import pygame
import pygame.locals
import numpy as np
import pyaudio
import whisper
# import logging
import threading
import queue
import cv2

# Configure logging
# logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

BACK_COLOR = (0,0,0)
REC_COLOR = (255,0,0)
TEXT_COLOR = (255,255,255)
REC_SIZE = 80
FONT_SIZE = 24
WIDTH = 320
HEIGHT = 240
KWIDTH = 20
KHEIGHT = 6
MAX_TEXT_LEN_DISPLAY = 32

INPUT_DEFAULT_DURATION_SECONDS = 5
INPUT_FORMAT = pyaudio.paInt16
INPUT_CHANNELS = 1
INPUT_RATE = 16000
INPUT_CHUNK = 1024
INPUT_CONFIG_PATH ="assistant.yaml"

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

class Assistant:
    def __init__(self):
        # logging.info("Initializing Assistant")
        self.config = self.init_config()

        programIcon = pygame.image.load('assistant.png')

        self.clock = pygame.time.Clock()
        pygame.display.set_icon(programIcon)
        pygame.display.set_caption("Assistant")

        self.windowSurface = pygame.display.set_mode((WIDTH, HEIGHT), 0, 32)
        self.font = pygame.font.SysFont(None, FONT_SIZE)

        self.audio = pyaudio.PyAudio()

        self.tts = pyttsx3.init("nsss");
        # self.tts.setProperty('rate', self.tts.getProperty('rate') - 20)
        voices = self.tts.getProperty('voices')
        self.tts.setProperty('voice', voices[0].id)

        try:
            self.audio.open(format=INPUT_FORMAT,
                            channels=INPUT_CHANNELS,
                            rate=INPUT_RATE,
                            input=True,
                            frames_per_buffer=INPUT_CHUNK).close()
        except Exception as e:
            # logging.error(f"Error opening audio stream: {str(e)}")
            self.wait_exit()

        self.display_message(self.config.messages.loadingModel)
        self.model = whisper.load_model(self.config.whisperRecognition.modelPath)
        self.context = []

        self.text_to_speech(self.config.conversation.greeting)
        time.sleep(0.5)
        self.display_message(self.config.messages.pressSpace)

    def wait_exit(self):
        while True:
            self.display_message(self.config.messages.noAudioInput)
            self.clock.tick(60)
            for event in pygame.event.get():
                if event.type == pygame.locals.QUIT:
                    self.shutdown()

    def shutdown(self):
        # logging.info("Shutting down Assistant")
        self.audio.terminate()
        pygame.quit()
        sys.exit()

    def init_config(self):
        # logging.info("Initializing configuration")
        class Inst:
            pass

        with open('assistant.yaml', encoding='utf-8') as data:
            configYaml = yaml.safe_load(data)

        config = Inst()
        config.messages = Inst()
        config.messages.loadingModel = configYaml["messages"]["loadingModel"]
        config.messages.pressSpace = configYaml["messages"]["pressSpace"]
        config.messages.noAudioInput = configYaml["messages"]["noAudioInput"]

        config.conversation = Inst()
        config.conversation.greeting = configYaml["conversation"]["greeting"]

        config.whisperRecognition = Inst()
        config.whisperRecognition.modelPath = configYaml["whisperRecognition"]["modelPath"]
        config.whisperRecognition.lang = configYaml["whisperRecognition"]["lang"]

        return config

    def display_rec_start(self):
        # logging.info("Displaying recording start")
        self.windowSurface.fill(BACK_COLOR)
        pygame.draw.circle(self.windowSurface, REC_COLOR, (WIDTH/2, HEIGHT/2), REC_SIZE)
        pygame.display.flip()

    def display_sound_energy(self, energy):
        # logging.info(f"Displaying sound energy: {energy}")
        COL_COUNT = 5
        RED_CENTER = 100
        FACTOR = 10
        MAX_AMPLITUDE = 100

        self.windowSurface.fill(BACK_COLOR)
        amplitude = int(MAX_AMPLITUDE*energy)
        hspace, vspace = 2*KWIDTH, int(KHEIGHT/2)
        def rect_coords(x, y):
            return (int(x-KWIDTH/2), int(y-KHEIGHT/2),
                    KWIDTH, KHEIGHT)
        for i in range(-int(np.floor(COL_COUNT/2)), int(np.ceil(COL_COUNT/2))):
            x, y, count = WIDTH/2+(i*hspace), HEIGHT/2, amplitude-2*abs(i)

            mid = int(np.ceil(count/2))
            for i in range(0, mid):
                offset = i*(KHEIGHT+vspace)
                pygame.draw.rect(self.windowSurface, RED_CENTER,
                                rect_coords(x, y+offset))
                #mirror:
                pygame.draw.rect(self.windowSurface, RED_CENTER,
                                rect_coords(x, y-offset))
        pygame.display.flip()

    def display_message(self, text):
        # logging.info(f"Displaying message: {text}")
        self.windowSurface.fill(BACK_COLOR)

        label = self.font.render(text
                                 if (len(text)<MAX_TEXT_LEN_DISPLAY)
                                 else (text[0:MAX_TEXT_LEN_DISPLAY]+"..."),
                                 1,
                                 TEXT_COLOR)

        size = label.get_rect()[2:4]
        self.windowSurface.blit(label, (WIDTH/2 - size[0]/2, HEIGHT/2 - size[1]/2))

        pygame.display.flip()

    def waveform_from_mic(self, key = pygame.K_SPACE) -> np.ndarray:
        # logging.info("Capturing waveform from microphone")
        self.display_rec_start()

        stream = self.audio.open(format=INPUT_FORMAT,
                                 channels=INPUT_CHANNELS,
                                 rate=INPUT_RATE,
                                 input=True,
                                 frames_per_buffer=INPUT_CHUNK)
        frames = []

        while True:
            pygame.event.pump() # process event queue
            pressed = pygame.key.get_pressed()
            if pressed[key]:
                data = stream.read(INPUT_CHUNK)
                frames.append(data)
            else:
                break

        stream.stop_stream()
        stream.close()

        return np.frombuffer(b''.join(frames), np.int16).astype(np.float32) * (1 / 32768.0)

    def speech_to_text(self, waveform):
        # logging.info("Converting speech to text")
        result_queue = queue.Queue()

        def transcribe_speech():
            try:
                # logging.info("Starting transcription")
                transcript = self.model.transcribe(waveform,
                                                language=self.config.whisperRecognition.lang,
                                                fp16=torch.cuda.is_available())
                # logging.info("Transcription completed")
                text = transcript["text"]
                print('\nMe:\n', text.strip())
                result_queue.put(text)
            except Exception as e:
                # logging.error(f"An error occurred during transcription: {str(e)}")
                result_queue.put("")

        transcription_thread = threading.Thread(target=transcribe_speech)
        transcription_thread.start()
        transcription_thread.join()

        return result_queue.get()


    def ask_openai(self, prompt, imagedata):
        # logging.info(f"Asking OpenAI with prompt: {prompt}")
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

    def text_to_speech(self, text):
        # logging.info(f"Converting text to speech: {text}")
        print('\nAI:\n', text.strip())

        # logging.info("Initializing TTS engine")
        engine = pyttsx3.init()
        
        # Adjust the speech rate (optional)
        # rate = engine.getProperty('rate')
        # engine.setProperty('rate', rate - 50)  # Decrease the rate by 50 units
        
        # Add a short delay before converting text to speech
        time.sleep(0.5)  # Adjust the delay as needed
        
        # logging.info("Converting text to speech")
        engine.say(text)
        engine.runAndWait()
        # logging.info("Speech playback completed")


def main():
    # logging.info("Starting Assistant")
    pygame.init()

    ass = Assistant()

    push_to_talk_key = pygame.K_SPACE
    quit_key = pygame.K_ESCAPE

    while True:
        ass.clock.tick(60)
        for event in pygame.event.get():
            if event.type == pygame.KEYDOWN:
                if event.key == push_to_talk_key:
                    # logging.info("Push-to-talk key pressed")
                    speech = ass.waveform_from_mic(push_to_talk_key)

                    transcription = ass.speech_to_text(waveform=speech)
                    result, image = cam.read() # read frame from webcam
                    cv2.imwrite("camview.jpg",image) #save image

                    # convert image to base64
                    _, buffer = cv2.imencode('.jpg', image)
                    image_base64 = base64.b64encode(buffer).decode('utf-8')

                    response = ass.ask_openai(transcription, image_base64)
                    ass.text_to_speech(response)

                    time.sleep(1)
                    ass.display_message(ass.config.messages.pressSpace)

                elif event.key == quit_key:
                    # logging.info("Quit key pressed")
                    ass.shutdown()


if __name__ == "__main__":
    main()
