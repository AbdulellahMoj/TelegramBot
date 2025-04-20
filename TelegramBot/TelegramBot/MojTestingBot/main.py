import os
import random
import datetime
from dotenv import load_dotenv
import telebot
from Predefined import greetings

import logging
import base64
import time
import requests
from io import BytesIO
from PIL import Image
import openai
# Load environment variables
load_dotenv('.env')
# Configure logging
logging.basicConfig(level=logging.INFO)

# Get the Telegram Bot API Key
API_TOKEN: str = os.getenv("API_KEY")
IMGBB_API_KEY = os.getenv("Imgbb_KEY")
# Initialize the OpenAI client
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Initialize the bot
bot = telebot.TeleBot(API_TOKEN)
# Predefined replies for different messages
greetings = greetings  # Import greetings from Predefined.py

def upload_image_to_imgbb(file_data):
    try:
        # make sure the image is in JPEG format
        image = Image.open(BytesIO(file_data))
        output = BytesIO()
        image.convert("RGB").save(output, format="JPEG")
        output.seek(0)
        
        # covert the image to base64 | why? because imgbb api requires base64 image
        base64_image = base64.b64encode(output.read()).decode('utf-8')
        
        # Prepare the request to upload the image to imgbb
        url = "https://api.imgbb.com/1/upload"
        payload = {
            'key': IMGBB_API_KEY,
            'image': base64_image,
        }
        response = requests.post(url, data=payload)
        logging.info(f"ImgBB response status code: {response.status_code}")
        logging.info(f"ImgBB response text: {response.text}")
        
        if response.status_code == 200:
            data = response.json()
            logging.info(f"Image uploaded successfully to ImgBB: {data['data']['url']}")
            return data['data']['url']
        else:
            logging.error(f"Failed to upload image to ImgBB: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        logging.error(f"Exception during image upload to ImgBB: {str(e)}")
        return None            

# Function to analyze the image using OpenAI's Vision API with retry
def analyse_image_with_retry(image_url, retries=3,delay = 2):
    for attempt in range(retries):
        try:
            # log the image url
            logging.info(f"Sending image to OpenAI Vision API: {image_url}")
            
            response = client.chat.completions.create(
                model="gpt-4-turbo",
                messages=[
                    { "role": "user",
                        "content": [
                            {"type": "text", "text": "What’s in this image?(in saudi arabian dialect)"},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": image_url
                                }
                            }
                        ]
                    }
                ],
                max_tokens=1000,
            )
            logging.info(f"OpenAI Vision API response: {response}")
            
            return response.choices[0].message.content.strip()
        except Exception as e:
             logging.error(f"Error analyzing image with OpenAI Vision on attempt {attempt + 1}: {str(e)}")
             if attempt < retries - 1:
                    time.sleep(delay)
             else:
                 logging.error("Max retries reached. Failed to analyze image.")
                 return None



# Handle the received photos
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    try:
        # Download the image file from Telegram
        file_info = bot.get_file(message.photo[-1].file_id)
        file_data = bot.download_file(file_info.file_path)

        # Convert WebP to JPEG if needed
        try:
            image = Image.open(BytesIO(file_data))
            if image.format == "WEBP":
                output = BytesIO()
                image.convert("RGB").save(output, format="JPEG")
                file_data = output.getvalue()  # Update the file_data with JPEG content
                logging.info("Converted WebP image to JPEG format")
        except Exception as e:
            logging.error(f"Error converting image to JPEG: {str(e)}")
            bot.reply_to(message, "حدث خطأ أثناء معالجة الصورة.")
            return
        
        # Upload the image to ImgBB
        image_url = upload_image_to_imgbb(file_data)
        if image_url:
            # Analyze the image using OpenAI's Vision API
            analysis = analyse_image_with_retry(image_url)
            if analysis:
                bot.reply_to(message, f"تحليل الصورة: {analysis}")
            else:
                bot.reply_to(message, "حدث خطأ أثناء تحليل الصورة.")
        else:
            bot.reply_to(message, "حدث خطأ أثناء رفع الصورة.")
    except Exception as e:
        logging.error(f"Error handling photo: {str(e)}")
        bot.reply_to(message, "حدث خطأ أثناء معالجة الصورة.")
            







# Handle predefined greeting messages
@bot.message_handler(func=lambda message: message.text in greetings.keys())
def send_greeting(message):
    user_name = message.from_user.first_name  # Get the user's first name
    response = random.choice(greetings[message.text])  # Pick a random reply
    bot.reply_to(message, f"{user_name}, {response}")  # Personalize response

# Handle the `/time` command to send the current time
@bot.message_handler(commands=['time'])
def send_time(message):
    now = datetime.datetime.now().strftime(" %H:%M")
    bot.reply_to(message, f"⏰ الوقت الحالي: {now}")

# Handle the `/test` command to send a welcome message
@bot.message_handler(commands=['test'])
def send_test(message):
    user_name = message.from_user.first_name
    bot.reply_to(message, f"مرحبا {user_name}، كيف حالك؟")

# Handle all other messages by echoing them back
@bot.message_handler(func=lambda message: True)
def echo_message(message):
    user_name = message.from_user.first_name  # Get user's first name
    bot.reply_to(message, f"{user_name}, أنت قلت: {message.text}")  # Echo message

# Keep the bot running
bot.infinity_polling()
