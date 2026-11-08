import streamlit as st
import pandas as pd
import io
import zipfile
import re
import json
import os
import math
from datetime import datetime, timedelta, timezone

# --- PENGATURAN HALAMAN ---
st.set_page_config(page_title="Aplikasi Cetak TUL VI-01", layout="wide")

# --- SISTEM PENYIMPANAN MULTI-UNIT (AUTO-SAVE) ---
DB_CONFIG_FILE = "db_profil_unit_tul.json"

DEFAULT_MAPPING_TULUNG = {
    "JCA": "c01", "TAA": "c02", "JCB": "c03", "JCC": "c04", "NCD": "c05",
    "KBA": "c06", "TAB": "c07", "JCE": "c08", "TAC": "c09", "MBB": "c10",
    "KAD": "c11", "TAE": "c12", "KCF": "c13", "JCG": "c14", "TAF": "c15",
    "KAG": "c16", "BBC": "c17", "TAH": "c18", "BCK": "c19", "NCH": "c20",
    "JBE": "c21", "MBF": "c22", "MBG": "c23", "KBH": "c24", "KBI": "c25",
    "KAI": "c26", "MCI": "c27", "KBJ": "c28", "JCJ": "c29", "TAJ": "c30",
    "MBK": "c31", "KBL": "c32", "TAK": "c33", "KAL": "c34", "JCL": "c35",
    "MBD": "c36", "KCJ": "c29", "NBJ": "c28", "TAI": "c26", "BBD": "c19",
    "KCG": "c29", "MBM": "c23"
}

DEFAULT_IDPEL_TULUNG = {
    "524051069054": "c28", "524051263717": "c36", "524051265123": "c36", 
    "524051104194": "c04", "524051000615": "c08", "524050867033": "c08"
}

def buat_profil_standar(nama_ulp="ULP BARU", is_tulung=False):
    return {
        "up3": "UP3 KLATEN",
        "ulp": nama_ulp,
        "mode_cetak": "Tahap 2: Isi Blangko Saja",
        "tipe_printer": "Epson LQ-2190 (Standar Blangko 15 CPI - ESC g)",
        "geser_kanan": 0.0,
        "geser_bawah": 0.0,
        "tinggi_halaman": 44,
        "geser_koked": 0,
        "geser_rptag": 0,
        "geser_bk": 0,
        "geser_total": 0,
        "cetak_kota": False,
        "kota_cetak": nama_ulp.replace("ULP ", ""),
        "geser_kota_x": 0.0,
        "cetak_tgl": True,
        "geser_tgl": 8.0,
        "geser_kota_tgl_y": 0,
        "cetak_jab": False,
        "jabatan": "MANAGER",
        "geser_jab_x": 0.0,
        "geser_jab_y": 0,
        "cetak_mgr": True,
        "nama_manager": "MARTONO AJI PRABOWO" if is_tulung else "NAMA MANAGER ULP",
        "geser_mgr_x": 0.0,
        "geser_mgr_y": 0,
        "batas_daya_pln": 33000,
        "posisi_kddk_awal": 4,
        "posisi_kddk_akhir": 6,
        "map_kddk": DEFAULT_MAPPING_TULUNG.copy() if is_tulung else {},
        "map_idpel": DEFAULT_IDPEL_TULUNG.copy() if is_tulung else {}
    }

