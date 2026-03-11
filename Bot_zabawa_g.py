import discord
from discord.ext import commands
import yt_dlp 
import asyncio
import random
import requests
import os
import sys
import aiohttp
from datetime import datetime, timedelta
from collections import defaultdict, Counter
import openai

intents = discord.Intents.default()
intents.members = True
intents.message_content = True
intents.guilds = True
bot = commands.Bot(command_prefix="!", intents=intents, case_insensitive=True)
OWNER_ID = 856522677896609803  # Zmień na swoje ID

queues = {}  # Słownik przechowujący kolejkę dla każdej gildii

INVITE_LINK = "https://discord.gg/qn7sQFtP"
RMF_FM_STREAM_URL = "http://195.150.20.242:8000/rmf_fm"  # Link do RMF FM

@bot.event
async def on_ready():
    print(f'✅ Zalogowano jako {bot.user}')


queues = {}

def get_queue(guild_id):
    return queues.setdefault(guild_id, [])

@bot.command(aliases=['graj'])
async def play(ctx, *, search: str):
    if not ctx.author.voice:
        await ctx.send("❌ Musisz być na kanale głosowym!")
        return

    voice_client = ctx.voice_client
    channel = ctx.author.voice.channel

    if voice_client is None:
        voice_client = await channel.connect()
    elif voice_client.channel != channel:
        await voice_client.move_to(channel)

    ydl_opts = {
        'format': 'bestaudio/best',
        'noplaylist': True,
        'quiet': True,
        'default_search': 'ytsearch',
        'extract_flat': False,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(search, download=False)
        if 'entries' in info:
            info = info['entries'][0]
        url = info['url']
        title = info.get('title', 'Nieznany tytuł')
        video_url = info.get('webpage_url', 'https://youtube.com')
        thumbnail = info.get('thumbnail')

    guild_id = ctx.guild.id
    queue = get_queue(guild_id)

    song = {'title': title, 'url': url, 'video_url': video_url, 'thumbnail': thumbnail}

    def after_playing(error):
        if error:
            print(f"Błąd podczas odtwarzania: {error}")

        next_song = None
        if queue:
            next_song = queue.pop(0)

        if next_song:
            source = discord.FFmpegPCMAudio(
                next_song['url'],
                before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
                options="-vn"
            )
            voice_client.play(source, after=after_playing)

            embed = discord.Embed(
                title=f"[{next_song['title']}]({next_song['video_url']})",
                color=discord.Color.green()
            )
            if next_song.get('thumbnail'):
                embed.set_thumbnail(url=next_song['thumbnail'])

            coro = ctx.send(embed=embed)
            fut = asyncio.run_coroutine_threadsafe(coro, bot.loop)
            try:
                fut.result()
            except Exception as e:
                print(e)

    # Główna wiadomość embed
    embed = discord.Embed(
        title=f"[{title}]({video_url})",
        color=discord.Color.green() if not (voice_client.is_playing() or voice_client.is_paused()) else discord.Color.blue()
    )
    if thumbnail:
        embed.set_thumbnail(url=thumbnail)

    if voice_client.is_playing() or voice_client.is_paused():
        queue.append(song)
    else:
        source = discord.FFmpegPCMAudio(
            url,
            before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
            options="-vn"
        )
        voice_client.play(source, after=after_playing)

    await ctx.send(embed=embed)

@bot.command()
async def skip(ctx):
    voice_client = ctx.voice_client
    if voice_client and voice_client.is_playing():
        voice_client.stop()
        await ctx.send("⏭ Pominąłem utwór.")
    else:
        await ctx.send("Nie ma nic do pominięcia.")

@bot.command()
async def queue(ctx):
    guild_id = ctx.guild.id
    queue = get_queue(guild_id)
    if not queue:
        await ctx.send("Kolejka jest pusta.")
        return

    embed = discord.Embed(title="Kolejka utworów", color=discord.Color.blue())
    description = ""
    for i, song in enumerate(queue, start=1):
        description += f"{i}. {song['title']}\n"
    embed.description = description
    await ctx.send(embed=embed)

@bot.command()
async def stop(ctx):
    voice_client = ctx.voice_client
    if voice_client:
        queues[ctx.guild.id] = []
        await voice_client.disconnect()
        await ctx.send("⏹ Zatrzymałem odtwarzanie i wyczyściłem kolejkę.")
    else:
        await ctx.send("Bot nie jest na żadnym kanale głosowym.")

@bot.command()
@commands.has_permissions(administrator=True)
async def witam(ctx, member: discord.Member):
    """Symuluje ładowanie i wysyła powitanie do użytkownika. (Tylko dla administratorów)"""
    for i in range(10, 101, 10):
        await ctx.send(f"ładowanie witania ✅{i}%✅")
        await asyncio.sleep(0.1)
    
    for _ in range(10):
        await member.send("witam")

@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ **Uprawnień nie masz**")

        # Pobieramy pierwsze zaproszenie do serwera (jeśli istnieje)
        invite_link = None
        if ctx.guild.vanity_url_code:  # Jeśli serwer ma własny link zaproszeniowy
            invite_link = f"https://discord.gg/{ctx.guild.vanity_url_code}"
        else:
            invites = await ctx.guild.invites()
            if invites:
                invite_link = invites[0].url  # Bierzemy pierwsze zaproszenie

        # Tworzymy wiadomość dla użytkownika
        message = f"Nie masz uprawnień do korzystania z bota na serwerze"
        if invite_link:
            message += f"🔗 **Link do serwera:** \n {invite_link}."

        await ctx.author.send(message)

@bot.command()
@commands.has_permissions(manage_messages=True)
async def clear(ctx, amount: int = 10):
    """Usuwa określoną liczbę wiadomości z czatu (domyślnie 10)"""
    if amount < 1:
        await ctx.send("❌ **Podaj liczbę większą od 0!**")
        return

    deleted = await ctx.channel.purge(limit=amount + 1)  # +1, żeby usunąć też komendę
    await ctx.send(f"✅ **Usunięto {len(deleted) - 1} wiadomości.**", delete_after=5)


GIPHY_API_KEY = "ZJ9fTqulZBJTMPCsalNv5JEsbnIWM00o"

@bot.command()
async def kot(ctx):
    """Wysyła losowy GIF z kotkiem w embedzie"""
    url = f"https://api.giphy.com/v1/gifs/random?api_key={GIPHY_API_KEY}&tag=cat&rating=g"
    
    response = requests.get(url).json()
    
    if "data" in response and response["data"]:
        gif_url = response["data"]["images"]["original"]["url"]

        embed = discord.Embed(
            title="Łap kota",
            color=discord.Color.orange()
        )
        embed.set_image(url=gif_url)
        embed.set_footer(text="😺")

        await ctx.send(embed=embed)
    else:
        await ctx.send("❌ blad jakis jest")


@bot.event
async def on_error(event, *args, **kwargs):
    """Obsługa nieoczekiwanych błędów"""
    print(f"❌ Wystąpił nieoczekiwany błąd w {event}. Restartuję bota...")
    restart_bot()


def restart_bot():
    """Restartuje bota"""
    os.execv(sys.executable, ['python'] + sys.argv)


@bot.command()
@commands.has_permissions(administrator=True)
async def restart(ctx):
    """Restartuje bota (tylko dla administratorów)"""
    await ctx.send("🔄 **Restartuję bota...**")

    python = sys.executable
    os.execl(python, python, *sys.argv)

@bot.command()
async def wisielec(ctx):
    """Animowana gra w wisielca"""
    stages = [
        "```\n\n\n\n🎭```",  # Początkowa szubienica
        "```\n\n\n O \n🎭```",  # Głowa
        "```\n\n\n O \n | \n🎭```",  # Tułów
        "```\n\n\n O \n/| \n🎭```",  # Jedno ramię
        "```\n\n\n O \n/|\\ \n🎭```",  # Oba ramiona
        "```\n\n\n O \n/|\\ \n/ \n🎭```",  # Jedna noga
        "```\n\n\n O \n/|\\ \n/ \\ \n🎭```"  # Obie nogi (koniec animacji)
    ]

    message = await ctx.send(stages[0])  # Wysyłamy pierwszą wersję

    for stage in stages[1:]:
        await asyncio.sleep(1)  # Czekamy 1 sekundę
        await message.edit(content=stage)  # Edytujemy wiadomość

    await ctx.send("💀 **Wisielec skończony!**")

    
@bot.command()
async def wypadek(ctx):
    """Bardzo szybka animacja samochodu wjeżdżającego w drzewo"""
    frames = [
        "🚗        🌳",
        "  🚗      🌳",
        "    🚗    🌳",
        "      🚗  🌳",
        "        💥🌳"  
    ]

    for frame in frames:
        await ctx.send(frame)
        await asyncio.sleep(0.2)  # Skrócony czas między klatkami

from discord.ext import commands
from discord.ext.commands import BucketType
import asyncio

@bot.command()
@commands.cooldown(rate=1, per=60.0, type=BucketType.default)  # Globalny cooldown: 1 użycie na 60 sek
async def strzal(ctx):
    """Skrócona animacja strzału z pistoletu"""
    gun = "🔫"
    bullet = "●"
    target_alive = "🙂"
    target_dead = "💀"
    studs_text = "**1742 studs!**"

    frames = [target_alive + " " * (10 - i) + bullet + " " * i + gun for i in range(1, 11)]

    msg = await ctx.send(frames[0])  

    for frame in frames:
        await msg.edit(content=frame)
        await asyncio.sleep(0.04)

    for impact in ["💥", "💢"]:
        await msg.edit(content=target_alive + impact + " " * 10 + gun)
        await asyncio.sleep(0.08)

    await msg.edit(content=f"{target_dead} {' ' * 10} {gun}\n      {studs_text} \n https://tr.rbxcdn.com/30DAY-AvatarHeadshot-ECBCB88404656C75E0D35B3B167C555E-Png/150/150/AvatarHeadshot/Webp/noFilter")

@strzal.error
async def strzal_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"⏳ Ta komenda ma cooldown! Spróbuj ponownie za {round(error.retry_after, 1)} sekund.")






