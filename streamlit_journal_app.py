import os
import base64
import hashlib
import shutil
from io import StringIO, BytesIO
from pathlib import Path
from datetime import datetime, date, time as dtime

import pandas as pd
import streamlit as st
import streamlit_authenticator as stauth
from filelock import FileLock
from cryptography.fernet import Fernet
import zipfile

# --- Timezone support ---
try:
    from zoneinfo import ZoneInfo  # py>=3.9
except Exception:
    from pytz import timezone as ZoneInfo

TZ = ZoneInfo("Europe/Athens")

# ============================================================
# 1) AUTHENTICATION
# ============================================================
credentials = st.secrets["credentials"]
authenticator = stauth.Authenticate(
    credentials,
    cookie_name="journal_auth",
    key="super_secret_key",   # change to any random string
    cookie_expiry_days=7,
)
name, auth_status, username = authenticator.login("Login", "main")
if auth_status is False:
    st.error("Invalid credentials")
    st.stop()
elif auth_status is None:
    st.stop()
authenticator.logout("Logout", "sidebar")

# ============================================================
# 2) USER PATHS
# ============================================================
USER_DIR = os.path.join("data", username)
os.makedirs(USER_DIR, exist_ok=True)

USER_FILE = os.path.join(USER_DIR, "journal_entries.csv.enc")
LOCK_FILE = USER_FILE + ".lock"

ALL_COLUMNS = [
    "date", "time_local", "datetime_iso",  # date, time, combined local ISO
    "mood", "stress", "energy", "focus",
    "notes", "tags"
]

# ============================================================
# 3) ENCRYPTION UTILITIES (Fernet: AES-128-CBC + HMAC)
# ============================================================
def derive_key(password: str) -> bytes:
    digest = hashlib.sha256(password.encode()).digest()
    return base64.urlsafe_b64encode(digest)

def encrypt_csv(df: pd.DataFrame, password: str) -> bytes:
    key = derive_key(password)
    f = Fernet(key)
    csv_data = df.to_csv(index=False).encode("utf-8")
    return f.encrypt(csv_data)

def decrypt_csv(enc_bytes: bytes, password: str) -> pd.DataFrame:
    key = derive_key(password)
    f = Fernet(key)
    plain = f.decrypt(enc_bytes).decode("utf-8")
    return pd.read_csv(StringIO(plain))

# ============================================================
# 4) LOCKED + ENCRYPTED I/O
# ============================================================
def _ensure_columns(df: pd.DataFrame) -> pd.DataFrame:
    for c in ALL_COLUMNS:
        if c not in df.columns:
            df[c] = None
    return df[ALL_COLUMNS]

def load_data(path=USER_FILE) -> pd.DataFrame:
    with FileLock(LOCK_FILE):
        if not os.path.exists(path):
            return pd.DataFrame(columns=ALL_COLUMNS)

        password = st.session_state.get("enc_key")
        if not password:
            password = st.text_input(
                "🔑 Enter your encryption key to unlock your journal:",
                type="password",
                key="enter_key",
            )
            if not password:
                st.stop()
            st.session_state["enc_key"] = password

        with open(path, "rb") as f:
            enc = f.read()
        try:
            df = decrypt_csv(enc, st.session_state["enc_key"])
        except Exception:
            st.error("❌ Wrong key or corrupted file.")
            st.stop()

        return _ensure_columns(df)

def save_data(df: pd.DataFrame, path=USER_FILE):
    password = st.session_state.get("enc_key")
    if not password:
        password = st.text_input(
            "Set your encryption key:",
            type="password",
            key="set_key",
        )
        if not password:
            st.warning("Enter a key to save securely.")
            st.stop()
        st.session_state["enc_key"] = password

    enc = encrypt_csv(df, password)
    with FileLock(LOCK_FILE):
        with open(path, "wb") as f:
            f.write(enc)

# ============================================================
# 5) CHANGE / RESET ENCRYPTION KEY
# ============================================================
def change_encryption_key():
    if not os.path.exists(USER_FILE):
        st.warning("No journal file to re-encrypt yet.")
        return
    old_key = st.text_input("Current encryption key", type="password", key="old_key")
    new_key = st.text_input("New encryption key", type="password", key="new_key")
    confirm = st.text_input("Confirm new encryption key", type="password", key="confirm_key")

    if st.button("🔄 Re-encrypt with new key"):
        if new_key != confirm:
            st.error("New keys do not match.")
            return
        try:
            with FileLock(LOCK_FILE):
                enc_bytes = open(USER_FILE, "rb").read()
                df = decrypt_csv(enc_bytes, old_key)
                new_enc = encrypt_csv(df, new_key)
                open(USER_FILE, "wb").write(new_enc)
            st.session_state["enc_key"] = new_key
            st.success("✅ File re-encrypted with your new key.")
        except Exception:
            st.error("❌ Incorrect old key or decryption failed.")

