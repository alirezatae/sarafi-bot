# bot.py
import re
import telebot
from telebot import types
from config import BOT_TOKEN, ADMIN_IDS
from db import (
    init_db,
    create_transaction,
    get_pending_transactions,
    add_uk_account,
    get_uk_accounts,
    get_transaction,
    set_transaction_status,
    set_transaction_account_text,
    save_receipt_file_id,
    get_latest_tx_by_user_and_status,
    save_recipient_info,
)

def format_user(username, fullname, user_id):
    if username:
        return f"@{username}"
    if fullname:
        return f"{fullname} (ID: {user_id})"
    return f"ID: {user_id}"

def is_admin(user_id):
    return user_id in ADMIN_IDS

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
user_state = {}


# --------- /start ---------
@bot.message_handler(commands=["start"])
def cmd_start(message):
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.add("📊 نمایش نرخ روز")
    keyboard.add("💸 حواله از انگلستان به ایران")
    keyboard.add("💷 انتقال از ایران به انگلستان")
    keyboard.add("📎 راهنما")

    bot.send_message(
        message.chat.id,
        "به صرافی اعتبار خوش آمدید 👋\n"
        "لطفاً یکی از گزینه‌های زیر را انتخاب کنید:",
        reply_markup=keyboard,
    )


# --------- نرخ روز ---------
@bot.message_handler(func=lambda m: m.text == "📊 نمایش نرخ روز")
def show_rates(message):
    keyboard = types.InlineKeyboardMarkup()
    keyboard.add(
        types.InlineKeyboardButton("CASH", callback_data="rate_cash"),
        types.InlineKeyboardButton("TRANSFER", callback_data="rate_transfer"),
    )
    bot.send_message(message.chat.id, "نوع معامله را انتخاب کنید:", reply_markup=keyboard)


@bot.callback_query_handler(func=lambda call: call.data.startswith("rate_"))
def process_rate_callback(call):
    kind = call.data.split("_")[1]
    if kind == "cash":
        buy, sell = 130000, 135000
        title = "نرخ CASH"
    else:
        buy, sell = 132000, 137000
        title = "نرخ TRANSFER"

    text = f"{title}\nخرید: <b>{buy:,}</b> تومان\nفروش: <b>{sell:,}</b> تومان"
    bot.edit_message_text(text, call.message.chat.id, call.message.message_id)
    bot.answer_callback_query(call.id)


# --------- راهنما / ایران->انگلیس (دمو) ---------
@bot.message_handler(func=lambda m: m.text == "💷 انتقال از ایران به انگلستان")
def ir_to_uk_demo(message):
    bot.send_message(message.chat.id, "دموی انتقال از ایران به انگلستان به‌زودی فعال می‌شود.")

@bot.message_handler(func=lambda m: m.text == "📎 راهنما")
def help_menu(message):
    bot.send_message(
        message.chat.id,
        "برای ارسال رسید پرداخت در اپلیکیشن بانک:\n"
        "- از بخش Share / اشتراک‌گذاری استفاده کنید.\n"
        "- گزینه Telegram را انتخاب کرده و ربات صرافی را انتخاب کنید.\n"
        "- یا اسکرین‌شات بگیرید و مستقیماً به ربات ارسال کنید."
    )


# ================= UK -> IR =================

@bot.message_handler(func=lambda m: m.text == "💸 حواله از انگلستان به ایران")
def uk_to_ir_start(message):
    bot.send_message(
        message.chat.id,
        "لطفاً مبلغ حواله را به پوند وارد کنید.\n"
        "(اگر مبلغ زیر £500 باشد، 10 پوند کارمزد اضافه می‌شود.)"
    )
    user_state[message.chat.id] = "WAITING_UK_AMOUNT"


@bot.message_handler(func=lambda m: user_state.get(m.chat.id) == "WAITING_UK_AMOUNT")
def uk_to_ir_amount(message):
    amount_text = message.text.replace(",", "").strip()
    if not re.match(r"^\d+(\.\d+)?$", amount_text):
        bot.send_message(message.chat.id, "❌ لطفاً فقط عدد وارد کنید.")
        return

    amount = float(amount_text)
    fee = 10 if amount < 500 else 0
    final_amount = amount + fee

    rate = 132000
    amount_irt = int(final_amount * rate)

    user_state[message.chat.id] = {
        "step": "CONFIRM",
        "amount": amount,
        "fee": fee,
        "final": final_amount,
        "irt": amount_irt,
    }

    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("تأیید ✔️", callback_data="confirm_uk"))
    kb.add(types.InlineKeyboardButton("لغو ❌", callback_data="cancel_uk"))

    bot.send_message(
        message.chat.id,
        f"🔹 مبلغ وارد شده: £{amount}\n"
        f"🔸 کارمزد: £{fee}\n"
        f"🔹 مبلغ نهایی: <b>£{final_amount}</b>\n"
        f"🔸 معادل تقریبی: <b>{amount_irt:,} تومان</b>\n\n"
        "آیا تأیید می‌کنید؟",
        reply_markup=kb
    )


