import asyncio
import json
import logging
import os
import re
import uuid
from aiogram import Bot, Dispatcher, Router, types, F
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, StateFilter, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.client.default import DefaultBotProperties

# Включаем логирование
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# --- Настройки бота ---
# Замените 'YOUR_DUMMY_TOKEN_HERE' на токен, полученный от BotFather.
BOT_TOKEN = "YOUR_DUMMY_TOKEN_HERE"

# --- Настройки файлов конфигурации и супер-админа ---
AUTHORIZED_USERS_FILE = "authorized_users.json"
ADMINS_FILE = "admins.json"
CONFIG_FILE = "config.json"
# Укажите здесь свой Telegram ID. Этот пользователь всегда будет администратором.
# Замените 1234567890 на ваш реальный ID.
SUPER_ADMIN_ID = 1234567890

# Словарь для временного хранения отчётов
pending_reports = {}

# --- Функции для работы с файлами конфигурации ---
def load_authorized_users():
    """Загружает список авторизованных пользователей из JSON-файла."""
    if os.path.exists(AUTHORIZED_USERS_FILE):
        try:
            with open(AUTHORIZED_USERS_FILE, "r") as f:
                return set(json.load(f))
        except (IOError, json.JSONDecodeError):
            logging.error("Failed to load authorized users file. Starting with an empty list.")
    return set()

def save_authorized_users(user_ids):
    """Сохраняет список авторизованных пользователей в JSON-файл."""
    try:
        with open(AUTHORIZED_USERS_FILE, "w") as f:
            json.dump(list(user_ids), f)
    except IOError:
        logging.error("Failed to save authorized users file.")

def load_admins():
    """Загружает список администраторов из JSON-файла."""
    if os.path.exists(ADMINS_FILE):
        try:
            with open(ADMINS_FILE, "r") as f:
                return set(json.load(f))
        except (IOError, json.JSONDecodeError):
            logging.error("Failed to load admins file. Starting with an empty list.")
    return set()

def save_admins(admin_ids):
    """Сохраняет список администраторов в JSON-файл."""
    try:
        with open(ADMINS_FILE, "w") as f:
            json.dump(list(admin_ids), f)
    except IOError:
        logging.error("Failed to save admins file.")

def load_config():
    """Загружает конфигурацию из JSON-файла."""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except (IOError, json.JSONDecodeError):
            logging.error("Failed to load config file. Starting with default settings.")
    return {}

def save_config(config_data):
    """Сохраняет конфигурацию в JSON-файл."""
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(config_data, f, indent=4)
    except IOError:
        logging.error("Failed to save config file.")

def get_dispatcher_chat_id():
    """Получает ID чата диспетчера из файла конфигурации."""
    config = load_config()
    return config.get("dispatcher_chat_id")

def is_admin(user_id):
    """Проверяет, является ли пользователь администратором."""
    admins = load_admins()
    return str(user_id) == str(SUPER_ADMIN_ID) or str(user_id) in admins

def is_authorized(user_id):
    """
    Проверяет, авторизован ли пользователь.
    Пользователь авторизован, если он есть в списке механиков или администраторов.
    """
    authorized_users = load_authorized_users()
    admins = load_admins()
    return str(user_id) in authorized_users or str(user_id) in admins or str(user_id) == str(SUPER_ADMIN_ID)


