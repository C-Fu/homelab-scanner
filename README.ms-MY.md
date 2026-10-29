# homelab-scanner

`homelab-scanner` ialah alat inventori baca sahaja yang ringkas untuk homelab
Linux. Ia mengumpul maklumat langsung tentang port yang sedang mendengar,
beban kerja Docker, volum, susunan compose, perkhidmatan hos dan penggunaan
cakera, kemudian menulis laporan Markdown dan memaparkan laporan yang sama di
terminal.

Tujuannya ialah menggantikan `service-inventory.md` yang diselenggara secara
manual dengan laporan yang boleh dijana semula pada bila-bila masa berdasarkan
keadaan mesin semasa.

## Ciri-ciri

- **Ringkasan sistem** — nama hos, OS, alamat IP, keadaan firewall, penggunaan
  sistem fail akar, RAM dan masa hidup.
- **Port yang mendengar** — mengesan pendengar TCP dan UDP menggunakan `ss`,
  `netstat` atau `/proc/net`, kemudian melabel setiap port dengan kontena
  Docker, unit systemd atau nama proses.
- **Inventori Docker** — kontena, imej, port yang diterbitkan dan port dalaman
  sahaja, kontena yang dihentikan, penggunaan storan Docker dan volum bernama.
- **Laluan proksi songsang** — menemui laluan HTTP Traefik melalui API Traefik,
  dengan sandaran daripada label kontena.
- **Saiz perkhidmatan** — saiz imej, saiz data bind mount dan jumlah bagi
  setiap susunan.
- **Perkhidmatan hos** — perkhidmatan systemd yang berjalan bersama port, PID
  dan anggaran saiz.
- **Susunan compose** — mengimbas fail compose tempatan, melaporkan port yang
  dikonfigurasikan, keadaan berjalan/idle dan saiz pada cakera.
- **Gambaran cakera dan pembersihan** — direktori besar, jumlah cakera, data
  susunan idle, volum tidak digunakan dan cadangan penjimatan ruang lain tanpa
  memadam apa-apa.

## Keperluan

- Linux. Binari siap bina `homelab-scanner` adalah untuk **x86-64** dan tidak
  memerlukan Python dipasang.
- Untuk menjalankan skrip sumber, gunakan Python **3.8 atau lebih baharu**.
- Tiada pakej Python pihak ketiga diperlukan semasa runtime; semuanya
  menggunakan pustaka standard.
- Alat pilihan akan digunakan jika tersedia:
  - `docker` dan pemalam Docker Compose
  - `systemctl`
  - `ss` atau `netstat` (terdapat sandaran `/proc/net`)
  - `du`
  - `nft`, `ufw` atau `iptables`
  - `findmnt` dan `hostname`

Jalankan sebagai root (atau dengan akses kepada Docker socket dan direktori
terlindung) untuk mendapatkan hasil yang lengkap. Tanpa akses tersebut, skrip
masih berjalan dan hanya membiarkan bahagian yang tidak tersedia kosong atau
anggaran.

## Susun atur projek

```text
homelab-scanner/
├── homelab-scanner          # executable Linux x86-64 siap bina
├── homelab-scanner.py       # skrip sumber mudah alih
├── homelab-report-YYYYMMDD-HHMMSS.md
├── homelab-sample-report-yyyymmdd-hhmmdd.md
├── RELEASE_NOTES.md
├── scripts/prepare-release.sh
├── README.md
└── README.ms-MY.md
```

Nama fail laporan mengandungi tarikh dan masa tempatan, contohnya
`homelab-report-20250614-093000.md`. Setiap kali dijalankan, laporan baharu
dicipta dan laporan lama tidak ditimpa. Kedua-dua binari dan skrip sumber
menggunakan corak nama fail yang sama dan menulis laporan di sebelah fail itu
secara lalai. Laporan yang dijana diabaikan oleh Git; lihat laporan contoh yang
telah disanitasi untuk format tanpa mendedahkan data hos sebenar.

## Pemasangan

Letakkan direktori projek di mana-mana pada hos. Contohnya:

```bash
cd ~
# salin atau clone direktori homelab-scanner ke sini
cd ~/homelab-scanner
chmod +x homelab-scanner homelab-scanner.py
```

Tiada pemasang, persekitaran maya atau langkah `pip install` diperlukan untuk
menjalankan binari siap bina atau skrip sumber.

## Penggunaan

### Binari siap bina

Jana laporan bercap masa dan paparkannya di terminal:

```bash
cd ~/homelab-scanner
./homelab-scanner
```

Binari ini ialah binaan PyInstaller untuk Linux x86-64. Ia mengandungi runtime
Python sendiri, jadi Python tidak perlu dipasang. Walau bagaimanapun, ia
bergantung pada glibc dan kernel Linux hos, jadi gunakannya pada sistem dengan
glibc yang serasi atau lebih baharu daripada hos binaan (Debian 12 / glibc
2.36). Untuk menggunakan binari pada seni bina lain atau distribusi yang lebih
lama, bina semula pada sasaran tersebut.

