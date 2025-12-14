import json
import os
import re
from datetime import datetime, timedelta
from prettytable import PrettyTable
import pwinput
import matplotlib.pyplot as plt

# Mengambil data ke directory
DATA_DIR = "data"
USERS_FILE = os.path.join(DATA_DIR, "pengguna.json")
PRODUCTS_FILE = os.path.join(DATA_DIR, "produk.json")
TRANSACTIONS_FILE = os.path.join(DATA_DIR, "data_transaksi.json")

LOCK_DURATION_SECS = 30  # Durasi Kunci akun jika salah password
VIP_DISCOUNT_PERCENT = 7  # diskon default untuk member VIP (7% untuk pembelian >100rb)
SUBSCRIPTION_DAYS = 30
VIP_BONUS_LUNITE = 200  # bonus Lunite untuk VIP pada pembelian >100rb
VOUCHER_PERCENT_ON_BIG = 3  # voucher 3% jika transaksi >100rb
VOUCHER_EXPIRY_DAYS = 3  # voucher berlaku 3 hari

# # Utilitas: load/save file ke JSON

def load_json(path):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return []


def save_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def ensure_data_dir():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
    for path in [USERS_FILE, PRODUCTS_FILE, TRANSACTIONS_FILE]:
        if not os.path.exists(path):
            save_json(path, [])


def next_id(prefix, existing_ids):
    num = 1
    while True:
        candidate = f"{prefix}-{num:04d}"
        if candidate not in existing_ids:
            return candidate
        num += 1

def find_user_by_username(users, username):
    return next((u for u in users if u.get("username") == username), None)


def find_user_by_id(users, uid):
    return next((u for u in users if u.get("id") == uid), None)


def find_product(products, pid):
    return next((p for p in products if p.get("id") == pid), None)

# Setting agar Username hanya berupa huruf
USERNAME_REGEX = re.compile(r"^[A-Za-z]{3,16}$")

def validate_username(username):
    if not USERNAME_REGEX.match(username):
        return False, "Username harus 3-16 huruf alphabet tanpa angka atau simbol."
    return True, ""


def validate_password(password):
    if len(password) < 6 or len(password) > 16:
        return False, "Password harus antara 6 sampai 16 karakter."
    # hitung simbol unik 
    symbols = set(ch for ch in password if not ch.isalnum())
    if len(symbols) > 3:
        return False, "Password tidak boleh memiliki lebih dari 3 simbol unik."
    return True, ""


def validate_uid(uid):
    if not uid.isdigit():
        return False, "UID harus berupa angka."
    if len(uid) < 8:
        return False, "UID harus minimal 8 digit."
    return True, ""

# ---------- VOUCHER HELPERS ----------
def gen_voucher_id(existing_ids):
    return next_id('V', existing_ids)

def create_voucher_for_user(user, percent, users):
    # buat id unik dari semua voucher di semua user
    existing_vids = []
    for u in users:
        for vv in u.get('vouchers', []):
            existing_vids.append(vv.get('id'))
    vid = gen_voucher_id(existing_vids)
    created_at = datetime.now()
    expiry = created_at + timedelta(days=VOUCHER_EXPIRY_DAYS)
    v = {
        'id': vid,
        'percent': percent,
        'used': False,
        'created_at': created_at.strftime("%Y-%m-%d %H:%M:%S"),
        'expiry': expiry.strftime("%Y-%m-%d %H:%M:%S")
    }
    user.setdefault('vouchers', []).append(v)
    return v

def filter_valid_vouchers(vouchers):
    """ kembalikan hanya voucher yang belum dipakai dan belum kadaluarsa """
    res = []
    now = datetime.now()
    for v in vouchers:
        if v.get('used'):
            continue
        try:
            exp = datetime.strptime(v.get('expiry'), "%Y-%m-%d %H:%M:%S")
            if now <= exp:
                res.append(v)
        except Exception:
            # jika expiry corrupt, ignore voucher
            continue
    return res

# Tampilkan tabel produk
def show_products_table(products, role='member'):
    table = PrettyTable()
    table.field_names = ["ID", "Nama", "Harga", "Harga(VIP)", "Tipe", "Stok"]
    for p in products:
        vip_price = int(p['price'] * (100 - VIP_DISCOUNT_PERCENT) / 100)
        table.add_row([p['id'], p['name'], p['price'], vip_price, p.get('type','-'), p.get('stock',0)])
    print(table)