# --- Список выполняемых работ, сгруппированных по категориям ---
REPAIR_CATEGORIES = {
    "🛠️ Частый ремонт": [
        "🛞 Переднее колесо", "🩹 Камера", "⚙️ Мотор колесо", "⚙️ Звезда задняя",
        "⚙️ Передний подшипник", "🛑 Колодки (задние)", "🛑 Колодки (передние)",
        "🔗 Тормозной трос (задний)", "🔗 Тормозной трос (перед)", "🪞 Зеркало (л)",
        "🪞 Зеркало (п)", "💧 Флягодержатель", "📱 ДДТ", "📎 Зажим багажника",
    ],
    "⚙️ Колёса и тормоза": [
        "🔗 Тормозной трос (задний)", "🔗 Тормозной трос (перед)", "🛞 Переднее колесо",
        "⚡️ Мотор колесо", "🛑 Колодки (передние)", "🛑 Колодки (задние)",
        "💿 Передний диск", "🥁 Барабан переднего колеса", "⚙️ Передний подшипник",
        "⚙️ Задний подшипник", "⚙️ Звезда задняя", "🩹 Камера", "🚲 Покрышка",
    ],
    "⚡️ Электрика": [
        "💨 Курок газа", "🖥️ Дисплей", "🎛️ Контролер", "🔒 Замок АКБ",
        "🔌 USB порт", "💡 Фара", "➡️ Поворотник (п)", "⬅️ Поворотник (л)",
        "🔋 ячейка 2 акб", "🔌 Проводка", "🔔 Зуммер", "🔌 Розетка",
        "⚡️ Кабель для зарядки", "🔴 Задняя фара", "🛡️ Защитная пластина заднего фонаря",
    ],
    "🚲 Рама и навесное": [
        "📱 ДДТ", "📎 Зажим багажника", "💧 Флягодержатель", "🪞 Зеркало (п)",
        "🪞 Зеркало (л)", "🦵 Подножка", "🛡️ Крыло переднее", "🛡️ Крыло заднее",
        "🆔 Номерной знак", "🦶 Подставка для ног (п)", "🦶 Подставка для ног (л)",
        "🔒 Замок седла", "🪑 Сидение", "🛡️ Кожух цепи", "🧳 Задний багажник",
        "💡 Крышка фары", "📢 Рекламнный банер (п)", "📢 Рекламный банер (л)",
        "🧳 Передний багажник", "🔋 Направляющая для аккамулятора",
        "🔋 Верхняя крышка отсека аккумулятора", "🔋 Держатель аккумулятора (площадка)",
        "🛹 Дека", "🔒 Внутренняя скоба замка сидения", "🤖 Задняя крышка IoT",
        "🤖 Пластина боковая держатель IoT", "💡 Светоотражатль IoT", "⚓️ Якорь",
        "🔒 Крышка замка сидения", "🛡️ Защита двигателя от закручивания",
        "⛓️ Натяжитель цепи", "🧳 Задняя полка багажника",
    ],
    "⛓️ Трансмиссия и подшипники": [
        "⚙️ Звезда задняя", "🦶 Педаль (л)", "🦶 Педаль (п)", "⛓️ Цепь",
        "🔧 Замена шатуна", "🔒 Замок цепи", "⚙️ Каретка", "⚙️ Передний подшипник",
        "⚙️ Задний подшипник", "⚙️ Подшипник вилки руля",
    ],
    "🎛️ Рулевое управление": [
        "🍴 Вилка", "✋ Ручка тормоза (Л)", "✋ Ручка тормоза (П)",
        "⚙️ Стакан вилки руля", "🕹️ Руль", "🛡️ Верхняя накладка на руль",
        "🛡️ Нижняя накладка на руль", "🤚 Грипса (п)", "🤚 Грипса (л)",
        "🕳️ Заглушка под грипсу", "📎 Хомут руля", "⚙️ Чашка несущая вилки",
        "🎛️ Панель управлением",
    ],
    "🔧 Прочее": [
        "🩹 Заплатка", "📶 SIM", "🔌 Пластиковые проставка БП (Внутренняя)",
        "🔌 Пластиковые проставка БП (Наружная)",
    ]
}

# Список фиксированных локаций для отчётов, укажите свои списки ремонтных точек
LOCATIONS = ["Пример1", "Пример2"]

# Создаем сопоставление коротких ключей и полных имен категорий
CATEGORY_CALLBACKS = {f"cat_{i+1}": name for i, name in enumerate(REPAIR_CATEGORIES.keys())}
REVERSE_CATEGORY_CALLBACKS = {name: key for key, name in CATEGORY_CALLBACKS.items()}

# Создаём сопоставление коротких ключей для каждой работы
WORK_CALLBACKS = {}
REVERSE_WORK_CALLBACKS = {}
for category_name, works_list in REPAIR_CATEGORIES.items():
    for work_name in works_list:
        work_key = str(uuid.uuid4())[:8]
        WORK_CALLBACKS[work_name] = work_key
        REVERSE_WORK_CALLBACKS[work_key] = work_name


# --- Состояния для FSM (Finite State Machine) ---
class Form(StatesGroup):
    """Состояния для заполнения формы отчёта."""
    get_bike_id = State()
    get_repair_type = State()
    get_location = State()
    select_category = State()
    select_works = State()
    confirm = State()
    get_custom_work = State()

class AdminForm(StatesGroup):
    """Состояния для административной панели."""
    menu = State()
    add_user = State()
    remove_user = State()
    add_admin = State()
    remove_admin = State()
    set_dispatcher_id = State()

# Создаем главный роутер для обработки событий.
router = Router()

# --- Функции-помощники для создания клавиатур ---
def get_repair_type_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="🚴‍♂️ Быстрый ремонт", callback_data="type_Быстрый ремонт"),
        types.InlineKeyboardButton(text="📦 На выдачу", callback_data="type_На выдачу")
    )
    builder.row(
        types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")
    )
    return builder.as_markup()

def get_locations_keyboard():
    """Создает клавиатуру для выбора фиксированных локаций."""
    builder = InlineKeyboardBuilder()
    for loc in LOCATIONS:
        builder.add(types.InlineKeyboardButton(text=loc, callback_data=f"loc_{loc}"))
    builder.adjust(2)
    builder.row(
        types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")
    )
    return builder.as_markup()