@bot.command()
async def invite(ctx, user: discord.User):
    """Wysyła zaproszenie do użytkownika, nawet jeśli nie jest na serwerze"""
    try:
        await user.send(f"Hej {user.name}, dołącz do naszego serwera! 🎉\n{INVITE_LINK}")
        await ctx.send(f"✅ Zaproszenie wysłane do {user.name}!")
    except discord.Forbidden:
        # Jeśli użytkownik ma wyłączone wiadomości prywatne
        await ctx.author.send(f"⚠️ Nie mogłem wysłać zaproszenia do {user.name}, ponieważ ma wyłączone DM-y.")
        
@bot.command()
async def rmffm(ctx):
    """Komenda do odtwarzania RMF FM na kanale głosowym."""
    if ctx.author.voice:
        channel = ctx.author.voice.channel
        vc = await channel.connect()

        # Uruchamiamy strumień audio przez FFmpeg
        ffmpeg_options = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
            'options': '-vn'
        }
        source = discord.FFmpegPCMAudio("http://195.150.20.242:8000/rmf_fm", **ffmpeg_options)

        print("🔊 Rozpoczynam odtwarzanie RMF FM...")  # Debugowanie
        vc.play(source, after=lambda e: print(f"❌ Błąd: {e}") if e else None)
        
        await ctx.send("🎵 **Odtwarzam RMF FM na żywo!** 📻")
    else:
        await ctx.send("❌ **Musisz być na kanale głosowym!**")


@bot.command(name="stopradio")
async def stopradio(ctx):
    """Komenda do zatrzymania radia i odłączenia bota."""
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        await ctx.send("⏹ **Radio zatrzymane!**")
    else:
        await ctx.send("❌ **Bot nie jest na kanale głosowym!**")


@bot.command()
@commands.cooldown(rate=1, per=10, type=commands.BucketType.user)
async def yesno(ctx, *, content: str):
    try:
        countdown_msg = await ctx.send("3...")

        await asyncio.sleep(1)
        await countdown_msg.edit(content="2...")

        await asyncio.sleep(1)
        await countdown_msg.edit(content="1...")

        await asyncio.sleep(1)
        choice = random.choice(["Tak", "Nie"])
        embed = discord.Embed(
            title=choice,
            description=content,
            color=discord.Color.green() if choice == "Tak" else discord.Color.red()
        )
        embed.set_footer(text="Komendy można użyć raz na 10 sekund")
        await countdown_msg.edit(content=None, embed=embed)

    except Exception as e:
        await ctx.send(f"Wystąpił błąd: {e}")

@yesno.error
async def yesno_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"Poczekaj {error.retry_after:.1f} sekundy przed ponownym użyciem.")


@bot.command()
@commands.cooldown(rate=1, per=60.0, type=commands.BucketType.user)  # 1 użycie co 60 sekund per użytkownik
async def Kokonut(ctx):
    try:
        user = await bot.fetch_user(476739957948416022)
        link = "https://discord.com/channels/927491981670776862/927491981670776866"
        message = (
            "Wbijaj do nas!\n"
            f"{link}\n\n"
            f"Wiadomość wysłana przez użytkownika: **{ctx.author.name}**"
        )
        await user.send(message)
        await ctx.send("Wiadomość do Kokonuta została wysłana.")
    except Exception as e:
        await ctx.send(f"Nie udało się wysłać wiadomości do Kokonuta. Błąd: {e}")

# Obsługa błędów cooldownu
@Kokonut.error
async def Kokonut_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"Ta komenda jest na cooldownie. Spróbuj ponownie za {int(error.retry_after)} sekund.")
    else:
        raise error


@bot.command()
@commands.cooldown(rate=1, per=60.0, type=commands.BucketType.user)  # 1 użycie co 60 sekund per użytkownik
async def Franek(ctx):
    try:
        user = await bot.fetch_user(775679101481779230)
        link = "https://discord.com/channels/927491981670776862/927491981670776866"
        message = (
            "Wbijaj do nas!\n"
            f"{link}\n\n"
            f"Wiadomość wysłana przez użytkownika: **{ctx.author.name}**"
        )
        await user.send(message)
        await ctx.send("Wiadomość do Franka została wysłana.")
    except Exception as e:
        await ctx.send(f"Nie udało się wysłać wiadomości do Franka. Błąd: {e}")

@Franek.error
async def Franek_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"Ta komenda jest na cooldownie. Spróbuj ponownie za {int(error.retry_after)} sekund.")
    else:
        raise error




@bot.command(name="Lukasz")
@commands.cooldown(rate=1, per=60.0, type=commands.BucketType.user)  # 1 użycie co 60s per user
async def Lukasz(ctx):
    try:
        user = await bot.fetch_user(1290639426770173994)
        link = "https://discord.com/channels/927491981670776862/927491981670776866"
        message = (
            "Wbijaj do nas!\n"
            f"{link}\n\n"
            f"Wiadomość wysłana przez użytkownika: **{ctx.author.name}**"
        )
        await user.send(message)
        await ctx.send("Wiadomość do Łukasza została wysłana.")
    except Exception as e:
        await ctx.send(f"Nie udało się wysłać wiadomości do Łukasza. Błąd: {e}")

# Obsługa błędów cooldownu
@Lukasz.error
async def Lukasz_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"⏳ Ta komenda jest na cooldownie. Spróbuj ponownie za {int(error.retry_after)} sekund.")
    else:
        raise error



@bot.command()
@commands.cooldown(rate=1, per=60.0, type=commands.BucketType.user)  # 1 użycie co 60 sekund na użytkownika
async def Grubek(ctx):
    try:
        user = await bot.fetch_user(747177807934783569)
        link = "https://discord.com/channels/927491981670776862/927491981670776866"
        message = (
            "wbijaj!\n\n"
            f"Wiadomość wysłana przez użytkownika: **{ctx.author.name}**\n\n"
            f"Link: {link}"
        )
        await user.send(message)
        await ctx.send("Wiadomość do Grubka została wysłana.")
    except Exception as e:
        await ctx.send(f"Nie udało się wysłać wiadomości do Grubka. Błąd: {e}")

# Obsługa błędów cooldownu
@Grubek.error
async def Grubek_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"Ta komenda jest na cooldownie. Spróbuj ponownie za {int(error.retry_after)} sekund.")
    else:
        raise error



@bot.command()
async def pies(ctx):
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get("https://dog.ceo/api/breeds/image/random") as response:
                if response.status == 200:
                    data = await response.json()
                    image_url = data["message"]

                    embed = discord.Embed(
                        title="Pies:",
                        color=discord.Color.orange()
                    )
                    embed.set_image(url=image_url)
                    embed.set_footer(text=f"Wywołane przez: {ctx.author.name}", icon_url=ctx.author.avatar.url if ctx.author.avatar else None)

                    await ctx.send(embed=embed)
                else:
                    await ctx.send("Nie udało się pobrać pieska 🐾")
    except Exception as e:
        await ctx.send(f"Wystąpił błąd: {e}")

@bot.command()
@commands.cooldown(rate=1, per=60.0, type=commands.BucketType.user)  # 1 użycie na 60 sekund na użytkownika
async def monka(ctx):
    try:
        user = await bot.fetch_user(977936159034454147)
        message = "Wbijaj!\nhttps://discord.com/channels/927491981670776862/927491981670776866"
        await user.send(message)
        await ctx.send("Wiadomość została wysłana do Monki.")
    except Exception as e:
        await ctx.send(f"Nie udało się wysłać wiadomości. Błąd: {e}")

# Opcjonalnie: obsługa błędu cooldownu
@monka.error
async def monka_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"Ta komenda jest na cooldownie. Spróbuj ponownie za {int(error.retry_after)} sekund.")
    else:
        raise error

import discord
from discord.ext import commands

@bot.command(aliases=['ar2'])
async def ar(ctx):
    image_url = "https://tr.rbxcdn.com/180DAY-f12b0d431bdfd9ff446b8b2cc76ba94d/768/432/Image/Webp/noFilter"  # <-- podaj swój link tutaj

    embed = discord.Embed(
        title="Apocalypse Rising 2!",
        url="https://www.roblox.com/games/863266079/Apocalypse-Rising-2",
        description="Kliknij tytuł, aby przejść do gry.",
        color=discord.Color.red()
    )
    embed.set_image(url=image_url)
    await ctx.send(embed=embed)



@bot.command()
async def roblox(ctx, username: str):
    async with aiohttp.ClientSession() as session:
        search_url = f"https://users.roblox.com/v1/users/search?keyword={username}"
        try:
            async with session.get(search_url) as resp:
                if resp.status == 429:
                    await ctx.send("⏳ Zbyt wiele zapytań do Roblox API. Spróbuj ponownie za chwilę.")
                    return
                if resp.status != 200:
                    await ctx.send(f"❌ Błąd serwera Roblox: status {resp.status}")
                    return
                search_data = await resp.json()
        except Exception as e:
            await ctx.send(f"❌ Wystąpił błąd podczas wyszukiwania użytkownika: {e}")
            return

        if not search_data.get("data"):
            await ctx.send(f"❌ Nie znaleziono użytkownika o nicku **{username}**.")
            return

        user = search_data["data"][0]
        user_id = user["id"]
        user_name = user["name"]

        await asyncio.sleep(1)

        details_url = f"https://users.roblox.com/v1/users/{user_id}"
        try:
            async with session.get(details_url) as resp:
                if resp.status == 429:
                    await ctx.send("⏳ Zbyt wiele zapytań do Roblox API. Spróbuj ponownie za chwilę.")
                    return
                if resp.status != 200:
                    await ctx.send(f"❌ Błąd serwera Roblox przy pobieraniu szczegółów: status {resp.status}")
                    return
                details = await resp.json()
        except Exception as e:
            await ctx.send(f"❌ Wystąpił błąd podczas pobierania szczegółów użytkownika: {e}")
            return

    created_str = details.get('created')
    if not created_str:
        await ctx.send("❌ Nie udało się znaleźć daty założenia konta.")
        return

    try:
        created_date = datetime.fromisoformat(created_str.rstrip('Z'))
        created_date_str = created_date.strftime("%d-%m-%Y %H:%M:%S")
    except Exception as e:
        await ctx.send(f"❌ Błąd podczas parsowania daty: {e}")
        return

    embed = discord.Embed(
        title=f"{created_date_str}",
        color=discord.Color.green()
    )
    embed.set_footer(text=f"Nazwa konta: {user_name}")
    embed.set_thumbnail(url=f"https://www.roblox.com/headshot-thumbnail/image?userId={user_id}&width=150&height=150&format=png")

    await ctx.send(embed=embed)


