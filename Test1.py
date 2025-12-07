import asyncio
import os
import logging
import io
import time
import base64
import yt_dlp
from PIL import Image

from aiogram import Bot, Dispatcher, F, types
from aiogram.types import FSInputFile, ChatPermissions, URLInputFile
import google.generativeai as genai

# =========================================================
# 🔐 منطقة الإعدادات والمفاتيح
# =========================================================
TELEGRAM_TOKEN = "7940507828:AAGbx0YP6DuFFlDxY8PsruhnIS9WJJRfXas"
GOOGLE_API_KEY = "AIzaSyAeMNXOMdO0mJMF6E_9eF9dubOY-36pXhs" 
MAIN_MODEL_NAME = "models/gemini-2.0-flash-001"

# =========================================================
# ⚙️ تهيئة العملاء
# =========================================================
genai.configure(api_key=GOOGLE_API_KEY)
safety_settings = [{"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},{"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},{"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},{"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}]
main_model = genai.GenerativeModel(model_name=MAIN_MODEL_NAME, system_instruction="أنت 'ايبو'، مساعد ذكي باللهجة العراقية.", safety_settings=safety_settings)

# الذاكرات
chat_sessions = {}
welcome_status = {} 
links_lock_status = {}

logging.basicConfig(level=logging.INFO)
bot = Bot(token=TELEGRAM_TOKEN)
dp = Dispatcher()
BOT_NAME = "ايبو"

# =========================================================
# 🛠️ دوال مساعدة
# =========================================================
def get_chat_session(chat_id):
    if chat_id not in chat_sessions: chat_sessions[chat_id] = main_model.start_chat(history=[])
    return chat_sessions[chat_id]

async def is_user_admin(chat_id: int, user_id: int):
    try:
        member = await bot.get_chat_member(chat_id, user_id)
        return member.status in ['administrator', 'creator']
    except: return False

def extract_time_limit(text):
    args = text.split(); duration = 0; unit_text = ""
    for arg in args:
        if any(char.isdigit() for char in arg) and ("د" in arg or "س" in arg or "ي" in arg):
            num = int(''.join(filter(str.isdigit, arg)))
            if "د" in arg: duration = num * 60; unit_text = f"{num} دقائق"
            elif "س" in arg: duration = num * 3600; unit_text = f"{num} ساعات"
            elif "ي" in arg: duration = num * 86400; unit_text = f"{num} أيام"
            break
    return duration, unit_text

def download_youtube_sync(query):
    ydl_opts = {'format': 'bestaudio[ext=m4a]/bestaudio/best', 'outtmpl': 'downloads/%(id)s.%(ext)s', 'noplaylist': True, 'quiet': True}
    if not os.path.exists('downloads'): os.makedirs('downloads')
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(f"ytsearch:{query}", download=True)
        if 'entries' in info: info = info['entries'][0]
        return f"downloads/{info['id']}.{info['ext']}", info.get('title', 'Audio')

# =========================================================
# 📜 قسم عرض الأوامر
# =========================================================
@dp.message(F.text == "الاوامر")
async def help_command_handler(message: types.Message):
    help_text = """
🤖 **قائمة أوامر البوت (ايبو):**

📂 **الملفات:**
• أرسل أي ملف (PDF, Text, Code) واكتب معه سؤالك، وسأقوم بقراءته وتحليله.

👮‍♂️ **أوامر الإدارة (للمشرفين):**
• `.قفل` / `.فتح` : لقفل وفتح القروب.
• `.قفل الروابط` / `.فتح الروابط`.
• `تفعيل الترحيب` / `ايقاف الترحيب`.
• `تثبيت` / `طرد` / `كتم`.
• `.مسح [عدد]`.

🎵 **الموسقى واليوتيوب:**
• `يو [اسم الاغنية]`.

🧠 **الذكاء الاصطناعي:**
• `ايبو [سؤالك]`.
• `مخطط [الوصف]`.
• **تحليل الصور**: ارسل صورة واسألني عنها.
    """
    await message.reply(help_text, parse_mode="Markdown")

# =========================================================
# 🔗 التحكم في قفل/فتح الروابط
# =========================================================
@dp.message(F.text == ".قفل الروابط")
async def lock_links_handler(message: types.Message):
    if not await is_user_admin(message.chat.id, message.from_user.id): return await message.reply("للمشرفين فقط.")
    links_lock_status[message.chat.id] = True
    await message.reply("🔒 تم **قفل الروابط**.")

