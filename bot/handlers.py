"""
BOT: HANDLERS
Handles all user commands and interactive UI elements.
Manages the logic flow from user input to database storage.
"""
import os 
from aiogram import Router, types, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

# Services & States
from services.session_manager import SessionService
from services.repost_engine import RepostService
from .states import SessionUpload, CreatePair

# Logic for cleaning channel IDs
from core.repost.logic import sanitize_channel_id 

router = Router()

# Initialize services
session_service = SessionService()
repost_service = RepostService()

# --- START & HELP ---

@router.message(CommandStart())
async def cmd_start(message: types.Message):
    """Adds the user to the database and shows the main menu."""
    await repost_service.register_user(message.from_user.id, message.from_user.username)
    await message.answer(
        "👋 **Mister Reposter V2 Online**\n\n"
        "1. /uploadsession - Link your Telegram account\n"
        "2. /createpair - Start linking channels\n"
        "3. /viewpairs - View your active links\n\n"
        "**Management:**\n"
        "/stoppair <id> - Pause a specific pair\n"
        "/startpair <id> - Resume a paused pair\n"
        "/deletepair <id> - Remove a pair forever\n"
        "/deleteall - Wipe everything from the vault"
    )

# --- SESSION MANAGEMENT ---

@router.message(Command("uploadsession"))
async def cmd_upload_session(message: types.Message, state: FSMContext):
    """Starts the session upload process."""
    user_id = message.from_user.id
    
    # Check if a session already exists to avoid locking errors
    session_file = os.path.join("data", "sessions", f"{user_id}.session")
    
    if os.path.exists(session_file):
        await message.answer("⚠️ **Session Already Active**\n\nYou already have a session file. Use /deleteall if you need to reset.")
        return

    await state.set_state(SessionUpload.waiting_for_input)
    await message.answer("📤 Please send your **Session String** or upload the `.session` file.")

@router.message(SessionUpload.waiting_for_input)
async def process_session_input(message: types.Message, state: FSMContext):
    """Processes the session string or file provided by the user."""
    await message.answer("🧠 Processing session... please wait.")
    await session_service.handle_session_input(message)
    await state.clear()
    await message.answer("✅ Session processed successfully. You can now use /createpair.")

# --- CREATE REPOST PAIR (The Multi-Step Flow) ---

@router.message(Command("createpair"))
async def cmd_create_pair(message: types.Message, state: FSMContext):
    """Step 1: Ask for Source."""
    await state.set_state(CreatePair.waiting_for_source)
    await message.answer("🔗 **Step 1/4**: Send the **Source** channel (Username or Link).")

@router.message(CreatePair.waiting_for_source)
async def process_source(message: types.Message, state: FSMContext):
    """Step 2: Save Source and Ask for Destination."""
    if message.text and message.text.startswith("/"):
        return await message.answer("❌ Please provide a channel, not a command.")

    clean_source = sanitize_channel_id(message.text)
    await state.update_data(source_id=clean_source)
    
    await message.answer(f"✅ Source: `{clean_source}`\n\n🔗 **Step 2/4**: Send the **Destination** channel.")
    await state.set_state(CreatePair.waiting_for_destination)

@router.message(CreatePair.waiting_for_destination)
async def process_destination(message: types.Message, state: FSMContext):
    """Step 3: Save Destination and show Filter Buttons."""
    if message.text and message.text.startswith("/"):
        return await message.answer("❌ Please provide a channel, not a command.")

    clean_dest = sanitize_channel_id(message.text)
    await state.update_data(destination_id=clean_dest)
    
    # Create the button UI for filter selection
    builder = InlineKeyboardBuilder()
    builder.button(text="🧺 Remove All Links", callback_data="setfilt_1")
    builder.button(text="🔄 Replace with Mine", callback_data="setfilt_2")
    builder.button(text="💎 Keep Original", callback_data="setfilt_0")
    builder.adjust(1) # Stack buttons vertically
    
    await message.answer(
        "🔗 **Step 3/4**: Choose a filter for this pair:", 
        reply_markup=builder.as_markup()
    )
    await state.set_state(CreatePair.waiting_for_filter)