@bot.command()
async def food(ctx):
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get("https://foodish-api.com/api/") as resp:
                if resp.status != 200:
                    await ctx.send("❌ Nie udało się pobrać jedzenia.")
                    return
                data = await resp.json()
                image_url = data["image"]
        except Exception as e:
            await ctx.send(f"❌ Błąd: {e}")
            return

    embed = discord.Embed(
        description="Jedzenie",
        color=discord.Color.orange()
    )
    embed.set_image(url=image_url)
    await ctx.send(embed=embed)

@bot.command()
async def lis(ctx):
    url = "https://randomfox.ca/floof/"
    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url) as resp:
                if resp.status != 200:
                    await ctx.send("❌ Nie udało się pobrać lisa.")
                    return
                data = await resp.json()
                fox_url = data["image"]
        except Exception as e:
            await ctx.send(f"❌ Błąd podczas pobierania lisa: {e}")
            return

    embed = discord.Embed(
        description="🦊 Lisek nadchodzi!",
        color=discord.Color.orange()
    )
    embed.set_image(url=fox_url)

    await ctx.send(embed=embed)

@bot.command()
async def vagrant(ctx):
    # 🔁 Wstaw tu swoje dwa linki do obrazków
    link1 = "https://static.wikia.nocookie.net/roblox-apocalypse-rising/images/8/87/%22Vagrant%22_Lupara_Shotgun.png/revision/latest?cb=20231230012651"
    link2 = "https://static.wikia.nocookie.net/roblox-apocalypse-rising/images/d/d7/Lupara_%28AR2%29.png/revision/latest/scale-to-width-down/1200?cb=20240714194254"

    chosen = random.choice([link1, link2])

    embed = discord.Embed(
        title="🎲 Wylosowano!",
        description="Jedna z dwóch możliwości!",
        color=discord.Color.green()
    )
    embed.set_image(url=chosen)
    await ctx.send(embed=embed)


@bot.command()
async def pomoc(ctx):
    embed = discord.Embed(
        title="🤖 Pomoc — Bot dedykowany Apocalypse Rising 2",
        description="Poniżej znajdziesz listę dostępnych komend uporządkowaną według kategorii:",
        color=discord.Color.from_rgb(47, 49, 54)
    )

    # 🎮 Komendy AR2
    embed.add_field(
        name="🎮 **Apocalypse Rising 2**",
        value=(
            "• `!ar` / `!ar2` — Link do gry\n"
            "• `!loadout` — 🎒 Losowy loadout\n"
            "• `!dobryloadout` — 💎 Lepszy loadout\n"
            "• `!privloadout` — 📩 Loadout na priv\n"
            "• `!gunar` — 🔫 Losowa broń\n"
            "• `!sgunar` — 🔧 Losowa *secondary* broń\n"
            "• `!pgunar` — 💥 Losowa *primary* broń\n"
            "• `!attachments` — ⚙️ Losowy attachment\n"
            "• `!sights` — 🔭 Losowy celownik\n"
            "• `!grips` — ✊ Losowy grip\n"
            "• `!mapa` — 🗺️ Wyświetla mapę AR2\n"
            "• `!ammo` — 💥 Pokazuje jakie ammo do jakiej broni jest\n"
            "• `!leaderboard` — 🏆 Wyświetla tabelę wyników\n"
            "• `!ciekawostki` — 📚 Pokazuje losową ciekawostkę\n"
            "• `!sniper` — 🎯 Tworzy loadout dla snajpera\n"
            "• `!demolisher` — 💣 Tworzy loadout z mocną bronią (np. demolisher)\n"
            "• `!rush / !rusher` — ⚡ Tworzy loadout dla gracza na szybkiego rusha\n"
            "• `!serverinfo` - podaje aktualną liczbe graczy grających w Apocalype Rising 2\n"
            "• `!balance` — 💰 Pokazuje status konta (ilość monet)\n"
            "• `!shop` — 🛒 Wyświetla dostępne przedmioty do kupienia w sklepie" 
        ),
        inline=False
    )

    # 📩 Komendy pingujące użytkowników
    embed.add_field(
        name="📬 **Pingowanie użytkowników** *(Cooldown: 60s)*",
        value=(
            "• `!Grubek` — Wyślij Grubkowi zaproszenie do wbicia\n"
            "• `!Kokonut` — Wyślij Kokonutowi zaproszenie do wbicia\n"
            "• `!Monka` — Wyślij Monce zaproszenie do wbicia\n"
            "• `!lukasz` — Wyślij Laxkowi zaproszenie do wbicia"
        ),
        inline=False
    )

    # 🎶 Muzyka i radio
    embed.add_field(
        name="🎶 **Muzyka & Radio**",
        value=(
            "• `!graj [nazwa]` — ▶️ Odtwórz z YouTube\n"
            "• `!zloteprzeboje` — 📻 Złote Przeboje\n"
            "• `!rmffm` — 🎧 RMF FM\n"
            "• `!radiozet` — 📡 Odtwarzaj Radio Zet\n"
            "• `!eska` — 📡 Odtwarzaj Radio Eska\n"
            "• `!volume [0-100]` — 🔊 Ustaw głośność odtwarzania"
        ),
        inline=False
    )

    # 🐾 Zwierzaki & Random
    embed.add_field(
        name="🌟 **Random & Zwierzaki**",
        value=(
            "• `!pies` — 🐶 Losowy piesek\n"
            "• `!kot` — 🐱 Losowy kot\n"
            "• `!lis` — 🦊 Losowy lisek (gif)\n"
            "• `!food` — 🍔 Random jedzenie\n"
            "• `!yesno` — 🎲 Tak albo Nie\n"
            "• `!vagrant` — 🖼️ Losowy vagrant\n"
            "• `!gift [@gracz]` — 🎁 Podaruj prezent wybranemu graczowi"
        ),
        inline=False
    )

    # 🗑️ Śmieci
    embed.add_field(
        name="🗑️ **Śmieci**",
        value=(
            "• `!smiec [nazwa]` — Dodaj kogoś do listy śmieci\n"
            "• `!smiecie` — Wyświetl listę śmieci\n"
            "• `!czyscsmieci` — Wyczyść listę śmieci"
        ),
        inline=False
    )

    # 🏅 Pojedynki / Mecze
    embed.add_field(
        name="🏅 **Pojedynki & Mecze**",
        value=(
            "• `!mecz (gracz1) / (gracz2) (Wynik np. 3:0)` — Zapisuje wynik graczy\n"
            "• `!pojedynki` / `!mecze` — Wyświetla wyniki wszystkich graczy\n"
            "• `!wynik (gracz)` — Wyświetla wynik meczy konkretnego gracza"
        ),
        inline=False
    )

    embed.set_footer(
        text=f"📨 Wywołano przez: {ctx.author.name}",
        icon_url=ctx.author.avatar.url if ctx.author.avatar else None
    )

    await ctx.send(embed=embed)

#zlote przeboje
#zlote przeboje
#zlote przeboje
#zlote przeboje


@bot.command(aliases=["złoteprzeboje"])
async def zloteprzeboje(ctx):
    if not ctx.author.voice:
        await ctx.send("❌ Musisz być na kanale głosowym!")
        return

    channel = ctx.author.voice.channel
    voice = ctx.voice_client

    if voice is None:
        voice = await channel.connect()
    elif voice.channel != channel:
        await voice.move_to(channel)

    stream_url = "https://radiostream.pl/tuba8914-1.mp3"

    try:
        if voice.is_playing():
            voice.stop()

        source = discord.FFmpegPCMAudio(
            stream_url,
            before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
            options="-vn"
        )
        voice.play(source, after=lambda e: print("✅ Radio Złote Przeboje zakończone."))
        await ctx.send("📻 Odtwarzam **Radio Złote Przeboje**!")
    except Exception as e:
        await ctx.send(f"❌ Błąd odtwarzania: {e}")



#rmf max

@bot.command(aliases=["rmfmaxxx","max","rmfmax"])
async def maxxx(ctx):
    if not ctx.author.voice:
        await ctx.send("❌ Musisz być na kanale głosowym!")
        return

    channel = ctx.author.voice.channel
    voice = ctx.voice_client

    if voice is None:
        voice = await channel.connect()
    elif voice.channel != channel:
        await voice.move_to(channel)

    stream_url = "https://rs202-krk.rmfstream.pl/RMFMAXXX48"

    try:
        if voice.is_playing():
            voice.stop()

        source = discord.FFmpegPCMAudio(
            stream_url,
            before_options="-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
            options="-vn"
        )
        voice.play(source, after=lambda e: print("✅ Radio RMF MAXXX zakończone."))
        await ctx.send("🎧 Odtwarzam **RMF MAXXX**!")
    except Exception as e:
        await ctx.send(f"❌ Błąd odtwarzania: {e}")