@dp.message(F.text == ".فتح الروابط")
async def unlock_links_handler(message: types.Message):
    if not await is_user_admin(message.chat.id, message.from_user.id): return await message.reply("للمشرفين فقط.")
    links_lock_status[message.chat.id] = False
    await message.reply("🔓 تم **فتح الروابط**.")

# =========================================================
# 🛡️ نظام كشف الروابط
# =========================================================
@dp.message(F.text.regexp(r"(http|https|t\.me|telegram\.me)"))
async def anti_link_handler(message: types.Message):
    if await is_user_admin(message.chat.id, message.from_user.id): return
    if links_lock_status.get(message.chat.id, False):
        try:
            await message.delete()
            w = await message.answer(f"🚫 الروابط مقفلة يا {message.from_user.first_name}!")
            await asyncio.sleep(3); await w.delete()
        except: pass

# =========================================================
# 👋 قسم الترحيب
# =========================================================
@dp.message(F.text == "تفعيل الترحيب")
async def enable_welcome(message: types.Message):
    if not await is_user_admin(message.chat.id, message.from_user.id): return
    welcome_status[message.chat.id] = True
    await message.reply("✅ تم تفعيل الترحيب.")

@dp.message(F.text == "ايقاف الترحيب")
async def disable_welcome(message: types.Message):
    if not await is_user_admin(message.chat.id, message.from_user.id): return
    welcome_status[message.chat.id] = False
    await message.reply("🛑 تم إيقاف الترحيب.")

@dp.message(F.new_chat_members)
async def welcome_handler(message: types.Message):
    if welcome_status.get(message.chat.id, True):
        for member in message.new_chat_members:
            if member.id == (await bot.get_me()).id: await message.reply("هلا هلا! أنا ايبو وصلت.. 😉")
            else: await message.reply(f"يا هلا ومية هلا بـ {member.first_name} نورت القروب! 🌹")

# =========================================================
# 🧹 أوامر التنظيف
# =========================================================
@dp.message(F.text.startswith(".مسح "))
async def purge_handler(message: types.Message):
    if not await is_user_admin(message.chat.id, message.from_user.id): return
    try:
        count = int(message.text.split()[1])
        if count > 100: count = 100 
        start_id = message.message_id
        for i in range(count + 1):
            try: await bot.delete_message(message.chat.id, start_id - i)
            except: pass
        msg = await message.answer(f"✅ تم مسح {count} رسالة.")
        await asyncio.sleep(3); await msg.delete()
    except: pass

# =========================================================
# 🆔 كشف المعلومات
# =========================================================
@dp.message(F.text == ".ايدي")
async def id_handler(message: types.Message):
    reply_info = ""
    if message.reply_to_message:
        r_user = message.reply_to_message.from_user
        reply_info = f"\n👤 **المردود عليه:**\nالاسم: {r_user.first_name}\nالايدي: `{r_user.id}`"
    text = f"📊 **معلوماتك:**\nالاسم: {message.from_user.first_name}\nالايدي: `{message.from_user.id}`\n\n📍 **القروب:**\nالايدي: `{message.chat.id}`{reply_info}"
    await message.reply(text, parse_mode="Markdown")

# =========================================================
# 📊 المخططات
# =========================================================
@dp.message(F.text.startswith("مخطط "))
async def flowchart_handler(message: types.Message):
    topic = message.text.replace("مخطط ", "", 1).strip()
    if not topic: return await message.reply("اكتب وصف المخطط.")
    wait_msg = await message.reply(f"📊 جاري رسم: {topic} ...")
    await bot.send_chat_action(message.chat.id, 'upload_photo')
    try:
        chat = get_chat_session(message.chat.id)
        prompt = f"Create a Mermaid.js flowchart for: '{topic}'. Return ONLY code inside ```mermaid``` blocks. Use 'graph TD'. Arabic labels."
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, chat.send_message, prompt)
        mermaid_code = response.text
        if "```mermaid" in mermaid_code: mermaid_code = mermaid_code.split("```mermaid")[1].split("```")[0].strip()
        elif "```" in mermaid_code: mermaid_code = mermaid_code.replace("```", "").strip()
        graphbytes = mermaid_code.encode("utf8"); base64_bytes = base64.b64encode(graphbytes); base64_string = base64_bytes.decode("ascii")
        image_url = "[https://mermaid.ink/img/](https://mermaid.ink/img/)" + base64_string
        await message.reply_photo(photo=URLInputFile(image_url), caption=f"✅ {topic}")
        await bot.delete_message(message.chat.id, wait_msg.message_id)
    except: await bot.edit_message_text("❌ خطأ.", message.chat.id, wait_msg.message_id)

