from pyrogram import Client, filters
from pyrogram.types import Message
from pytgcalls import PyTgCalls
from pytgcalls.types import AudioPiped, AudioParameters
import asyncio
import subprocess
import os
from config import *

# ===== SETUP =====
authorized_users = set([OWNER_ID])
target_groups = {}

current_volume = DEFAULT_VOLUME
current_bass = DEFAULT_BASS
current_eq = DEFAULT_EQ

# Source Bot
source_app = Client(
    "source_bot",
    api_id=SOURCE_API_ID,
    api_hash=SOURCE_API_HASH,
    phone_number=SOURCE_PHONE
)

# Target Bot
target_app = Client(
    "target_bot",
    api_id=TARGET_API_ID,
    api_hash=TARGET_API_HASH,
    phone_number=TARGET_PHONE
)

source_calls = PyTgCalls(source_app)
target_calls = PyTgCalls(target_app)

# ===== PERMISSION CHECK =====
def is_authorized(user_id):
    return user_id in authorized_users

# ===== HD AUDIO FILTER =====
def get_filter(volume=1000, bass=5, eq="normal"):
    vol = volume / 100.0

    bass_filter = f"equalizer=f=60:width_type=o:width=2:g={bass}"

    if eq == "bass":
        eq_filter = f"{bass_filter},equalizer=f=170:width_type=o:width=2:g=8"
    elif eq == "treble":
        eq_filter = f"equalizer=f=3000:width_type=o:width=2:g=8,equalizer=f=8000:width_type=o:width=2:g=10"
    elif eq == "clear":
        eq_filter = f"equalizer=f=1000:width_type=o:width=2:g=5,equalizer=f=3000:width_type=o:width=2:g=3"
    elif eq == "vocal":
        eq_filter = f"equalizer=f=800:width_type=o:width=2:g=6,equalizer=f=2500:width_type=o:width=2:g=5"
    else:
        eq_filter = f"{bass_filter}"

    # HD Quality filter
    hd_filter = (
        f"volume={vol},"
        f"{eq_filter},"
        f"aresample=48000,"
        f"aformat=sample_fmts=s16:channel_layouts=stereo,"
        f"highpass=f=20,"
        f"lowpass=f=20000,"
        f"dynaudnorm=f=150:g=15"
    )
    return hd_filter

# ===== SOURCE BOT JOIN =====
async def source_join():
    try:
        audio_filter = get_filter(current_volume, current_bass, current_eq)
        await source_calls.join_group_call(
            SOURCE_GROUP,
            AudioPiped(
                f"ffmpeg -f pulse -i default "
                f"-af '{audio_filter}' "
                f"-f s16le -ac 2 -ar 48000 "
                f"-acodec pcm_s16le pipe:1",
                AudioParameters(
                    bitrate=320,
                    channels=2,
                    sample_rate=48000
                )
            )
        )
        return True
    except Exception as e:
        print(f"Source join error: {e}")
        return False

# ===== TARGET BOT JOIN =====
async def target_join(group_id):
    try:
        audio_filter = get_filter(current_volume, current_bass, current_eq)
        await target_calls.join_group_call(
            group_id,
            AudioPiped(
                f"ffmpeg -f pulse -i default "
                f"-af '{audio_filter}' "
                f"-f s16le -ac 2 -ar 48000 "
                f"-acodec pcm_s16le pipe:1",
                AudioParameters(
                    bitrate=320,
                    channels=2,
                    sample_rate=48000
                )
            )
        )
        return True
    except Exception as e:
        print(f"Target join error: {e}")
        return False

# ===== JOIN COMMAND =====
@source_app.on_message(filters.command("join") & filters.group)
async def join_vc(client: Client, message: Message):
    if not is_authorized(message.from_user.id):
        await message.reply("❌ Permission nahi hai!")
        return

    group_id = message.chat.id

    # Source bot source group mein join
    source_ok = await source_join()

    # Target bot is group mein join
    target_ok = await target_join(group_id)

    if source_ok and target_ok:
        target_groups[group_id] = {
            "volume": current_volume,
            "bass": current_bass,
            "eq": current_eq
        }
        await message.reply(
            f"✅ **Dono Bots Join Ho Gaye!**\n\n"
            f"🎙️ Source Bot: Aapke group mein\n"
            f"📢 Target Bot: Is group mein\n"
            f"🔊 Volume: **{current_volume}%**\n"
            f"🎸 Bass: **{current_bass}**\n"
            f"🎛️ EQ: **{current_eq}**\n"
            f"🎵 Quality: **HD 320kbps**"
        )
    else:
        await message.reply("❌ Kuch error aaya! Dobara try karo.")

# ===== LEAVE COMMAND =====
@source_app.on_message(filters.command("leave") & filters.group)
async def leave_vc(client: Client, message: Message):
    if not is_authorized(message.from_user.id):
        await message.reply("❌ Permission nahi hai!")
        return

    group_id = message.chat.id

    try:
        await target_calls.leave_group_call(group_id)
        target_groups.pop(group_id, None)
        await message.reply("✅ Target Bot Ne VC Chhod Diya!")
    except Exception as e:
        await message.reply(f"❌ Error: {str(e)}")

# ===== LEAVE ALL =====
@source_app.on_message(filters.command("leaveall") & filters.group)
async def leave_all(client: Client, message: Message):
    if not is_authorized(message.from_user.id):
        await message.reply("❌ Permission nahi hai!")
        return

    count = 0
    for group_id in list(target_groups.keys()):
        try:
            await target_calls.leave_group_call(group_id)
            count += 1
        except:
            pass

    try:
        await source_calls.leave_group_call(SOURCE_GROUP)
    except:
        pass

    target_groups.clear()
    await message.reply(f"✅ Sab Groups Chhod Diye! ({count} groups)")