# Cooldown: 1 użycie na 10 sekund per użytkownik
@bot.command()
@commands.cooldown(1, 10, commands.BucketType.user)
async def gunar(ctx):
    bronie_ar2 = [
          # Assault Carbines
        "SKS", "XM177", "AKS-74U", "Patriot", "Operator M4A1",
        # Assault Rifles
        "AC-556", "AUG", "AK-47", "AKM", "M16A1", "M16A2", "AK-74",
        # Battle Rifles
        "FAL", "G3", "M1 Garand", "M14", "SVT-40",
        # Carbines
        "Camp Carbine", "Model 44 Carbine", "M1 Carbine", "M2 Carbine", "Mosin-Nagant M44",
        # Light Machine Guns
        "M1918A2 BAR", "M1919A6", "M249 SAW", "M249 Paratrooper", "M60", "RPK", "PKM", "Trooper M1919A6",
        # Marksman Rifles
        "M21 DMR", "M1903 Springfield", "Model 788", "Model 788 Carbine", "PSG-1", "Dragunov", "Mosin-Nagant PU",
        # Rifles
        "Mini-14", "Model 94", "Model 94 Ranger",
        # Sniper Rifles
        "L96A1", "M40A1",
        # Shotguns
        "Auto-5", "Coach Gun", "Maverick 88", "Maverick 88 Tactical", "SPAS-12", "Boomstick Coach Gun",
        # Submachine Guns
        "M1 Thompson", "M3A1", "MP5", "MAT-49", "MP 40", "PP-19 Bizon",
        # Machine Pistols
        "MAC-10", "TEC-9", "Skorpion vz.65", "Sweeper Desert Eagle", "Snake's MAC-10",
        # Pistols
        "Desert Eagle", "Hi-Power", "G17", "M1911", "M9", "Model 459", "P38", "P220", "Makarov", "Silent Partner M1911",
        # Revolvers
        "Model 29", "Snubnose", "Python",
        # Short Rifles
        "Stunted AK-47", "Obrez Mosin-Nagant",
        # More Shotguns
        "Lupara", "Broadside Lupara",
        # More SMGs
        "MP5K", "UZI", "AO-46", "Rogue UZI",
        # Event/Unobtainable
        "Avtomat Makarov", "M1918 Tankgewehr", "Santa's Pig"
    ]

    wybrana_bron = random.choice(bronie_ar2)
    await ctx.send(f"🔫 Wylosowano broń z AR2: **{wybrana_bron}**")

@bot.command()
async def sgunar(ctx):
    secondary_weapons = [
        # Machine Pistols
        "MAC-10", "TEC-9", "Skorpion vz.65", "Sweeper Desert Eagle", "Snake's MAC-10",
        # Pistols
        "Desert Eagle", "Hi-Power", "G17", "M1911", "M9", "Model 459", "P38", "P220",
        "Makarov", "Silent Partner M1911",
        # Revolvers
        "Model 29", "Snubnose", "Python",
        # Short rifles / shotguns
        "Stunted AK-47", "Obrez Mosin-Nagant", "Lupara", "Broadside Lupara",
        # Secondary SMGs
        "MP5K", "UZI", "AO-46", "Rogue UZI"
    ]

    wybrana = random.choice(secondary_weapons)
    await ctx.send(f"🔫 Twoja **secondary** broń z AR2 to: **{wybrana}**")

@bot.command()
async def pgunar(ctx):
    primary_weapons = [
        # Assault Carbines
        "SKS", "XM177", "AKS-74U", "Patriot", "Operator M4A1",

        # Assault Rifles
        "AC-556", "AUG", "AK-47", "AKM", "M16A1", "M16A2", "AK-74",

        # Battle Rifles
        "FAL", "G3", "M1 Garand", "M14", "SVT-40",

        # Carbines
        "Camp Carbine", "Model 44 Carbine", "M1 Carbine", "M2 Carbine", "Mosin-Nagant M44",

        # Light Machine Guns
        "M1918A2 BAR", "M1919A6", "M249 SAW", "M249 Paratrooper",
        "M60", "RPK", "PKM", "Trooper M1919A6",

        # Marksman Rifles
        "M21 DMR", "M1903 Springfield", "Model 788", "Model 788 Carbine",
        "PSG-1", "Dragunov", "Mosin-Nagant PU",

        # Rifles
        "Mini-14", "Model 94", "Model 94 Ranger",

        # Sniper Rifles
        "L96A1", "M40A1"
    ]

    wybrana = random.choice(primary_weapons)
    await ctx.send(f"💥 Twoja **primary** broń z AR2 to: **{wybrana}**")

@bot.command()
async def attachments(ctx):
    attachments = [
        # 🔭 Optics
        "CQR Sight", "Holographic Sight", "Kobra Sight", "Soviet Reflex Sight",
        "Reflex Sight", "OCR Sight", "Pelican Scope", "Prism Scope", "Rifle Scope",
        # 🔇 Barrel (Suppressors)
        "Oil Filter Suppressor", "Military Suppressor", "Heavy Standard Suppressor",
        "Standard Suppressor", "Soviet Military Suppressor", "Professional Suppressor",
        "NATO Operator Suppressor", "Soviet Spetsnaz Suppressor",
        # 🎯 Underbarrel
        "Laser Sight", "Green Laser Sight", "Pink Laser Sight",
        "Folding Foregrip", "Short Foregrip", "Straight Foregrip"
    ]

    selected = random.choice(attachments)
    await ctx.send(f"🔧 Wylosowany attachment z **AR2**: **{selected}**")


@bot.command()
async def sights(ctx):
    sights = [
        "CQR Sight", "Holographic Sight", "Kobra Sight",
        "Soviet Reflex Sight", "Reflex Sight", "OCR Sight",
        "Pelican Scope", "Prism Scope", "Rifle Scope"
    ]

    wybrany = random.choice(sights)
    await ctx.send(f"🔭 Wylosowany celownik z **AR2**: **{wybrany}**")

@bot.command()
async def silencers(ctx):
    silencers = [
        "Oil Filter Suppressor",
        "Military Suppressor",
        "Heavy Standard Suppressor",
        "Standard Suppressor",
        "Soviet Military Suppressor",
        "Professional Suppressor",
        "NATO Operator Suppressor",
        "Soviet Spetsnaz Suppressor"
    ]

    wybrany = random.choice(silencers)
    await ctx.send(f"🔇 Wylosowany tłumik z AR2: **{wybrany}**")

@bot.command()
async def grips(ctx):
    grips = [
        "Laser Sight",
        "Green Laser Sight",
        "Pink Laser Sight",
        "Folding Foregrip",
        "Short Foregrip",
        "Straight Foregrip"
    ]

    wybrany = random.choice(grips)
    await ctx.send(f"🖐️ Wylosowany grip z AR2: **{wybrany}**")

@bot.command(name="loadout", aliases=["zestaw"])
@commands.cooldown(rate=1, per=10, type=commands.BucketType.user)
async def loadout(ctx):
    primary_weapons = [
        "M16A1", "AK-47", "M14", "FAL", "M1 Garand", "M1 Carbine", "M249 SAW", "M60", "RPK", "PKM",
        "M1903 Springfield", "Model 788", "PSG-1", "Dragunov", "M21 DMR", "Mini-14", "Model 94",
        "Model 94 Ranger", "M1 Thompson", "M14 DMR", "M16A2", "AUG", "Coach Gun", "Maverick 88", 
        "Maverick 88 Tactical", "Spas-12", "Auto-5", "M3A1", "PP-bizon19", "M2-Carbine", "Nosin-nagant"
        "SKS", "Patriot", "AC-556", "AKM", "AK-74", "M1919A2 BAR", "G3", "AS VAL", "AK-47", "XM177","l96A1", "M40A1"
    ]

    secondary_weapons = [
        "Desert Eagle", "Hi-Power", "G17", "M1911", "M9", "Model 459", "P38", "P220", "Makarov",
        "MAC-10", "TEC-9", "Skorpion vz.65", "Sweeper Desert Eagle", "Snake's MAC-10", "MP5K", "UZI",
        "AO-46", "Rogue UZI", "Model 29", "Snubnose", "Python", "Grubek(bez)", "Silent partner", "Snake MAC10"
    ]

    primary_optics = [
        "CQR Sight", "Holographic Sight", "Kobra Sight", "Reflex Sight", "Reflex Sight", "CQR Sight", "Holographic Sight",
        "OCR Sight", "Pelican Scope", "Prism Scope", "Rifle Scope", "Bez sighta noobie", "Grubek(bez)"
    ]

    secondary_optics = [
         "Kobra Sight", "Reflex Sight", "bez sighta noobie"
    ]

    primary_suppressors = [
        "Oil Filter Suppressor", "Military Suppressor", "Standard Suppressor",
        "Soviet Military Suppressor", "Standard Suppressor", "NATO Operator Suppressor", "Soviet Spetsnaz Suppressor", "Grubek(bez)"
    ]

    secondary_suppressors = [
        "Oil Filter Suppressor", "Standard Suppressor", "bez"
    ]

    primary_grips = [
        "Laser Sight", "Green Laser Sight", "Pink Laser Sight", "Folding Foregrip", "Short Foregrip", "Straight Foregrip", "bez"
    ]

    secondary_grips = [
        "Laser Sight", "Green Laser Sight", "Pink Laser Sight", "bez"
    ]

    # Losowanie
    primary = random.choice(primary_weapons)
    secondary = random.choice(secondary_weapons)

    primary_optic = random.choice(primary_optics)
    secondary_optic = random.choice(secondary_optics)

    primary_suppressor = random.choice(primary_suppressors)
    secondary_suppressor = random.choice(secondary_suppressors)

    primary_grip = random.choice(primary_grips)
    secondary_grip = random.choice(secondary_grips)

    # Tworzenie embeda
    embed = discord.Embed(title="🔫 Twój losowy loadout z Apocalypse Rising 2", color=0x1abc9c)
    embed.add_field(name="🔹 Broń główna", value=f"**{primary}**", inline=False)
    embed.add_field(name="• Celownik", value=primary_optic, inline=True)
    embed.add_field(name="• Tłumik", value=primary_suppressor, inline=True)
    embed.add_field(name="• Grip", value=primary_grip, inline=True)

    embed.add_field(name="\u200B", value="\u200B", inline=False)

    embed.add_field(name="🔸 Broń boczna", value=f"**{secondary}**", inline=False)
    embed.add_field(name="• Celownik", value=secondary_optic, inline=True)
    embed.add_field(name="• Tłumik", value=secondary_suppressor, inline=True)
    embed.add_field(name="• Grip", value=secondary_grip, inline=True)

    await ctx.send(embed=embed)