### Skrip Python

Jalankan versi sumber mudah alih dengan:

```bash
cd ~/homelab-scanner
./homelab-scanner.py
```

Seruan yang setara dengan jurubahasa yang jelas:

```bash
python3 ~/homelab-scanner/homelab-scanner.py
```

Secara lalai, laporan ditulis di sebelah executable atau skrip sebagai
`homelab-report-YYYYMMDD-HHMMSS.md`, dan kandungan yang sama dipaparkan ke
stdout. Pengesahan ringkas seperti `wrote /root/homelab-scanner/...md`
dipaparkan ke stderr.

### Arahan biasa

Binari dan skrip Python menerima pilihan yang sama. Contoh di bawah menggunakan
binari; gantikan `./homelab-scanner` dengan `./homelab-scanner.py` untuk
menggunakan versi sumber.

```bash
# Papar sahaja, tanpa mencipta fail
./homelab-scanner --no-file

# Papar sahaja, secara eksplisit ke stdout
./homelab-scanner -o -

# Tulis ke laluan tertentu
./homelab-scanner -o /tmp/homelab.md

# Larian lebih pantas: langkau ukuran du yang mendalam
./homelab-scanner --fast

# Langkau imbasan fail compose
./homelab-scanner --skip-compose

# Imbas akar tambahan atau akar yang berbeza untuk fail compose
./homelab-scanner --scan-root /opt --scan-root /srv
```

### Membina semula binari

Binari mesti dibina pada platform dan seni bina tempat ia akan dijalankan.
Dengan Python dan pip tersedia:

```bash
cd ~/homelab-scanner
python3 -m venv .venv-build
. .venv-build/bin/activate
python -m pip install --upgrade pyinstaller
pyinstaller --onefile --clean --noconfirm \
  --name homelab-scanner \
  --distpath . --workpath build --specpath build \
  homelab-scanner.py
```

Executable yang terhasil ialah `~/homelab-scanner/homelab-scanner`. Direktori
`build/` dan `.venv-build/` ialah artifak binaan sementara dan boleh dipadamkan
selepas selesai.

### Menyediakan artifak release

Cipta binari berversi, tarball dan fail checksum untuk release Git:

```bash
cd ~/homelab-scanner
./scripts/prepare-release.sh
```

Ini menghasilkan fail berikut secara tempatan, yang diabaikan oleh Git dan
boleh dimuat naik sebagai aset release:

```text
release/homelab-scanner-v1.1.0-linux-amd64
release/homelab-scanner-v1.1.0-linux-amd64.tar.gz
release/SHA256SUMS
```

Sahkan artifak dengan:

```bash
cd release
sha256sum -c SHA256SUMS
```

### Pilihan

| Pilihan | Keterangan |
|---|---|
| `-o`, `--output PATH` | Tulis laporan ke `PATH`. Gunakan `-` untuk stdout sahaja. Lalai ialah `homelab-report-YYYYMMDD-HHMMSS.md` bercap masa di sebelah executable atau skrip. |
| `--no-file` | Papar laporan tetapi jangan tulis fail. |
| `--fast` | Langkau ukuran `du` yang mendalam. Struktur dan data port masih dikumpul, tetapi saiz mungkin tiada atau sifar. |
| `--skip-compose` | Langkau imbasan fail compose dan saiz susunan compose idle. |
| `--scan-root PATH` | Tambah direktori akar untuk diimbas bagi fail compose. Boleh diulang. Lalai: `/root`, `/home`, `/srv`, `/opt`. |
| `--max-stacks N` | Bilangan susunan compose yang dipaparkan dalam laporan (lalai: 15). |
| `--max-volumes N` | Bilangan volum Docker yang dipaparkan dalam laporan (lalai: 15). |
| `--version` | Papar versi skrip. |
| `-h`, `--help` | Tunjukkan semua pilihan baris arahan. |

## Kandungan laporan

Lihat
[`homelab-sample-report-yyyymmdd-hhmmdd.md`](homelab-sample-report-yyyymmdd-hhmmdd.md)
untuk contoh fiksyen dan bersih bagi format laporan.

Laporan Markdown yang dijana mengandungi bahagian berikut, bergantung pada apa
yang tersedia pada hos:

1. **Sistem** — hos, OS, IP, firewall, cakera, RAM, masa hidup dan versi Docker.
2. **Port yang mendengar** — port, protokol, label perkhidmatan/kontena dan
   skop ikatan.
3. **Pemetaan port kontena** — port kontena yang diterbitkan dan port dalaman
   sahaja.
4. **Laluan proksi songsang** — peraturan hos Traefik dan sasaran bahagian
   belakang.
5. **Perkhidmatan Docker yang berjalan** — saiz imej, saiz data bind dan jumlah
   bagi setiap susunan.