def get_categories_keyboard():
    builder = InlineKeyboardBuilder()
    for key, name in CATEGORY_CALLBACKS.items():
        builder.add(types.InlineKeyboardButton(text=name, callback_data=f"category_{key}"))
    builder.adjust(2)
    builder.row(
        types.InlineKeyboardButton(text="✅ Подтвердить", callback_data="confirm")
    )
    builder.row(
        types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")
    )
    return builder.as_markup()

def get_category_works_keyboard(category: str, selected_works: list):
    builder = InlineKeyboardBuilder()
    works_list = REPAIR_CATEGORIES.get(category, [])
    for work in works_list:
        button_text = f"✅ {work}" if work in selected_works else work
        work_key = WORK_CALLBACKS.get(work)
        if work_key:
            builder.add(types.InlineKeyboardButton(text=button_text, callback_data=f"work_{work_key}"))

    builder.adjust(2)
    builder.row(
        types.InlineKeyboardButton(text="↩️ Назад к категориям", callback_data="back_to_categories")
    )
    builder.row(
        types.InlineKeyboardButton(text="✏️ Добавить вручную", callback_data="add_custom")
    )
    return builder.as_markup()

def get_final_confirmation_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="✅ Подтвердить", callback_data="final_confirm"),
        types.InlineKeyboardButton(text="❌ Отмена", callback_data="restart")
    )
    return builder.as_markup()

def get_start_over_keyboard():
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="🔄 Начать новую форму", callback_data="restart")
    )
    return builder.as_markup()

def get_dispatcher_keyboard(report_key: str):
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="✅ Принять", callback_data=f"accept_{report_key}"),
        types.InlineKeyboardButton(text="❌ Отклонить", callback_data=f"decline_{report_key}")
    )
    return builder.as_markup()

def get_admin_menu_keyboard():
    """Клавиатура для админ-панели."""
    builder = InlineKeyboardBuilder()
    builder.row(
        types.InlineKeyboardButton(text="➕ Добавить механика", callback_data="admin_add_mechanic"),
        types.InlineKeyboardButton(text="➖ Удалить механика", callback_data="admin_remove_mechanic")
    )
    builder.row(
        types.InlineKeyboardButton(text="➕ Добавить администратора", callback_data="admin_add_admin"),
        types.InlineKeyboardButton(text="➖ Удалить администратора", callback_data="admin_remove_admin")
    )
    builder.row(
        types.InlineKeyboardButton(text="📝 Список механиков", callback_data="admin_list_mechanics"),
        types.InlineKeyboardButton(text="📝 Список администраторов", callback_data="admin_list_admins")
    )
    builder.row(
        types.InlineKeyboardButton(text="⚙️ Настроить ID чата диспетчера", callback_data="admin_set_dispatcher_id")
    )
    builder.row(
        types.InlineKeyboardButton(text="↩️ Выйти", callback_data="admin_exit")
    )
    builder.adjust(2, 2, 2, 1, 1)
    return builder.as_markup()


# --- Обработчики команд и сообщений ---
@router.message(CommandStart())
async def cmd_start(message: types.Message, state: FSMContext):
    """
    Обработчик команды /start.
    Проверяет авторизацию и начинает диалог.
    """
    await state.clear()
    if not is_authorized(message.from_user.id):
        await message.answer("У вас нет прав для использования этого бота. Если вы механик, обратитесь к администратору для авторизации.")
        return

    await message.answer(
        "Привет! 👋 Чтобы начать, введи номер велосипеда (ID):",
        reply_markup=InlineKeyboardBuilder().row(
            types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")
        ).as_markup(),
    )
    await state.set_state(Form.get_bike_id)


@router.message(Command("myid"))
async def cmd_myid(message: types.Message):
    """
    Обработчик команды /myid.
    Выводит Telegram ID пользователя.
    """
    user_id = message.from_user.id
    # Используем ParseMode.MARKDOWN_V2 и обратные кавычки для красивого отображения ID
    await message.answer(f"Твой Telegram ID: `{user_id}`", parse_mode=ParseMode.MARKDOWN_V2)


@router.message(Form.get_bike_id, F.text)
async def process_bike_id(message: types.Message, state: FSMContext):
    """
    Обрабатывает ввод ID велосипеда с валидацией.
    """
    # Проверяем авторизацию перед обработкой
    if not is_authorized(message.from_user.id):
        await message.answer("У вас нет прав для использования этого бота. Обратитесь к администратору.")
        await state.clear()
        return

    bike_id = message.text.upper()
    pattern = r"^[A-Z]{2}\d{3}[A-Z]$"
    
    if re.fullmatch(pattern, bike_id):
        await state.update_data(bike_id=bike_id)
        await message.answer(
            f"Номер велосипеда: {bike_id}\n\nТеперь выбери тип ремонта:",
            reply_markup=get_repair_type_keyboard(),
        )
        await state.set_state(Form.get_repair_type)
    else:
        await message.answer(
            "❌ Неверный формат. Пример: AB123C",
            reply_markup=InlineKeyboardBuilder().row(
                types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")
            ).as_markup(),
        )
        await state.set_state(Form.get_bike_id)


