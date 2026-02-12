"""
BOT: HANDLERS
The 'Mouth & Ears'. (Anatomy: Mouth)
Translates user events into Service calls. (Rule 11)
Fighting ghost errors while Gabzy plays in the background.
"""
import os 
from aiogram import Router, types
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext

# Services & States
from services.session_manager import SessionService
from services.repost_engine import RepostService
from .states import SessionUpload, CreatePair

# The Brain's Sanitizer
from core.repost.logic import sanitize_channel_id 

router = Router()

# Neural Connectors
session_service = SessionService()
repost_service = RepostService()

# --- BASIC COMMANDS ---

@router.message(CommandStart())
async def cmd_start(message: types.Message):
    """Initializes the User record via the Service."""
    # <REACTION: If the user is new, we need to get them into the Vault immediately.>
    await repost_service.register_user(message.from_user.id, message.from_user.username)
    await message.answer(
        "👋 **Mister Reposter V2 Online**\n\n"
        "1. Use /uploadsession to link your Telegram account.\n"
        "2. Use /createpair to link your channels.\n"
        "3. Use /viewpairs to check status."
    )

# --- SESSION UPLOAD FLOW ---

@router.message(Command("uploadsession"))
async def cmd_upload_session(message: types.Message, state: FSMContext):
    # <THINK: Let's check the Librarian before we waste time on a new upload.>
    user_id = message.from_user.id
    
    # We check both the DB and the physical folder
    current_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(current_dir)
    session_file = os.path.join(project_root, "data", "sessions", f"{user_id}.session")
    
    # If the soul is already in the Vault
    if os.path.exists(session_file):
        await message.answer("⚠️ **Session Already Active**\n\nYou have already uploaded a session. To replace it, use `/deleteall` first (Note: this wipes your pairs too) or contact support.")
        return

    await state.set_state(SessionUpload.waiting_for_input)
    await message.answer("📤 Please send your **Session String** or upload the `.session` file.")



@router.message(SessionUpload.waiting_for_input)
async def process_session_input(message: types.Message, state: FSMContext):
    # <REACTION: Brain is fried. Processing session... hope the Librarian actually writes this down.>
    await message.answer("🧠 Processing session... please wait.")
    await session_service.handle_session_input(message)
    await state.clear()
    await message.answer("✅ Session processed. You can now use /createpair.")

# --- CREATE PAIR FLOW (Synchronized with Middleware) ---

@router.message(Command("createpair"))
async def cmd_create_pair(message: types.Message, state: FSMContext):
    # <REACTION: Oga, the Gatekeeper (Middleware) already checked the badge. 
    # We removed the redundant DB check here so the physical file is enough to pass.>
    
    await state.set_state(CreatePair.waiting_for_source)
    await message.answer("🔗 **Step 1/2**: Send the **Source** channel (Username or Link).")

@router.message(CreatePair.waiting_for_source)
async def process_source(message: types.Message, state: FSMContext):
    # <REACTION: If they send a command now, I might actually lose it. Check for the slash.>
    if message.text.startswith("/"):
        await message.answer("❌ Error: Please provide a channel, not a command.")
        return

    clean_source = sanitize_channel_id(message.text)
    await state.update_data(source_id=clean_source)
    
    await message.answer(f"✅ Source set to: `{clean_source}`\n\n🔗 **Step 2/2**: Send the **Destination** channel.")
    await state.set_state(CreatePair.waiting_for_destination)

@router.message(CreatePair.waiting_for_destination)
async def process_destination(message: types.Message, state: FSMContext):
    # <THINK: Finalizing the link. Hope the destination id is clean.>
    if message.text.startswith("/"):
        await message.answer("❌ Error: Please provide a channel, not a command.")
        return

    user_data = await state.get_data()
    clean_dest = sanitize_channel_id(message.text)
    
    if not user_data.get('source_id'):
        await message.answer("⚠️ Error: Source ID lost. Please restart /createpair.")
        await state.clear()
        return

    # Call the Nervous System to link them
    await repost_service.add_new_pair(
        message.from_user.id, 
        user_data['source_id'], 
        clean_dest
    )
    
    await message.answer(
        f"🎉 **Pair Linked Successfully!**\n\n"
        f"📤 **From**: `{user_data['source_id']}`\n"
        f"📥 **To**: `{clean_dest}`\n\n"
        f"The bot is now watching the source..."
    )
    await state.clear()

# --- VIEW & MANAGEMENT ---

@router.message(Command("viewpairs"))
async def cmd_view_pairs(message: types.Message):
    # <REACTION: Checking the Vault for everything we've linked so far.>
    pairs = await repost_service.get_user_pairs(message.from_user.id)

    if not pairs:
        await message.answer("Empty Vault. Use /createpair to start.")
        return

    text = "📋 **Your Repost Pairs:**\n\n"
    for i, p in enumerate(pairs, 1):
        status = "🟢 Active" if p.is_active else "🔴 Stopped"
        text += f"{i}. **ID: {p.id}**\n   From: `{p.source_id}`\n   To: `{p.destination_id}`\n   Status: {status}\n\n"
    
    await message.answer(text, parse_mode="Markdown")

@router.message(Command("stoppair"))
async def cmd_stop_pair(message: types.Message):
    """Usage: /stoppair <pair_id>"""
    # <THINK: Taking a pair out of commission.>
    args = message.text.split()
    if len(args) < 2 or not args[1].isdigit():
        await message.answer("Usage: `/stoppair <id>` (Get ID from /viewpairs)")
        return

    pair_id = int(args[1])
    success = await repost_service.stop_repost_pair(message.from_user.id, pair_id)
    
    if success:
        await message.answer(f"✅ Pair #{pair_id} stopped.")
    else:
        await message.answer(f"⚠️ Could not stop Pair #{pair_id}. Is the ID correct?")


@router.message(Command("deleteall"))
async def cmd_delete_all_pairs(message: types.Message):
    # <REACTION: 6 pairs of the same thing? Oga, let's just burn the whole list and start fresh.>
    count = await repost_service.delete_all_user_pairs(message.from_user.id)
    
    if count > 0:
        await message.answer(f"🗑️ Vault cleared! Removed {count} pairs. You're back to a clean slate.")
    else:
        await message.answer("⚠️ Your Vault was already empty.")