#Tampilkan tabel akun pengguna
def show_user_profile(user):
    print(f"ID: {user.get('id')}")
    print(f"Username: {user.get('username')}")
    print(f"Role: {user.get('role')}")
    print(f"Saldo (Rp): {user.get('balance',0)}")
    print(f"Lunite: {user.get('lunite',0)}")
    vip_expiry = user.get('vip_expiry')
    if vip_expiry:
        print(f"VIP expiry: {vip_expiry}")
    pending = user.get('pending_subscription_days',0)
    if pending:
        print(f"Pending subscription extension: {pending} hari")
    vouchers = user.get('vouchers',[])
    valid_vs = filter_valid_vouchers(vouchers)
    if valid_vs:
        vs = ', '.join([f"{v['id']}({v['percent']}%){' used' if v.get('used') else ''}" for v in valid_vs])
        print(f"Vouchers aktif: {vs}")
    else:
        print("Vouchers: -")

# Authentifikasi Akun
#Buat akun
def register(users):
    print("=== Registrasi Akun Baru ===")
    username = input("Username baru: ").strip()
    ok, msg = validate_username(username)
    if not ok:
        print("Error:", msg)
        return None
    if find_user_by_username(users, username):
        print("Username sudah digunakan.")
        return None
    password = pwinput.pwinput("Password: ").strip()
    ok, msg = validate_password(password)
    if not ok:
        print("Error:", msg)
        return None
    
    # Role akun baru bawaan/default
    existing_ids = [u.get('id') for u in users if u.get('id')]
    uid = next_id('U', existing_ids)
    new_user = {
        'id': uid,
        'username': username,
        'password': password,
        'role': 'member',
        'balance': 0,
        'lunite': 0,
        'failed_attempts': 0,
        'locked_until': None,
        'vouchers': [],
        'vip_expiry': None,
        'pending_subscription_days': 0
    }
    #Simpan data akun baru
    users.append(new_user)
    save_json(USERS_FILE, users)
    print(f"Akun berhasil dibuat. ID: {uid}. Silakan login kembali.")
    return new_user

#Periksa status VIP Akun
def check_and_update_vip_status(user):
    # Jika VIP kadaluarsa
    vip_expiry = user.get('vip_expiry')
    if vip_expiry:
        try:
            exp = datetime.strptime(vip_expiry, "%Y-%m-%d %H:%M:%S")
            if datetime.now() > exp:
                # nonaktifkan VIP
                user['vip_expiry'] = None
                user['role'] = 'member'

                # Jika ada perpanjangan durasi VIP
                pending_days = user.get('pending_subscription_days',0)
                if pending_days > 0:
                    new_exp = datetime.now() + timedelta(days=pending_days)
                    user['vip_expiry'] = new_exp.strftime("%Y-%m-%d %H:%M:%S")
                    user['role'] = 'vip'
                    user['pending_subscription_days'] = 0
                return True  
        except Exception:
            user['vip_expiry'] = None
            user['role'] = 'member'
            return True
    return False


def login(users):
    print("=== Log In ===")
    username = input("Username: ").strip()
    user = find_user_by_username(users, username)
    if not user:
        print("User tidak ditemukan.")
        return None
    # cek lock
    if user.get('locked_until'):
        try:
            lu = datetime.strptime(user.get('locked_until'), "%Y-%m-%d %H:%M:%S")
            if datetime.now() < lu:
                rem = int((lu - datetime.now()).total_seconds())
                print(f"Akun terkunci sementara. Coba lagi dalam {rem} detik.")
                return None
            else:
                user['locked_until'] = None
                user['failed_attempts'] = 0
        except Exception:
            user['locked_until'] = None
            user['failed_attempts'] = 0

    password = pwinput.pwinput("Password: ").strip()
    if password == user.get('password'):
        user['failed_attempts'] = 0
        user['locked_until'] = None
        # cek status VIP ketika login
        changed = check_and_update_vip_status(user)
        if changed:
            save_json(USERS_FILE, users)
        save_json(USERS_FILE, users)
        print(f"Selamat datang, {user.get('username')}! Role: {user.get('role')}")
        return user
    else:
        user['failed_attempts'] = user.get('failed_attempts',0) + 1
        print("Password salah.")
        if user['failed_attempts'] >= 3:
            lu = datetime.now() + timedelta(seconds=LOCK_DURATION_SECS)
            user['locked_until'] = lu.strftime("%Y-%m-%d %H:%M:%S")
            print(f"Akun dikunci sementara selama {LOCK_DURATION_SECS} detik karena 3 kali gagal login.")
        save_json(USERS_FILE, users)
        return None

