import discord
from discord.ext import commands
from datetime import datetime
import asyncio
import sqlite3
import os
from contextlib import contextmanager
from dotenv import load_dotenv

load_dotenv("tok.env")
TOKEN = os.getenv("BOT_TOKEN")

permissions = discord.Intents.default()
permissions.message_content = True
permissions.members = True
bot = commands.Bot(command_prefix='/', intents=permissions)

# Configurações
age_tolerance_months = 2
timeout_seconds = 300  # 5 minutos

# Context manager para conexões com o banco de dados
@contextmanager
def db_connection(guild_id: int):
    if not os.path.exists("databases"):
        os.makedirs("databases")
    db_path = os.path.join("databases", f"{guild_id}_birthday_data.db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS birthdays (
                user_id INTEGER PRIMARY KEY,
                user_tag TEXT NOT NULL,
                birthday_date TEXT NOT NULL,
                verified INTEGER DEFAULT 0
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS log_channel (
                guild_id INTEGER PRIMARY KEY,
                channel_id INTEGER NOT NULL
            )
        ''')
        conn.commit()
        yield conn, cursor
        conn.commit()
    finally:
        conn.close()

# Modal para verificação de idade
class BirthdayModal(discord.ui.Modal):
    def __init__(self, member: discord.Member, verification_channel: discord.TextChannel = None):
        super().__init__(title='🔞 Verificação de Idade')
        self.member = member
        # verification_channel é opcional; se estiver em DM, não há canal a apagar
        self.verification_channel = verification_channel

        self.birthday = discord.ui.TextInput(
            label="Data de Aniversário (DD-MM-AAAA)",
            placeholder="Exemplo: 19-10-2004",
            max_length=10,
        )
        self.add_item(self.birthday)

    async def on_submit(self, interaction: discord.Interaction):
        birthday = self.birthday.value.strip()
        with db_connection(self.member.guild.id) as (conn, cursor):
            cursor.execute("SELECT * FROM birthdays WHERE user_id = ?", (self.member.id,))
            if cursor.fetchone():
                await interaction.response.send_message("❌ Você já forneceu sua data de aniversário.", ephemeral=True)
                return

            if not self.is_valid_date(birthday):
                await interaction.response.send_message("❌ Formato inválido! Use DD-MM-AAAA.", ephemeral=True)
                return

            # Recupera canal de log, se configurado
            cursor.execute("SELECT channel_id FROM log_channel WHERE guild_id = ?", (self.member.guild.id,))
            log_channel_data = cursor.fetchone()
            log_channel = self.member.guild.get_channel(log_channel_data[0]) if log_channel_data else None

            age, within_tolerance = self.calculate_age(birthday)
            timestamp = datetime.now().strftime("%d-%m-%Y %H:%M")
            if age < 18 and not within_tolerance:
                await interaction.response.send_message("🚫 Você precisa ter pelo menos 18 anos para continuar.", ephemeral=True)
                try:
                    await self.member.ban(reason="Idade abaixo de 18 anos")
                except Exception as e:
                    print(f"Erro ao banir usuário {self.member}: {e}")
                if log_channel:
                    await log_channel.send(
                        f"📢 **Usuário Banido**\nUsuário: {self.member.mention}\nIdade: {age}\nAniversário: {birthday}\nData/Hora: {timestamp}"
                    )
            else:
                cursor.execute("INSERT INTO birthdays (user_id, user_tag, birthday_date) VALUES (?, ?, ?)",
                               (self.member.id, self.member.name, birthday))
                await interaction.response.send_message(f"🎉 Sua idade foi confirmada como **{age} anos**!", ephemeral=True)
                if log_channel:
                    await log_channel.send(
                        f"📢 **Usuário Registrado**\nUsuário: {self.member.mention}\nIdade: {age}\nAniversário: {birthday}\nData/Hora: {timestamp}"
                    )
        # Se houver canal de verificação, tente apagá-lo após um pequeno atraso
        if self.verification_channel:
            await asyncio.sleep(3)
            try:
                await self.verification_channel.delete()
            except Exception as e:
                print(f"Erro ao excluir canal de verificação: {e}")

    def is_valid_date(self, date_str: str) -> bool:
        try:
            datetime.strptime(date_str, "%d-%m-%Y")
            return True
        except ValueError:
            return False

    def calculate_age(self, birthday: str):
        birth_date = datetime.strptime(birthday, "%d-%m-%Y")
        today = datetime.now()
        age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
        age_in_months = (today.year - birth_date.year) * 12 + today.month - birth_date.month - (1 if today.day < birth_date.day else 0)
        within_tolerance = age_in_months >= (18 * 12) - age_tolerance_months
        return age, within_tolerance

# Comando para configurar o canal de log
@bot.command()
@commands.has_permissions(administrator=True)
async def chopper_log(ctx: commands.Context, channel_id: int):
    channel = bot.get_channel(channel_id)
    if not channel:
        await ctx.reply("❌ Canal inválido. Certifique-se de que o ID está correto.")
        return

    with db_connection(ctx.guild.id) as (conn, cursor):
        cursor.execute("INSERT OR REPLACE INTO log_channel (guild_id, channel_id) VALUES (?, ?)", (ctx.guild.id, channel_id))
    await ctx.reply(f"✅ Canal de logs configurado para <#{channel_id}>.")

# Tarefa auxiliar para aguardar a verificação
async def wait_for_verification(member: discord.Member, verification_channel: discord.TextChannel):
    await asyncio.sleep(timeout_seconds)
    with db_connection(member.guild.id) as (conn, cursor):
        cursor.execute("SELECT * FROM birthdays WHERE user_id = ?", (member.id,))
        if not cursor.fetchone():
            try:
                await member.kick(reason="Não respondeu à verificação de idade a tempo")
            except Exception as e:
                print(f"Erro ao expulsar o usuário {member}: {e}")
            try:
                await verification_channel.delete()
            except Exception as e:
                print(f"Erro ao excluir canal de verificação: {e}")

# Evento ao entrar um novo membro
@bot.event
async def on_member_join(member: discord.Member):
    with db_connection(member.guild.id) as (conn, cursor):
        cursor.execute("SELECT * FROM birthdays WHERE user_id = ?", (member.id,))
        if cursor.fetchone():
            return  # Usuário já verificado; ignora

    guild = member.guild

    # Define permissões para o canal de verificação
    mod_role = discord.utils.get(guild.roles, name="Moderador")
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        member: discord.PermissionOverwrite(read_messages=True, send_messages=True)
    }
    if mod_role:
        overwrites[mod_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

    verification_channel = await guild.create_text_channel(
        name="🛡️-verificação-de-entrada",
        overwrites=overwrites
    )

    async def button_callback(interaction: discord.Interaction):
        if interaction.user != member:
            await interaction.response.send_message("Este botão é apenas para você.", ephemeral=True)
            return
        modal = BirthdayModal(member, verification_channel)
        await interaction.response.send_modal(modal)

    view = discord.ui.View()
    button = discord.ui.Button(label="👀 Insira sua data de aniversário", style=discord.ButtonStyle.primary)
    button.callback = button_callback
    view.add_item(button)

    embed = discord.Embed(
        title="✨ Bem-vindo(a)!",
        description="Clique no botão abaixo para verificar sua idade.",
        color=discord.Color.purple()
    )

    await verification_channel.send(content=member.mention, embed=embed, view=view)
    # Agenda a tarefa de timeout sem bloquear o fluxo do bot
    asyncio.create_task(wait_for_verification(member, verification_channel))

# Comandos administrativos para gerenciar datas de aniversário
@bot.command()
@commands.has_permissions(administrator=True)
async def age(ctx: commands.Context, user_id: int):
    with db_connection(ctx.guild.id) as (conn, cursor):
        cursor.execute("SELECT * FROM birthdays WHERE user_id = ?", (user_id,))
        user_data = cursor.fetchone()

    if user_data:
        verified_status = "✅ Verificado" if user_data[3] else "❌ Não verificado"
        embed = discord.Embed(
            title="🎂 Data de Aniversário Encontrada",
            description=f"O usuário com ID {user_id} tem o aniversário em: {user_data[2]}.\nStatus: {verified_status}",
            color=discord.Color.green()
        )
        await ctx.reply(embed=embed)
    else:
        embed = discord.Embed(
            title="❌ Usuário Não Encontrado",
            description="Não há data de aniversário registrada para esse usuário.",
            color=discord.Color.red()
        )
        await ctx.reply(embed=embed)

@bot.command()
@commands.has_permissions(administrator=True)
async def age_delete(ctx: commands.Context, user_id: int):
    with db_connection(ctx.guild.id) as (conn, cursor):
        cursor.execute("DELETE FROM birthdays WHERE user_id = ?", (user_id,))
    await ctx.reply(f"🗑️ A data de aniversário do usuário com ID `{user_id}` foi removida.")

@bot.command()
@commands.has_permissions(administrator=True)
async def age_edit(ctx: commands.Context, user_id: int, new_birthday: str):
    try:
        datetime.strptime(new_birthday, "%d-%m-%Y")
    except ValueError:
        await ctx.reply("❌ Formato inválido! Use DD-MM-AAAA.")
        return

    with db_connection(ctx.guild.id) as (conn, cursor):
        cursor.execute("SELECT * FROM birthdays WHERE user_id = ?", (user_id,))
        user_data = cursor.fetchone()
        if user_data:
            cursor.execute("UPDATE birthdays SET birthday_date = ? WHERE user_id = ?", (new_birthday, user_id))
        else:
            await ctx.reply("❌ Usuário não encontrado no banco de dados.")
            return
    await ctx.reply(f"✅ A data de aniversário do usuário com ID `{user_id}` foi alterada para `{new_birthday}`.")

@bot.command()
@commands.has_permissions(administrator=True)
async def age_list(ctx: commands.Context):
    with db_connection(ctx.guild.id) as (conn, cursor):
        cursor.execute("SELECT user_id, user_tag, birthday_date, verified FROM birthdays")
        data = cursor.fetchall()

    if data:
        birthdays = "\n".join([
            f"`{user[0]}` - **{user[1]}**: {user[2]} - {'✅ Verificado' if user[3] else '❌ Não verificado'}"
            for user in data
        ])
        embed = discord.Embed(title="🎂 Lista de Aniversários", description=birthdays, color=discord.Color.blue())
        await ctx.reply(embed=embed)
    else:
        await ctx.reply("❌ Nenhum aniversário registrado.")

@bot.command()
@commands.has_permissions(administrator=True)
async def age_add(ctx: commands.Context, user_id: int, birthday: str):
    try:
        datetime.strptime(birthday, "%d-%m-%Y")
    except ValueError:
        await ctx.reply("❌ Formato inválido! Use DD-MM-AAAA.")
        return

    with db_connection(ctx.guild.id) as (conn, cursor):
        cursor.execute("SELECT * FROM birthdays WHERE user_id = ?", (user_id,))
        if cursor.fetchone():
            await ctx.reply("❌ Esse usuário já tem uma data de aniversário registrada. Use `/age_edit` para modificar.")
            return

        user = bot.get_user(user_id)
        user_tag = user.name if user else "Desconhecido"
        cursor.execute("INSERT INTO birthdays (user_id, user_tag, birthday_date) VALUES (?, ?, ?)",
                       (user_id, user_tag, birthday))
    await ctx.reply(f"✅ Data de aniversário `{birthday}` adicionada para o usuário com ID `{user_id}`.")

@bot.command()
@commands.has_permissions(administrator=True)
async def age_id_verified(ctx: commands.Context, user_id: int):
    with db_connection(ctx.guild.id) as (conn, cursor):
        cursor.execute("SELECT * FROM birthdays WHERE user_id = ?", (user_id,))
        user_data = cursor.fetchone()
        if user_data:
            cursor.execute("UPDATE birthdays SET verified = 1 WHERE user_id = ?", (user_id,))
        else:
            await ctx.reply("❌ Usuário não encontrado no banco de dados.")
            return
    await ctx.reply(f"✅ O usuário com ID `{user_id}` foi verificado!")

# Novo comando para que o próprio usuário possa verificar sua idade via DM
@bot.command()
async def verify(ctx: commands.Context):
    with db_connection(ctx.guild.id) as (conn, cursor):
        cursor.execute("SELECT * FROM birthdays WHERE user_id = ?", (ctx.author.id,))
        if cursor.fetchone():
            await ctx.reply("Você já está verificado!")
            return

    try:
        dm_channel = await ctx.author.create_dm()
        view = discord.ui.View()
        button = discord.ui.Button(label="Verificar idade", style=discord.ButtonStyle.primary)
        
        async def dm_button_callback(interaction: discord.Interaction):
            modal = BirthdayModal(ctx.author)  # Aqui, não há canal de verificação para excluir
            await interaction.response.send_modal(modal)
        
        button.callback = dm_button_callback
        view.add_item(button)
        await dm_channel.send("Clique no botão para verificar sua idade.", view=view)
        await ctx.reply("Enviamos um DM para você com o processo de verificação!")
    except Exception as e:
        await ctx.reply("Não foi possível enviar um DM. Verifique suas configurações de privacidade.")

bot.run(TOKEN)
