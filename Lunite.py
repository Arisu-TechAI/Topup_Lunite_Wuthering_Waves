# Nama  : Arizky Saputra
# NIM   : 2509116088
# Kelas : Sistem Informasi (C)

import json
import os
import re
from datetime import datetime, timedelta
from prettytable import PrettyTable
import pwinput

# Mengambil data ke directory
DATA_DIR = "data"
USERS_FILE = os.path.join(DATA_DIR, "pengguna.json")
PRODUCTS_FILE = os.path.join(DATA_DIR, "produk.json")
TRANSACTIONS_FILE = os.path.join(DATA_DIR, "data_transaksi.json")

LOCK_DURATION_SECS = 30  # Durasi Kunci akun jika salah password
VIP_DISCOUNT_PERCENT = 10  # diskon untuk member VIP 
SUBSCRIPTION_DAYS = 30

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

# Pengaturan untuk Voucher

def compute_voucher_percent(amount):
    # jika >= 100000, 2% per 100k
    if amount < 100000:
        return 0
    times = amount // 100000
    return int(times * 2)

def gen_voucher_id(existing_ids):
    return next_id('V', existing_ids)

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
    print(f"Saldo: Rp{user.get('balance',0)}")
    vip_expiry = user.get('vip_expiry')
    if vip_expiry:
        print(f"VIP expiry: {vip_expiry}")
    pending = user.get('pending_subscription_days',0)
    if pending:
        print(f"Pending subscription extension: {pending} hari")
    vouchers = user.get('vouchers',[])
    if vouchers:
        vs = ', '.join([f"{v['id']}({v['percent']}%){' used' if v.get('used') else ''}" for v in vouchers])
        print(f"Vouchers: {vs}")
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

# Pembelian

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
    if current_user.get('role') == 'vip':
        unit_price = int(unit_price * (100 - VIP_DISCOUNT_PERCENT) / 100)

    subtotal = unit_price * qty

    # pilih voucher
    usable_vouchers = [v for v in current_user.get('vouchers',[]) if not v.get('used')]
    applied_voucher = None
    if usable_vouchers:
        print("Voucher tersedia:")
        for i,v in enumerate(usable_vouchers,1):
            print(f"{i}. {v['id']} - {v['percent']}%")
        choose = input("Pakai voucher? (masukkan nomor / kosong = tidak): ").strip()
        if choose:
            try:
                idx = int(choose)-1
                applied_voucher = usable_vouchers[idx]
            except Exception:
                applied_voucher = None

    # ringkasan & konfirmasi
    total = subtotal
    if applied_voucher:
        disc = int(total * applied_voucher['percent'] / 100)
        total = total - disc
    print("--- Ringkasan Pembelian ---")
    print(f"Produk: {p['name']}")
    print(f"UID tujuan: {uid_game}")
    print(f"Harga satuan: Rp{unit_price}")
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
        'created_at': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    transactions.append(trx)
    p['stock'] = p.get('stock',0) - qty

    # tandai voucher terpakai
    if applied_voucher:
        for v in current_user.get('vouchers',[]):
            if v['id'] == applied_voucher['id']:
                v['used'] = True
                break

    # buat voucher baru jika memenuhi
    new_v_pct = compute_voucher_percent(total)
    if new_v_pct > 0:
        existing_vids = []
        for u in users:
            for vv in u.get('vouchers',[]):
                existing_vids.append(vv['id'])
        new_vid = gen_voucher_id(existing_vids)
        new_v = {'id': new_vid, 'percent': new_v_pct, 'used': False}
        current_user.setdefault('vouchers', []).append(new_v)
        print(f"Anda mendapat voucher {new_vid} sebesar {new_v_pct}% untuk pembelian berikutnya.")

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
    table.field_names = ['Invoice','User','Produk','Qty','Total','Metode','UID','Tanggal']
    table.add_row([trx['id'], current_user.get('username'), p.get('name'), trx['qty'], trx['total'], trx['method'], trx['uid_game'], trx['created_at']])
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
    table.field_names = ['ID','Produk','Qty','Total','Metode','UID','Tgl']
    for t in my:
        table.add_row([t.get('id'), t.get('product_id'), t.get('qty'), t.get('total'), t.get('method'), t.get('uid_game'), t.get('created_at')])
    print(table)

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
                print('1. Lihat Produk (Harga VIP)')
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
            print('7. Logout')
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
                existing = [p.get('id') for p in products if p.get('id')]
                pid = next_id('P', existing)
                products.append({'id': pid, 'name': name, 'price': price, 'stock': stock, 'type':'topup'})
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
                table.field_names = ['ID','Username','Role','Saldo','Failed','Locked','VIP Expiry']
                for u in users:
                    table.add_row([u.get('id'), u.get('username'), u.get('role'), u.get('balance'), u.get('failed_attempts'), u.get('locked_until'), u.get('vip_expiry')])
                print(table)
            elif c == '6':
                table = PrettyTable()
                table.field_names = ['ID','User','Produk','Qty','Total','Metode','UID','Tgl']
                for t in transactions:
                    table.add_row([t.get('id'), t.get('user_id'), t.get('product_id'), t.get('qty'), t.get('total'), t.get('method'), t.get('uid_game'), t.get('created_at')])
                print(table)
            elif c == '7':
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
        u.setdefault('vip_expiry',None)
        u.setdefault('pending_subscription_days',0)

    save_json(USERS_FILE, users)

    try:
        while True:
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