@loadout.error
async def loadout_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"⏳ Poczekaj jeszcze {error.retry_after:.1f} sekund zanim użyjesz tej komendy ponownie.")

@bot.command(name="privloadout")
@commands.cooldown(rate=1, per=10, type=commands.BucketType.user)
async def privloadout(ctx):
    primary_weapons = [
        "M16A1", "AK-47", "M14", "FAL", "M1 Garand", "M1 Carbine", "M249 SAW", "M60", "RPK", "PKM",
        "M1903 Springfield", "Model 788", "PSG-1", "Dragunov", "M21 DMR", "Mini-14", "Model 94",
        "Model 94 Ranger", "M1 Thompson", "M14 DMR", "M16A2", "AUG", "Coach Gun", "Maverick 88", 
        "Maverick 88 Tactical", "Spas-12", "Auto-5", "M3A1", "PP-bizon19", "M2-Carbine", "Nosin-nagant"
        "SKS", "Patriot", "AC-556", "AKM", "AK-74", "M1919A2 BAR", "G3", "AS VAL", "AK-47", "XM-177"
    ]

    secondary_weapons = [
        "Desert Eagle", "Hi-Power", "G17", "M1911", "M9", "Model 459", "P38", "P220", "Makarov",
        "MAC-10", "TEC-9", "Skorpion vz.65", "Sweeper Desert Eagle", "Snake's MAC-10", "MP5K", "UZI",
        "AO-46", "Rogue UZI", "Model 29", "Snubnose", "Python"
    ]

    primary_optics = [
        "CQR Sight", "Holographic Sight", "Kobra Sight", "Reflex Sight",
        "OCR Sight", "Pelican Scope", "Prism Scope", "Rifle Scope", "Bez sighta noobie"
    ]

    secondary_optics = [
        "Kobra Sight", "Reflex Sight", "Bez sighta noobie"
    ]

    primary_suppressors = [
        "Oil Filter Suppressor", "Military Suppressor", "Standard Suppressor", "Bez suppresora"
        "Military Suppressor", "Standard Suppressor", "NATO Operator Suppressor", "Soviet Spetsnaz Suppressor"
    ]

    secondary_suppressors = [
        "Oil Filter Suppressor", "Standard Suppressor"
    ]

    primary_grips = [
        "Laser Sight", "Green Laser Sight", "Pink Laser Sight", "Folding Foregrip", "Short Foregrip", "Straight Foregrip"
    ]

    secondary_grips = [
        "Laser Sight", "Green Laser Sight", "Pink Laser Sight"
    ]

    # Losowanie
    primary = random.choice(primary_weapons)
    secondary = random.choice(secondary_weapons)
    primary_optic = random.choice(primary_optics)
    secondary_optic = random.choice(secondary_optics)
    primary_suppressor = random.choice(primary_suppressors)
    secondary_suppressor = random.choice(secondary_suppressors)
    primary_grip = random.choice(primary_grips)
    secondary_grip = random.choice(secondary_grips)

    # Tworzenie embeda
    embed = discord.Embed(title="🔫 Twój losowy loadout z Apocalypse Rising 2", color=0x1abc9c)
    embed.add_field(name="🔹 Broń główna", value=f"**{primary}**", inline=False)
    embed.add_field(name="• Celownik", value=primary_optic, inline=True)
    embed.add_field(name="• Tłumik", value=primary_suppressor, inline=True)
    embed.add_field(name="• Grip", value=primary_grip, inline=True)
    embed.add_field(name="\u200B", value="\u200B", inline=False)
    embed.add_field(name="🔸 Broń boczna", value=f"**{secondary}**", inline=False)
    embed.add_field(name="• Celownik", value=secondary_optic, inline=True)
    embed.add_field(name="• Tłumik", value=secondary_suppressor, inline=True)
    embed.add_field(name="• Grip", value=secondary_grip, inline=True)

    try:
        await ctx.author.send(embed=embed)
        await ctx.send("📩 Loadout został wysłany na Twojego DM.")
    except discord.Forbidden:
        await ctx.send("❌ Nie mogłem wysłać wiadomości prywatnej – sprawdź ustawienia prywatności.")



@bot.command(name="dobryloadout")
@commands.cooldown(rate=1, per=10, type=commands.BucketType.user)
async def dobryloadout(ctx):
    # Dobre bronie główne
    primary_weapons = [
        "AK-47", "FAL", "M249 SAW", "PKM", "G3", "AS VAL", "AK-74", "AUG", "AKM", "AC-556"
    ]

    # Dobre bronie boczne
    secondary_weapons = [
        "Desert Eagle", "Snake's MAC-10", "Silent partner", "Python", "Sweeper Desert Eagle", "MAC-10", "MP5K"
    ]

    primary_optics = [
        "Holographic Sight", "Kobra Sight", "CQR Sight", "Reflex Sight"
    ]

    secondary_optics = [
        "Kobra Sight", "Reflex Sight"
    ]

    primary_suppressors = [
        "Military Suppressor", "Military Suppressor", "NATO Operator Suppressor", "Soviet Spetsnaz Suppressor"
    ]

    secondary_suppressors = [
        "Standard Suppressor"
    ]

    primary_grips = [
        "Laser Sight", "Green Laser Sight", "Folding Foregrip", "Straight Foregrip"
    ]

    secondary_grips = [
        "Laser Sight", "Green Laser Sight"
    ]

    # Losowanie
    primary = random.choice(primary_weapons)
    secondary = random.choice(secondary_weapons)

    primary_optic = random.choice(primary_optics)
    secondary_optic = random.choice(secondary_optics)

    primary_suppressor = random.choice(primary_suppressors)
    secondary_suppressor = random.choice(secondary_suppressors)

    primary_grip = random.choice(primary_grips)
    secondary_grip = random.choice(secondary_grips)

    # Tworzenie embeda
    embed = discord.Embed(title="🎯 Twój DOBRY loadout z Apocalypse Rising 2", color=0xe67e22)
    embed.add_field(name="🔹 Broń główna", value=f"**{primary}**", inline=False)
    embed.add_field(name="• Celownik", value=primary_optic, inline=True)
    embed.add_field(name="• Tłumik", value=primary_suppressor, inline=True)
    embed.add_field(name="• Grip", value=primary_grip, inline=True)

    embed.add_field(name="\u200B", value="\u200B", inline=False)

    embed.add_field(name="🔸 Broń boczna", value=f"**{secondary}**", inline=False)
    embed.add_field(name="• Celownik", value=secondary_optic, inline=True)
    embed.add_field(name="• Tłumik", value=secondary_suppressor, inline=True)
    embed.add_field(name="• Grip", value=secondary_grip, inline=True)

    await ctx.send(embed=embed)

@dobryloadout.error
async def dobryloadout_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"⏳ Poczekaj jeszcze {error.retry_after:.1f} sekund zanim użyjesz tej komendy ponownie.")





FILE_NAME = "smiecie.txt"

@bot.command()
@commands.cooldown(rate=1, per=120, type=commands.BucketType.user)
async def smiec(ctx, *, nazwa: str):
    """Dodaje wpis do pliku smiecie.txt jeśli go tam jeszcze nie ma."""
    if not os.path.exists(FILE_NAME):
        with open(FILE_NAME, "w", encoding="utf-8") as f:
            pass

    with open(FILE_NAME, "r", encoding="utf-8") as f:
        lines = [line.strip().lower() for line in f if line.strip()]

    if nazwa.lower() in lines:
        await ctx.send(f"❗ '{nazwa}' już jest na liście śmieci, nie dodaję ponownie.")
        return

    with open(FILE_NAME, "a", encoding="utf-8") as f:
        f.write(nazwa + "\n")

    await ctx.send(f"✅ Dodano '{nazwa}' do listy śmieci.")

@bot.command()
@commands.cooldown(rate=1, per=120, type=commands.BucketType.user)
async def smiecie(ctx):
    """Wyświetla zawartość pliku smiecie.txt jako listę."""
    if not os.path.exists(FILE_NAME):
        await ctx.send("Lista śmieci jest pusta.")
        return

    with open(FILE_NAME, "r", encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    if not lines:
        await ctx.send("Lista śmieci jest pusta.")
        return

    lista = "\n".join(f"{i+1}. {item}" for i, item in enumerate(lines))
    embed = discord.Embed(title="🗑️ Lista śmieci", description=lista, color=0x7289da)
    await ctx.send(embed=embed)

@bot.command()
@commands.cooldown(rate=1, per=120, type=commands.BucketType.user)
async def czyscsmieci(ctx):
    """Czyści cały plik smiecie.txt."""
    try:
        with open(FILE_NAME, "w", encoding="utf-8") as f:
            pass

        await ctx.send("✅ Lista śmieci została wyczyszczona.")
    except Exception as e:
        await ctx.send(f"❌ Wystąpił błąd podczas czyszczenia listy śmieci: {e}")

# Dodaj też obsługę błędów cooldownu, jeśli chcesz, np:

@smiec.error
@smiecie.error
@czyscsmieci.error
async def cooldown_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"⏳ Ta komenda jest na cooldownie. Spróbuj ponownie za {int(error.retry_after)} sekund.")
    else:
        raise error

