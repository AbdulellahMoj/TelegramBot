import os
import random
import datetime
from dotenv import load_dotenv
import telebot
from telebot import types
from Predefined import greetings

import logging
import base64
import time
import requests
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from io import BytesIO
from PIL import Image
import openai

# Load environment variables
load_dotenv('.env')
# Configure logging
logging.basicConfig(level=logging.INFO)

# Get the Telegram Bot API Key
API_TOKEN: str = os.getenv("Telegram_KEY")

# Get the Telegram Bot API Key
IMGBB_API_KEY = os.getenv("Imgbb_KEY")

# Initialize the OpenAI client
client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Initialize the bot
bot = telebot.TeleBot(API_TOKEN)
# Predefined replies for different messages
greetings = greetings  # Import greetings from Predefined.py

from MOVIE_RECOMMENDER import *


def get_movie_recommendation(description):
    """Get a movie recommendation based on user description"""
    return recommender.get_recommendation_by_description(description)

def get_movie_recommendation_from_openai(description_or_image_url):
    """Get a movie recommendation based on user description or image URL"""
    prompt = f"Suggest a movie based on the following description or image content: {description_or_image_url}"
    
    try:
        response = client.Completion.create(
            model="gpt-4",
            prompt=prompt,
            max_tokens=200,
            temperature=0.7
        )
        movie_recommendation = response.choices[0].text.strip()
        return movie_recommendation
    except Exception as e:
        logging.error(f"Error with OpenAI API: {str(e)}")
        return None

# Image analysis Methods
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
                            {"type": "text", "text": "What’s in this image? the vibe? and the mood? (in an artistic way) make it short"},
                            {
                                "type": "text",
                                "text": "Please provide a detailed description of the image, including any objects, people, or scenes present."
                            },
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

# Movie Recommender 2.0
def get_movie_from_description_or_image(message):
    """Get a movie recommendation based on either a description or an image."""
    if message.content_type == 'text':  # If the user sent a description as text
        description = message.text
        movie = get_movie_recommendation_from_openai(description)
        send_movie_recommendation(message, movie)
    
    elif message.content_type == 'photo':  # If the user sent an image
        handle_image(message)

def handle_image(message):
    """Process the image sent by the user and extract information to recommend a movie."""
    try:
        # Download the image
        file_info = bot.get_file(message.photo[-1].file_id)
        file_data = bot.download_file(file_info.file_path)
        
        # Upload the image to ImgBB and get the URL
        image_url = upload_image_to_imgbb(file_data)
        
        if image_url:
            # Analyze the image using OpenAI's Vision API
            analysis = analyse_image_with_retry(image_url)
            if analysis:
                # Use the analysis result as the description for movie recommendation
                movie = get_movie_recommendation_from_openai(analysis)
                send_movie_recommendation(message, movie)
            else:
                bot.reply_to(message, "حدث خطأ أثناء تحليل الصورة.")
        else:
            bot.reply_to(message, "حدث خطأ أثناء رفع الصورة.")
    except Exception as e:
        logging.error(f"Error handling image: {str(e)}")
        bot.reply_to(message, "حدث خطأ أثناء معالجة الصورة.")

def send_movie_recommendation(message, movie):
    """Send the movie recommendation to the user."""
    if movie:
        user_name = message.from_user.first_name
        response = f"*🎬 توصية فيلم لك يا {user_name}:*\n\n"
        response += f"*العنوان:* {movie['title']}\n"
        response += f"*التصنيف:* {movie['genres']}\n"
        response += f"*التقييم:* ⭐ {movie['rating']}/10\n\n"
        response += f"*نبذة:*\n{movie['overview']}"
        
        bot.send_message(
            message.chat.id,
            response,
            parse_mode='Markdown'
        )
        
        if movie['poster_url']:
            bot.send_photo(
                message.chat.id,
                movie['poster_url'],
                caption=f"ملصق فيلم {movie['title']}"
            )
        
        # Buttons for more actions
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("بحث آخر 🔍", callback_data="new_movie_search"),
            types.InlineKeyboardButton("IMDB 🌐", url=f"https://www.imdb.com/find?q={movie['title']}")
        )
        
        bot.send_message(
            message.chat.id, 
            "هل ترغب في البحث عن فيلم آخر؟",
            reply_markup=markup
        )
    else:
        bot.reply_to(message, "عذراً، لم أتمكن من إيجاد فيلم يناسب وصفك.")





# ============ TELEGRAM BOT HANDLERS ==================================================================================================
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
            

# Movie recommendation 2.0 command handler
@bot.message_handler(commands=['movie2.0'])
def handle_movie_command(message):
    """Handle the /movie command."""
    bot.reply_to(message, "أخبرني عن نوع الفيلم الذي ترغب في مشاهدته أو أرسل لي صورة.")
    # Register the next step handler for both text and image
    bot.register_next_step_handler(message, get_movie_from_description_or_image)



# Movie recommendation command handler
@bot.message_handler(commands=['movie'])
def handle_movie_command(message):
    """Handle the /movie command"""
    bot.reply_to(message, "أخبرني عن نوع الفيلم الذي ترغب في مشاهدته، وسأقترح عليك فيلماً يناسبك.")
    # Register the next step handler
    bot.register_next_step_handler(message, process_movie_description)

def process_movie_description(message):
    """Process the movie description and provide a recommendation"""
    user_description = message.text
    user_name = message.from_user.first_name
    
    # Send typing indicator
    bot.send_chat_action(message.chat.id, 'typing')
    
    # Get movie recommendation
    try:
        movie = get_movie_recommendation(user_description)
        
        if movie:
            # Format the response message
            response = f"*🎬 توصية فيلم لك يا {user_name}:*\n\n"
            response += f"*العنوان:* {movie['title']}\n"
            response += f"*التصنيف:* {movie['genres']}\n"
            response += f"*التقييم:* ⭐ {movie['rating']}/10\n\n"
            response += f"*نبذة:*\n{movie['overview']}"
            
            # Send the text response with markdown
            bot.send_message(
                message.chat.id,
                response,
                parse_mode='Markdown'
            )
            
            # Send the movie poster if available
            if movie['poster_url']:
                bot.send_photo(
                    message.chat.id,
                    movie['poster_url'],
                    caption=f"ملصق فيلم {movie['title']}"
                )
                
            # Add buttons for actions
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton("بحث آخر 🔍", callback_data="new_movie_search"),
                types.InlineKeyboardButton("IMDB 🌐", url=f"https://www.imdb.com/find?q={movie['title']}")
            )
            
            bot.send_message(
                message.chat.id, 
                "هل ترغب في البحث عن فيلم آخر؟",
                reply_markup=markup
            )
        else:
            bot.reply_to(
                message,
                f"عذراً {user_name}، لم أتمكن من إيجاد فيلم يناسب وصفك. يرجى المحاولة بوصف آخر."
            )
    except Exception as e:
        logging.error(f"Error processing movie recommendation: {str(e)}")
        bot.reply_to(message, "حدث خطأ أثناء البحث عن توصية فيلم. يرجى المحاولة مرة أخرى لاحقاً.")

# Handle callback queries
@bot.callback_query_handler(func=lambda call: call.data == "new_movie_search")
def new_movie_search_callback(call):
    """Handle new movie search button click"""
    bot.answer_callback_query(call.id)
    bot.send_message(call.message.chat.id, "أخبرني عن نوع الفيلم الذي ترغب في مشاهدته.")
    bot.register_next_step_handler(call.message, process_movie_description)

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
if __name__ == "__main__":
    # Log that the bot is starting
    logging.info("Bot starting...")
    bot.infinity_polling()
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
    
