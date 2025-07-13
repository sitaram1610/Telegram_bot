import logging
import json
import os
import random
from datetime import datetime

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    ContextTypes,
    filters,
)

# --- Configuration ---
BOT_TOKEN = "5935271318:AAFI_uE_67Je_kw-KTh98tIlbmgRSdPCuRw"
ADMIN_ID = 5935271318
USERS_FILE = 'users.json'
ARTISTS_FILE = 'artists.json'
ORDERS_FILE = 'orders.json'

# --- Logging Setup ---
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- Conversation States ---
ARTIST_PORTFOLIO, ORDER_PHOTO, RATE_ARTIST_ID, RATE_STARS = range(4)

# --- Data Persistence ---
def load_data(filename: str) -> list | dict:
    """Load data from a JSON file, creating it if it doesn't exist."""
    if not os.path.exists(filename):
        with open(filename, 'w') as f:
            json.dump([], f)
        return []
    try:
        with open(filename, 'r') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        logger.error(f"Error reading or creating {filename}. Returning empty list.")
        return []

def save_data(filename: str, data: list | dict):
    """Save data to a JSON file with pretty printing."""
    with open(filename, 'w') as f:
        json.dump(data, f, indent=4)

# --- Helper Functions ---
def get_username(user) -> str:
    """Get user's username or fallback to first_name."""
    return user.username if user.username else user.first_name

def calculate_average_rating(ratings: list) -> float:
    """Calculate the average rating from a list of rating values."""
    if not ratings:
        return 0.0
    return sum(ratings) / len(ratings)

# --- Command Handlers ---
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for the /start command."""
    await update.message.reply_text(
        "🎨 Welcome to the Sketch Order Bot! 🎨\n\n"
        "I can help you commission sketches from talented artists.\n\n"
        "🔹 To order a sketch, use /register\n"
        "🔹 To offer your art services, use /register_artist\n\n"
        "Use /help to see a full list of commands."
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handler for the /help command."""
    help_text = (
        "Here are the available commands:\n\n"
        "<b>For Everyone:</b>\n"
        "/start - Welcome message\n"
        "/login - Check your registration status\n"
        "/search_artist - List all approved artists\n"
        "/searchid &lt;artist_id&gt; - Get a specific artist's profile\n\n"
        "<b>For Users:</b>\n"
        "/register - Register as a user\n"
        "/order - Start a new sketch order\n"
        "/track - Check the status of your orders\n"
        "/rate - Rate an artist after an order\n\n"
        "<b>For Artists:</b>\n"
        "/register_artist - Register as an artist\n\n"
        "<b>Admin Only:</b>\n"
        "/approve_artist &lt;artist_id&gt; - Approve an artist"
    )
    await update.message.reply_text(help_text, parse_mode='HTML')


async def register_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Registers a new user."""
    users = load_data(USERS_FILE)
    user = update.message.from_user
    if any(u['id'] == user.id for u in users):
        await update.message.reply_text("You are already registered as a user.")
        return

    new_user = {"id": user.id, "username": get_username(user)}
    users.append(new_user)
    save_data(USERS_FILE, users)
    await update.message.reply_text("✅ Success! You are now registered and can /order a sketch.")

async def login_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Checks if a user is registered as a user or artist."""
    user_id = update.message.from_user.id
    users = load_data(USERS_FILE)
    artists = load_data(ARTISTS_FILE)

    is_user = any(u['id'] == user_id for u in users)
    artist_info = next((a for a in artists if a['id'] == user_id), None)

    if artist_info:
        status = "Approved" if artist_info.get("approved") else "Pending Approval"
        await update.message.reply_text(f"Logged in as: <b>Artist</b>\nStatus: <b>{status}</b>", parse_mode='HTML')
    elif is_user:
        await update.message.reply_text("Logged in as: <b>User</b>", parse_mode='HTML')
    else:
        await update.message.reply_text("You are not registered. Use /register or /register_artist.")