@bot.command()
async def radiozet(ctx):
    if ctx.author.voice is None or ctx.author.voice.channel is None:
        await ctx.send("❌ Musisz być na kanale głosowym, aby użyć tej komendy.")
        return

    voice_channel = ctx.author.voice.channel
    voice_client = ctx.guild.voice_client

    try:
        if voice_client is not None:
            if voice_client.channel != voice_channel:
                await voice_client.move_to(voice_channel)
        else:
            voice_client = await voice_channel.connect()

        radio_url = "https://n-4-6.dcs.redcdn.pl/sc/o2/Eurozet/live/audio.livx"

        voice_client.stop()
        source = discord.FFmpegPCMAudio(radio_url)
        voice_client.play(source)

        embed = discord.Embed(
            title="📻 Radio Zet",
            description=f"▶️ **Rozpoczęto odtwarzanie Radio Zet** na kanale `{voice_channel.name}`!",
            color=discord.Color.red()
        )

        embed.set_footer(text="🔫 Agenci zostali wysłani do wrogów")
        embed.set_author(name=ctx.author.display_name, icon_url=ctx.author.avatar.url if ctx.author.avatar else None)

        await ctx.send(embed=embed)

    except Exception as e:
        await ctx.send(f"❌ Wystąpił błąd podczas odtwarzania radia: {e}")

 

@bot.command()
async def eska(ctx):
    if ctx.author.voice is None or ctx.author.voice.channel is None:
        await ctx.send("❌ Musisz być na kanale głosowym, aby użyć tej komendy.")
        return

    voice_channel = ctx.author.voice.channel
    voice_client = ctx.guild.voice_client

    try:
        if voice_client is not None:
            if voice_client.channel != voice_channel:
                await voice_client.move_to(voice_channel)
        else:
            voice_client = await voice_channel.connect()

        radio_url = "https://radio.stream.smcdn.pl/timeradio-p/2380-2.aac/playlist.m3u8"

        voice_client.stop()
        source = discord.FFmpegPCMAudio(radio_url)
        voice_client.play(source)

        embed = discord.Embed(
            title="🎶 Radio Eska 🎶",
            description=f"**▶️ Odtwarzam Radio Eska na kanale __{voice_channel.name}__!**",
            color=0x1abc9c
        )
        embed.add_field(name="🎤 Wywołane przez:", value=f"**{ctx.author.mention}**", inline=False)
        embed.set_footer(text="🎯 +25% do aima! 🔥✨")

        await ctx.send(embed=embed)

    except Exception as e:
        await ctx.send(f"❌ Wystąpił błąd podczas odtwarzania radia: {e}")


@bot.command()
async def mapa(ctx):
    mapa_url = "https://static.wikia.nocookie.net/roblox-apocalypse-rising/images/e/e2/Beta_Map.png/revision/latest/scale-to-width-down/1000?cb=20240427030649"
    embed = discord.Embed(title="🗺️ Mapa Apocalypse Rising 2", color=0x00ff00)
    embed.set_image(url=mapa_url)
    await ctx.send(embed=embed)





@bot.command(name="sniper")
@commands.cooldown(rate=1, per=10, type=commands.BucketType.user)
async def sniper(ctx):
    sniper_rifles = [
        "M1903 Springfield", "Model 788", "PSG-1", "Dragunov", "M21 DMR", "Mini-14",
        "M14 DMR", "Model 94 Ranger", "Pelican PSG", "Nosin-nagant", "SKS", "L96A1", "M40A1"
    ]

    secondary_weapons = [
        "Desert Eagle", "Model 29", "Python", "Snubnose", "MAC-10", "Snake's MAC-10", "TEC-9", "Silent partner"
    ]

    optics = [
        "Pelican Scope", "Rifle Scope", "Prism Scope", "CQR Sight", "Bez sighta noobie"
    ]

    suppressors = [
        "Oil Filter Suppressor", "Standard Suppressor", "Military Suppressor", "bez"
    ]

    grips = [
        "Laser Sight", "Green Laser Sight", "Pink Laser Sight", "bez"
    ]

    # Losowanie
    sniper = random.choice(sniper_rifles)
    secondary = random.choice(secondary_weapons)

    sniper_optic = random.choice(optics)
    secondary_optic = random.choice(["Kobra Sight", "Reflex Sight", "bez sighta noobie"])

    sniper_suppressor = random.choice(suppressors)
    secondary_suppressor = random.choice(suppressors)

    sniper_grip = random.choice(grips)
    secondary_grip = random.choice(grips)

    # Tworzenie embeda
    embed = discord.Embed(title="🎯 Twój loadout snajpera z AR2", color=0x7289da)
    embed.add_field(name="🔹 Karabin snajperski", value=f"**{sniper}**", inline=False)
    embed.add_field(name="• Celownik", value=sniper_optic, inline=True)
    embed.add_field(name="• Tłumik", value=sniper_suppressor, inline=True)
    embed.add_field(name="• Grip", value=sniper_grip, inline=True)

    embed.add_field(name="\u200B", value="\u200B", inline=False)

    embed.add_field(name="🔸 Broń boczna", value=f"**{secondary}**", inline=False)
    embed.add_field(name="• Celownik", value=secondary_optic, inline=True)
    embed.add_field(name="• Tłumik", value=secondary_suppressor, inline=True)
    embed.add_field(name="• Grip", value=secondary_grip, inline=True)

    embed.set_footer(text="🎖️ Snipe z dystansu, nie z emocji 😎")

    await ctx.send(embed=embed)



@bot.command(name="rusher", aliases=["szturmowiec", "rusz", "rush"])
@commands.cooldown(rate=1, per=10, type=commands.BucketType.user)
async def rusher(ctx):
    primary_rusher_weapons = [
        "M1 Thompson", "MAC-10", "PP-bizon19", "Maverick 88", "Maverick 88 Tactical", "Spas-12",
        "Coach Gun", "Auto-5", "AK-74", "AS VAL"
    ]

    secondary_rusher_weapons = [
        "MAC-10", "TEC-9", "Skorpion vz.65", "UZI", "Snake's MAC-10", "Silent partner", "Snubnose", "Desert Eagle"
    ]

    optics = [
        "Reflex Sight", "Kobra Sight", "CQR Sight", "bez sighta noobie"
    ]

    suppressors = [
        "Oil Filter Suppressor", "Standard Suppressor", "bez"
    ]

    grips = [
        "Laser Sight", "Green Laser Sight", "Pink Laser Sight", "Folding Foregrip", "Short Foregrip", "bez"
    ]

    # Losowanie
    primary = random.choice(primary_rusher_weapons)
    secondary = random.choice(secondary_rusher_weapons)

    primary_optic = random.choice(optics)
    secondary_optic = random.choice(optics)

    primary_suppressor = random.choice(suppressors)
    secondary_suppressor = random.choice(suppressors)

    primary_grip = random.choice(grips)
    secondary_grip = random.choice(grips)

    # Tworzenie embeda
    embed = discord.Embed(title="⚡ Twój Rusher Loadout z AR2", color=0xff5733)
    embed.add_field(name="🔹 Broń główna (rush)", value=f"**{primary}**", inline=False)
    embed.add_field(name="• Celownik", value=primary_optic, inline=True)
    embed.add_field(name="• Tłumik", value=primary_suppressor, inline=True)
    embed.add_field(name="• Grip", value=primary_grip, inline=True)

    embed.add_field(name="\u200B", value="\u200B", inline=False)

    embed.add_field(name="🔸 Broń boczna", value=f"**{secondary}**", inline=False)
    embed.add_field(name="• Celownik", value=secondary_optic, inline=True)
    embed.add_field(name="• Tłumik", value=secondary_suppressor, inline=True)
    embed.add_field(name="• Grip", value=secondary_grip, inline=True)

    embed.set_footer(text="🏃‍♂️ Rushuj zanim cię zobaczą!")

    await ctx.send(embed=embed)







@bot.command(name="radia")
async def radia(ctx):
    embed = discord.Embed(
        title="📻 Lista dostępnych stacji radiowych i muzycznych komend",
        description="Wybierz swoje ulubione brzmienie i rozkręć kanał głosowy! 🎶",
        color=0x3498db
    )

    embed.add_field(
        name="🎶 **Muzyka & Radio**",
        value=(
            "• `!graj [nazwa]` — ▶️ Odtwórz utwór z YouTube\n"
            "• `!zloteprzeboje` — 📻 Złote Przeboje\n"
            "• `!rmffm` — 🎧 RMF FM\n"
            "• `!radiozet` — 📡 Radio Zet\n"
            "• `!eska` — 📡 Radio Eska"
        ),
        inline=False
    )

    embed.set_footer(text="🎧 Ciesz się dźwiękiem — Powered by TwojeRadioBot3000™")
    await ctx.send(embed=embed)



