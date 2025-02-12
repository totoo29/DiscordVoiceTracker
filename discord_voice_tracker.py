import discord
from discord.ext import tasks, commands
import sqlite3
from datetime import datetime, timedelta
import random
import asyncio

# Configura tu token de bot
TOKEN = 'TOKEN DE DS'

# Configuración del bot
intents = discord.Intents.default()
intents.voice_states = True
intents.guilds = True
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Configuración de la base de datos
conn = sqlite3.connect('voice_activity.db')
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS voice_activity (
                user_id INTEGER,
                join_time TEXT,
                duration INTEGER DEFAULT 0
            )''')
c.execute('''CREATE TABLE IF NOT EXISTS config (
                key TEXT PRIMARY KEY,
                value TEXT
            )''')
conn.commit()

# Diccionario para rastrear el tiempo de conexión actual
active_sessions = {}

@bot.event
async def on_ready():
    print(f'Bot conectado como {bot.user}')
    print("Comandos cargados:", [command.name for command in bot.commands])
    weekly_summary.start()  # Iniciar la tarea programada

@bot.event
async def on_voice_state_update(member, before, after):
    user_id = member.id

    if before.channel is None and after.channel is not None:
        # Usuario se ha conectado a un canal de voz
        active_sessions[user_id] = datetime.now()

    elif before.channel is not None and after.channel is None:
        # Usuario se ha desconectado de un canal de voz
        join_time = active_sessions.pop(user_id, None)
        if join_time:
            duration = (datetime.now() - join_time).seconds // 60  # Duración en minutos
            c.execute('INSERT INTO voice_activity (user_id, join_time, duration) VALUES (?, ?, ?)',
                      (user_id, join_time.strftime('%Y-%m-%d %H:%M:%S'), duration))
            conn.commit()

@tasks.loop(hours=168)  # Cada semana (7 días * 24 horas)
async def weekly_summary():
    c.execute('SELECT value FROM config WHERE key = ?', ('ranking_channel',))
    result = c.fetchone()
    channel_id = int(result[0]) if result else ID DE CANAL  # ID por defecto si no está configurado
    channel = bot.get_channel(channel_id)

    # Calcular el top semanal
    one_week_ago = datetime.now() - timedelta(days=7)
    c.execute('''SELECT user_id, SUM(duration) as total_minutes 
                 FROM voice_activity 
                 WHERE join_time >= ? 
                 GROUP BY user_id 
                 ORDER BY total_minutes DESC 
                 LIMIT 10''', (one_week_ago.strftime('%Y-%m-%d %H:%M:%S'),))

    results = c.fetchall()
    
    if results:
        message = "**🏆 Top de Usuarios por Tiempo en Canal de Voz (Semanal) 🏆**\n"
        for index, (user_id, total_minutes) in enumerate(results, start=1):
            user = await bot.fetch_user(user_id)
            message += f"{index}. {user.name}: {total_minutes} minutos\n"
    else:
        message = "No hay actividad registrada esta semana."

    if channel:
        await channel.send(message)
    else:
        print(f"❌ No se pudo encontrar el canal con ID {channel_id}. Verifica el ID.")

# Comando de estadísticas avanzadas
@bot.command()
async def promedio_tiempo(ctx):
    c.execute('SELECT AVG(duration) FROM voice_activity')
    result = c.fetchone()
    promedio = result[0] if result[0] else 0
    await ctx.send(f"📈 El tiempo de conexión promedio es de **{promedio:.2f} minutos**.")

@bot.command()
async def actividad_diaria(ctx):
    hoy = datetime.now().strftime('%Y-%m-%d')
    c.execute('SELECT SUM(duration) FROM voice_activity WHERE DATE(join_time) = ?', (hoy,))
    result = c.fetchone()
    total = result[0] if result[0] else 0
    await ctx.send(f"🗓️ Hoy se han registrado un total de **{total} minutos** de actividad en los canales de voz.")

@bot.command()
async def resumen_personal(ctx, dias: int = 7):
    user_id = ctx.author.id
    fecha_inicio = datetime.now() - timedelta(days=dias)
    c.execute('SELECT SUM(duration) FROM voice_activity WHERE user_id = ? AND join_time >= ?', (user_id, fecha_inicio))
    result = c.fetchone()
    total = result[0] if result[0] else 0
    await ctx.send(f"📊 Has estado conectado **{total} minutos** en los últimos **{dias} días**.")

@bot.command()
async def ranking_personalizado(ctx, inicio: str, fin: str):
    c.execute('''SELECT user_id, SUM(duration) as total_minutes
                 FROM voice_activity
                 WHERE join_time BETWEEN ? AND ?
                 GROUP BY user_id
                 ORDER BY total_minutes DESC
                 LIMIT 10''', (inicio, fin))
    results = c.fetchall()
    if results:
        message = f"🏆 Ranking del {inicio} al {fin}:\n"
        for index, (user_id, total_minutes) in enumerate(results, start=1):
            user = await bot.fetch_user(user_id)
            message += f"{index}. {user.name}: {total_minutes} minutos\n"
    else:
        message = "No hay actividad registrada en ese período."
    await ctx.send(message)

@bot.command()
@commands.has_permissions(administrator=True)
async def activar_resumen(ctx, estado: str):
    if estado.lower() in ['on', 'off']:
        c.execute('INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)', ('resumen_activo', estado.lower()))
        conn.commit()
        await ctx.send(f"✅ El resumen semanal ha sido **{estado.upper()}**.")
    else:
        await ctx.send("❌ Usa `on` o `off` para activar o desactivar el resumen semanal.")

@bot.command()
@commands.has_permissions(administrator=True)
async def configurar_prefijo(ctx, nuevo_prefijo: str):
    bot.command_prefix = nuevo_prefijo
    await ctx.send(f"✅ El prefijo del bot ha sido actualizado a **{nuevo_prefijo}**.")

@bot.command()
async def recordatorio(ctx, mensaje: str, tiempo: int):
    await ctx.send(f"⏰ Recordatorio programado para dentro de **{tiempo} segundos**.")
    await asyncio.sleep(tiempo)
    await ctx.send(f"🔔 Recordatorio: {mensaje}")

@bot.command()
async def alerta_inactividad(ctx, dias: int):
    fecha_limite = datetime.now() - timedelta(days=dias)
    c.execute('''SELECT DISTINCT user_id FROM voice_activity WHERE join_time < ?''', (fecha_limite,))
    resultados = c.fetchall()
    if resultados:
        usuarios_inactivos = ', '.join([f"<@{user_id[0]}>" for user_id in resultados])
        await ctx.send(f"⚠️ Usuarios inactivos en los últimos {dias} días: {usuarios_inactivos}")
    else:
        await ctx.send("✅ No hay usuarios inactivos en ese período.")

@bot.command()
async def ranking_random(ctx):
    c.execute('SELECT DISTINCT user_id FROM voice_activity')
    usuarios = [user[0] for user in c.fetchall()]
    random.shuffle(usuarios)
    if usuarios:
        mensaje = "🎲 Ranking Random del Día:\n"
        for index, user_id in enumerate(usuarios[:10], start=1):
            user = await bot.fetch_user(user_id)
            mensaje += f"{index}. {user.name}\n"
        await ctx.send(mensaje)
    else:
        await ctx.send("❌ No hay usuarios registrados para el ranking aleatorio.")

# Comando de frase motivadora
@bot.command()
async def frase_motivadora(ctx):
    frases = [
        "🌅 Cada amanecer es una nueva oportunidad para brillar.",
        "🚀 No importa lo lento que vayas, mientras no te detengas.",
        "🔥 La pasión es el combustible del éxito.",
        "💡 Las ideas solo brillan si las pones en acción.",
        "🏆 El éxito no es la meta, es el camino que recorres.",
        "🌱 Pequeños pasos crean grandes cambios.",
        "🧗 El mayor obstáculo está en tu mente, supéralo.",
        "💪 Eres más fuerte de lo que crees.",
        "🎯 Concéntrate en la meta, no en los obstáculos.",
        "🌈 Después de la tormenta, siempre sale el sol."
        # Asegúrate de que cada frase sea corta
    ]
    
    frase_aleatoria = random.choice(frases)
    
    if len(frase_aleatoria) <= 2000:
        await ctx.send(frase_aleatoria)
    else:
        await ctx.send("❌ La frase es demasiado larga para ser enviada.")
        
# Iniciar el bot
bot.run(TOKEN)