# ---------- Pesan Selamat Datang ----------
def Pesan_Sambutan():
    # Ubah nama hari ke Bahasa Indonesia
    def hari_indonesia(day_name):
        mapping = {
            "Monday": "Senin",
            "Tuesday": "Selasa",
            "Wednesday": "Rabu",
            "Thursday": "Kamis",
            "Friday": "Jumat",
            "Saturday": "Sabtu",
            "Sunday": "Minggu"
        }
        return mapping.get(day_name, day_name)

    now = datetime.now()
    day_name = now.strftime("%A")
    day_name_indo = hari_indonesia(day_name)

    # format tanggal dd-mm-yyyy
    date_str = now.strftime("%d %B %Y")
    hour = now.hour

    if 4 <= hour < 10:
        salam = "Pagi"
    elif 10 <= hour < 15:
        salam = "Siang"
    elif 15 <= hour < 18:
        salam = "Sore"
    else:
        salam = "Malam"

    print(f"Selamat Hari {day_name_indo}, {date_str}. Selamat {salam}!")


# Pembelian Lunite
def buy_lunite_flow(current_user, users, products, transactions):
    print("=== Beli Lunite ===")
    show_products_table(products, role=current_user.get('role'))
    pid = input("Masukkan ID produk: ").strip()
    p = find_product(products, pid)
    if not p:
        print("Produk tidak ditemukan.")
        return
    if p.get('stock',0) <= 0:
        print("Stok habis.")
        return
    
    # Input UID
    uid_game = input("Masukkan UID Wuthering Waves (minimal 8 digit): ").strip()
    ok, msg = validate_uid(uid_game)
    if not ok:
        print("UID Tidak Valid:", msg)
        return
    qty = 1
    # harga berdasarkan role akun
    unit_price = p['price']
    applied_vip_discount = 0
    # Jika VIP dan produk > 100rb, berikan special VIP discount (7%) dan bonus Lunite
    if current_user.get('role') == 'vip' and p['price'] > 100000:
        applied_vip_discount = VIP_DISCOUNT_PERCENT  # 7% (konstan di atas)
        unit_price = int(unit_price * (100 - applied_vip_discount) / 100)
    elif current_user.get('role') == 'vip':
        # jika VIP tapi produk <=100rb tetap bisa mendapat harga VIP (jika Anda mau).
        unit_price = int(unit_price * (100 - VIP_DISCOUNT_PERCENT) / 100)

    subtotal = unit_price * qty

    # pilih voucher (hanya voucher valid & belum expired)
    usable_vouchers = filter_valid_vouchers(current_user.get('vouchers', []))
    applied_voucher = None
    if usable_vouchers:
        print("Voucher tersedia:")
        for i,v in enumerate(usable_vouchers,1):
            print(f"{i}. {v['id']} - {v['percent']}% (exp: {v.get('expiry')})")
        choose = input("Pakai voucher? (masukkan nomor / kosong = tidak): ").strip()
        if choose:
            try:
                idx = int(choose)-1
                applied_voucher = usable_vouchers[idx]
            except Exception:
                applied_voucher = None
    else:
        print("Anda Tidak Memiliki Voucher aktif.")

    # ringkasan & konfirmasi
    total = subtotal
    disc = 0
    if applied_voucher:
        disc = int(total * applied_voucher['percent'] / 100)
        total = total - disc
    print("--- Ringkasan Pembelian ---")
    print(f"Produk: {p['name']}")
    print(f"UID tujuan: {uid_game}")
    print(f"Harga satuan (setelah diskon VIP jika ada): Rp{unit_price}")
    print(f"Subtotal: Rp{subtotal}")
    if applied_voucher:
        print(f"Voucher {applied_voucher['id']} -> {applied_voucher['percent']}% (-Rp{disc})")
    print(f"Total bayar: Rp{total}")

    print("Pilih metode pembayaran:")
    print("1. Saldo (E-money internal)")
    print("2. Gopay (simulasi)")
    print("3. Bank Transfer (simulasi)")
    m = input("Metode (1/2/3): ").strip()
    method = None
    if m == '1': method = 'Saldo'
    elif m == '2': method = 'Gopay'
    elif m == '3': method = 'Bank'
    else:
        print("Metode tidak valid.")
        return

    # Konfirmasi final sebelum pembayaran
    confirm = input(f"Konfirmasi: Bayar Rp{total} untuk {p['name']} ke UID {uid_game}? (y/n): ").strip().lower()
    if confirm != 'y':
        print("Pembelian dibatalkan.")
        return

    # Proses pembayaran
    if method == 'Saldo':
        if current_user.get('balance',0) < total:
            print("Saldo tidak cukup. Silakan top up atau pilih metode lain.")
            return
        current_user['balance'] -= total
        print("Pembayaran berhasil melalui Saldo.")
    else:
        ref = input(f"Masukkan referensi {method}: ").strip()
        if not ref:
            print("Referensi kosong. Pembayaran batal.")
            return
        print(f"Pembayaran {method} diterima (simulasi), ref: {ref}")

    # buat transaksi
    existing_tids = [t.get('id') for t in transactions if t.get('id')]
    tid = next_id('T', existing_tids)
    trx = {
        'id': tid,
        'user_id': current_user.get('id'),
        'product_id': p['id'],
        'qty': qty,
        'unit_price': unit_price,
        'subtotal': subtotal,
        'voucher_applied': applied_voucher['id'] if applied_voucher else None,
        'total': total,
        'method': method,
        'uid_game': uid_game,
        'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        # tambahan untuk laporan
        'bonus_lunite': 0
    }
    transactions.append(trx)
    p['stock'] = p.get('stock',0) - qty

    # tandai voucher terpakai
    if applied_voucher:
        for v in current_user.get('vouchers',[]):
            if v['id'] == applied_voucher['id']:
                v['used'] = True
                break

    # buat voucher baru jika memenuhi: rule baru -> jika pembelian item dengan harga asli (p['price']) >100rb
    if p.get('price',0) > 100000:
        new_v = create_voucher_for_user(current_user, VOUCHER_PERCENT_ON_BIG, users)
        print(f"Anda mendapat voucher {new_v['id']} sebesar {new_v['percent']}% (berlaku sampai {new_v['expiry']}).")

    # VIP bonus: jika VIP dan harga asli produk >100rb -> bonus 200 Lunite
    if current_user.get('role') == 'vip' and p.get('price',0) > 100000 and p.get('type') == 'topup':
        current_user['lunite'] = current_user.get('lunite',0) + VIP_BONUS_LUNITE
        trx['bonus_lunite'] = VIP_BONUS_LUNITE
        print(f"Sebagai VIP, Anda mendapat bonus {VIP_BONUS_LUNITE} Lunite!")

    # jika p['type'] == 'subscription' => extend VIP
    if p.get('type') == 'subscription':
        now = datetime.now()
        vip_expiry_str = current_user.get('vip_expiry')
        if vip_expiry_str:
            try:
                vip_expiry_dt = datetime.strptime(vip_expiry_str, "%Y-%m-%d %H:%M:%S")
            except Exception:
                vip_expiry_dt = None
        else:
            vip_expiry_dt = None

        if not vip_expiry_dt or now > vip_expiry_dt:
            # aktifkan akun VIP setelah pembelian Subscription
            new_exp = max(now, now) + timedelta(days=SUBSCRIPTION_DAYS)
            current_user['vip_expiry'] = new_exp.strftime("%Y-%m-%d %H:%M:%S")
            current_user['role'] = 'vip'
            print(f"Subscription aktif. Anda menjadi VIP sampai {current_user['vip_expiry']}")
        else:
            # jika subscription masih aktif akan dilanjutkan ke periode berikutnya
            new_exp = vip_expiry_dt + timedelta(days=SUBSCRIPTION_DAYS)
            current_user['vip_expiry'] = new_exp.strftime("%Y-%m-%d %H:%M:%S")
            # role tetap vip
            current_user['role'] = 'vip'
            print(f"Subscription ditambahkan. VIP sekarang berlaku sampai {current_user['vip_expiry']}")

    save_json(USERS_FILE, users)
    save_json(PRODUCTS_FILE, products)
    save_json(TRANSACTIONS_FILE, transactions)

    print("== Invoice ==")
    table = PrettyTable()
    table.field_names = ['Invoice','User','Produk','Qty','Total','Metode','UID','Tanggal','BonusLunite']
    table.add_row([trx['id'], current_user.get('username'), p.get('name'), trx['qty'], trx['total'], trx['method'], trx['uid_game'], trx['created_at'], trx.get('bonus_lunite',0)])
    print(table)
    print("Terima kasih telah berbelanja!")

