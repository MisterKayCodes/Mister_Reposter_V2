"""
BOT: HANDLERS
The 'Mouth & Ears'. (Anatomy: Mouth)
Translates user events into Service calls. (Rule 11)
"""
from aiogram import Router, types
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext

# We only import Services and DB session for the Mouth (Rule 11)
from services.session_manager import SessionService
from services.repost_engine import RepostService
from data.database import async_session
from data.repository import UserRepository
from .states import SessionUpload, CreatePair

router = Router()

session_service = SessionService()
repost_service = RepostService()

@router.message(CommandStart())
async def cmd_start(message: types.Message):
    async with async_session() as db_session:
        repo = UserRepository(db_session)
        await repo.create_or_update_user(message.from_user.id, message.from_user.username)
    await message.answer("Welcome! Use /uploadsession to connect or /createpair to link channels.")

@router.message(Command("uploadsession"))
async def cmd_upload_session(message: types.Message, state: FSMContext):
    await state.set_state(SessionUpload.waiting_for_input)
    await message.answer("Please send your session string or upload the .session file.")

@router.message(SessionUpload.waiting_for_input)
async def process_session_input(message: types.Message, state: FSMContext):
    await message.answer("Processing... please wait.")
    await session_service.handle_session_input(message)
    await state.clear()

@router.message(Command("createpair"))
async def cmd_create_pair(message: types.Message, state: FSMContext):
    await state.set_state(CreatePair.waiting_for_source)
    await message.answer("Step 1/2: Send the **Source** channel username or ID.")

@router.message(CreatePair.waiting_for_source)
async def process_source(message: types.Message, state: FSMContext):
    await state.update_data(source_id=message.text.strip())
    await state.set_state(CreatePair.waiting_for_destination)
    await message.answer("Step 2/2: Send the **Destination** channel username or ID.")

@router.message(CreatePair.waiting_for_destination)
async def process_destination(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    await repost_service.add_new_pair(message.from_user.id, user_data['source_id'], message.text.strip())
    await message.answer(f"✅ Pair Linked!\nFrom: `{user_data['source_id']}`\nTo: `{message.text.strip()}`")
    await state.clear()

@router.message(Command("viewpairs"))
async def cmd_view_pairs(message: types.Message):
    async with async_session() as db_session:
        repo = UserRepository(db_session)
        pairs = await repo.get_user_pairs(message.from_user.id)

    if not pairs:
        await message.answer("No active pairs found. Use /createpair to start.")
        return

    text = "📋 **Your Repost Pairs:**\n\n"
    for i, p in enumerate(pairs, 1):
        status = "✅ Active" if p.is_active else "❌ Stopped"
        text += f"{i}. From: `{p.source_id}`\n   To: `{p.destination_id}`\n   Status: {status}\n\n"
    await message.answer(text, parse_mode="Markdown")


@router.message(Command("stoppair"))
async def cmd_stop_pair(message: types.Message):
    """Usage: /stoppair <pair_id>"""
    args = message.text.split()
    if len(args) < 2 or not args[1].isdigit():
        await message.answer("Usage: /stoppair <pair_id>\nGet the ID from /viewpairs")
        return

    pair_id = int(args[1])
    success = await repost_service.stop_repost_pair(message.from_user.id, pair_id)
    
    if success:
        await message.answer(f"✅ Pair #{pair_id} stopped and disconnected.")
    else:
        await message.answer(f"⚠️ Pair #{pair_id} deactivated in DB, but no active listener was found.")