@bot.callback_query_handler(func=lambda call: call.data in ["confirm_uk", "cancel_uk"])
def confirm_or_cancel(call):
    chat_id = call.message.chat.id
    data = user_state.get(chat_id)

    if call.data == "cancel_uk":
        bot.edit_message_text("❌ عملیات لغو شد.", chat_id, call.message.message_id)
        user_state.pop(chat_id, None)
        return

    if not isinstance(data, dict) or data.get("step") != "CONFIRM":
        bot.answer_callback_query(call.id, "اطلاعات این درخواست پیدا نشد.", show_alert=True)
        return

    create_transaction(
        user_id=chat_id,
        username=call.from_user.username,
        fullname=call.from_user.full_name,
        amount_gbp=data["amount"],
        final_gbp=data["final"],
        amount_irt=data["irt"],
    )

    bot.edit_message_text(
        "✅ درخواست شما ثبت شد.\n"
        f"مبلغ نهایی: <b>£{data['final']}</b>\n"
        f"معادل تقریبی: <b>{data['irt']:,} تومان</b>\n\n"
        "لطفاً منتظر ارسال شماره حساب توسط پشتیبانی باشید.",
        chat_id,
        call.message.message_id,
    )

    display = format_user(call.from_user.username, call.from_user.full_name, chat_id)

    for admin in ADMIN_IDS:
        bot.send_message(
            admin,
            f"🔔 درخواست جدید حواله UK→IR\n"
            f"مشتری: {display}\n"
            f"مبلغ نهایی: £{data['final']}\n"
            f"معادل: {data['irt']:,} تومان\n"
            "وضعیت: منتظر ارسال شماره حساب"
        )

    user_state.pop(chat_id, None)


# ================= Admin Panel =================

@bot.message_handler(commands=["admin"])
def admin_menu(message):
    if not is_admin(message.from_user.id):
        return

    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("درخواست‌های منتظر شماره حساب", callback_data="admin_pending"))
    kb.add(types.InlineKeyboardButton("افزودن حساب انگلیس", callback_data="admin_add_uk_account"))
    kb.add(types.InlineKeyboardButton("حساب‌های انگلیس", callback_data="admin_list_uk_accounts"))

    bot.send_message(message.chat.id, "پنل ادمین:", reply_markup=kb)


@bot.callback_query_handler(func=lambda call: call.data == "admin_list_uk_accounts")
def admin_list_uk_accounts(call):
    if not is_admin(call.from_user.id):
        return

    accounts = get_uk_accounts()
    if not accounts:
        bot.answer_callback_query(call.id, "هیچ حساب انگلیسی ثبت نشده است.", show_alert=True)
        return

    lines = []
    for acc_id, bank, sort_code, account_number, name in accounts:
        lines.append(f"#{acc_id} - {bank}\n{name}\nSC: {sort_code} | ACC: {account_number}")

    bot.send_message(call.message.chat.id, "حساب‌های ثبت‌شده:\n\n" + "\n\n".join(lines))
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data == "admin_add_uk_account")
def admin_add_uk_account_help(call):
    if not is_admin(call.from_user.id):
        return
    bot.send_message(
        call.message.chat.id,
        "برای افزودن حساب انگلیس:\n"
        "/add_uk_account BANK SORTCODE ACCOUNTNUMBER NAME\n"
        "مثال:\n"
        "/add_uk_account LLOYDS 11-33-33 456797545 mehdi"
    )
    bot.answer_callback_query(call.id)


@bot.message_handler(commands=["add_uk_account"])
def admin_add_uk_account_cmd(message):
    if not is_admin(message.from_user.id):
        return

    try:
        _, bank, sort_code, account_number, name = message.text.split(maxsplit=4)
    except ValueError:
        bot.send_message(message.chat.id, "فرمت اشتباه است. مثال:\n/add_uk_account LLOYDS 11-33-33 456797545 mehdi")
        return

    add_uk_account(bank, sort_code, account_number, name)
    bot.send_message(message.chat.id, "✅ حساب انگلیس ذخیره شد.")