# Top up saldo
def topup_balance(current_user, users):
    print("=== Top Up Saldo ===")
    try:
        amt = int(input("Masukkan nominal top up: ").strip())
        if amt <= 0:
            print("Nominal harus > 0")
            return
    except ValueError:
        print("Masukkan angka yang valid")
        return
    current_user['balance'] = current_user.get('balance',0) + amt
    save_json(USERS_FILE, users)
    print(f"Top up berhasil. Saldo sekarang Rp{current_user['balance']}")

def view_transactions(current_user, transactions):
    my = [t for t in transactions if t.get('user_id') == current_user.get('id')]
    if not my:
        print("Belum ada transaksi")
        return
    table = PrettyTable()
    table.field_names = ['ID','Produk','Qty','Total','Metode','UID','Tgl','BonusLunite']
    for t in my:
        table.add_row([t.get('id'), t.get('product_id'), t.get('qty'), t.get('total'), t.get('method'), t.get('uid_game'), t.get('created_at'), t.get('bonus_lunite',0)])
    print(table)

# ---------- Charting untuk Admin ----------
def admin_show_sales_charts(products, transactions):
    if not transactions:
        print("Belum ada transaksi untuk ditampilkan.")
        return
    # hitung frekuensi pembelian per produk id
    counts = {}
    for t in transactions:
        pid = t.get('product_id')
        counts[pid] = counts.get(pid, 0) + (t.get('qty',1) or 1)

    # mapping id -> nama
    id_to_name = {p['id']: p.get('name', p['id']) for p in products}

    labels = []
    values = []
    for pid, cnt in counts.items():
        labels.append(id_to_name.get(pid, pid))
        values.append(cnt)

    # Bar chart
    plt.figure()
    plt.bar(range(len(values)), values)
    plt.xticks(range(len(values)), labels, rotation=45, ha='right')
    plt.title("Jumlah Pembelian per Produk (Bar Chart)")
    plt.tight_layout()
    plt.show()

    # Pie chart
    plt.figure()
    plt.pie(values, labels=labels, autopct='%1.1f%%')
    plt.title("Proporsi Pembelian per Produk (Pie Chart)")
    plt.tight_layout()
    plt.show()

