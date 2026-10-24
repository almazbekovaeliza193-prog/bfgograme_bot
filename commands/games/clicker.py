import time
from decimal import Decimal

from aiogram import Dispatcher, types

from assets.antispam import antispam, antispam_earning
from commands.db import conn, cursor
from filters.custom import TextIn, StartsWith
from user import BFGuser
from assets import keyboards as kb


# Награда за клик и кулдаун
CLICK_REWARD = 1000
CLICK_COOLDOWN = 1  # секунд между кликами

# Антифлуд хранилище: {user_id: last_click_time}
_last_click = {}


async def add_balance(user_id: int, amount: int) -> None:
    """Начисляет деньги пользователю."""
    balance = cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,)).fetchone()[0]
    new_balance = Decimal(balance) + Decimal(amount)
    cursor.execute('UPDATE users SET balance = ? WHERE user_id = ?', (str(int(new_balance)), user_id))
    conn.commit()


def clicker_kb(user_id: int, clicks: int):
    """Клавиатура кликера."""
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(types.InlineKeyboardButton(
        text=f"👆 КЛИК! ({clicks})",
        callback_data=f"clicker_click|{user_id}"
    ))
    return keyboard


@antispam
async def clicker_cmd(message: types.Message, user: BFGuser):
    text = (
        f"👆 <b>Кликер</b>\n\n"
        f"{user.url}, нажимай на кнопку и зарабатывай деньги!\n\n"
        f"💰 За каждый клик: <b>{CLICK_REWARD:,}$</b>\n"
        f"⏱ Задержка: {CLICK_COOLDOWN} сек\n\n"
        f"<blockquote>💡 Чем больше кликаешь — тем больше зарабатываешь!</blockquote>"
    )
    await message.answer(text, reply_markup=clicker_kb(user.user_id, 0))


@antispam_earning
async def clicker_click(call: types.CallbackQuery, user: BFGuser):
    uid = user.user_id
    now = time.time()

    # Антифлуд
    last = _last_click.get(uid, 0)
    if now - last < CLICK_COOLDOWN:
        await call.answer("⏳ Не так быстро!", show_alert=False)
        return

    _last_click[uid] = now

    # Начисляем деньги
    await add_balance(uid, CLICK_REWARD)

    # Считаем клики в рамках текущего сообщения
    clicks = call.message.text
    # Берём число из callback хранилища через счётчик на сообщении
    count = getattr(clicker_click, '_counters', {}).get((call.message.chat.id, call.message.message_id), 0) + 1
    if not hasattr(clicker_click, '_counters'):
        clicker_click._counters = {}
    clicker_click._counters[(call.message.chat.id, call.message.message_id)] = count

    await call.answer(f"💰 +{CLICK_REWARD:,}$")

    text = (
        f"👆 <b>Кликер</b>\n\n"
        f"{user.url}, нажимай на кнопку и зарабатывай деньги!\n\n"
        f"💰 За каждый клик: <b>{CLICK_REWARD:,}$</b>\n"
        f"📊 Сделано кликов: <b>{count}</b>\n"
        f"💵 Заработано: <b>{count * CLICK_REWARD:,}$</b>\n\n"
        f"<blockquote>💡 Чем больше кликаешь — тем больше зарабатываешь!</blockquote>"
    )

    try:
        await call.message.edit_text(text, reply_markup=clicker_kb(uid, count))
    except Exception:
        pass


def reg(dp: Dispatcher):
    dp.message.register(clicker_cmd, TextIn("кликер", "clicker"))
    dp.callback_query.register(clicker_click, StartsWith("clicker_click"))