# ============================================================
# 6) BACKUPS: daily auto + manual + restore
# ============================================================
BACKUP_DIR = Path(USER_DIR) / "backups"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)
RETENTION_DAYS = 14

def backup_filename_for_today() -> Path:
    today = datetime.now(TZ).strftime("%Y-%m-%d")
    return BACKUP_DIR / f"journal_entries_{today}.csv.enc"

def list_backups():
    return sorted(BACKUP_DIR.glob("journal_entries_*.csv.enc"))

def latest_backup():
    files = list_backups()
    return files[-1] if files else None

def create_backup_now():
    if not os.path.exists(USER_FILE):
        return False
    dest = backup_filename_for_today()
    if dest.exists():
        return True
    with FileLock(LOCK_FILE):
        shutil.copy2(USER_FILE, dest)
    return True

def enforce_retention():
    # keep only the most recent RETENTION_DAYS backups
    files = list_backups()
    if len(files) <= RETENTION_DAYS:
        return
    to_delete = files[0 : len(files) - RETENTION_DAYS]
    for f in to_delete:
        try:
            f.unlink()
        except Exception:
            pass

def ensure_backup_today():
    try:
        if create_backup_now():
            enforce_retention()
    except Exception:
        st.warning("Automatic backup attempt failed.")

# ============================================================
# 7) FORM STATE: always blank when returning to New Entry tab
# ============================================================
ENTRY_KEYS = [
    "entry_date", "entry_time", "entry_mood", "entry_stress",
    "entry_energy", "entry_focus", "entry_notes", "entry_tags"
]

def reset_entry_form():
    # Defaults: date=today local, time=now local, others blank/neutral
    now = datetime.now(TZ)
    st.session_state["entry_date"] = date.fromtimestamp(now.timestamp())
    st.session_state["entry_time"] = dtime(hour=now.hour, minute=now.minute, second=0)
    st.session_state["entry_mood"] = ""
    st.session_state["entry_stress"] = 5
    st.session_state["entry_energy"] = 5
    st.session_state["entry_focus"] = 5
    st.session_state["entry_notes"] = ""
    st.session_state["entry_tags"] = ""

def ensure_entry_defaults():
    for k in ENTRY_KEYS:
        if k not in st.session_state:
            reset_entry_form()
            break

# Track active tab to clear when user returns to "New Entry"
if "active_tab" not in st.session_state:
    st.session_state["active_tab"] = "New Entry"

def on_tab_change(tab_name: str):
    prev = st.session_state.get("active_tab")
    st.session_state["active_tab"] = tab_name
    if tab_name == "New Entry" and prev != "New Entry":
        reset_entry_form()  # blank form every time you come back

# ============================================================
# 8) APP UI
# ============================================================
st.title(f"🔒 Secure Journal — {name}")

# Do a daily backup early
ensure_backup_today()

st.sidebar.header("Security & Backups")
if st.sidebar.button("Change / Reset Encryption Key"):
    st.session_state["show_key_change"] = True
if st.session_state.get("show_key_change"):
    change_encryption_key()

with st.sidebar.expander("Backups"):
    if st.button("📦 Backup now"):
        ok = create_backup_now()
        st.success("Backup created (encrypted).") if ok else st.warning("Nothing to back up yet.")
    lb = latest_backup()
    if lb and lb.exists():
        with open(lb, "rb") as f:
            st.download_button(
                label=f"⬇️ Download latest backup ({lb.name})",
                data=f.read(),
                file_name=lb.name,
                mime="application/octet-stream",
                key="dl_latest_backup",
            )
    backups = list_backups()
    if backups:
        names = [b.name for b in backups]
        choice = st.selectbox("Restore from backup:", names, key="restore_choice")
        if st.button("Restore selected backup"):
            chosen = BACKUP_DIR / st.session_state["restore_choice"]
            try:
                with FileLock(LOCK_FILE):
                    shutil.copy2(chosen, USER_FILE)
                st.success("Restored. Reload app and unlock with your key.")
            except Exception as e:
                st.error(f"Restore failed: {e}")
    else:
        st.caption("No backups available yet.")