@router.callback_query(Form.get_repair_type, F.data.startswith("type_"))
async def process_repair_type(callback_query: types.CallbackQuery, state: FSMContext):
    repair_type = callback_query.data.split("_")[1]
    await state.update_data(repair_type=repair_type, selected_works=[])
    await callback_query.message.edit_text(
        f"Тип ремонта: {repair_type}\n\nТеперь выбери локацию:",
        reply_markup=get_locations_keyboard(),
    )
    await callback_query.answer()
    await state.set_state(Form.get_location) # Переход к новому состоянию для выбора локации


@router.callback_query(Form.get_location, F.data.startswith("loc_"))
async def process_location_selection(callback_query: types.CallbackQuery, state: FSMContext):
    """Обрабатывает выбор фиксированной локации."""
    location = callback_query.data.split("_", 1)[1]
    await state.update_data(location=location)

    user_data = await state.get_data()
    repair_type = user_data.get("repair_type")
    
    await callback_query.message.edit_text(
        f"Локация: {location}\nТип ремонта: {repair_type}\n\nТеперь выбери категорию:",
        reply_markup=get_categories_keyboard(),
    )
    await callback_query.answer()
    await state.set_state(Form.select_category)


@router.callback_query(Form.select_category, F.data.startswith("category_"))
async def process_category_selection(callback_query: types.CallbackQuery, state: FSMContext):
    category_key = callback_query.data.split("_", 1)[1]
    category = CATEGORY_CALLBACKS.get(category_key)
    
    if not category:
        await callback_query.answer("Категория не найдена. Попробуйте еще раз.", show_alert=True)
        return
        
    user_data = await state.get_data()
    selected_works = user_data.get("selected_works", [])
    
    await state.update_data(current_category=category)
    
    await callback_query.message.edit_text(
        f"Категория: {category}\n\nВыбери выполненные работы:",
        reply_markup=get_category_works_keyboard(category, selected_works),
    )
    await callback_query.answer()
    await state.set_state(Form.select_works)