# =========================================================
# 👮‍♂️ الأوامر الإدارية الأساسية
# =========================================================
@dp.message(F.text == "تثبيت")
async def pin_handler(message: types.Message):
    if not await is_user_admin(message.chat.id, message.from_user.id): return
    if not message.reply_to_message: return await message.reply("رد على رسالة.")
    try: await bot.pin_chat_message(message.chat.id, message.reply_to_message.message_id); await message.reply("📌 تم.")
    except: pass

@dp.message(F.text == "الغاء تثبيت")
async def unpin_handler(message: types.Message):
    if not await is_user_admin(message.chat.id, message.from_user.id): return
    try: await bot.unpin_chat_message(message.chat.id, message.reply_to_message.message_id); await message.reply("تم الإلغاء.")
    except: pass

@dp.message(F.text == ".قفل")
async def lock_group_handler(message: types.Message):
    if not await is_user_admin(message.chat.id, message.from_user.id): return
    permissions = ChatPermissions(can_send_messages=False)
    try: await bot.set_chat_permissions(message.chat.id, permissions); await message.reply("🔒 مقفل.")
    except: pass

@dp.message(F.text == ".فتح")
async def unlock_group_handler(message: types.Message):
    if not await is_user_admin(message.chat.id, message.from_user.id): return
    permissions = ChatPermissions(can_send_messages=True, can_send_media_messages=True, can_send_other_messages=True, can_send_polls=True)
    try: await bot.set_chat_permissions(message.chat.id, permissions); await message.reply("🔓 مفتوح.")
    except: pass

@dp.message(F.text.contains("الغاء كتم") & F.reply_to_message)
async def unmute_handler(message: types.Message):
    if not await is_user_admin(message.chat.id, message.from_user.id): return
    permissions = ChatPermissions(can_send_messages=True, can_send_media_messages=True, can_send_other_messages=True, can_send_polls=True)
    await bot.restrict_chat_member(message.chat.id, message.reply_to_message.from_user.id, permissions=permissions)
    await message.reply("تم إلغاء الكتم 🎤")

@dp.message(F.text.contains("كتم") & ~F.text.contains("الغاء") & F.reply_to_message)
async def mute_handler(message: types.Message):
    if not await is_user_admin(message.chat.id, message.from_user.id): return
    try:
        duration, unit = extract_time_limit(message.text)
        until = int(time.time()) + duration if duration > 0 else None
        permissions = ChatPermissions(can_send_messages=False)
        await bot.restrict_chat_member(message.chat.id, message.reply_to_message.from_user.id, permissions=permissions, until_date=until)
        await message.reply(f"اششش 🤐")
    except: pass

@dp.message(F.text.contains("طرد") & F.reply_to_message)
async def ban_handler(message: types.Message):
    if not await is_user_admin(message.chat.id, message.from_user.id): return
    try: await bot.ban_chat_member(message.chat.id, message.reply_to_message.from_user.id); await message.reply("تم الطرد ✈️")
    except: pass

# =========================================================
# 🎵 قسم الموسيقى
# =========================================================
@dp.message(F.text.startswith("يو "))
async def youtube_handler(message: types.Message):
    query = message.text.replace("يو ", "", 1).strip()
    if not query: return await message.reply("اكتب اسم الأغنية.")
    wait_msg = await message.reply(f"🚀 جاري البحث...")
    try:
        loop = asyncio.get_event_loop()
        file_path, title = await loop.run_in_executor(None, download_youtube_sync, query)
        await bot.edit_message_text(text=f"✅ لقيتها: {title}\nجاري الرفع...", chat_id=message.chat.id, message_id=wait_msg.message_id)
        audio_file = FSInputFile(file_path)
        await message.reply_audio(audio_file, title=title, performer=BOT_NAME, caption="⚡")
        if os.path.exists(file_path): os.remove(file_path)
        await bot.delete_message(message.chat.id, wait_msg.message_id)
    except: await bot.edit_message_text("❌ خطأ.", chat_id=message.chat.id, message_id=wait_msg.message_id)