def load_all_profiles():
    default_db = {"ULP TULUNG": buat_profil_standar("ULP TULUNG", is_tulung=True)}
    if os.path.exists(DB_CONFIG_FILE):
        try:
            with open(DB_CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                if isinstance(saved, dict) and len(saved) > 0:
                    for k, v in saved.items():
                        base = buat_profil_standar(k, is_tulung=(k == "ULP TULUNG"))
                        base.update(v)
                        saved[k] = base
                    return saved
        except Exception:
            pass
    return default_db

def save_all_profiles(db):
    try:
        with open(DB_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(db, f, indent=4, ensure_ascii=False)
    except Exception:
        pass

if "db_unit" not in st.session_state:
    st.session_state.db_unit = load_all_profiles()
if "unit_aktif" not in st.session_state:
    st.session_state.unit_aktif = list(st.session_state.db_unit.keys())[0]


# --- LOGIKA PENENTUAN PETUGAS BERJENJANG ---
def ekstrak_kode_rbm(kddk, pos_awal=4, pos_akhir=6):
    s = str(kddk).strip().upper()
    idx_start = max(0, int(pos_awal) - 1)
    idx_end = int(pos_akhir)
    if len(s) >= idx_end and idx_end > idx_start:
        return s[idx_start:idx_end]
    return ""

def tentukan_petugas_universal(idpel, tarif_daya, kddk, cfg):
    idpel_clean = str(idpel).replace('.0', '').strip()
    map_idpel = cfg.get("map_idpel", {})
    map_kddk = cfg.get("map_kddk", {})
    
    # PRIORITAS 1: Cek IDPEL Khusus (Mengalahkan aturan Daya > 33.000 VA & aturan KDDK)
    if idpel_clean in map_idpel and str(map_idpel[idpel_clean]).strip() != "":
        return str(map_idpel[idpel_clean]).strip()

    # PRIORITAS 2: Cek Batas Daya PLN (> 33.000 VA otomatis masuk PLN)
    daya = 0
    match_daya = re.search(r'/(\d+)', str(tarif_daya))
    if match_daya:
        daya = int(match_daya.group(1))
    else:
        bersih_angka = re.sub(r'[^\d]', '', str(tarif_daya))
        if bersih_angka.isdigit():
            daya = int(bersih_angka)
            
    batas_pln = int(cfg.get("batas_daya_pln", 33000))
    if batas_pln > 0 and daya > batas_pln:
        return "PLN"
        
    # PRIORITAS 3: Cek Kode KDDK (Default digit ke-4 s/d ke-6)
    pos_awal = cfg.get("posisi_kddk_awal", 4)
    pos_akhir = cfg.get("posisi_kddk_akhir", 6)
    kode_mid = ekstrak_kode_rbm(kddk, pos_awal, pos_akhir)
    if kode_mid:
        if kode_mid in map_kddk and str(map_kddk[kode_mid]).strip() != "":
            return str(map_kddk[kode_mid]).strip()
        return f"RBM_{kode_mid}"
        
    return "TANPA_KDDK"


# --- FUNGSI BACA FILE ICONPRN ---
def baca_data_dari_iconprn_tul(teks_mentah, cfg):
    hasil = []
    blok_halaman = re.split(r'PEMBERITAHUAN PELAKSANAAN PEMUTUSAN', teks_mentah)
    for blok in blok_halaman:
        if "ID. Pelanggan" not in blok: continue
        
        data = {
            'IDPEL': "", 'Nomor TUL': "", 'Nama': "", 'KDDK': "", 'Gardu/Tiang': "", 
            'Loket': "", 'Alamat': "", 'Nomor Meter': "", 'Tarif/Daya': "", 'Kelompok': "", 
            'Bulan Rekening': "", 'Bulan Keterlambatan': "", 'Jumlah Rekening': 0, 
            'Jumlah Denda': 0, 'Jumlah Tunggakan': 0, 'petugas': ""
        }
        
        idpel = re.search(r'ID\. Pelanggan\s*:\s*[^0-9]*(\d{11,13})', blok)
        if idpel: data['IDPEL'] = str(idpel.group(1).strip())

        tul = re.search(r'NO\. TUL\s*:\s*([A-Z0-9/\-]+)', blok)
        if tul: data['Nomor TUL'] = tul.group(1).strip()

        nama = re.search(r'Nama\s*:\s*(.+)', blok)
        if nama: data['Nama'] = nama.group(1).strip()

        kddk = re.search(r'Kode Kedudukan\s*:\s*([A-Z0-9]+)', blok)
        if kddk: data['KDDK'] = kddk.group(1).strip()

        gardu = re.search(r'Gardu\s*/?\s*Tiang\s*:\s*(.*?)(?=\s{2,}|\s+Loket\s*:|\n|\r|$)', blok, re.IGNORECASE)
        if gardu: data['Gardu/Tiang'] = gardu.group(1).strip()

        loket = re.search(r'Loket\s*:\s*(.*?)(?=\s{2,}|\s+Tarip|\s+Tarif|\s+Alamat|\s+Kelompok|\n|\r|$)', blok, re.IGNORECASE)
        if loket: 
            val_loket = loket.group(1).strip()
            if "Tarip" in val_loket or "Kelompok" in val_loket or "Daya" in val_loket: val_loket = ""
            data['Loket'] = val_loket

        alamat = re.search(r'Alamat\s*:\s*(.+)', blok)
        if alamat: data['Alamat'] = alamat.group(1).strip()

        meter = re.search(r'Nomor Meter\s*:\s*([A-Z0-9]+)', blok, re.IGNORECASE)
        if meter: data['Nomor Meter'] = str(meter.group(1).strip())

        tarif_match = re.search(r'Tarip / Daya\s*:\s*(.+?)\s+Kelompok\s*:\s*([^\n]+)', blok)
        if tarif_match:
            data['Tarif/Daya'] = tarif_match.group(1).strip()
            data['Kelompok'] = tarif_match.group(2).strip()
        else:
            tarif = re.search(r'Tarip / Daya\s*:\s*([A-Z0-9/ ]+)', blok)
            if tarif: data['Tarif/Daya'] = tarif.group(1).strip()
            data['Kelompok'] = "1"

        rek = re.search(r'Rekening\s*:\s*(.+?)\s*Rp\.\s*:\s*[^0-9]*([\d,]+)', blok)
        if rek:
            data['Bulan Rekening'] = rek.group(1).strip()
            val_rek = rek.group(2).replace(',', '').replace('.', '').strip()
            data['Jumlah Rekening'] = int(val_rek) if val_rek.isdigit() else 0

        denda = re.search(r'Jumlah Biaya Keterlambatan s\.d bulan\s*:\s*(.+?)\s*Rp\.\s*:\s*[^0-9]*([\d,]+)', blok)
        if denda:
            data['Bulan Keterlambatan'] = denda.group(1).strip()
            val_denda = denda.group(2).replace(',', '').replace('.', '').strip()
            data['Jumlah Denda'] = int(val_denda) if val_denda.isdigit() else 0

        tunggakan = re.search(r'Jumlah Tunggakan.*?Rp\.\s*:\s*[^0-9]*([\d,]+)', blok)
        if tunggakan:
            val_tung = tunggakan.group(1).replace(',', '').replace('.', '').strip()
            data['Jumlah Tunggakan'] = int(val_tung) if val_tung.isdigit() else 0

        data['petugas'] = tentukan_petugas_universal(data['IDPEL'], data['Tarif/Daya'], data['KDDK'], cfg)
        hasil.append(data)
    return hasil

STANDAR_KOLOM_TUL = {
    "IDPEL": ["idpel", "id pelanggan", "id_pelanggan", "no pelanggan"],
    "Nomor TUL": ["nomor tul", "no tul", "no. tul", "nomor_tul"],
    "Nama": ["nama", "nama pelanggan", "nama_pelanggan"],
    "KDDK": ["kddk", "kode kedudukan", "kedudukan", "koked"],
    "Gardu/Tiang": ["gardu/tiang", "gardu", "nama gardu/tiang", "gardutiang", "tiang"],
    "Loket": ["loket", "kode loket"],
    "Alamat": ["alamat", "alamat pelanggan"],
    "Nomor Meter": ["nomor meter", "no meter", "nomor_meter", "nomormeter", "nomorkwh"],
    "Tarif/Daya": ["tarif/daya", "tarip / daya", "tarifdaya", "tarif", "daya"],
    "Kelompok": ["kelompok", "klp"],
    "Bulan Rekening": ["bulan rekening", "bulan_rekening", "rekening", "blth"],
    "Bulan Keterlambatan": ["bulan keterlambatan", "bulan_keterlambatan", "keterlambatan"],
    "Jumlah Rekening": ["jumlah rekening", "jumlah_rekening", "jumlah_rekening_", "rp rekening", "tagihan", "rptag"],
    "Jumlah Denda": ["jumlah denda", "jumlah_denda", "jumlah_denda_", "denda", "bk", "biaya keterlambatan"],
    "Jumlah Tunggakan": ["jumlah tunggakan", "jumlah_tunggakan", "jumlah_tunggakan_", "total", "total tunggakan"],
    "petugas": ["petugas", "kode petugas", "nama petugas", "cater", "rbm"]
}

def deteksi_kolom_otomatis(df_cols):
    mapping = {}
    cols_lower = {c.strip().lower(): c for c in df_cols}
    for target, kandidat_list in STANDAR_KOLOM_TUL.items():
        found = None
        for k in kandidat_list:
            if k in cols_lower:
                found = cols_lower[k]
                break
        if not found:
            for c_low, c_orig in cols_lower.items():
                if any(k in c_low for k in kandidat_list):
                    found = c_orig
                    break
        mapping[target] = found
    return mapping

# --- FUNGSI GENERATOR ESC/P DOT MATRIX ---
def get_printer_init_code(printer_choice, page_lines=44):
    ESC = "\x1b"
    base = ""
    if "LQ-2190" in printer_choice: base = f"{ESC}g{ESC}0"
    elif "17 CPI" in printer_choice: base = f"{ESC}P\x0f{ESC}0"
    else: base = f"{ESC}M\x12{ESC}0"
    return f"{base}{ESC}C{chr(page_lines)}"

def format_rupiah(val):
    try:
        if pd.isna(val) or str(val).strip() == "": return "0"
        bersih = str(val).replace(".", "").replace(",", "").strip()
        return f"{int(float(bersih)):,}".replace(",", ".")
    except Exception:
        return str(val)

def get_cpi_value(printer_choice):
    if "LQ-2190" in printer_choice: return 15.0
    elif "17 CPI" in printer_choice: return 17.14
    else: return 12.0

def shift_line(text, offset_x, cpi=15.0):
    if not text: return ""
    int_shift = math.floor(float(offset_x))
    frac_shift = float(offset_x) - int_shift
    
    if int_shift > 0: shifted = (" " * int_shift) + text
    elif int_shift < 0:
        leading = len(text) - len(text.lstrip(" "))
        shifted = text[min(abs(int_shift), leading):]
    else: shifted = text

    if frac_shift > 1e-6:
        units = int(round(frac_shift * (60.0 / cpi)))
        if units > 0:
            nL = units % 256
            nH = units // 256
            shifted = f"\x1b${chr(nL)}{chr(nH)}" + shifted
    return shifted

def ambil_nilai(row, col_map, key, default=""):
    if col_map is None: return str(row.get(key, default)).strip()
    nama_kolom = col_map.get(key)
    if nama_kolom and nama_kolom in row and pd.notna(row[nama_kolom]):
        return str(row[nama_kolom]).strip()
    return default

def buat_isian_blangko(
    row, col_map, init_code, kota, tgl, jab, manager, 
    cetak_kota=False, cetak_tgl=True, cetak_jab=False, cetak_mgr=True,
    geser_kota_x=0.0, geser_tgl=8.0, geser_kota_tgl_y=0,
    geser_jab_x=0.0, geser_jab_y=0,
    geser_mgr_x=0.0, geser_mgr_y=0,
    offset_x=0.0, offset_y=0.0, page_lines=44, printer_choice="", page_idx=0, 
    geser_koked=0, geser_rptag=0, geser_bk=0, geser_total=0
):
    ESC = "\x1b"
    BOLD_ON = f"{ESC}E"  
    BOLD_OFF = f"{ESC}F" 
    cpi = get_cpi_value(printer_choice)

    no_tul = ambil_nilai(row, col_map, "Nomor TUL")
    nama = ambil_nilai(row, col_map, "Nama")[:33]
    idpel = ambil_nilai(row, col_map, "IDPEL")
    kddk = ambil_nilai(row, col_map, "KDDK")
    alamat = ambil_nilai(row, col_map, "Alamat")[:50]
    no_meter = ambil_nilai(row, col_map, "Nomor Meter")
    gardu = ambil_nilai(row, col_map, "Gardu/Tiang")
    loket = ambil_nilai(row, col_map, "Loket")
    tarif = ambil_nilai(row, col_map, "Tarif/Daya")
    kelompok = ambil_nilai(row, col_map, "Kelompok", "0")
    bln_rek = ambil_nilai(row, col_map, "Bulan Rekening")
    bln_lambat = ambil_nilai(row, col_map, "Bulan Keterlambatan")

    rp_rek = format_rupiah(ambil_nilai(row, col_map, "Jumlah Rekening", "0")).rjust(15)
    rp_denda = format_rupiah(ambil_nilai(row, col_map, "Jumlah Denda", "0")).rjust(15)
    rp_total = format_rupiah(ambil_nilai(row, col_map, "Jumlah Tunggakan", "0")).rjust(15)

    raw_lines = [""] * page_lines
    int_y = math.floor(float(offset_y))
    frac_y = float(offset_y) - int_y

    def set_line(idx, content, extra_x=0.0):
        target = idx + int_y
        if 0 <= target < page_lines:
            raw_lines[target] = shift_line(content, float(offset_x) + float(extra_x), cpi=cpi)

    w_koked = max(1, 58 + int(geser_koked))
    w_rptag = max(1, 62 + int(geser_rptag))
    w_bk    = max(1, 35 + int(geser_bk))
    w_total = max(0, 74 + int(geser_total))

    set_line(1,  f"{'':<73}{no_tul}")
    set_line(7,  f"{'':<21}{nama}")
    set_line(8,  f"{'':<21}{idpel:<{w_koked}}{kddk}")         
    set_line(9,  f"{'':<21}{alamat}")
    set_line(10, f"{'':<21}{no_meter}")
    set_line(11, f"{'':<21}{gardu:<53}{loket}")        
    set_line(12, f"{'':<21}{tarif:<53}{kelompok}")     
    
    set_line(14, f"{'':<12}{bln_rek:<{w_rptag}}{rp_rek}")
    set_line(15, f"{'':<39}{bln_lambat:<{w_bk}}{rp_denda}")
    set_line(17, f"{'':<{w_total}}{rp_total}")
    
    if cetak_kota and cetak_tgl:
        teks_kota_tgl = f"{kota}, {tgl}"
        x_kota_tgl = float(geser_kota_x) + float(geser_tgl)
    elif cetak_kota and not cetak_tgl:
        teks_kota_tgl = f"{kota}"
        x_kota_tgl = float(geser_kota_x)
    elif not cetak_kota and cetak_tgl:
        teks_kota_tgl = f"{tgl}"
        x_kota_tgl = float(geser_tgl)
    else:
        teks_kota_tgl = ""
        x_kota_tgl = 0.0

    if teks_kota_tgl:
        set_line(30 + int(geser_kota_tgl_y), f"{'':<64}{teks_kota_tgl}", extra_x=x_kota_tgl)
        
    if cetak_jab and str(jab).strip():
        set_line(31 + int(geser_jab_y), f"{'':<69}{jab}", extra_x=geser_jab_x)
        
    if cetak_mgr and str(manager).strip():
        set_line(36 + int(geser_mgr_y), f"{'':<64}{BOLD_ON}{manager}{BOLD_OFF}", extra_x=geser_mgr_x)

    last_idx = 0
    for i in range(page_lines - 1, -1, -1):
        if raw_lines[i] != "":
            last_idx = i
            break
            
    output_lines = raw_lines[:last_idx + 1]

    if frac_y > 1e-6:
        if "LQ-2190" in printer_choice: line_units = 23 
        else: line_units = 27
            
        n_down = int(round(frac_y * line_units))
        if n_down > 0:
            output_lines[0] = f"{ESC}J{chr(n_down)}" + output_lines[0]

    output_lines[0] = init_code + output_lines[0]
    
    return "\r\n".join(output_lines) + "\r\x0C"

def buat_blangko_dan_isi(
    row, col_map, init_code, up3, ulp, kota, tgl, jab, manager, page_lines=44,
    cetak_kota=True, cetak_tgl=True, cetak_jab=True, cetak_mgr=True
):
    ESC = "\x1b"
    BOLD_ON = f"{ESC}E"
    BOLD_OFF = f"{ESC}F"

    no_tul = ambil_nilai(row, col_map, "Nomor TUL")
    nama = ambil_nilai(row, col_map, "Nama")[:33]
    idpel = ambil_nilai(row, col_map, "IDPEL")
    kddk = ambil_nilai(row, col_map, "KDDK")
    alamat = ambil_nilai(row, col_map, "Alamat")[:50]
    no_meter = ambil_nilai(row, col_map, "Nomor Meter")
    gardu = ambil_nilai(row, col_map, "Gardu/Tiang")
    loket = ambil_nilai(row, col_map, "Loket")
    tarif = ambil_nilai(row, col_map, "Tarif/Daya")
    kelompok = ambil_nilai(row, col_map, "Kelompok", "0")
    bln_rek = ambil_nilai(row, col_map, "Bulan Rekening")
    bln_lambat = ambil_nilai(row, col_map, "Bulan Keterlambatan")

    rp_rek = format_rupiah(ambil_nilai(row, col_map, "Jumlah Rekening", "0")).rjust(15)
    rp_denda = format_rupiah(ambil_nilai(row, col_map, "Jumlah Denda", "0")).rjust(15)
    rp_total = format_rupiah(ambil_nilai(row, col_map, "Jumlah Tunggakan", "0")).rjust(15)

    if cetak_kota and cetak_tgl: baris_kota_tgl = f"                                                                {kota}, {tgl}"
    elif cetak_kota: baris_kota_tgl = f"                                                                {kota}"
    elif cetak_tgl: baris_kota_tgl = f"                                                                {tgl}"
    else: baris_kota_tgl = ""

    baris_jab = f"                                                                     {jab}" if cetak_jab else ""
    baris_mgr = f"|------------------------------------------------------|        {BOLD_ON}{manager}{BOLD_OFF}" if cetak_mgr else "|------------------------------------------------------|"

    lines = [
        f"{init_code}PT. PLN (PERSERO) UID JAWA TENGAH DAN DIY",
        f"{up3:<62}NO. TUL :  {no_tul}",
        f"{ulp}",
        "",
        "             PEMBERITAHUAN PELAKSANAAN PEMUTUSAN SEMENTARA SAMBUNGAN TENAGA LISTRIK             ",
        "             ======================================================================             ",
        "Kepada Yth. ",
        f"Nama              :  {nama}",
        f"ID. Pelanggan     :  {idpel:<42}Kode Kedudukan : {kddk}",
        f"Alamat            :  {alamat}",
        f"Nomor Meter       :  {no_meter}",
        f"Nama Gardu/Tiang  :  {gardu:<44}Loket    : {loket}",
        f"Tarip / Daya      :  {tarif:<42}Kelompok : {kelompok}",
        "",
        f"Rekening :  {bln_rek:<55}Rp. : {rp_rek}",
        f"Jumlah Biaya Keterlambatan s.d bulan : {bln_lambat:<28}Rp. : {rp_denda}",
        "                                                                       ---------------",
        f"Jumlah Tunggakan (belum termasuk biaya Administrasi)               Rp. : {rp_total}",
        "",
        "   Dengan ini diberitahukan dengan hormat bahwa pada hari ini aliran listrik di rumah/alamat seperti tersebut diatas   ",
        "terpaksa diputus untuk sementara karena rekening listrik belum dilunasi pada waktu yang telah ditetapkan.",
        "Penyambungan kembali akan dilakukan pada setiap hari jam kerja apabila rekening serta biaya keterlambatan dilunasi",
        "di tempat penerimaan pembayaran rekening listrik, kantor pos, atau bank yang ditunjuk oleh PLN.                       ",
        "   Apabila dalam jangka waktu 60 hari terhitung sejak dilakukan pemutusan sementara tunggakan belum dilunasi,         ",
        "maka instalasi milik PLN akan dibongkar, dan penyambungan kembali dapat dilaksanakan setelah Saudara menyelesaikan    ",
        "Biaya Penyambungan yang diperlakukan sebagai sambungan baru serta tetap diwajibkan membayar tagihan listrik           ",
        "yang belum dilunasi beserta dendanya.                     ",
        "",
        "UNTUK MENGHINDARI RESIKO, MOHON TIDAK TITIP PEMBAYARAN REKENING KEPADA PETUGAS",
        "",
        baris_kota_tgl,
        baris_jab,
        "",
        "|------------------------------------------------------|",
        "|       PADA WAKTU MELAKUKAN PEMBAYARAN DIMOHON        |",
        "|         MENUNJUKKAN SURAT PEMBERITAHUAN INI          |",
        baris_mgr,
        "                              TGL  STAND PUTUS  PELANGGAN        ",
        "",
        "A5 TUL VI-01/PETUGAS PEMUTUS...... ... ... ... ...........                   ",
        "ABAIKAN PEMBERITAHUAN INI JIKA SUDAH MEMBAYAR TAGIHAN"
    ]
    
    while lines and lines[-1].strip() == "":
        lines.pop()
        
    return "\r\n".join(lines) + "\r\x0C"

def buat_blangko_kosong(init_code, up3, ulp, jml_lembar=50, page_lines=44):
    lines = [
        f"{init_code}PT. PLN (PERSERO) UID JAWA TENGAH DAN DIY",
        f"{up3:<62}NO. TUL :  ",
        f"{ulp}", "",
        "             PEMBERITAHUAN PELAKSANAAN PEMUTUSAN SEMENTARA SAMBUNGAN TENAGA LISTRIK             ",
        "             ======================================================================             ",
        "Kepada Yth. ",
        "Nama              :                                                  ",
        "ID. Pelanggan     :  \t\t                              Kode Kedudukan :     ",
        "Alamat            :                                                  ",
        "Nomor Meter       :                                                                ",
        "Nama Gardu/Tiang  :  \t                                      Loket    :              ",
        "Tarip / Daya      :  \t                                      Kelompok :               ", "",
        "Rekening :        \t\t\t\t                   Rp. :  ",
        "Jumlah Biaya Keterlambatan s.d bulan :                             Rp. :  ",
        "                                                                        ---------------",
        "Jumlah Tunggakan (belum termasuk biaya Administrasi)               Rp. :  ", "",
        "   Dengan ini diberitahukan dengan hormat bahwa pada hari ini aliran listrik di rumah/alamat seperti tersebut diatas   ",
        "terpaksa diputus untuk sementara karena rekening listrik belum dilunasi pada waktu yang telah ditetapkan.",
        "Penyambungan kembali akan dilakukan pada setiap hari jam kerja apabila rekening serta biaya keterlambatan dilunasi",
        "di tempat penerimaan pembayaran rekening listrik, kantor pos, atau bank yang ditunjuk oleh PLN.                       ",
        "   Apabila dalam jangka waktu 60 hari terhitung sejak dilakukan pemutusan sementara tunggakan belum dilunasi,         ",
        "maka instalasi milik PLN akan dibongkar, dan penyambungan kembali dapat dilaksanakan setelah Saudara menyelesaikan    ",
        "Biaya Penyambungan yang diperlakukan sebagai sambungan baru serta tetap diwajibkan membayar tagihan listrik           ",
        "yang belum dilunasi beserta dendanya.                     ", "",
        "UNTUK MENGHINDARI RESIKO, MOHON TIDAK TITIP PEMBAYARAN REKENING KEPADA PETUGAS", "",
        "                                                                           ",
        "                                                                               ", "",
        "|------------------------------------------------------|",
        "|       PADA WAKTU MELAKUKAN PEMBAYARAN DIMOHON        |",
        "|         MENUNJUKKAN SURAT PEMBERITAHUAN INI          |",
        "|------------------------------------------------------|",
        "                              TGL  STAND PUTUS  PELANGGAN        ", "",
        "A5 TUL VI-01/PETUGAS PEMUTUS...... ... ... ... ...........                   ",
        "ABAIKAN PEMBERITAHUAN INI JIKA SUDAH MEMBAYAR TAGIHAN"
    ]
    
    while lines and lines[-1].strip() == "":
        lines.pop()
        
    single_page = "\r\n".join(lines) + "\r\x0C"
    return single_page * jml_lembar


# ==========================================
# HEADER & PEMILIHAN PROFIL UNIT (ULP)
# ==========================================
st.title("🖨️ Aplikasi Cetak TUL VI-01 (Multi-Unit & Auto-Save)")

col_top1, col_top2, col_top3 = st.columns([2, 1.5, 1])
with col_top1:
    daftar_unit = list(st.session_state.db_unit.keys())
    idx_unit = daftar_unit.index(st.session_state.unit_aktif) if st.session_state.unit_aktif in daftar_unit else 0
    pilihan_unit = st.selectbox("🏢 Pilih Profil Unit (ULP):", daftar_unit, index=idx_unit)
    if pilihan_unit != st.session_state.unit_aktif:
        st.session_state.unit_aktif = pilihan_unit
        st.rerun()

with col_top2:
    nama_unit_baru = st.text_input("➕ Buat Profil Unit Baru (Misal: ULP KLATEN KOTA):", placeholder="Ketik nama ULP lalu klik Tambah")
with col_top3:
    st.write("")
    st.write("")
    if st.button("Tambah Unit Baru", use_container_width=True):
        nama_bersih = nama_unit_baru.strip().upper()
        if nama_bersih:
            if not nama_bersih.startswith("ULP "):
                nama_bersih = "ULP " + nama_bersih
            if nama_bersih not in st.session_state.db_unit:
                st.session_state.db_unit[nama_bersih] = buat_profil_standar(nama_bersih, is_tulung=False)
                save_all_profiles(st.session_state.db_unit)
            st.session_state.unit_aktif = nama_bersih
            st.rerun()

st.markdown("---")

cfg = st.session_state.db_unit[st.session_state.unit_aktif]
u_key = st.session_state.unit_aktif.replace(" ", "_")

col_kiri, col_kanan = st.columns([1.15, 2])

# ==========================================
# PANEL KIRI: PENGATURAN CETAK & KALIBRASI
# ==========================================
with col_kiri:
    st.subheader(f"⚙️ Pengaturan {st.session_state.unit_aktif}")
    
    opsi_mode = ["Tahap 2: Isi Blangko Saja", "Tahap 1 & 2 Sekaligus", "Tahap 1 Saja: Cetak Blangko Kosong"]
    idx_mode = opsi_mode.index(cfg["mode_cetak"]) if cfg["mode_cetak"] in opsi_mode else 0
    mode_cetak = st.radio("Pilih Tahap Pencetakan:", opsi_mode, index=idx_mode, key=f"mode_{u_key}")

    opsi_printer = [
        "Epson LQ-2190 (Standar Blangko 15 CPI - ESC g)", 
        "Epson LX-310 / LX-300+II (9-Pin Condensed 17 CPI)", 
        "Epson LX-310 / LX-300+II (9-Pin Elite 12 CPI)"
    ]
    idx_prt = opsi_printer.index(cfg["tipe_printer"]) if cfg["tipe_printer"] in opsi_printer else 0
    tipe_printer = st.selectbox("Pilih Printer yang Digunakan:", opsi_printer, index=idx_prt, key=f"prt_{u_key}")

    # 1. PENGATURAN UNIT & TANDA TANGAN
    with st.expander("✍️ Pengaturan Unit, Kota, Tgl, Jabatan & Pejabat", expanded=True):
        c_u1, c_u2 = st.columns(2)
        with c_u1: up3 = st.text_input("Nama UP3", value=cfg.get("up3", "UP3 KLATEN"), key=f"up3_{u_key}")
        with c_u2: ulp = st.text_input("Nama ULP", value=cfg.get("ulp", st.session_state.unit_aktif), key=f"ulp_{u_key}")
        
        st.markdown("---")
        st.caption("**1. Pengaturan Kota & Tanggal Cetak:**")
        c_kt1, c_kt2 = st.columns(2)
        with c_kt1:
            cetak_kota = st.checkbox("Cetak Kota", value=bool(cfg.get("cetak_kota", False)), key=f"ckota_{u_key}")
            kota_cetak = st.text_input("Nama Kota", value=cfg.get("kota_cetak", "TULUNG"), key=f"kota_{u_key}")
            geser_kota_x = st.number_input("Geser Kiri/Kanan Kota (Spasi):", min_value=-30.0, max_value=30.0, value=float(cfg.get("geser_kota_x", 0.0)), step=0.5, format="%.2f", key=f"gkx_{u_key}")
        with c_kt2:
            cetak_tgl = st.checkbox("Cetak Tanggal", value=bool(cfg.get("cetak_tgl", True)), key=f"ctgl_{u_key}")
            zona_wib = timezone(timedelta(hours=7))
            tgl_hari_ini = datetime.now(zona_wib).strftime("%d-%m-%Y")
            tgl_cetak = st.text_input("Tanggal Cetak", value=tgl_hari_ini, key=f"tgl_{u_key}")
            geser_tgl = st.number_input("Geser Kiri/Kanan Tgl (Spasi):", min_value=-30.0, max_value=30.0, value=float(cfg.get("geser_tgl", 8.0)), step=0.5, format="%.2f", key=f"gtgl_{u_key}")
        geser_kota_tgl_y = st.number_input("Geser Turun/Naik Baris Kota & Tgl (Baris):", min_value=-10, max_value=10, value=int(cfg.get("geser_kota_tgl_y", 0)), step=1, key=f"gkty_{u_key}")

        st.markdown("---")
        st.caption("**2. Pengaturan Jabatan:**")
        cetak_jab = st.checkbox("Cetak Jabatan", value=bool(cfg.get("cetak_jab", False)), key=f"cjab_{u_key}")
        jabatan = st.text_input("Nama Jabatan", value=cfg.get("jabatan", "MANAGER"), key=f"jab_{u_key}")
        c_jb1, c_jb2 = st.columns(2)
        with c_jb1:
            geser_jab_x = st.number_input("Geser Kiri/Kanan Jabatan (Spasi):", min_value=-30.0, max_value=30.0, value=float(cfg.get("geser_jab_x", 0.0)), step=0.5, format="%.2f", key=f"gjx_{u_key}")
        with c_jb2:
            geser_jab_y = st.number_input("Geser Turun/Naik Jabatan (Baris):", min_value=-10, max_value=10, value=int(cfg.get("geser_jab_y", 0)), step=1, key=f"gjy_{u_key}")

        st.markdown("---")
        st.caption("**3. Pengaturan Nama Pejabat / Manager:**")
        cetak_mgr = st.checkbox("Cetak Nama Pejabat", value=bool(cfg.get("cetak_mgr", True)), key=f"cmgr_{u_key}")
        nama_manager = st.text_input("Nama Pejabat / Manager", value=cfg.get("nama_manager", "MARTONO AJI PRABOWO"), key=f"mgr_{u_key}")
        c_mg1, c_mg2 = st.columns(2)
        with c_mg1:
            geser_mgr_x = st.number_input("Geser Kiri/Kanan Nama (Spasi):", min_value=-30.0, max_value=30.0, value=float(cfg.get("geser_mgr_x", 0.0)), step=0.5, format="%.2f", key=f"gmx_{u_key}")
        with c_mg2:
            geser_mgr_y = st.number_input("Geser Turun/Naik Nama (Baris):", min_value=-10, max_value=10, value=int(cfg.get("geser_mgr_y", 0)), step=1, key=f"gmy_{u_key}")

    # 2. KALIBRASI POSISI KERTAS & KOLOM
    with st.expander("📐 Kalibrasi Posisi Kertas & Kolom Khusus"):
        geser_kanan = st.number_input("Geser Kanan/Kiri Semua Teks (Spasi):", min_value=-15.0, max_value=30.0, value=float(cfg.get("geser_kanan", 0.0)), step=0.5, format="%.2f", key=f"gkanan_{u_key}")
        geser_bawah = st.number_input("Geser Turun/Naik Semua Teks (Baris):", min_value=-5.0, max_value=10.0, value=float(cfg.get("geser_bawah", 0.0)), step=0.5, format="%.2f", key=f"gbawah_{u_key}")
        tinggi_halaman = st.number_input("Jumlah Baris per Lembar:", min_value=30, max_value=66, value=int(cfg.get("tinggi_halaman", 44)), key=f"tinggi_{u_key}")
        st.markdown("---")
        st.caption("**Pengaturan Posisi Kolom Khusus (Spasi Kiri/Kanan):**")
        geser_koked = st.number_input("Geser Posisi Koked (KDDK):", min_value=-30, max_value=30, value=int(cfg.get("geser_koked", 0)), step=1, key=f"gkoked_{u_key}")
        geser_rptag = st.number_input("Geser Posisi RpTag (Jumlah Rekening):", min_value=-30, max_value=30, value=int(cfg.get("geser_rptag", 0)), step=1, key=f"grptag_{u_key}")
        geser_bk = st.number_input("Geser Posisi Biaya Keterlambatan:", min_value=-30, max_value=30, value=int(cfg.get("geser_bk", 0)), step=1, key=f"gbk_{u_key}")
        geser_total = st.number_input("Geser Posisi Jumlah Total:", min_value=-30, max_value=30, value=int(cfg.get("geser_total", 0)), step=1, key=f"gtot_{u_key}")

    # Update perubahan pengaturan dasar secara otomatis
    cfg.update({
        "up3": up3, "ulp": ulp,
        "mode_cetak": mode_cetak, "tipe_printer": tipe_printer,
        "geser_kanan": geser_kanan, "geser_bawah": geser_bawah, "tinggi_halaman": tinggi_halaman,
        "geser_koked": geser_koked, "geser_rptag": geser_rptag, "geser_bk": geser_bk, "geser_total": geser_total,
        "cetak_kota": cetak_kota, "kota_cetak": kota_cetak, "geser_kota_x": geser_kota_x,
        "cetak_tgl": cetak_tgl, "geser_tgl": geser_tgl, "geser_kota_tgl_y": geser_kota_tgl_y,
        "cetak_jab": cetak_jab, "jabatan": jabatan, "geser_jab_x": geser_jab_x, "geser_jab_y": geser_jab_y,
        "cetak_mgr": cetak_mgr, "nama_manager": nama_manager, "geser_mgr_x": geser_mgr_x, "geser_mgr_y": geser_mgr_y,
    })
    save_all_profiles(st.session_state.db_unit)

    # 3. BACKUP / RESTORE PROFIL JSON
    with st.expander("💾 Download / Upload Backup Pengaturan (.json)"):
        st.caption("Cadangkan pengaturan unit Anda ke komputer agar aman kapan saja:")
        st.download_button(
            f"⬇️ Download Profil {st.session_state.unit_aktif} (.json)",
            data=json.dumps(cfg, indent=4, ensure_ascii=False).encode("utf-8"),
            file_name=f"Profil_{u_key}.json",
            mime="application/json",
            use_container_width=True
        )
        file_profil = st.file_uploader("⬆️ Pulihkan dari File Profil (.json)", type=["json"], key=f"up_prof_{u_key}")
        if file_profil is not None:
            try:
                loaded_prof = json.load(file_profil)
                st.session_state.db_unit[st.session_state.unit_aktif].update(loaded_prof)
                save_all_profiles(st.session_state.db_unit)
                st.success("✅ Profil berhasil dipulihkan!")
                st.rerun()
            except Exception as e:
                st.error(f"Gagal memuat profil: {e}")


# ==========================================
# PANEL KANAN: UPLOAD DATA, ATUR PETUGAS & CETAK
# ==========================================
with col_kanan:
    init_esc = get_printer_init_code(tipe_printer, tinggi_halaman)
    
    if "Tahap 1 Saja" in mode_cetak:
        st.subheader("📄 Cetak Blangko Kosong (.iconprn)")
        jml = st.number_input("Jumlah Lembar Blangko:", min_value=1, max_value=1000, value=50)
        raw_blanko = buat_blangko_kosong(init_esc, up3, ulp, jml, tinggi_halaman)
        st.download_button(
            label=f"🖨️ Download BLANKO_{jml}_LEMBAR.iconprn", 
            data=raw_blanko.encode("latin1", errors="replace"), 
            file_name=f"BLANKO_{jml}_LEMBAR.iconprn", 
            mime="application/octet-stream",
            type="primary"
        )
    else:
        st.subheader("📂 1. Upload File Tagihan (.iconprn / .xlsx / .zip)")
        uploaded_files = st.file_uploader(
            "Upload File Data (Bisa langsung banyak file .iconprn, .zip, atau .xlsx)", 
            type=["xlsx", "xls", "iconprn", "prn", "zip"], 
            accept_multiple_files=True
        )

        # Ekstrak daftar kode KDDK unik dari file yang di-upload untuk memudahkan pengisian tabel petugas
        kddk_terdeteksi_di_file = set()
        df_t12 = None
        col_map_final = None 
        semua_data_iconprn = []
        excel_uploaded = False

        if uploaded_files:
            with st.spinner("Memproses file masukan..."):
                for uploaded_file in uploaded_files:
                    nama_file = uploaded_file.name.lower()
                    if nama_file.endswith(('.xlsx', '.xls')): 
                        excel_uploaded = True
                    elif nama_file.endswith('.zip'):
                        with zipfile.ZipFile(uploaded_file, 'r') as z:
                            for z_name in z.namelist():
                                if z_name.lower().endswith(('.iconprn', '.prn', '.txt')):
                                    teks_mentah = z.read(z_name).decode('latin1', errors='ignore')
                                    semua_data_iconprn.extend(baca_data_dari_iconprn_tul(teks_mentah, cfg))
                    else:
                        teks_mentah = uploaded_file.getvalue().decode('latin1', errors='ignore')
                        semua_data_iconprn.extend(baca_data_dari_iconprn_tul(teks_mentah, cfg))

            if semua_data_iconprn:
                for d in semua_data_iconprn:
                    kd = ekstrak_kode_rbm(d.get("KDDK", ""), cfg.get("posisi_kddk_awal", 4), cfg.get("posisi_kddk_akhir", 6))
                    if kd: kddk_terdeteksi_di_file.add(kd)

        # ==========================================
        # PENGATURAN TABEL PEMBAGIAN PETUGAS & IDPEL KHUSUS
        # ==========================================
        with st.expander("👷 2. Atur Pembagian Kode Petugas & IDPEL Khusus (Auto-Save)", expanded=False):
            st.info(
                "📌 **Urutan Prioritas Penentuan Petugas:**\n"
                "1. **Tabel IDPEL Khusus** *(Prioritas Tertinggi — Meskipun daya > 33.000 VA / dibaca PLN atau KDDK berbeda, jika IDPEL terdaftar di tabel ini maka otomatis masuk ke petugas yang ditentukan)*.\n"
                "2. **Daya > Batas Daya PLN (33.000 VA)** otomatis masuk kelompok **`PLN`**.\n"
                "3. **Tabel Kode KDDK** *(Otomatis mendeteksi kode tengah KDDK dari file yang Anda upload — tinggal ketik nama/kode petugasnya di kolom kanan)*."
            )

            c_rule1, c_rule2, c_rule3 = st.columns(3)
            with c_rule1:
                batas_daya_pln = st.number_input("Batas Daya PLN (VA):", min_value=0, max_value=1000000, value=int(cfg.get("batas_daya_pln", 33000)), step=1000, key=f"bdaya_{u_key}")
            with c_rule2:
                pos_awal = st.number_input("Ambil KDDK dari Huruf ke-:", min_value=1, max_value=12, value=int(cfg.get("posisi_kddk_awal", 4)), step=1, key=f"pawal_{u_key}")
            with c_rule3:
                pos_akhir = st.number_input("Sampai Huruf ke-:", min_value=1, max_value=12, value=int(cfg.get("posisi_kddk_akhir", 6)), step=1, key=f"pakhir_{u_key}")

            tab_map_kddk, tab_map_idpel = st.tabs([
                f"📋 Tabel Kode KDDK ke Petugas ({len(kddk_terdeteksi_di_file)} Terdeteksi di File)", 
                "⭐ Tabel IDPEL Khusus (Termasuk Daya > 33.000 VA yg Ikut Petugas)"
            ])

            with tab_map_kddk:
                st.caption("Ketik/ubah **Kode Petugas** di kolom sebelah kanan. Anda juga bisa menambah baris baru di paling bawah tabel:")
                map_kddk_saved = cfg.get("map_kddk", {}).copy()
                # Gabungkan kode KDDK yang sudah tersimpan dengan kode KDDK baru yang terdeteksi dari file upload
                semua_kode_kddk = sorted(set(list(map_kddk_saved.keys()) + list(kddk_terdeteksi_di_file)))
                
                rows_kddk = []
                for k in semua_kode_kddk:
                    status_file = "✅ Ada di File" if k in kddk_terdeteksi_di_file else "Tersimpan"
                    rows_kddk.append({
                        "Kode KDDK": k,
                        "Kode Petugas": map_kddk_saved.get(k, f"RBM_{k}"),
                        "Status": status_file
                    })
                if not rows_kddk:
                    rows_kddk = [{"Kode KDDK": "", "Kode Petugas": "", "Status": "Baru"}]

                df_editor_kddk = pd.DataFrame(rows_kddk)
                edited_kddk = st.data_editor(
                    df_editor_kddk,
                    num_rows="dynamic",
                    use_container_width=True,
                    height=260,
                    disabled=["Status"],
                    key=f"ed_kddk_{u_key}_{len(kddk_terdeteksi_di_file)}"
                )

            with tab_map_idpel:
                st.caption("Masukkan **IDPEL** yang pembagian petugasnya khusus (atau pelanggan daya > 33.000 VA / bacaan PLN yang tagihannya diserahkan ke petugas tertentu):")
                map_idpel_saved = cfg.get("map_idpel", {}).copy()
                rows_idpel = [{"IDPEL Khusus": k, "Kode Petugas": v} for k, v in map_idpel_saved.items()]
                if not rows_idpel:
                    rows_idpel = [{"IDPEL Khusus": "", "Kode Petugas": ""}]

                df_editor_idpel = pd.DataFrame(rows_idpel)
                edited_idpel = st.data_editor(
                    df_editor_idpel,
                    num_rows="dynamic",
                    use_container_width=True,
                    height=240,
                    key=f"ed_idpel_{u_key}"
                )

            if st.button("💾 Simpan Pengaturan Petugas & Terapkan ke Data", type="primary", use_container_width=True):
                new_map_kddk = {}
                for _, r in edited_kddk.iterrows():
                    k_val = str(r.get("Kode KDDK", "")).strip().upper()
                    p_val = str(r.get("Kode Petugas", "")).strip()
                    if k_val and p_val and k_val != "NAN":
                        new_map_kddk[k_val] = p_val

                new_map_idpel = {}
                for _, r in edited_idpel.iterrows():
                    id_val = str(r.get("IDPEL Khusus", "")).replace('.0', '').strip()
                    pt_val = str(r.get("Kode Petugas", "")).strip()
                    if id_val and pt_val and id_val != "NAN":
                        new_map_idpel[id_val] = pt_val

                cfg["batas_daya_pln"] = batas_daya_pln
                cfg["posisi_kddk_awal"] = pos_awal
                cfg["posisi_kddk_akhir"] = pos_akhir
                cfg["map_kddk"] = new_map_kddk
                cfg["map_idpel"] = new_map_idpel
                save_all_profiles(st.session_state.db_unit)
                st.success("✅ Pembagian Kode KDDK dan IDPEL Khusus berhasil disimpan & diterapkan!")
                st.rerun()

        # ==========================================
        # TAMPILKAN DATA & TOMBOL CETAK
        # ==========================================
        if uploaded_files:
            if excel_uploaded:
                file_excel = next(f for f in uploaded_files if f.name.lower().endswith(('.xlsx', '.xls')))
                xls = pd.ExcelFile(file_excel)
                pilih_sheet = st.selectbox("Pilih Sheet Excel:", xls.sheet_names) if len(xls.sheet_names) > 1 else xls.sheet_names[0]
                df_excel = pd.read_excel(file_excel, sheet_name=pilih_sheet, dtype=str)
                
                auto_map = deteksi_kolom_otomatis(df_excel.columns.tolist())
                kolom_hilang = [k for k, v in auto_map.items() if v is None and k != "petugas"]

                with st.expander("🔗 Pengaturan Pencocokan Kolom Excel", expanded=len(kolom_hilang) > 0):
                    if kolom_hilang: 
                        st.warning(f"⚠️ Ada nama kolom yang belum cocok otomatis: **{', '.join(kolom_hilang)}**. Silakan sesuaikan:")
                    else: 
                        st.success("✅ Semua kolom Excel otomatis dikenali!")

                    opsi_kolom = ["(Hitung Otomatis dari Aturan Unit / Kosongkan)"] + df_excel.columns.tolist()
                    col_map_final = {}
                    cols_ui = st.columns(3)
                    for idx, (field_blangko, terdeteksi) in enumerate(auto_map.items()):
                        with cols_ui[idx % 3]:
                            idx_default = opsi_kolom.index(terdeteksi) if terdeteksi in opsi_kolom else 0
                            pilihan_kol = st.selectbox(f"[{field_blangko}]:", opsi_kolom, index=idx_default, key=f"map_{field_blangko}")
                            col_map_final[field_blangko] = None if pilihan_kol == "(Hitung Otomatis dari Aturan Unit / Kosongkan)" else pilihan_kol

                # Tambahkan opsi apakah ingin memakai kolom petugas di Excel atau hitung ulang pakai aturan Unit
                pakai_aturan_unit = st.checkbox(
                    "Gunakan Aturan Pembagian Petugas & IDPEL Khusus Unit Ini (Abaikan kolom petugas bawaan Excel)", 
                    value=(col_map_final.get("petugas") is None)
                )

                if pakai_aturan_unit or col_map_final.get("petugas") is None:
                    df_excel["_petugas_auto"] = df_excel.apply(
                        lambda r: tentukan_petugas_universal(
                            ambil_nilai(r, col_map_final, "IDPEL"),
                            ambil_nilai(r, col_map_final, "Tarif/Daya"),
                            ambil_nilai(r, col_map_final, "KDDK"),
                            cfg
                        ), axis=1
                    )
                    col_map_final["petugas"] = "_petugas_auto"

                df_t12 = df_excel
            else:
                if semua_data_iconprn: 
                    df_t12 = pd.DataFrame(semua_data_iconprn)
                    
            if df_t12 is not None and len(df_t12) > 0:
                c_info1, c_info2 = st.columns([2, 1])
                with c_info1:
                    st.success(f"✅ Berhasil memuat **{len(df_t12)} lembar** tagihan pelanggan!")
                with c_info2:
                    out_xl = io.BytesIO()
                    with pd.ExcelWriter(out_xl, engine='openpyxl') as writer:
                        df_t12.to_excel(writer, index=False)
                    st.download_button(
                        "📥 Download Rekap Excel (.xlsx)",
                        data=out_xl.getvalue(),
                        file_name=f"Rekap_TUL_{u_key}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
                
                kol_petugas = col_map_final.get("petugas") if col_map_final else "petugas"
                
                if kol_petugas and kol_petugas in df_t12.columns:
                    df_t12[kol_petugas] = df_t12[kol_petugas].fillna("TANPA_PETUGAS").astype(str)
                    daftar_ptg = sorted(df_t12[kol_petugas].unique().tolist())

                    st.subheader("🖨️ 3. Pilih Petugas & Urutan Cetak")
                    c_p1, c_p2 = st.columns([3, 1])
                    with c_p2:
                        pilih_semua_ptg = st.checkbox("Pilih Semua Petugas", value=False)
                    with c_p1:
                        default_ptg = daftar_ptg if pilih_semua_ptg else ([daftar_ptg[0]] if daftar_ptg else [])
                        ptg_terpilih = st.multiselect("Pilih Kode Petugas / RBM:", daftar_ptg, default=default_ptg)
                    df_saring = df_t12[df_t12[kol_petugas].isin(ptg_terpilih)].reset_index(drop=True)
                else:
                    st.subheader("🖨️ 3. Rentang Urutan Cetak")
                    ptg_terpilih = ["SEMUA"]
                    df_saring = df_t12.reset_index(drop=True)

                total_data = len(df_saring)
                dynamic_key = f"{'_'.join(ptg_terpilih[:3])}_{total_data}"
                
                c2, c3 = st.columns(2)
                with c2: 
                    urut_awal = st.number_input("Mulai Urutan ke-:", min_value=1, max_value=max(1, total_data), value=1, key=f"awal_{dynamic_key}")
                with c3: 
                    urut_akhir = st.number_input("Sampai Urutan ke-:", min_value=1, max_value=max(1, total_data), value=max(1, total_data), key=f"akhir_{dynamic_key}")

                df_cetak = df_saring.iloc[urut_awal - 1 : urut_akhir]
                label_ptg_info = ", ".join(ptg_terpilih[:5]) + ("..." if len(ptg_terpilih) > 5 else "")
                st.info(f"Siap mencetak **{len(df_cetak)} lembar** (Petugas: **{label_ptg_info}**, Urutan {urut_awal} s/d {urut_akhir}).")
                st.dataframe(df_cetak, use_container_width=True, height=240)

                if len(df_cetak) > 0:
                    hasil_iconprn = ""
                    for page_idx, (_, baris) in enumerate(df_cetak.iterrows()):
                        if "Tahap 2" in mode_cetak:
                            hasil_iconprn += buat_isian_blangko(
                                baris, col_map_final, init_esc, kota_cetak, tgl_cetak, jabatan, nama_manager, 
                                cetak_kota, cetak_tgl, cetak_jab, cetak_mgr,
                                geser_kota_x, geser_tgl, geser_kota_tgl_y,
                                geser_jab_x, geser_jab_y,
                                geser_mgr_x, geser_mgr_y,
                                geser_kanan, geser_bawah, tinggi_halaman, tipe_printer, page_idx, 
                                geser_koked, geser_rptag, geser_bk, geser_total
                            )
                        else:
                            hasil_iconprn += buat_blangko_dan_isi(
                                baris, col_map_final, init_esc, up3, ulp, kota_cetak, tgl_cetak, jabatan, nama_manager, tinggi_halaman,
                                cetak_kota, cetak_tgl, cetak_jab, cetak_mgr
                            )

                    nama_ptg_file = "_".join(ptg_terpilih[:3])
                    
                    b1, b2 = st.columns(2)
                    with b1:
                        st.download_button(
                            label=f"🖨️ DOWNLOAD FILE CETAK ({len(df_cetak)} Lbr)",
                            data=hasil_iconprn.encode("latin1", errors="replace"),
                            file_name=f"CETAK_TUL_{nama_ptg_file}_{urut_awal}_{urut_akhir}.iconprn",
                            mime="application/octet-stream",
                            type="primary",
                            use_container_width=True,
                            key=f"dl_cetak_{dynamic_key}"
                        )
                    with b2:
                        if kol_petugas and kol_petugas in df_cetak.columns:
                            buf = io.BytesIO()
                            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
                                for kode_p, grp in df_cetak.groupby(kol_petugas):
                                    teks_p = ""
                                    for p_idx, (_, r) in enumerate(grp.iterrows()):
                                        if "Tahap 2" in mode_cetak:
                                            teks_p += buat_isian_blangko(
                                                r, col_map_final, init_esc, kota_cetak, tgl_cetak, jabatan, nama_manager, 
                                                cetak_kota, cetak_tgl, cetak_jab, cetak_mgr,
                                                geser_kota_x, geser_tgl, geser_kota_tgl_y,
                                                geser_jab_x, geser_jab_y,
                                                geser_mgr_x, geser_mgr_y,
                                                geser_kanan, geser_bawah, tinggi_halaman, tipe_printer, p_idx, 
                                                geser_koked, geser_rptag, geser_bk, geser_total
                                            )
                                        else:
                                            teks_p += buat_blangko_dan_isi(
                                                r, col_map_final, init_esc, up3, ulp, kota_cetak, tgl_cetak, jabatan, nama_manager, tinggi_halaman,
                                                cetak_kota, cetak_tgl, cetak_jab, cetak_mgr
                                            )
                                    zf.writestr(f"TUL_{kode_p}_{len(grp)}lembar.iconprn", teks_p.encode("latin1", errors="replace"))
                            
                            st.download_button(
                                label="📦 DOWNLOAD PAKET PER PETUGAS (.ZIP)",
                                data=buf.getvalue(),
                                file_name=f"PAKET_TUL_{u_key}_{urut_awal}_sd_{urut_akhir}.zip",
                                mime="application/zip",
                                use_container_width=True,
                                key=f"dl_zip_{dynamic_key}"
                            )