@bot.command(name="demolisher")
@commands.cooldown(rate=1, per=10, type=commands.BucketType.user)
async def demolisher(ctx):
    # Główna broń - ciężkie, niszczycielskie
    primary_weapons = [
        "M249 SAW", "M60", "RPK", "PKM", "Spas-12", "M249 Paratrooper"
        "M1919A2 BAR", "AS VAL", "AK-47", "AKM", "M14", "FAL", "Dragunov", "M21 DMR","XM-177"
    ]

    # Boczne - mocne pistolety lub SMG
    secondary_weapons = [
        "Desert Eagle", "Python", "Model 29", "MAC-10", "Sweeper Desert Eagle", "Snake's MAC-10"
    ]

    optics = [
        "Pelican Scope", "Holographic Sight", "Reflex Sight", "CQR Sight", "Bez sighta"
    ]

    suppressors = [
        "Standard Suppressor", "Military Suppressor", "Oil Filter Suppressor", "bez"
    ]

    grips = [
        "Folding Foregrip", "Short Foregrip", "Straight Foregrip", "Green Laser Sight", "bez"
    ]

    # Losowanie
    primary = random.choice(primary_weapons)
    secondary = random.choice(secondary_weapons)
    primary_optic = random.choice(optics)
    primary_suppressor = random.choice(suppressors)
    primary_grip = random.choice(grips)

    # Tworzenie embeda
    embed = discord.Embed(title="💥 Twój demolisher loadout z AR2", color=0xe74c3c)
    embed.add_field(name="🔹 Broń główna", value=f"**{primary}**", inline=False)
    embed.add_field(name="• Celownik", value=primary_optic, inline=True)
    embed.add_field(name="• Tłumik", value=primary_suppressor, inline=True)
    embed.add_field(name="• Grip", value=primary_grip, inline=True)

    embed.add_field(name="\u200B", value="\u200B", inline=False)

    embed.add_field(name="🔸 Broń boczna", value=f"**{secondary}**", inline=False)

    await ctx.send(embed=embed)







GIPHY_API_KEY = '1L4WJfniDOYyg9vgio8cyV0cZxR2gVo8'  # Zdobądź darmowy z https://developers.giphy.com/

@bot.command(name="dzik")
async def dzik(ctx):
    async with aiohttp.ClientSession() as session:
        params = {
            "api_key": GIPHY_API_KEY,
            "q": "wild boar",
            "limit": 25,
            "rating": "pg"
        }
        async with session.get("https://api.giphy.com/v1/gifs/search", params=params) as r:
            if r.status == 200:
                data = await r.json()
                gifs = data.get("data", [])
                if gifs:
                    gif_url = random.choice(gifs)["images"]["original"]["url"]

                    embed = discord.Embed(
                        title="Dzik: ",
                        description="Losowy dzik z lasu Internetu",
                        color=0x8B4513  # brązowy kolor dzika 😅
                    )
                    embed.set_image(url=gif_url)
                    await ctx.send(embed=embed)
                else:
                    await ctx.send("❌ Nie znaleziono dzików.")
            else:
                await ctx.send("⚠️ Błąd przy łączeniu z Giphy.")





@bot.command(name="ammo")
async def ammo(ctx, *, weapon_input: str):
    input_clean = weapon_input.strip().lower()

    # Wczytywanie aliasów z pliku
    aliases = {}
    try:
        with open("bronie.txt", "r", encoding="utf-8") as f:
            for line in f:
                if "=" in line:
                    key, value = line.strip().split("=", 1)
                    aliases[key.strip().lower()] = value.strip()
    except FileNotFoundError:
        await ctx.send("❌ Nie znaleziono pliku `bronie.txt`.")
        return

    # Nowa struktura: amunicja → lista broni
    ammo_groups = {
        "5.56x45mm NATO": ["M16A1", "M249 SAW", "Mini-14", "Aug", "M16A2", "AC-556", "M4A1","Operator M4A1", "Patriot", "XM177", "M249 Paratrooper"],
        "7.62x51mm NATO": ["M14", "FAL", "M60", "PSG-1", "G3", "M40A1", "M110","L96A1", "M21", "Model 788 Carbine", "MSG-90"],
        "7.62x39mm": ["AK-47", "SKS", "AKM", "RPK", "Stunted AK-47"],
        ".30-06 Springfield": ["M1 Garand", "M1903 Springfield", "M1918A2 BAR", "M1919A6", "Trooper M1919A6"],
        ".30 Carbine": ["M1 Carbine"],
        ".45 ACP": ["M1 Thompson", "MAC-10", "Snubnose"],
        "9x19mm Parabellum": ["M9", "MP5K", "Hi-Power", "G17", "P38", "MP40", "MP5","TEC-9", "UZI", "Rogue UZI", "Model 459", "Camp Carbine", "MAT-49"],
        ".50 AE": ["Desert Eagle"],
        ".357 Magnum": ["Python"],
        ".30-30 Winchester": ["Model 94", "Model 94 Ranger"],
        "12 Gauge": ["Coach Gun", "Spas-12", "Auto-5"],
        "7.62x54mmR": ["Dragunov"],
        "9x39mm": ["AS VAL"],
        ".38 Special": [],
        "7.62mm Plastic Balls" : ["Santa's Pig Machine Gun"]
    }

    # Mapa amunicji do miniatur
    ammo_thumbnails = {
        "5.56x45mm NATO": "https://static.wikia.nocookie.net/roblox-apocalypse-rising/images/7/78/Icon_ammo_556n.png/revision/latest/scale-to-width-down/90?cb=20240628224334",
        "7.62x51mm NATO": "https://static.wikia.nocookie.net/roblox-apocalypse-rising/images/5/56/Icon_ammo_762n.png/revision/latest/scale-to-width-down/90?cb=20240628224626",
        "7.62x39mm": "https://static.wikia.nocookie.net/roblox-apocalypse-rising/images/8/83/Icon_ammo_762sv.png/revision/latest/scale-to-width-down/90?cb=20231230000622",
        ".30-06 Springfield" : "https://static.wikia.nocookie.net/roblox-apocalypse-rising/images/8/8a/Icon_ammo_762sf.png/revision/latest/scale-to-width-down/90?cb=20231224033659",
        ".45 ACP": "https://static.wikia.nocookie.net/roblox-apocalypse-rising/images/6/68/Icon_ammo_45acp.png/revision/latest/scale-to-width-down/90?cb=20231224033322",
        "9x19mm Parabellum" : "https://static.wikia.nocookie.net/roblox-apocalypse-rising/images/5/5f/Icon_ammo_9mm.png/revision/latest/scale-to-width-down/90?cb=20231224033941",
        "7.62mm Plastic Balls" : "https://static.wikia.nocookie.net/roblox-apocalypse-rising/images/f/f0/%22Santa%27s_Pig%22.png/revision/latest?cb=20231230211528"
    }

    # Szukaj poprawnej nazwy broni
    proper_name = aliases.get(input_clean)
    if not proper_name:
        await ctx.send(f"❌ Nie rozpoznano broni: `{weapon_input}`.")
        return

    # Szukaj amunicji dla danej broni
    ammo = None
    for ammo_type, weapons in ammo_groups.items():
        if proper_name in weapons:
            ammo = ammo_type
            break

    if ammo:
        embed = discord.Embed(title="🔫 Informacje o amunicji", color=0x3498db)
        embed.add_field(name="Broń", value=proper_name, inline=False)
        embed.add_field(name="Amunicja", value=ammo, inline=False)

        # Ustaw miniaturkę jeśli istnieje dla tej amunicji
        thumbnail_url = ammo_thumbnails.get(ammo)
        if thumbnail_url:
            embed.set_thumbnail(url=thumbnail_url)

        await ctx.send(embed=embed)
    else:
        await ctx.send(f"❌ Nie znaleziono danych o amunicji dla `{proper_name}`.")











@bot.command(name="gift")
async def gift(ctx, member: discord.Member = None):
    if member is None:
        await ctx.send("❗ Użyj: `!gift @użytkownik` — musisz oznaczyć osobę, której chcesz wysłać prezent.")
        return

    try:
        # Losowy kod gift card
        platforms = {
            "Steam": lambda: f"{random.randint(10000, 99999)}-{random.randint(10000, 99999)}-{random.randint(10000, 99999)}",
            "Roblox": lambda: "".join(random.choices("ABCDEFGHJKLMNPQRSTUVWXYZ23456789", k=10)),
            "Xbox": lambda: f"{random.randint(1000,9999)}-{random.randint(1000,9999)}-{random.randint(1000,9999)}-{random.randint(1000,9999)}"
        }

        platform = random.choice(list(platforms.keys()))
        code = platforms[platform]()

        embed = discord.Embed(
            title="🎁 Masz nowy prezent!",
            description="Gratulacje! Poniżej znajdziesz swój kod 🎉",
            color=0xffa500
        )
        embed.add_field(name="💳 Platforma", value=platform, inline=True)
        embed.add_field(name="🔢 Kod", value=f"||{code}||", inline=False)
        embed.set_image(url="https://media.tenor.com/XatvpYJ2ut4AAAAC/check.gif")

        await member.send(embed=embed)
        await ctx.send(f"✅ Wysłano wiadomość prywatną z prezentem dla {member.mention}!")

    except discord.Forbidden:
        await ctx.send(f"❌ Nie mogę wysłać wiadomości — {member.mention} ma wyłączone DM-y.")
    except discord.HTTPException:
        await ctx.send("⚠️ Wystąpił błąd podczas wysyłania wiadomości.")





@bot.command()
async def volume(ctx, vol: int):
    await ctx.send("Spierdalaj to nie działa")





last_facts = {}

@bot.command(name="ciekawostki", aliases = ["ciekawostka"])
async def ciekawostki(ctx):
    user_id = ctx.author.id
    try:
        with open("ciekawostki.txt", "r", encoding="utf-8") as file:
            lines = [line.strip() for line in file if line.strip()]
            
            if not lines:
                await ctx.send("Brak ciekawostek w pliku.")
                return

            # Usuń ostatnią ciekawostkę użytkownika z możliwych (jeśli istnieje i jest więcej niż 1)
            possible_choices = lines.copy()
            if user_id in last_facts and len(lines) > 1:
                try:
                    possible_choices.remove(last_facts[user_id])
                except ValueError:
                    pass  # W razie jakby ciekawostka nie istniała w aktualnym zbiorze

            random_line = random.choice(possible_choices)
            last_facts[user_id] = random_line  # Zapisz ostatnią dla danego użytkownika

            embed = discord.Embed(
                title="Ciekawostka",
                description=random_line,
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)

    except FileNotFoundError:
        await ctx.send("Plik 'ciekawostki.txt' nie został znaleziony.")
    except Exception as e:
        await ctx.send(f"Wystąpił błąd: {e}")



