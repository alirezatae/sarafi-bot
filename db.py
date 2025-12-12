# db.py
import sqlite3
import datetime

DB_NAME = "database.db"


def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()

    c.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            fullname TEXT,
            amount_gbp REAL,
            final_gbp REAL,
            amount_irt REAL,
            status TEXT,
            uk_account_text TEXT,
            receipt_file_id TEXT,
            created_at TEXT,
            recipient_name TEXT,
            recipient_account TEXT,
            recipient_iban TEXT
        )
    """)

    c.execute("""
        CREATE TABLE IF NOT EXISTS uk_accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bank TEXT,
            sort_code TEXT,
            account_number TEXT,
            name TEXT
        )
    """)

    conn.commit()
    conn.close()


def create_transaction(user_id, username, fullname, amount_gbp, final_gbp, amount_irt):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        INSERT INTO transactions
        (user_id, username, fullname, amount_gbp, final_gbp, amount_irt, status, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        user_id,
        username,
        fullname,
        amount_gbp,
        final_gbp,
        amount_irt,
        "WAITING_FOR_ACCOUNT",
        datetime.datetime.utcnow().isoformat()
    ))
    conn.commit()
    conn.close()


def get_pending_transactions():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        SELECT id, username, final_gbp, amount_irt
        FROM transactions
        WHERE status = 'WAITING_FOR_ACCOUNT'
        ORDER BY id DESC
    """)
    rows = c.fetchall()
    conn.close()
    return rows


def add_uk_account(bank, sort_code, account_number, name):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        INSERT INTO uk_accounts (bank, sort_code, account_number, name)
        VALUES (?, ?, ?, ?)
    """, (bank, sort_code, account_number, name))
    conn.commit()
    conn.close()


def get_uk_accounts():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT id, bank, sort_code, account_number, name FROM uk_accounts")
    rows = c.fetchall()
    conn.close()
    return rows


def get_transaction(tx_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        SELECT id, user_id, username, fullname, final_gbp, amount_irt, status
        FROM transactions
        WHERE id = ?
    """, (tx_id,))
    row = c.fetchone()
    conn.close()
    return row


def set_transaction_status(tx_id, status):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE transactions SET status = ? WHERE id = ?", (status, tx_id))
    conn.commit()
    conn.close()


def set_transaction_account_text(tx_id, text):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE transactions SET uk_account_text = ? WHERE id = ?", (text, tx_id))
    conn.commit()
    conn.close()


def save_receipt_file_id(tx_id, file_id):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("UPDATE transactions SET receipt_file_id = ? WHERE id = ?", (file_id, tx_id))
    conn.commit()
    conn.close()


def get_latest_tx_by_user_and_status(user_id, status):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        SELECT id, user_id, final_gbp, amount_irt
        FROM transactions
        WHERE user_id = ? AND status = ?
        ORDER BY id DESC
        LIMIT 1
    """, (user_id, status))
    row = c.fetchone()
    conn.close()
    if not row:
        return None
    return {"id": row[0], "user_id": row[1], "final_gbp": row[2], "amount_irt": row[3]}


def save_recipient_info(tx_id, name, account, iban):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        UPDATE transactions
        SET recipient_name = ?, recipient_account = ?, recipient_iban = ?, status = 'READY_TO_SEND_IR'
        WHERE id = ?
    """, (name, account, iban, tx_id))
    conn.commit()
    conn.close()

