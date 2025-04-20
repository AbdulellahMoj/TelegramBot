import telebot
import datetime
import random
from dotenv import load_dotenv
import os
from telebot import types

# Load the environment variables
load_dotenv()
TOKEN = os.getenv("Telegram_KEY")
bot = telebot.TeleBot("7638042408:AAFyjjRDWH_4Nwi7N3NgGpanv2QSCSjdTz8")

# To keep track of user inputs
user_inputs = {}

# Start command
@bot.message_handler(commands=['start'])
def send_welcome(message):
    user_name = message.from_user.first_name
    bot.reply_to(message, f"Hello {user_name}! I'm your new bot assistant. How can I help you today?")

@bot.message_handler(commands=['help'])
def send_help(message):
    help_text = (
        "🆘 Available commands:\n"
        "/start - Welcome message\n"
        "/time - Current time\n"
        "/survey - Give us your feedback\n"
        "/calc - Open calculator\n"
        "/help - Show this help message"
    )
    bot.reply_to(message, help_text)


# Time command
@bot.message_handler(commands=['time'])
def send_time(message):
    now = datetime.datetime.now().strftime(" %H:%M")
    bot.reply_to(message, f"⏰ الوقت الحالي: {now}")

# Survey with inline buttons
@bot.message_handler(commands=['survey'])
def send_survey(message):
    markup = types.InlineKeyboardMarkup(row_width=2)
    yes_btn = types.InlineKeyboardButton('Yes', callback_data='yes')
    no_btn = types.InlineKeyboardButton('No', callback_data='no')
    markup.add(yes_btn, no_btn)
    bot.send_message(message.chat.id, "Are you enjoying this workshop?", reply_markup=markup)


# Handle survey button responses
@bot.callback_query_handler(func=lambda call: call.data in ['yes', 'no'])
def handle_survey_callback(call):
    if call.data == 'yes':
        bot.answer_callback_query(call.id, "Great to hear that!")
        bot.send_message(call.message.chat.id, "Thank you for your positive feedback!")
    elif call.data == 'no':
        bot.answer_callback_query(call.id, "We'll try to improve!")
        bot.send_message(call.message.chat.id, "Thank you for your honest feedback!")

# Greetings
greetings = {
    "hi": ["Hello!", "Hey there!", "Hi! How are you?"],
    "hello": ["Welcome!", "Hi friend!", "Hello, nice to see you!"],
    "hey": ["Hey!", "What's up?", "Hello there!"]
}

@bot.message_handler(func=lambda message: message.text and message.text.lower() in greetings.keys())
def send_greeting(message):
    user_name = message.from_user.first_name
    response = random.choice(greetings[message.text.lower()])
    bot.reply_to(message, f"{user_name}, {response}")


# Echo fallback - must be last handler
@bot.message_handler(func=lambda message: True)
def echo_message(message):
    user_name = message.from_user.first_name
    bot.reply_to(message, f"{user_name}, you said: {message.text}")


# Photo reply
@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    bot.reply_to(message, "Nice picture!")
    


# Create calculator markup
def create_calc_markup():
    markup = types.InlineKeyboardMarkup(row_width=4)
    buttons = [
        '1', '2', '3', '+',
        '4', '5', '6', '-',
        '7', '8', '9', '*',
        'C', '0', '=', '/'
    ]
    
    # Create buttons in rows of 4
    rows = []
    for i in range(0, len(buttons), 4):
        row = []
        for btn in buttons[i:i+4]:
            row.append(types.InlineKeyboardButton(text=btn, callback_data=f'calc_{btn}'))
        rows.append(row)
    
    # Add rows to markup
    for row in rows:
        markup.row(*row)
    
    return markup

# Real Calculator
@bot.message_handler(commands=['calc'])
def calculator(message):
    user_inputs[message.chat.id] = ""
    markup = create_calc_markup()
    bot.send_message(message.chat.id, "🧮 Calculator: 0", reply_markup=markup)


# Handle calculator button presses
@bot.callback_query_handler(func=lambda call: call.data.startswith('calc_'))
def handle_calc_callback(call):
    chat_id = call.message.chat.id
    message_id = call.message.message_id
    data = call.data.replace('calc_', '')
    
    # Initialize user input if needed
    if chat_id not in user_inputs:
        user_inputs[chat_id] = ""
    
    # Handle different button presses
    if data == 'C':
        # Clear calculator
        user_inputs[chat_id] = ""
        bot.edit_message_text("🧮 Calculator: 0", chat_id, message_id, reply_markup=create_calc_markup())
    
    elif data == '=':
        try:
            # Calculate result
            expression = user_inputs[chat_id]
            # Basic validation to avoid security issues with eval()
            if any(c not in "0123456789+-*/. " for c in expression):
                raise ValueError("Invalid characters in expression")
                
            result = eval(expression)
            # Format result to avoid long decimals
            if isinstance(result, float) and result.is_integer():
                result = int(result)
                
            # Show result and keep calculator open
            bot.edit_message_text(f"🧮 Calculator: {result}", chat_id, message_id, reply_markup=create_calc_markup())
            # Store result as new input for continued calculations
            user_inputs[chat_id] = str(result)
        except Exception as e:
            # Handle calculation errors
            bot.edit_message_text(f"❌ Error: Invalid expression", chat_id, message_id, reply_markup=create_calc_markup())
            user_inputs[chat_id] = ""
    
    else:
        # Add button press to current input
        user_inputs[chat_id] += data
        bot.edit_message_text(f"🧮 Calculator: {user_inputs[chat_id]}", chat_id, message_id, reply_markup=create_calc_markup())
    
    # Acknowledge the callback
    bot.answer_callback_query(call.id)

# Bot start
if __name__ == "__main__":
    print("Bot is running...")
    bot.infinity_polling()