# Tampilkan Menu
#Menu user 
def user_menu(current_user, users, products, transactions):
    try:
        while True:
            print('===== MENU USER =====')
            show_user_profile(current_user)
            #Tampilan menu jika akun adalah jenis VIP
            if current_user.get('role') == 'vip':
                print('--- Menu VIP ---')
                print('1. Lihat Produk (Harga VIP & bonus untuk >100rb)')
                print('2. Top Up Saldo')
                print('3. Beli Lunite')
                print('4. Riwayat Transaksi')
                print('5. Perpanjang Subscription (Beli Subscription)')
                print('6. Logout')
            else:
            #Tampilan menu jika akun adalah jenis user biasa
                print('1. Lihat Produk')
                print('2. Top Up Saldo')
                print('3. Beli Lunite')
                print('4. Riwayat Transaksi')
                print('5. Beli Lunite Subscription (Upgrade VIP)')
                print('6. Logout')
            choice = input('Pilih: ').strip()
            if choice == '1':
                show_products_table(products, role=current_user.get('role'))
            elif choice == '2':
                topup_balance(current_user, users)
            elif choice == '3':
                buy_lunite_flow(current_user, users, products, transactions)
            elif choice == '4':
                view_transactions(current_user, transactions)
            elif choice == '5':
                buy_lunite_flow(current_user, users, products, transactions)
            elif choice == '6':
                print('Logout...')
                break
            else:
                print('Pilihan tidak valid')
    except KeyboardInterrupt:
        print('Kembali ke menu utama')
        return