@bot.callback_query_handler(func=lambda call: call.data == "admin_pending")
def admin_show_pending(call):
    if not is_admin(call.from_user.id):
        return

    rows = get_pending_transactions()
    if not rows:
        bot.answer_callback_query(call.id, "درخواستی در انتظار شماره حساب نیست.")
        return

    kb = types.InlineKeyboardMarkup()
    for tx_id, username, final_gbp, amount_irt in rows:
        label = f"#{tx_id} {('@'+username) if username else ''} - £{final_gbp}"
        kb.add(types.InlineKeyboardButton(label, callback_data=f"admin_tx_{tx_id}"))

    bot.send_message(call.message.chat.id, "درخواست‌های باز:", reply_markup=kb)
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_tx_"))
def admin_tx_detail(call):
    if not is_admin(call.from_user.id):
        return

    tx_id = int(call.data.split("_")[2])
    tx = get_transaction(tx_id)
    if not tx:
        bot.answer_callback_query(call.id, "تراکنش یافت نشد.", show_alert=True)
        return

    _, user_id, username, fullname, final_gbp, amount_irt, status = tx
    display = format_user(username, fullname, user_id)

    text = (
        f"جزئیات تراکنش #{tx_id}\n"
        f"مشتری: {display}\n"
        f"مبلغ نهایی: £{final_gbp}\n"
        f"معادل: {amount_irt:,} تومان\n"
        f"وضعیت: {status}"
    )

    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("ارسال شماره حساب به مشتری", callback_data=f"admin_sendacc_{tx_id}"))
    kb.add(types.InlineKeyboardButton("❌ لغو تراکنش", callback_data=f"admin_cancel_{tx_id}"))

    bot.send_message(call.message.chat.id, text, reply_markup=kb)
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_cancel_"))
def admin_cancel_tx(call):
    if not is_admin(call.from_user.id):
        return

    tx_id = int(call.data.split("_")[2])
    tx = get_transaction(tx_id)
    if not tx:
        bot.answer_callback_query(call.id, "تراکنش یافت نشد.", show_alert=True)
        return

    _, user_id, username, fullname, final_gbp, amount_irt, status = tx

    if status not in ("WAITING_FOR_ACCOUNT", "WAITING_FOR_RECEIPT"):
        bot.answer_callback_query(call.id, "این تراکنش در این مرحله قابل لغو نیست.", show_alert=True)
        return

    set_transaction_status(tx_id, "CANCELLED_BY_ADMIN")
    bot.send_message(user_id, "درخواست حواله شما توسط صرافی لغو شد.")
    bot.send_message(call.message.chat.id, f"تراکنش #{tx_id} لغو شد.")
    bot.answer_callback_query(call.id, "لغو شد.")


@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_sendacc_"))
def admin_send_account(call):
    if not is_admin(call.from_user.id):
        return

    tx_id = int(call.data.split("_")[2])
    accounts = get_uk_accounts()
    if not accounts:
        bot.answer_callback_query(call.id, "هیچ حسابی ثبت نشده. از /add_uk_account استفاده کنید.", show_alert=True)
        return

    kb = types.InlineKeyboardMarkup()
    for acc_id, bank, sort_code, account_number, name in accounts:
        kb.add(types.InlineKeyboardButton(f"{bank} - {name}", callback_data=f"admin_chooseacc_{tx_id}_{acc_id}"))

    bot.send_message(call.message.chat.id, "یک حساب انتخاب کنید:", reply_markup=kb)
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda call: call.data.startswith("admin_chooseacc_"))
def admin_choose_account(call):
    if not is_admin(call.from_user.id):
        return

    parts = call.data.split("_")
    tx_id = int(parts[2])
    acc_id = int(parts[3])

    tx = get_transaction(tx_id)
    if not tx:
        bot.answer_callback_query(call.id, "تراکنش یافت نشد.", show_alert=True)
        return

    _, user_id, username, fullname, final_gbp, amount_irt, status = tx

    acc = next((a for a in get_uk_accounts() if a[0] == acc_id), None)
    if not acc:
        bot.answer_callback_query(call.id, "حساب یافت نشد.", show_alert=True)
        return

    _, bank, sort_code, account_number, name = acc

    text = (
        f"£{final_gbp}\n"
        f"BANK: {bank}\n"
        f"Sort code: {sort_code}\n"
        f"Account number: {account_number}\n"
        f"Name: {name}"
    )

    bot.send_message(user_id, text)
    bot.send_message(
        user_id,
        "این اطلاعات حساب تا ۳۰ دقیقه معتبر است.\n"
        "پس از انجام پرداخت، لطفاً تصویر رسید خود را برای همین ربات ارسال کنید."
    )

    set_transaction_account_text(tx_id, text)
    set_transaction_status(tx_id, "WAITING_FOR_RECEIPT")

    bot.send_message(call.message.chat.id, f"شماره حساب برای تراکنش #{tx_id} ارسال شد.")
    bot.answer_callback_query(call.id)