6. **Perkhidmatan hos** — unit systemd yang berjalan, port, PID dan anggaran
   saiz.
7. **Storan Docker** — penggunaan imej, kontena, volum dan cache binaan.
8. **Volum** — saiz yang diukur, label pemilik dan keadaan aktif/tidak
   digunakan.
9. **Kontena yang dihentikan** — susunan yang dihentikan atau dicipta serta
   saiz imejnya.
10. **Susunan compose pada cakera** — port yang dikonfigurasikan, keadaan
    berjalan/idle dan saiz.
11. **Data aplikasi yang dimigrasi/legasi** — data aplikasi Runtipi yang
    dimigrasi, jika ada.
12. **Penggunaan cakera** — direktori besar dan jumlah sistem fail.
13. **Jumlah dan cadangan penjimatan ruang** — ringkasan kategori dan petunjuk
    pembersihan.

## Cara saiz dikira

Saiz sengaja dilabel sebagai anggaran.

- **Saiz imej Docker** ialah saiz maya imej. Lapisan yang dikongsi dikira bagi
  setiap imej, jadi jumlah saiz imej yang berjalan bukanlah penggunaan cakera
  fizikal sebenar.
- **Saiz data Docker** diukur daripada bind mount menggunakan `du`. Jika bind
  mount bersarang, mount yang paling spesifik digunakan untuk mengurangkan
  pengiraan berganda.
- **Volum bernama** diukur daripada mountpoint Docker masing-masing.
- **Saiz susunan compose** ialah saiz `du` bagi direktori susunan. Hanya
  projek compose paling cetek dalam sesuatu pokok direktori yang dikira.
- **Saiz perkhidmatan hos** merangkumi direktori pakej yang dikesan daripada
  laluan executable serta `StateDirectory` systemd. Ia tidak merangkumi semua
  pustaka sistem yang dikongsi atau data masa jalan.
- **Angka sistem fail dan storan Docker** datang daripada hos dan Docker, dan
  mungkin menggunakan kaedah perakaunan yang berbeza.

Larian penuh boleh mengambil masa beberapa minit pada hos yang sibuk kerana ia
menelusuri direktori besar seperti `/root`, `/var/lib/docker` dan `/opt`.
Gunakan `--fast` apabila anda hanya memerlukan struktur dan tidak memerlukan
ukuran cakera yang mendalam.

## Keselamatan

Pengimbas ini adalah **baca sahaja**:

- Ia tidak menghentikan kontena, memadam fail, memangkas imej atau mengubah
  peraturan firewall.
- Cadangan penjimatan ruang hanyalah untuk makluman.
- Arahan seperti `docker system prune -a --volumes` **tidak pernah dijalankan**
  oleh skrip ini.

Semak semula apa-apa sebelum memadamnya. Jumlah yang boleh dituntut semula oleh
Docker ialah anggaran dan mungkin merangkumi data yang digunakan oleh kontena
yang dihentikan atau lapisan yang dikongsi.

## Batasan

- Skrip ini menyasarkan Linux. Ia bergantung pada `/proc`, systemd dan tingkah
  laku sistem fail Linux untuk sesetengah bahagian.
- Ringkasan firewall hanyalah penerangan terbaik tentang peraturan hos; ia
  bukan audit keselamatan yang lengkap.
- Label port kepada perkhidmatan bergantung pada keterlihatan proses. Jalankan
  dengan kebenaran yang sesuai untuk hasil paling tepat.
- Nama kontena diselesaikan daripada cgroup jika boleh, dengan pemetaan port
  yang diterbitkan sebagai sandaran.
- Tamat masa atau alat pilihan yang tiada boleh menyebabkan sesetengah saiz
  atau bahagian menjadi kosong tanpa menggagalkan keseluruhan laporan.

## Penyelesaian masalah

**Bahagian Docker kosong**

Pastikan daemon Docker berjalan dan pengguna semasa boleh mengakses Docker
socket:

```bash
docker version
docker ps
```

**Port menunjukkan `?` atau hanya nama proses**

Jalankan pengimbas sebagai root, atau dengan kebenaran untuk memeriksa proses
berkenaan. Sesetengah pendengar tidak dapat dikaitkan tanpa akses yang lebih
tinggi.

**Saiz tiada atau larian terlalu perlahan**

Biasanya ini disebabkan oleh `du` yang menelusuri sistem fail besar atau jauh.
Cuba:

```bash
./homelab-scanner.py --fast
```

**Fail compose tidak ditemui**

Tambahkan direktori yang mengandunginya:

```bash
./homelab-scanner.py --scan-root /path/to/stacks
```

**Laporan sudah wujud**

Itu memang dijangka. Laporan menggunakan cap masa; laporan lama dibiarkan.
Pindahkan atau padam laporan lama sendiri jika tidak diperlukan.