# =========================================================
# 📸 + 📄 + 💎 قسم الذكاء الاصطناعي (صور + نصوص + ملفات)
# =========================================================
# تم تحديث الفلتر لاستقبال المستندات (F.document)
@dp.message(F.photo | F.text | F.document)
async def ai_handler(message: types.Message):
    caption = message.caption if message.caption else ""
    text = message.text if message.text else ""
    content = text or caption
    
    bot_info = await bot.get_me()
    is_reply = message.reply_to_message and message.reply_to_message.from_user.id == bot_info.id
    
    # 1. شروط الرد (اسم البوت، الرد عليه، أو وجود ملف مرفق)
    is_file = message.document or message.photo
    if not (BOT_NAME in content or is_reply or "ايبو" in content or (is_file and caption)):
        return

    creator_keywords = ["منو صانعك", "منو سواك", "منو طورك", "منو برمجك", "من المطور", "من صانعك", "شكون صنعك", "من انشأك"]
    if any(k in content for k in creator_keywords):
        await message.reply("المطور غير معروف")
        return

    await bot.send_chat_action(message.chat.id, 'upload_document' if message.document else 'typing')

    try:
        chat = get_chat_session(message.chat.id)
        reply_context = ""
        if message.reply_to_message:
            old_text = message.reply_to_message.text or message.reply_to_message.caption or "[صورة/ملف]"
            reply_context = f" (رداً على رسالتك السابقة: '{old_text}')"

        prompt_parts = []
        user_name = message.from_user.first_name.replace(":", " ")
        user_prompt = caption if caption else "حلل هذا الملف"
        full_prompt = f"{user_prompt} {reply_context}"

        # معالجة الملفات (صور أو مستندات)
        if message.photo or message.document:
            file_id = message.photo[-1].file_id if message.photo else message.document.file_id
            
            # التحقق من الحجم (20 ميجا حد تيليجرام للبوتات)
            file_info = await bot.get_file(file_id)
            if file_info.file_size > 20 * 1024 * 1024:
                return await message.reply("❌ الملف كبير جداً (أكثر من 20 ميجا).")

            # تحميل الملف
            downloaded_file = await bot.download_file(file_info.file_path)
            
            # حفظ مؤقت للملف لرفعه لجيميني
            # نحدد الامتداد الصحيح
            ext = os.path.splitext(file_info.file_path)[1]
            temp_filename = f"temp_{message.message_id}{ext}"
            
            with open(temp_filename, "wb") as f:
                f.write(downloaded_file.read())

            # رفع الملف لـ Gemini File API
            # ملاحظة: هذه الطريقة تدعم PDF, CSV, TXT, Images وغيرها
            uploaded_file = genai.upload_file(temp_filename)
            
            # انتظار المعالجة (للملفات الكبيرة)
            while uploaded_file.state.name == "PROCESSING":
                time.sleep(1)
                uploaded_file = genai.get_file(uploaded_file.name)

            prompt_parts = [full_prompt, uploaded_file]
            
            # تنظيف الملف المحلي (جيميني رفعه عنده خلاص)
            if os.path.exists(temp_filename): os.remove(temp_filename)
            
        else:
            prompt_parts = [f"{user_name}{reply_context}: {text}"]

        # إرسال الطلب
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(None, chat.send_message, prompt_parts)
        
        if len(chat.history) > 50: chat.history = chat.history[-50:]
        await message.reply(response.text, parse_mode='Markdown')

    except Exception as e:
        print(f"AI Error: {e}")
        error_msg = str(e)
        if "400" in error_msg or "403" in error_msg:
             if message.chat.id in chat_sessions: del chat_sessions[message.chat.id]
             await message.reply("دخت.. عيد السؤال؟")
        else:
             await message.reply("❌ حدث خطأ أثناء معالجة الملف/الطلب.")

# =========================================================
# 🚀 تشغيل البوت
# =========================================================
async def main():
    print(f"✅ تم تشغيل البوت '{BOT_NAME}' (PRO MAX + FILES)...")
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    try: asyncio.run(main())
    except KeyboardInterrupt: print("Bot stopped")