@router.callback_query(F.data.startswith("setfilt_"))
async def process_filter_choice(callback: types.CallbackQuery, state: FSMContext):
    """Handles the button click for filter selection."""
    filter_mode = int(callback.data.split("_")[1])
    await state.update_data(filter_type=filter_mode)
    
    if filter_mode == 2:
        # Step 4: If REPLACE is chosen, ask for the replacement link
        await callback.message.edit_text("🔗 **Step 4/4**: Send the link/text you want to use as a replacement.")
        await state.set_state(CreatePair.waiting_for_replacement)
    else:
        # Skip step 4 and finish if REMOVE or AS_IS is chosen
        await finalize_pair_creation(callback.message, state)
    
    await callback.answer()

@router.message(CreatePair.waiting_for_replacement)
async def process_replacement_link(message: types.Message, state: FSMContext):
    """Step 4: Save replacement text and finish."""
    await state.update_data(replacement_link=message.text)
    await finalize_pair_creation(message, state)

async def finalize_pair_creation(message: types.Message, state: FSMContext):
    """Helper function to save the full pair to the database."""
    data = await state.get_data()
    
    # Send all collected data to the service layer
    await repost_service.add_new_pair(
        user_id=message.chat.id, 
        source=data['source_id'], 
        destination=data['destination_id'],
        filter_type=data.get('filter_type', 1),
        replacement_link=data.get('replacement_link')
    )
    
    await message.answer(
        f"🎉 **Pair Linked Successfully!**\n\n"
        f"📤 **From**: `{data['source_id']}`\n"
        f"📥 **To**: `{data['destination_id']}`\n"
        f"⚙️ **Filter**: Mode {data.get('filter_type', 1)}"
    )
    await state.clear()

# --- MANAGEMENT & VIEWING ---

@router.message(Command("viewpairs"))
async def cmd_view_pairs(message: types.Message):
    """Lists all pairs for the user."""
    pairs = await repost_service.get_user_pairs(message.from_user.id)

    if not pairs:
        await message.answer("Your vault is empty. Use /createpair to start.")
        return

    text = "📋 **Your Repost Pairs:**\n\n"
    for p in pairs:
        status = "🟢 Active" if p.is_active else "🔴 Stopped"
        text += f"**ID: {p.id}** | {status}\n  From: `{p.source_id}`\n  To: `{p.destination_id}`\n\n"
    
    await message.answer(text)

@router.message(Command("stoppair"))
async def cmd_stop_pair(message: types.Message):
    """Pauses a repost pair."""
    args = message.text.split()
    if len(args) < 2 or not args[1].isdigit():
        return await message.answer("❌ Usage: `/stoppair <id>`")

    pair_id = int(args[1])
    success = await repost_service.deactivate_pair(message.from_user.id, pair_id)
    
    if success:
        await message.answer(f"🔴 Pair #{pair_id} stopped.")
    else:
        await message.answer(f"⚠️ Pair #{pair_id} not found.")

@router.message(Command("startpair"))
async def cmd_start_pair(message: types.Message):
    """Resumes a paused pair."""
    args = message.text.split()
    if len(args) < 2 or not args[1].isdigit():
        return await message.answer("❌ Usage: `/startpair <id>`")

    pair_id = int(args[1])
    success = await repost_service.activate_pair(message.from_user.id, pair_id)
    
    if success:
        await message.answer(f"🟢 Pair #{pair_id} is now active.")
    else:
        await message.answer(f"⚠️ Pair #{pair_id} not found.")

@router.message(Command("deletepair"))
async def cmd_delete_pair(message: types.Message):
    """Deletes a single pair."""
    args = message.text.split()
    if len(args) < 2 or not args[1].isdigit():
        return await message.answer("❌ Usage: `/deletepair <id>`")

    pair_id = int(args[1])
    success = await repost_service.delete_single_pair(message.from_user.id, pair_id)
    
    if success:
        await message.answer(f"🗑️ Pair #{pair_id} deleted.")
    else:
        await message.answer(f"⚠️ Pair #{pair_id} not found.")

@router.message(Command("deleteall"))
async def cmd_delete_all(message: types.Message):
    """Wipes all pairs for the user."""
    count = await repost_service.delete_all_user_pairs(message.from_user.id)
    await message.answer(f"🗑️ Vault cleared! Removed {count} pairs.")


    #LovefromMister 