async def track_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Tracks all orders for the user."""
    user_id = update.message.from_user.id
    orders = load_data(ORDERS_FILE)
    artists = load_data(ARTISTS_FILE)
    user_orders = [o for o in orders if o['user_id'] == user_id]

    if not user_orders:
        await update.message.reply_text("You have no orders. Use /order to create one.")
        return

    response = "<b>Your Order History:</b>\n\n"
    for order in user_orders:
        artist_info = next((a for a in artists if a['id'] == order['artist_id']), None)
        artist_name = f"@{artist_info['username']}" if artist_info else "Unknown"
        response += (
            f"📦 <b>Order ID:</b> <code>{order['id']}</code>\n"
            f"   - <b>Artist:</b> {artist_name}\n"
            f"   - <b>Status:</b> {order['status']}\n"
            f"   - <b>Date:</b> {order['order_date']}\n\n"
        )
    await update.message.reply_text(response, parse_mode='HTML')

async def search_artist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lists all approved artists."""
    artists = load_data(ARTISTS_FILE)
    approved_artists = [a for a in artists if a.get('approved')]

    if not approved_artists:
        await update.message.reply_text("There are no approved artists available at the moment.")
        return

    response = "<b>🎨 Approved Artists 🎨</b>\n\n"
    for artist in approved_artists:
        avg_rating = calculate_average_rating(artist.get('ratings', []))
        rating_str = f"{avg_rating:.1f} ★ ({len(artist.get('ratings', []))})"
        response += (
            f"<b>ID:</b> <code>{artist['id']}</code>\n"
            f"<b>Username:</b> @{artist['username']}\n"
            f"<b>Rating:</b> {rating_str}\n"
            f"<b>Price:</b> {artist['price']}\n"
            f"<b>Portfolio:</b> {artist['portfolio_link']}\n"
            "--------------------\n"
        )
    await update.message.reply_text(response, parse_mode='HTML', disable_web_page_preview=True)

async def searchid_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Searches for a specific artist by their ID."""
    if not context.args:
        await update.message.reply_text("Please provide an Artist ID. Usage: /searchid <artist_id>")
        return

    try:
        artist_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid ID. Please provide a numeric ID.")
        return

    artists = load_data(ARTISTS_FILE)
    artist = next((a for a in artists if a['id'] == artist_id), None)

    if not artist:
        await update.message.reply_text("No artist found with that ID.")
        return

    avg_rating = calculate_average_rating(artist.get('ratings', []))
    rating_str = f"{avg_rating:.1f} ★ ({len(artist.get('ratings', []))} ratings)"
    status = "Approved" if artist.get("approved") else "Pending Approval"
    response = (
        f"<b>🧑‍🎨 Artist Profile 🧑‍🎨</b>\n\n"
        f"<b>ID:</b> <code>{artist['id']}</code>\n"
        f"<b>Username:</b> @{artist['username']}\n"
        f"<b>Status:</b> {status}\n"
        f"<b>Rating:</b> {rating_str}\n"
        f"<b>Price:</b> {artist['price']}\n"
        f"<b>Portfolio:</b> {artist['portfolio_link']}"
    )
    await update.message.reply_text(response, parse_mode='HTML', disable_web_page_preview=True)

async def approve_artist_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin command to approve an artist."""
    if update.message.from_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ This is an admin-only command.")
        return

    if not context.args:
        await update.message.reply_text("Usage: /approve_artist <artist_id>")
        return

    try:
        artist_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid ID. Please provide a numeric ID.")
        return

    artists = load_data(ARTISTS_FILE)
    artist_to_approve = next((a for a in artists if a['id'] == artist_id), None)

    if not artist_to_approve:
        await update.message.reply_text(f"Artist with ID {artist_id} not found.")
        return

    artist_to_approve['approved'] = True
    save_data(ARTISTS_FILE, artists)
    await update.message.reply_text(f"✅ Artist @{artist_to_approve['username']} (ID: {artist_id}) has been approved!")

    try:
        await context.bot.send_message(
            chat_id=artist_id,
            text="🎉 Congratulations! Your artist application has been approved. You will now be assigned new orders."
        )
    except Exception as e:
        logger.warning(f"Could not notify approved artist {artist_id}: {e}")