@bot.command(name="leaderboard")
async def leaderboard(ctx):
    players = [
        ("GrubeRs71", 987),
        ("Kokonutree2", 1),
        ("MyDadBuilderman", 890),
        ("frank_84848", 324),
        ("FilipoPL", 765),
        ("ILikeTrains123321", 432),
        ("23x99x11", 543),
        ("Majtczak", 876),
        ("wawacat_OhTheMisery", 654),
        ("AndrzejDudusPIS", 321),
        ("xkondzix1", 234),
        ("kupasia", 567)
    ]

    players.sort(key=lambda x: x[1], reverse=True)

    # Formatowanie tekstu
    player_lines = [f"{i+1:>2}. {name:<20}" for i, (name, _) in enumerate(players)]
    kill_lines = [f"{kills:>4}" for _, kills in players]

    player_block = "\n".join(player_lines)
    kill_block = "\n".join(kill_lines)

    embed = discord.Embed(
        title="🏆 AR2 Leaderboard",
        color=discord.Color.purple()
    )
    embed.set_author(
        name="Apocalypse Rising 2",
        icon_url="https://static.wikia.nocookie.net/roblox-apocalypse-rising/images/e/e6/Site-logo.png/revision/latest?cb=20231229233745"
    )

    embed.add_field(
        name="Gracze",
        value=f"```{player_block}```",
        inline=True
    )
    embed.add_field(
        name="Zabójstwa",
        value=f"```{kill_block}```",
        inline=True
    )

    await ctx.send(embed=embed)


@bot.command(name="pojedynek", aliases=["mecz"])
#@commands.has_permissions(administrator=True)
async def pojedynek(ctx, member1: discord.Member, separator: str, member2: discord.Member, result: str):
    try:
        if separator != "/":
            await ctx.send("❌ Poprawny format: `!pojedynek @gracz1 / @gracz2 wynik`, np. `!pojedynek @ktos / @ktos2 1:0`")
            return

        # Rozbij wynik
        try:
            score1, score2 = map(int, result.strip().split(":"))
        except ValueError:
            await ctx.send("❌ Nieprawidłowy format wyniku. Użyj `1:0`, `3:2`, itp.")
            return

        name1 = member1.display_name
        name2 = member2.display_name

        # Zapis do pliku
        with open("pojedynek.txt", "a", encoding="utf-8") as f:
            f.write(f"**{name1}** vs **{name2}**\nWynik: {score1}:{score2}\n\n")

        # Wyśrodkowanie wyniku względem długości nazw
        max_len = max(len(name1), len(name2))
        name1_padded = name1.ljust(max_len)
        name2_padded = name2.ljust(max_len)
        score_line = f"{str(score1).center(max_len)}:{str(score2).center(max_len)}"

        # Tworzenie embeda
        embed = discord.Embed(
            title="Apocalypse Rising VERSUSY",
            description=f"**{name1_padded} 🆚 {name2_padded}**\n`{score_line}`",
            color=discord.Color.red()
        )

        await ctx.send(embed=embed)

    except Exception as e:
        await ctx.send(f"❌ Wystąpił błąd: {e}")




@bot.command(name="pojedynki", aliases=["mecze"])
async def pojedynki(ctx):
    try:
        with open("pojedynek.txt", "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f if line.strip()]

        if not lines:
            await ctx.send("📭 Brak zapisanych pojedynków.")
            return

        # Tworzenie embeda
        embed = discord.Embed(
            title="📜 Historia pojedynków",
            description="",
            color=discord.Color.gold()
        )

        # Dodaj wszystkie linie jako opis w embedzie (ograniczenie do 4096 znaków)
        full_text = "\n".join(lines)
        if len(full_text) > 4096:
            full_text = full_text[:4093] + "..."

        embed.description = f"```{full_text}```"
        await ctx.send(embed=embed)

    except FileNotFoundError:
        await ctx.send("❌ Plik `pojedynek.txt` nie istnieje.")
    except Exception as e:
        await ctx.send(f"❌ Wystąpił błąd: {e}")




@bot.command(name="wyniki")
async def wyniki_uzytkownika(ctx, member: discord.Member):
    try:
        username = member.display_name

        try:
            with open("pojedynek.txt", "r", encoding="utf-8") as f:
                lines = f.readlines()
        except FileNotFoundError:
            await ctx.send("❌ Brak zapisanych pojedynków.")
            return

        # Filtruj linie zawierające nazwę użytkownika
        filtered_lines = [line.strip() for line in lines if username in line]

        if not filtered_lines:
            await ctx.send(f"ℹ️ Użytkownik **{username}** nie ma żadnych zapisanych wyników.")
            return

        # Stwórz embed z wynikami
        embed = discord.Embed(
            title=f"📊 Pojedynki użytkownika {username}",
            description="\n".join(filtered_lines),
            color=discord.Color.orange()
        )
        await ctx.send(embed=embed)

    except Exception as e:
        await ctx.send(f"❌ Wystąpił błąd: {e}")




@bot.command(name="serverinfo")
@commands.cooldown(1, 300, commands.BucketType.guild)  # cooldown 5 minut na serwer
async def serverinfo(ctx):
    place_id = "863266079"
    url = f"https://games.roblox.com/v1/games/{place_id}/servers/Public?sortOrder=Desc&limit=100"

    async with aiohttp.ClientSession() as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                await ctx.send("❌ Nie udało się pobrać danych o serwerach.")
                return
            data = await resp.json()
            servers = data.get("data", [])
            total_players = sum(server.get("playing", 0) for server in servers)

            embed = discord.Embed(
                title=f"🎮Graczy online: {total_players}",
                description="**Apocalypse Rising 2 - Aniołki**",
                color=discord.Color.red()
            )
            embed.set_footer(text=f"Poprosił: {ctx.author}", icon_url=ctx.author.avatar.url if ctx.author.avatar else None)

            await ctx.send(embed=embed)

@serverinfo.error
async def serverinfo_error(ctx, error):
    if isinstance(error, commands.CommandOnCooldown):
        seconds = int(error.retry_after)
        await ctx.send(f"⏳ Ta komenda jest na cooldownie. Spróbuj ponownie za {seconds} sekund.")






#@bot.command()
#async def shop(ctx):
 #   embed = discord.Embed(
 #       title="🛒 Sklep AR2",
 #       description="Wydaj swoje monety na przydatne rzeczy w świecie Apocalypse Rising!",
 #       color=discord.Color.green()
 #   )
#
  #  embed.add_field(name="🔫 Zestaw Startowy", value="Zawiera pistolet i apteczkę.\n💵 Cena: 200 monet", inline=False)
 #   embed.add_field(name="🚗 Pojazd terenowy", value="Szybsze przemieszczanie po mapie.\n💵 Cena: 500 monet", inline=False)
  #  embed.add_field(name="🎯 Mapa łupów", value="Odkrywa lokalizacje rzadkiego ekwipunku.\n💵 Cena: 350 monet", inline=False)
 ##   embed.add_field(name="🧢 Kamuflaż", value="Zmniejsza szansę wykrycia przez innych graczy.\n💵 Cena: 400 monet", inline=False)
#    embed.set_footer(text="Użyj !buy <nazwa_przedmiotu>, aby dokonać zakupu.")
#
 #   await ctx.send(embed=embed)






# Lista przekleństw (można rozbudować)
PRZEKLENSTWA = [
    "kurwa", "chuj", "pierdole", "jebac", "zjeb", "huj", "fuck", "shit", "dziwka",
    "skurwiel", "skurwysyn", "pierdol się", "pierdolony", "dupka", "jebany",
    "ciota", "cipka", "kutas", "zajebisty", "spierdalaj", "pizda", "pizdzisz",
    "gówno", "kurwiarz", "kurwa mać", "kurestwo", "kurwica", "zajebać",
    "jebnięty", "wypierdalaj", "odpierdalaj", "szmata", "sukinsyn", "pieprzony",
    "do dupy", "pierdol", "kutasie", "cioto", "dupa", "dupku", "zjebany",
    "jebać", "jebana", "jebać cię", "kurwo", "kurwy", "cwel", "śmierdziel",
    "fiut", "fiucie", "pizdowaty", "dupek", "pierdolisz", "chujowy", "chujowa",
    "chujem", "pierdolić", "pieprz się", "gówniarz", "wypierdalać", "chujnia",
    "jebac cie", "wypierdalaj kurwo", "pizdo jebana", "pizdo", "kurwo",
    "jebany chuju", "pierdol sie", "zjebie", "skurwysynie", "kurwidołek", "pizde", "cipa"
]
# Lista kanałów do monitorowania
MONITOROWANE_KANALY = [1041423745002254368, 123456789012345678]  # <-- dodaj więcej ID tutaj

# Licznik ostrzeżeń dla użytkowników
ostrzezenia = defaultdict(int)

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    if message.channel.id not in MONITOROWANE_KANALY:
        return

    tresc = message.content.lower()
    if any(w in tresc for w in PRZEKLENSTWA):
        user = message.author
        ostrzezenia[user.id] += 1

        await message.reply(f"❗ Nie wolno przeklinać! Ostrzeżenie {ostrzezenia[user.id]}/3")

        if ostrzezenia[user.id] >= 3:
            try:
                await user.timeout(timedelta(minutes=5), reason="Przeklinanie – 3 ostrzeżenia")
                await message.channel.send(f"🔇 {user.mention} został wyciszony na 5 minut za przeklinanie.")
                ostrzezenia[user.id] = 0  # reset ostrzeżeń po wyciszeniu
            except discord.Forbidden:
                await message.channel.send("❌ Nie mam uprawnień, by wyciszyć tego użytkownika.")
            except Exception as e:
                await message.channel.send(f"⚠️ Błąd: {e}")

    await bot.process_commands(message)












bot.run(os.getenv("TOKEN"))