#Menu Admin
def admin_menu(users, products, transactions):
    try:
        while True:
            print('===== MENU ADMIN =====')
            print('1. Lihat Produk')
            print('2. Tambah Produk')
            print('3. Ubah Produk')
            print('4. Hapus Produk')
            print('5. Lihat Pengguna')
            print('6. Lihat Transaksi')
            print('7. Statistik Penjualan (Chart)')
            print('8. Logout')
            c = input('Pilih: ').strip()
            if c == '1':
                show_products_table(products)
            elif c == '2':
                name = input('Nama produk: ').strip()
                try:
                    price = int(input('Harga: ').strip())
                    stock = int(input('Stok: ').strip())
                except ValueError:
                    print('Harga/stok harus angka')
                    continue
                ttype = input("Tipe produk (topup/subscription/other) [default topup]: ").strip() or "topup"
                existing = [p.get('id') for p in products if p.get('id')]
                pid = next_id('P', existing)
                products.append({'id': pid, 'name': name, 'price': price, 'stock': stock, 'type': ttype})
                save_json(PRODUCTS_FILE, products)
                print('Produk ditambahkan')
            elif c == '3':
                show_products_table(products)
                pid = input('ID produk: ').strip()
                p = find_product(products, pid)
                if not p:
                    print('Tidak ditemukan')
                    continue
                name = input(f"Nama ({p['name']}): ").strip()
                price_s = input(f"Harga ({p['price']}): ").strip()
                stock_s = input(f"Stok ({p['stock']}): ").strip()
                if name: p['name'] = name
                if price_s:
                    try: p['price'] = int(price_s)
                    except: pass
                if stock_s:
                    try: p['stock'] = int(stock_s)
                    except: pass
                save_json(PRODUCTS_FILE, products)
                print('Produk diperbarui')
            elif c == '4':
                show_products_table(products)
                pid = input('ID produk: ').strip()
                p = find_product(products, pid)
                if not p:
                    print('Tidak ditemukan')
                    continue
                products.remove(p)
                save_json(PRODUCTS_FILE, products)
                print('Produk dihapus')
            elif c == '5':
                table = PrettyTable()
                table.field_names = ['ID','Username','Role','Saldo','Lunite','Failed','Locked','VIP Expiry']
                for u in users:
                    table.add_row([u.get('id'), u.get('username'), u.get('role'), u.get('balance'), u.get('lunite',0), u.get('failed_attempts'), u.get('locked_until'), u.get('vip_expiry')])
                print(table)
            elif c == '6':
                table = PrettyTable()
                table.field_names = ['ID','User','Produk','Qty','Total','Metode','UID','Tgl','BonusLunite']
                for t in transactions:
                    table.add_row([t.get('id'), t.get('user_id'), t.get('product_id'), t.get('qty'), t.get('total'), t.get('method'), t.get('uid_game'), t.get('created_at'), t.get('bonus_lunite',0)])
                print(table)
            elif c == '7':
                # tampilkan charts

                admin_show_sales_charts(products, transactions)
            elif c == '8': #Log out
                break
            else:
                print('Pilihan tidak valid')
    except KeyboardInterrupt:
        print('Kembali ke menu utama')
        return


#Kode Utama
def main():
    ensure_data_dir()
    users = load_json(USERS_FILE)
    products = load_json(PRODUCTS_FILE)
    transactions = load_json(TRANSACTIONS_FILE)

    # pastikan default fields
    for u in users:
        u.setdefault('failed_attempts',0)
        u.setdefault('locked_until',None)
        u.setdefault('vouchers',[])
        u.setdefault('balance',0)
        u.setdefault('lunite',0)
        u.setdefault('vip_expiry',None)
        u.setdefault('pending_subscription_days',0)

    save_json(USERS_FILE, users)

    try:
        while True:
            # Tampilkan Pesan Sambutan Ketika kembali ke menu utama
            Pesan_Sambutan()
            print('=== Toko Top Up Lunite Wuthering Waves ===')
            print('1. Login')
            print('2. Registrasi')
            print('3. Keluar')
            choice = input('Pilih: ').strip()
            if choice == '1':
                user = login(users)
                if user:
                    if user.get('role') == 'admin':
                        admin_menu(users, products, transactions)
                    else:
                        user_menu(user, users, products, transactions)
            elif choice == '2':
                register(users)
                users = load_json(USERS_FILE)
            elif choice == '3':
                print('Sampai jumpa!')
                break
            else:
                print('Pilihan tidak valid')
    except KeyboardInterrupt:
        print('Keluar...')

if __name__ == '__main__':
    main()