# ===== VOLUME =====
@source_app.on_message(filters.command("vol") & filters.group)
async def set_volume(client: Client, message: Message):
    if not is_authorized(message.from_user.id):
        await message.reply("❌ Permission nahi hai!")
        return

    global current_volume

    try:
        vol = int(message.command[1])
        if vol < 1 or vol > 20000:
            await message.reply("⚠️ Volume 1 se 20000 ke beech!")
            return
        current_volume = vol
        await message.reply(f"🔊 Volume: **{vol}%**")
    except:
        await message.reply("❌ Use: `/vol 5000`")

# ===== BASS =====
@source_app.on_message(filters.command("bass") & filters.group)
async def set_bass(client: Client, message: Message):
    if not is_authorized(message.from_user.id):
        await message.reply("❌ Permission nahi hai!")
        return

    global current_bass

    try:
        bass = int(message.command[1])
        if bass < 0 or bass > 20:
            await message.reply("⚠️ Bass 0 se 20 ke beech!")
            return
        current_bass = bass
        await message.reply(f"🎸 Bass: **{bass}**")
    except:
        await message.reply("❌ Use: `/bass 10`")

# ===== EQUALIZER =====
@source_app.on_message(filters.command("eq") & filters.group)
async def set_eq(client: Client, message: Message):
    if not is_authorized(message.from_user.id):
        await message.reply("❌ Permission nahi hai!")
        return

    global current_eq

    try:
        mode = message.command[1].lower()
        if mode not in ["normal", "bass", "treble", "clear", "vocal"]:
            await message.reply(
                "⚠️ EQ Modes:\n"
                "`normal` — Default\n"
                "`bass` — Bass boost\n"
                "`treble` — Treble boost\n"
                "`clear` — Crystal clear\n"
                "`vocal` — Voice clear"
            )
            return
        current_eq = mode
        await message.reply(f"🎛️ EQ: **{mode}**")
    except:
        await message.reply("❌ Use: `/eq bass`")

# ===== ADD ADMIN =====
@source_app.on_message(filters.command("addadmin") & filters.group)
async def add_admin(client: Client, message: Message):
    if message.from_user.id != OWNER_ID:
        await message.reply("❌ Sirf owner kar sakta hai!")
        return

    try:
        user = message.reply_to_message.from_user
        authorized_users.add(user.id)
        await message.reply(f"✅ **{user.first_name}** ko permission mili!")
    except:
        await message.reply("❌ Reply karke `/addadmin` likho")

# ===== REMOVE ADMIN =====
@source_app.on_message(filters.command("removeadmin") & filters.group)
async def remove_admin(client: Client, message: Message):
    if message.from_user.id != OWNER_ID:
        await message.reply("❌ Sirf owner kar sakta hai!")
        return

    try:
        user = message.reply_to_message.from_user
        authorized_users.discard(user.id)
        await message.reply(f"✅ **{user.first_name}** ki permission gayi!")
    except:
        await message.reply("❌ Reply karke `/removeadmin` likho")

# ===== ADMINS LIST =====
@source_app.on_message(filters.command("admins") & filters.group)
async def admins_list(client: Client, message: Message):
    if not is_authorized(message.from_user.id):
        await message.reply("❌ Permission nahi hai!")
        return

    admins = "\n".join([f"• `{uid}`" for uid in authorized_users])
    await message.reply(f"👑 **Admins:**\n\n{admins}")

# ===== STATUS =====
@source_app.on_message(filters.command("status") & filters.group)
async def status(client: Client, message: Message):
    if not is_authorized(message.from_user.id):
        await message.reply("❌ Permission nahi hai!")
        return

    groups = "\n".join([f"• `{gid}`" for gid in target_groups.keys()]) or "Koi nahi"

    await message.reply(
        f"📊 **Bot Status**\n\n"
        f"🔊 Volume: **{current_volume}%**\n"
        f"🎸 Bass: **{current_bass}**\n"
        f"🎛️ EQ: **{current_eq}**\n"
        f"🎵 Quality: **HD 320kbps**\n"
        f"📢 Active Groups: **{len(target_groups)}**\n\n"
        f"**Groups:**\n{groups}"
    )

# ===== HELP =====
@source_app.on_message(filters.command("help") & filters.group)
async def help_cmd(client: Client, message: Message):
    await message.reply(
        "🎙️ **VC Bot Commands**\n\n"
        "**VC Control:**\n"
        "/join — Dono bots VC mein join\n"
        "/leave — Is group se leave\n"
        "/leaveall — Sab groups chhodo\n\n"
        "**Audio:**\n"
        "/vol 1000 — Volume (1-20000)\n"
        "/bass 10 — Bass (0-20)\n"
        "/eq bass — EQ mode\n\n"
        "**EQ Modes:**\n"
        "normal | bass | treble | clear | vocal\n\n"
        "**Admin:**\n"
        "/addadmin — Permission do\n"
        "/removeadmin — Permission lo\n"
        "/admins — List dekho\n"
        "/status — Bot info\n"
        "/help — Ye message"
    )

# ===== MAIN START =====
async def main():
    await source_app.start()
    await target_app.start()
    await source_calls.start()
    await target_calls.start()
    print("✅ Dono Bots Chal Rahe Hain!")
    print(f"🎙️ Source Bot: Ready")
    print(f"📢 Target Bot: Ready")
    await asyncio.get_event_loop().run_forever()

if __name__ == "__main__":
    asyncio.run(main())