# --------- دریافت رسید ---------
@bot.message_handler(content_types=["photo"])
def handle_receipt(message):
    user_id = message.chat.id
    tx = get_latest_tx_by_user_and_status(user_id, "WAITING_FOR_RECEIPT")
    if not tx:
        return

    tx_id = tx["id"]
    file_id = message.photo[-1].file_id
    save_receipt_file_id(tx_id, file_id)

    bot.send_message(user_id, "رسید شما دریافت شد. لطفاً منتظر بررسی صرافی بمانید. ✅")

    for admin in ADMIN_IDS:
        bot.forward_message(admin, user_id, message.message_id)

        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("تأیید پرداخت ✔", callback_data=f"confirm_tx_{tx_id}"))
        kb.add(types.InlineKeyboardButton("رد رسید ❌", callback_data=f"reject_tx_{tx_id}"))

        bot.send_message(admin, f"رسید جدید برای تراکنش #{tx_id} دریافت شد.", reply_markup=kb)


@bot.callback_query_handler(func=lambda call: call.data.startswith("confirm_tx_") or call.data.startswith("reject_tx_"))
def admin_handle_receipt_decision(call):
    if not is_admin(call.from_user.id):
        return

    tx_id = int(call.data.split("_")[2])
    tx = get_transaction(tx_id)
    if not tx:
        bot.answer_callback_query(call.id, "تراکنش یافت نشد.", show_alert=True)
        return

    _, user_id, username, fullname, final_gbp, amount_irt, status = tx

    if call.data.startswith("confirm_tx_"):
        set_transaction_status(tx_id, "WAITING_FOR_IR_INFO")
        bot.send_message(
            user_id,
            "پرداخت شما تأیید شد ✅\n"
            "لطفاً اطلاعات حساب گیرنده در ایران را به این شکل ارسال کنید:\n"
            "نام گیرنده\n"
            "شماره حساب / کارت\n"
            "شماره شبا (در صورت وجود)"
        )
        bot.answer_callback_query(call.id, "تأیید شد.")
    else:
        set_transaction_status(tx_id, "RECEIPT_REJECTED")
        bot.send_message(user_id, "رسید پرداخت شما تأیید نشد. لطفاً با پشتیبانی تماس بگیرید.")
        bot.answer_callback_query(call.id, "رد شد.")


# --------- دریافت اطلاعات گیرنده ایران ---------
@bot.message_handler(content_types=["text"])
def handle_iran_account(message):
    user_id = message.chat.id

    # جلوگیری از تداخل با مرحله مبلغ
    if user_state.get(user_id) == "WAITING_UK_AMOUNT":
        return

    tx = get_latest_tx_by_user_and_status(user_id, "WAITING_FOR_IR_INFO")
    if not tx:
        return

    tx_id = tx["id"]
    lines = [l.strip() for l in message.text.strip().splitlines() if l.strip()]
    if not lines:
        bot.send_message(user_id, "❌ متن خالی بود. لطفاً دوباره ارسال کنید.")
        return

    name = lines[0]
    account = lines[1] if len(lines) > 1 else ""
    iban = lines[2] if len(lines) > 2 else ""

    save_recipient_info(tx_id, name, account, iban)

    bot.send_message(user_id, "اطلاعات گیرنده ثبت شد ✅\nحواله شما در صف انجام قرار گرفت.")

    for admin in ADMIN_IDS:
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("✅ حواله انجام شد", callback_data=f"done_tx_{tx_id}"))

        bot.send_message(
            admin,
            f"اطلاعات گیرنده ایران برای تراکنش #{tx_id} ثبت شد:\n"
            f"نام گیرنده: {name}\n"
            f"شماره حساب/کارت: {account}\n"
            f"شبا: {iban}",
            reply_markup=kb
        )


@bot.callback_query_handler(func=lambda call: call.data.startswith("done_tx_"))
def admin_mark_done(call):
    if not is_admin(call.from_user.id):
        return

    tx_id = int(call.data.split("_")[2])
    tx = get_transaction(tx_id)
    if not tx:
        bot.answer_callback_query(call.id, "تراکنش یافت نشد.", show_alert=True)
        return

    _, user_id, username, fullname, final_gbp, amount_irt, status = tx
    set_transaction_status(tx_id, "DONE")

    bot.send_message(user_id, "حواله شما انجام شد ✅\nدر صورت نیاز به رسید، با پشتیبانی در تماس باشید.")
    bot.send_message(call.message.chat.id, f"تراکنش #{tx_id} DONE شد.")
    bot.answer_callback_query(call.id, "ثبت شد.")


# --------- run ---------
if __name__ == "__main__":
    print("Bot is running...")
    init_db()
    bot.infinity_polling()