# Load data after security/backups are rendered
df = load_data()

# Tabs
tabs = st.tabs(["New Entry", "Entries", "Download"])
# Handle tab changes (Streamlit doesn't provide a direct callback; emulate with radio-like tracking)
# We'll simply call on_tab_change inside each tab's block.

# --- New Entry Tab ---
with tabs[0]:
    on_tab_change("New Entry")
    ensure_entry_defaults()

    st.subheader("New Journal Entry (Europe/Athens time)")
    with st.form("entry_form", clear_on_submit=True):
        # Use local defaults from session_state; always reset on tab return
        col1, col2 = st.columns(2)
        with col1:
            entry_date = st.date_input("Date", key="entry_date")
            entry_mood = st.text_input("Mood", key="entry_mood", placeholder="e.g., calm, anxious")
            entry_energy = st.slider("Energy (0–10)", 0, 10, key="entry_energy")
            entry_focus = st.slider("Focus (0–10)", 0, 10, key="entry_focus")
        with col2:
            entry_time = st.time_input("Time (local)", key="entry_time")
            entry_stress = st.slider("Stress (0–10)", 0, 10, key="entry_stress")
            entry_tags = st.text_input("Tags (comma-separated)", key="entry_tags")
        entry_notes = st.text_area("Notes", key="entry_notes")

        submitted = st.form_submit_button("Add Entry")

    if submitted:
        # Combine date + time into local timezone ISO string
        try:
            local_dt = datetime.combine(entry_date, entry_time, tzinfo=TZ)
        except TypeError:
            # For Python <3.11, tzinfo parameter might not be applied directly; fallback:
            naive = datetime.combine(entry_date, entry_time)
            local_dt = naive.replace(tzinfo=TZ)

        new_row = {
            "date": entry_date.isoformat(),
            "time_local": local_dt.strftime("%H:%M:%S"),
            "datetime_iso": local_dt.isoformat(),
            "mood": entry_mood,
            "stress": entry_stress,
            "energy": entry_energy,
            "focus": entry_focus,
            "notes": entry_notes,
            "tags": entry_tags,
        }
        df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)
        save_data(df)
        ensure_backup_today()  # if first save of the day, create a backup
        st.success("Entry saved securely!")
        # After save, blank the form (even if user stays on this tab)
        reset_entry_form()

# --- Entries Tab ---
with tabs[1]:
    on_tab_change("Entries")
    st.subheader("Your Journal Entries (times shown in Europe/Athens)")
    st.dataframe(df)

# --- Download Tab ---
with tabs[2]:
    on_tab_change("Download")
    st.subheader("Download Options")
    # 1) Decrypted CSV
    decrypted_csv_bytes = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇️ Download Decrypted CSV",
        data=decrypted_csv_bytes,
        file_name="journal_entries.csv",
        mime="text/csv",
        key="dl_plain_csv",
    )

    # 1b) Decrypted CSV as ZIP
    zip_buf = BytesIO()
    with zipfile.ZipFile(zip_buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("journal_entries.csv", decrypted_csv_bytes)
    zip_buf.seek(0)
    st.download_button(
        label="⬇️ Download Decrypted CSV (ZIP)",
        data=zip_buf,
        file_name="journal_entries.zip",
        mime="application/zip",
        key="dl_plain_zip",
    )

    # 2) Encrypted file (.csv.enc)
    try:
        with open(USER_FILE, "rb") as f:
            enc_bytes = f.read()
        st.download_button(
            label="⬇️ Download Encrypted File (.csv.enc)",
            data=enc_bytes,
            file_name="journal_entries.csv.enc",
            mime="application/octet-stream",
            key="dl_encrypted",
        )
    except FileNotFoundError:
        st.info("No encrypted file found yet. Save an entry first.")

    # Checksums
    def sha256_hex(b: bytes) -> str:
        return hashlib.sha256(b).hexdigest()

    colA, colB = st.columns(2)
    with colA:
        st.caption("SHA-256 (decrypted CSV)")
        st.code(sha256_hex(decrypted_csv_bytes), language="text")
    with colB:
        st.caption("SHA-256 (encrypted .csv.enc)")
        if "enc_bytes" in locals():
            st.code(sha256_hex(enc_bytes), language="text")
        else:
            st.text("—")

# Footer info
st.caption("Times are saved and displayed in Europe/Athens timezone.")