# --- Conversation Handlers ---

# 1. Artist Registration
async def register_artist_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the artist registration conversation."""
    artists = load_data(ARTISTS_FILE)
    if any(a['id'] == update.message.from_user.id for a in artists):
        await update.message.reply_text("You have already registered as an artist.")
        return ConversationHandler.END

    await update.message.reply_text("Okay, let's get you registered as an artist.\n\nPlease send me a link to your portfolio or a text describing your work.")
    return ARTIST_PORTFOLIO

async def artist_portfolio_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Saves portfolio and completes artist registration."""
    user = update.message.from_user
    artists = load_data(ARTISTS_FILE)
    
    # Generate a random price for the artist
    random_price = f"${random.randint(15, 50)} USD"

    new_artist = {
        "id": user.id,
        "username": get_username(user),
        "portfolio_link": update.message.text,
        "price": random_price,
        "approved": False,
        "ratings": []
    }
    artists.append(new_artist)
    save_data(ARTISTS_FILE, artists)

    await update.message.reply_text(
        "✅ Your artist profile has been created and is pending approval.\n"
        "An admin will review it shortly. You will be notified upon approval."
    )
    return ConversationHandler.END

# 2. Sketch Ordering
async def order_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the sketch ordering process."""
    artists = load_data(ARTISTS_FILE)
    if not any(a.get('approved') for a in artists):
        await update.message.reply_text("Sorry, there are no approved artists available to take orders right now. Please check back later.")
        return ConversationHandler.END
        
    await update.message.reply_text("Please upload a single photo you would like sketched.")
    return ORDER_PHOTO

async def order_photo_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receives a photo, assigns an artist, and creates an order."""
    artists = load_data(ARTISTS_FILE)
    approved_artists = [a for a in artists if a.get('approved')]
    
    if not approved_artists:
        await update.message.reply_text("An unexpected error occurred: no artists are available.")
        return ConversationHandler.END

    assigned_artist = random.choice(approved_artists)
    photo = update.message.photo[-1]  # Highest resolution
    user = update.message.from_user
    
    orders = load_data(ORDERS_FILE)
    new_order = {
        "id": f"{int(datetime.now().timestamp())}",
        "user_id": user.id,
        "artist_id": assigned_artist['id'],
        "photo_file_id": photo.file_id,
        "status": "Pending Artist Acceptance",
        "order_date": datetime.now().strftime("%Y-%m-%d")
    }
    orders.append(new_order)
    save_data(ORDERS_FILE, orders)

    await update.message.reply_text(
        f"✅ Order placed successfully!\n\n"
        f"Your order (ID: <code>{new_order['id']}</code>) has been assigned to artist @{assigned_artist['username']}.\n"
        f"Use /track to monitor its status."
        , parse_mode='HTML')
    
    try:
        await context.bot.send_message(
            chat_id=assigned_artist['id'],
            text=f"📣 You have a new sketch order from @{get_username(user)}!"
        )
        await context.bot.send_photo(chat_id=assigned_artist['id'], photo=photo.file_id,
                                     caption=f"New order from user {user.id}. Please confirm or decline.")
    except Exception as e:
        logger.error(f"Failed to notify artist {assigned_artist['id']}: {e}")

    return ConversationHandler.END