@router.callback_query(Form.select_works, F.data.startswith("work_"))
async def process_works_selection(callback_query: types.CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    current_category = user_data.get("current_category")
    selected_works = user_data.get("selected_works", [])
    
    work_key = callback_query.data.split("_", 1)[1]
    work_name = REVERSE_WORK_CALLBACKS.get(work_key)

    if not work_name:
        await callback_query.answer("Работа не найдена. Попробуйте еще раз.", show_alert=True)
        return

    if work_name in selected_works:
        selected_works.remove(work_name)
    else:
        selected_works.append(work_name)

    await state.update_data(selected_works=selected_works)
    await callback_query.message.edit_reply_markup(reply_markup=get_category_works_keyboard(current_category, selected_works))
    await callback_query.answer()


@router.callback_query(Form.select_works, F.data == "back_to_categories")
async def back_to_categories(callback_query: types.CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    repair_type = user_data.get("repair_type")
    
    await callback_query.message.edit_text(
        f"Тип ремонта: {repair_type}\n\nВыбери следующую категорию:",
        reply_markup=get_categories_keyboard(),
    )
    await callback_query.answer()
    await state.set_state(Form.select_category)


@router.callback_query(Form.select_works, F.data == "add_custom")
async def add_custom_work_prompt(callback_query: types.CallbackQuery, state: FSMContext):
    await callback_query.message.edit_text(
        "Напиши название работы, которую нужно добавить, и отправь мне.",
        reply_markup=InlineKeyboardBuilder().row(
            types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_custom_add")
        ).as_markup(),
    )
    await callback_query.answer()
    await state.set_state(Form.get_custom_work)


@router.message(Form.get_custom_work, F.text)
async def process_custom_work(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    selected_works = user_data.get("selected_works", [])
    custom_work = message.text
    selected_works.append(custom_work)
    await state.update_data(selected_works=selected_works)
    await message.answer(
        f"Работа '{custom_work}' добавлена. Выбери следующую категорию или заверши отчёт:",
        reply_markup=get_categories_keyboard(),
    )
    await state.set_state(Form.select_category)


@router.callback_query(Form.get_custom_work, F.data == "cancel_custom_add")
async def cancel_custom_add(callback_query: types.CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    current_category = user_data.get("current_category")
    selected_works = user_data.get("selected_works", [])
    
    await callback_query.message.edit_text(
        f"Добавление работы отменено.\n\nКатегория: {current_category}\nВыбери выполненные работы:",
        reply_markup=get_category_works_keyboard(current_category, selected_works)
    )
    await callback_query.answer()
    await state.set_state(Form.select_works)


@router.callback_query(F.data == "confirm", StateFilter(Form.select_works, Form.select_category))
async def confirm_works(callback_query: types.CallbackQuery, state: FSMContext):
    user_data = await state.get_data()
    bike_id = user_data["bike_id"]
    repair_type = user_data["repair_type"]
    selected_works = user_data["selected_works"]
    location = user_data["location"]

    if not selected_works:
        await callback_query.answer("Пожалуйста, выбери хотя бы одну выполненную работу.", show_alert=True)
        return

    works_list = "\n- ".join(selected_works)
    summary = (
        f"Сводка по ремонту\n\n"
        f"Велосипед № {bike_id}\n"
        f"Тип ремонта: {repair_type}\n"
        f"Локация: {location}\n"
        f"Выполненные работы:\n- {works_list}\n"
    )

    await callback_query.message.edit_text(
        summary,
        reply_markup=get_final_confirmation_keyboard(),
    )
    await callback_query.answer()
    await state.set_state(Form.confirm)


def format_telegram_link(user: types.User) -> str:
    if user.username:
        return f"@{user.username}"
    else:
        return f"[{user.first_name}](tg://user?id={user.id})"

def remove_emojis_and_strip(text: str) -> str:
    """
    Удаляет все эмодзи из строки
    """
    emoji_pattern = re.compile(
        "["
        "\U00002600-\U000027BF"  # Unicode range for dingbats and symbols
        "\U0001F600-\U0001F64F"  # Emoticons
        "\U0001F300-\U0001F5FF"  # Transport & Map Symbols
        "\U0001F680-\U0001F6FF"  # Miscellaneous Symbols and Pictographs
        "\U0001F700-\U0001F77F"  # Geometric Shapes Extended
        "\U0001F780-\U0001F7FF"  # Alchemical Symbols
        "\U0001F800-\U0001F8FF"  # Supplemental Arrows-C
        "\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
        "\U0001FA00-\U0001FA6F"  # Chess Symbols
        "\U0001FA70-\U0001FAFF"  # Symbols and Pictographs Extended-A
        "\U00002702-\U000027B0"  # Dingbats
        "\U000024C2-\U0001F251"  # Enclosed symbols
        "\U00002B50"             # White medium star
        "\U0001F1E6-\U0001F1FF"  # Regional Indicator Symbols
        "]+",
        flags=re.UNICODE,
    )
    return emoji_pattern.sub("", text).strip()


@router.callback_query(Form.confirm, F.data == "final_confirm")
async def send_report(callback_query: types.CallbackQuery, state: FSMContext, bot: Bot):
    dispatcher_chat_id = get_dispatcher_chat_id()
    if not dispatcher_chat_id:
        await callback_query.message.edit_text(
            "❌ ID чата диспетчера не настроен. Пожалуйста, обратитесь к администратору, чтобы установить его через команду /admin."
        )
        await state.clear()
        return

    user_data = await state.get_data()
    bike_id = user_data["bike_id"]
    repair_type = user_data["repair_type"]
    selected_works = user_data["selected_works"]
    location = user_data["location"]
    mechanic = callback_query.from_user

    # Удаляем эмодзи из названий работ перед отправкой диспетчеру
    dispatcher_works = [remove_emojis_and_strip(work) for work in selected_works]
    works_list = "; ".join(dispatcher_works)
    
    report_message = (
        f"Велосипед № {bike_id}\n"
        f"Тип ремонта: {repair_type}\n"
        f"Локация: {location}\n"
        f"Статус: готов\n"
        f"Выполненные работы: {works_list}\n"
        f"ID механика: {format_telegram_link(mechanic)}"
    )

    report_key = str(uuid.uuid4())[:8]
    pending_reports[report_key] = {
        "bike_id": bike_id,
        "mechanic_id": mechanic.id
    }

    try:
        await bot.send_message(
            chat_id=dispatcher_chat_id,
            text=report_message,
            reply_markup=get_dispatcher_keyboard(report_key)
        )
        await callback_query.message.edit_text(
            "✅ Отчёт успешно отправлен диспетчерам. Они скоро его обработают.",
            reply_markup=get_start_over_keyboard(),
        )
    except Exception as e:
        await callback_query.message.edit_text(
            f"❌ Ошибка отправки отчёта: {str(e)}.",
            reply_markup=get_start_over_keyboard(),
        )
        if report_key in pending_reports:
            del pending_reports[report_key]
    finally:
        await state.clear()
        await callback_query.answer()


@router.callback_query(F.data.startswith("accept_"))
async def accept_report(callback_query: types.CallbackQuery, bot: Bot):
    try:
        report_key = callback_query.data.split("_", 1)[1]
        report_data = pending_reports.get(report_key)
        
        if not report_data:
            await callback_query.answer("Данные по отчёту не найдены. Возможно, они устарели.", show_alert=True)
            return

        mechanic_id = report_data["mechanic_id"]
        bike_id = report_data["bike_id"]

    except Exception:
        await callback_query.answer("Ошибка в данных. Попробуйте еще раз.", show_alert=True)
        return
        
    await callback_query.message.edit_text(
        f"{callback_query.message.text}\n\n✅ Отчёт принят диспетчером {callback_query.from_user.first_name}.",
    )
    
    try:
        await bot.send_message(
            chat_id=mechanic_id,
            text=f"🎉 Отчёт о ремонте велосипеда №{bike_id} принят диспетчером.",
        )
    except Exception as e:
        logging.error(f"Failed to send notification to mechanic {mechanic_id}: {e}")
    
    if report_key in pending_reports:
        del pending_reports[report_key]
        
    await callback_query.answer("Отчёт принят. Механик уведомлён.")


@router.callback_query(F.data.startswith("decline_"))
async def decline_report(callback_query: types.CallbackQuery, bot: Bot):
    try:
        report_key = callback_query.data.split("_", 1)[1]
        report_data = pending_reports.get(report_key)
        
        if not report_data:
            await callback_query.answer("Данные по отчёту не найдены. Возможно, они устарели.", show_alert=True)
            return

        mechanic_id = report_data["mechanic_id"]
        bike_id = report_data["bike_id"]
        
    except Exception:
        await callback_query.answer("Ошибка в данных. Попробуйте еще раз.", show_alert=True)
        return
    
    await callback_query.message.edit_text(
        f"{callback_query.message.text}\n\n❌ Отчёт отклонён диспетчером {callback_query.from_user.first_name}.",
    )
    
    try:
        await bot.send_message(
            chat_id=mechanic_id,
            text=f"😞 Отчёт о ремонте велосипеда №{bike_id} отклонён диспетчером. Пожалуйста, проверьте отчёт.",
        )
    except Exception as e:
        logging.error(f"Failed to send notification to mechanic {mechanic_id}: {e}")
    
    if report_key in pending_reports:
        del pending_reports[report_key]
        
    await callback_query.answer("Отчёт отклонён. Механик уведомлён.")


@router.callback_query(F.data == "restart")
async def restart_form(callback_query: types.CallbackQuery, state: FSMContext):
    """
    Обработчик для перезапуска формы.
    """
    user_id = callback_query.from_user.id
    if not is_authorized(user_id):
        await callback_query.message.answer("У вас нет прав для использования этого бота. Если вы механик, обратитесь к администратору для авторизации.")
        await state.clear()
        return

    await state.clear()
    await callback_query.message.edit_reply_markup(reply_markup=None)
    await callback_query.message.answer(
        "Привет! 👋 Чтобы начать, введи номер велосипеда (ID):",
        reply_markup=InlineKeyboardBuilder().row(
            types.InlineKeyboardButton(text="❌ Отмена", callback_data="cancel")
        ).as_markup(),
    )
    await state.set_state(Form.get_bike_id)
    await callback_query.answer()

@router.callback_query(StateFilter("*"), F.data == "cancel")
async def cancel_form(callback_query: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback_query.message.edit_text("Действие отменено.")
    await callback_query.answer()

# --- Обработчики для админ-панели ---
@router.message(Command("admin"))
async def cmd_admin(message: types.Message, state: FSMContext):
    """
    Открывает админ-панель для администратора.
    """
    if not is_admin(message.from_user.id):
        await message.answer("У вас нет прав администратора.")
        return
    
    await state.set_state(AdminForm.menu)
    await message.answer("Добро пожаловать в админ-панель!", reply_markup=get_admin_menu_keyboard())


@router.callback_query(AdminForm.menu, F.data == "admin_add_mechanic")
async def admin_add_mechanic_prompt(callback_query: types.CallbackQuery, state: FSMContext):
    """Запрашивает Telegram ID нового механика."""
    await callback_query.message.edit_text(
        "Введите Telegram ID нового механика (это числовой ID, его можно узнать у @userinfobot)."
    )
    await state.set_state(AdminForm.add_user)
    await callback_query.answer()


@router.message(AdminForm.add_user, F.text)
async def admin_add_mechanic_process(message: types.Message, state: FSMContext):
    """Добавляет нового механика в список."""
    user_id_to_add = message.text.strip()
    if not user_id_to_add.isdigit():
        await message.answer("Неверный формат ID. Пожалуйста, введите только число.")
        return
        
    authorized_users = load_authorized_users()
    if user_id_to_add in authorized_users:
        await message.answer("Этот пользователь уже авторизован.")
    else:
        authorized_users.add(user_id_to_add)
        save_authorized_users(authorized_users)
        await message.answer(f"Пользователь с ID {user_id_to_add} успешно добавлен.")
    
    await state.set_state(AdminForm.menu)
    await message.answer("Админ-панель:", reply_markup=get_admin_menu_keyboard())


@router.callback_query(AdminForm.menu, F.data == "admin_add_admin")
async def admin_add_admin_prompt(callback_query: types.CallbackQuery, state: FSMContext):
    """Запрашивает Telegram ID нового администратора."""
    await callback_query.message.edit_text(
        "Введите Telegram ID нового администратора."
    )
    await state.set_state(AdminForm.add_admin)
    await callback_query.answer()


@router.message(AdminForm.add_admin, F.text)
async def admin_add_admin_process(message: types.Message, state: FSMContext):
    """Добавляет нового администратора в список."""
    admin_id_to_add = message.text.strip()
    if not admin_id_to_add.isdigit():
        await message.answer("Неверный формат ID. Пожалуйста, введите только число.")
        return
        
    admins = load_admins()
    if admin_id_to_add in admins:
        await message.answer("Этот пользователь уже является администратором.")
    else:
        admins.add(admin_id_to_add)
        save_admins(admins)
        await message.answer(f"Пользователь с ID {admin_id_to_add} успешно добавлен в список администраторов.")
    
    await state.set_state(AdminForm.menu)
    await message.answer("Админ-панель:", reply_markup=get_admin_menu_keyboard())


@router.callback_query(AdminForm.menu, F.data == "admin_list_mechanics")
async def admin_list_mechanics(callback_query: types.CallbackQuery, state: FSMContext):
    """Отображает список авторизованных механиков."""
    authorized_users = load_authorized_users()
    
    if not authorized_users:
        message_text = "В списке нет авторизованных механиков."
    else:
        user_list = "\n".join(authorized_users)
        message_text = f"**Авторизованные механики:**\n\n{user_list}"
    
    await callback_query.message.edit_text(
        message_text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardBuilder().row(
            types.InlineKeyboardButton(text="↩️ Назад", callback_data="admin_back_to_menu")
        ).as_markup()
    )
    await callback_query.answer()


@router.callback_query(AdminForm.menu, F.data == "admin_list_admins")
async def admin_list_admins(callback_query: types.CallbackQuery, state: FSMContext):
    """Отображает список администраторов."""
    admins = load_admins()
    
    if not admins:
        message_text = "В списке нет администраторов."
    else:
        user_list = "\n".join(admins)
        message_text = f"**Администраторы:**\n\n{user_list}"
    
    await callback_query.message.edit_text(
        message_text,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardBuilder().row(
            types.InlineKeyboardButton(text="↩️ Назад", callback_data="admin_back_to_menu")
        ).as_markup()
    )
    await callback_query.answer()


@router.callback_query(AdminForm.menu, F.data == "admin_remove_mechanic")
async def admin_remove_mechanic_prompt(callback_query: types.CallbackQuery, state: FSMContext):
    """Запрашивает ID механика для удаления."""
    await callback_query.message.edit_text(
        "Введите Telegram ID механика, которого хотите удалить."
    )
    await state.set_state(AdminForm.remove_user)
    await callback_query.answer()


@router.message(AdminForm.remove_user, F.text)
async def admin_remove_mechanic_process(message: types.Message, state: FSMContext):
    """Удаляет механика из списка авторизованных."""
    user_id_to_remove = message.text.strip()
    if not user_id_to_remove.isdigit():
        await message.answer("Неверный формат ID. Пожалуйста, введите только число.")
        return
        
    authorized_users = load_authorized_users()
    if user_id_to_remove in authorized_users:
        authorized_users.remove(user_id_to_remove)
        save_authorized_users(authorized_users)
        await message.answer(f"Пользователь с ID {user_id_to_remove} успешно удален из списка механиков.")
    else:
        await message.answer("Пользователь с таким ID не найден в списке механиков.")
    
    await state.set_state(AdminForm.menu)
    await message.answer("Админ-панель:", reply_markup=get_admin_menu_keyboard())


@router.callback_query(AdminForm.menu, F.data == "admin_remove_admin")
async def admin_remove_admin_prompt(callback_query: types.CallbackQuery, state: FSMContext):
    """Запрашивает ID администратора для удаления."""
    await callback_query.message.edit_text(
        "Введите Telegram ID администратора, которого хотите удалить."
    )
    await state.set_state(AdminForm.remove_admin)
    await callback_query.answer()


@router.message(AdminForm.remove_admin, F.text)
async def admin_remove_admin_process(message: types.Message, state: FSMContext):
    """Удаляет администратора из списка."""
    admin_id_to_remove = message.text.strip()
    if not admin_id_to_remove.isdigit():
        await message.answer("Неверный формат ID. Пожалуйста, введите только число.")
        return
        
    if str(message.from_user.id) == str(SUPER_ADMIN_ID):
        if admin_id_to_remove == str(SUPER_ADMIN_ID):
            await message.answer("Вы не можете удалить супер-администратора.")
        else:
            admins = load_admins()
            if admin_id_to_remove in admins:
                admins.remove(admin_id_to_remove)
                save_admins(admins)
                await message.answer(f"Пользователь с ID {admin_id_to_remove} успешно удален из списка администраторов.")
            else:
                await message.answer("Пользователь с таким ID не является администратором.")
    else:
        await message.answer("У вас нет прав для удаления других администраторов.")
    
    await state.set_state(AdminForm.menu)
    await message.answer("Админ-панель:", reply_markup=get_admin_menu_keyboard())


@router.callback_query(AdminForm.menu, F.data == "admin_set_dispatcher_id")
async def admin_set_dispatcher_id_prompt(callback_query: types.CallbackQuery, state: FSMContext):
    """Запрашивает ID чата диспетчера."""
    await callback_query.message.edit_text(
        "Введите ID чата или канала, куда бот будет отправлять отчёты. Это числовой ID, который можно узнать у @userinfobot или аналогичного."
    )
    await state.set_state(AdminForm.set_dispatcher_id)
    await callback_query.answer()


@router.message(AdminForm.set_dispatcher_id, F.text)
async def admin_set_dispatcher_id_process(message: types.Message, state: FSMContext):
    """Сохраняет ID чата диспетчера."""
    dispatcher_id = message.text.strip()
    # Простая проверка на число, ID чата может быть отрицательным
    if not re.match(r"^-?\d+$", dispatcher_id):
        await message.answer("Неверный формат ID. Пожалуйста, введите число.")
        return

    config = load_config()
    config["dispatcher_chat_id"] = int(dispatcher_id)
    save_config(config)
    
    await message.answer(f"ID чата диспетчера ({dispatcher_id}) успешно сохранён.")
    await state.set_state(AdminForm.menu)
    await message.answer("Админ-панель:", reply_markup=get_admin_menu_keyboard())


@router.callback_query(F.data == "admin_back_to_menu")
async def admin_back_to_menu(callback_query: types.CallbackQuery, state: FSMContext):
    """Возвращает в главное меню админ-панели."""
    await state.set_state(AdminForm.menu)
    await callback_query.message.edit_text("Админ-панель:", reply_markup=get_admin_menu_keyboard())
    await callback_query.answer()


@router.callback_query(AdminForm.menu, F.data == "admin_exit")
async def admin_exit(callback_query: types.CallbackQuery, state: FSMContext):
    """Выход из админ-панели."""
    await state.clear()
    await callback_query.message.edit_text("Вы вышли из админ-панели.")
    await callback_query.answer()

def print_ascii_art():
    ascii_art = r'''
        __  _________________  _____    _   ____________   __  __________    ____  __________ 
       /  |/  / ____/ ____/ / / /   |  / | / /  _/ ____/  / / / / ____/ /   / __ \/ ____/ __ \
      / /|_/ / __/ / /   / /_/ / /| | /  |/ // // /      / /_/ / __/ / /   / /_/ / __/ / /_/ /
     / /  / / /___/ /___/ __  / ___ |/ /|  // // /___   / __  / /___/ /___/ ____/ /___/ _, _/ 
    /_/  /_/_____/\____/_/ /_/_/  |_/_/ |_/___/\____/  /_/ /_/_____/_____/_/   /_____/_/ |_|  

    # Copyright (c) 2025 Void-Owl-Studio. Этот проект распространяется по лицензии MIT.
    # AlexaMerens
    '''
    print(ascii_art)

# Он будет срабатывать, если ни один из предыдущих обработчиков не подошел.
@router.callback_query()
async def unhandled_callback_query(callback_query: types.CallbackQuery):
    """
    Обработчик, который ловит все необработанные запросы от кнопок.
    Отвечает на запрос и скрывает клавиатуру, чтобы избежать повторных нажатий.
    """
    await callback_query.answer("Это действие больше недоступно.", show_alert=True)
    await callback_query.message.edit_reply_markup(reply_markup=None)

# А этот обработчик - для текстовых сообщений, которые не соответствуют ни одному состоянию.
@router.message(F.text)
async def unhandled_message(message: types.Message, state: FSMContext):
    """
    Обработчик, который ловит все необработанные текстовые сообщения.
    """
    await message.answer("Я не понимаю эту команду. Пожалуйста, используйте кнопки или команду /start.")
    await state.clear()

# --- Главная функция ---
async def main():
    """Запускает бота."""
    print_ascii_art()
    
    # Создаем файлы, если их нет
    if not os.path.exists(AUTHORIZED_USERS_FILE):
        with open(AUTHORIZED_USERS_FILE, "w") as f:
            json.dump([], f)
    if not os.path.exists(ADMINS_FILE):
        with open(ADMINS_FILE, "w") as f:
            json.dump([], f)
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w") as f:
            json.dump({}, f)

    # Инициализируем бота
    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=None))
    dp = Dispatcher()
    dp.include_router(router)
    
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