# 3. Artist Rating
async def rate_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Starts the rating process by asking for an order or artist ID."""
    await update.message.reply_text("To rate an artist, please send their Artist ID.")
    return RATE_ARTIST_ID

async def rate_artist_id_received(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Receives artist ID and shows rating buttons."""
    try:
        artist_id = int(update.message.text)
    except ValueError:
        await update.message.reply_text("That's not a valid ID. Please send a numeric Artist ID.")
        return RATE_ARTIST_ID

    artists = load_data(ARTISTS_FILE)
    if not any(a['id'] == artist_id and a.get('approved') for a in artists):
        await update.message.reply_text("No approved artist found with this ID. Please check the ID and try again.")
        return ConversationHandler.END

    context.user_data['artist_to_rate'] = artist_id
    
    keyboard = [[
        InlineKeyboardButton("⭐️", callback_data='rate_1'),
        InlineKeyboardButton("⭐️⭐️", callback_data='rate_2'),
        InlineKeyboardButton("⭐️⭐️⭐️", callback_data='rate_3'),
        InlineKeyboardButton("⭐️⭐️⭐️⭐️", callback_data='rate_4'),
        InlineKeyboardButton("⭐️⭐️⭐️⭐️⭐️", callback_data='rate_5'),
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('How would you rate this artist?', reply_markup=reply_markup)
    return RATE_STARS

async def rate_stars_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Processes the inline button rating."""
    query = update.callback_query
    await query.answer()

    rating = int(query.data.split('_')[1])
    artist_id = context.user_data.get('artist_to_rate')

    if not artist_id:
        await query.edit_message_text("Session expired. Please start again with /rate.")
        return ConversationHandler.END

    artists = load_data(ARTISTS_FILE)
    artist_found = False
    for artist in artists:
        if artist['id'] == artist_id:
            artist.setdefault('ratings', []).append(rating)
            artist_found = True
            break
            
    if artist_found:
        save_data(ARTISTS_FILE, artists)
        await query.edit_message_text(f"Thank you! You gave a {rating}-star rating.")
    else:
        await query.edit_message_text("Error: Could not find the artist to rate.")

    context.user_data.clear()
    return ConversationHandler.END


async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Cancels and ends the current conversation."""
    await update.message.reply_text("Operation cancelled.")
    context.user_data.clear()
    return ConversationHandler.END
    
async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles unknown commands."""
    await update.message.reply_text("Sorry, I didn't understand that command. Try /help.")


def main():
    """Main function to set up and run the bot."""
    logger.info("Initializing bot...")

    # --- Build Application ---
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # --- Conversation Handlers Setup ---
    artist_reg_handler = ConversationHandler(
        entry_points=[CommandHandler('register_artist', register_artist_start)],
        states={ARTIST_PORTFOLIO: [MessageHandler(filters.TEXT & ~filters.COMMAND, artist_portfolio_received)]},
        fallbacks=[CommandHandler('cancel', cancel_conversation)],
    )

    order_handler = ConversationHandler(
        entry_points=[CommandHandler('order', order_start)],
        states={ORDER_PHOTO: [MessageHandler(filters.PHOTO, order_photo_received)]},
        fallbacks=[CommandHandler('cancel', cancel_conversation)],
    )
    
    rate_handler = ConversationHandler(
        entry_points=[CommandHandler('rate', rate_start)],
        states={
            RATE_ARTIST_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, rate_artist_id_received)],
            RATE_STARS: [CallbackQueryHandler(pattern='^rate_', callback=rate_stars_callback)]
        },
        fallbacks=[CommandHandler('cancel', cancel_conversation)],
    )

    # --- Add all handlers ---
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("register", register_command))
    app.add_handler(CommandHandler("login", login_command))
    app.add_handler(CommandHandler("track", track_command))
    app.add_handler(CommandHandler("search_artist", search_artist_command))
    app.add_handler(CommandHandler("searchid", searchid_command))
    app.add_handler(CommandHandler("approve_artist", approve_artist_command))

    app.add_handler(artist_reg_handler)
    app.add_handler(order_handler)
    app.add_handler(rate_handler)
    
    # Fallback for unknown commands
    app.add_handler(MessageHandler(filters.COMMAND, unknown_command))

    # --- Start Polling ---
    logger.info("Bot started successfully. Polling for updates...")
    app.run_polling()
    logger.info("Bot stopped.")

if __name__ == '__main__':
    main()
