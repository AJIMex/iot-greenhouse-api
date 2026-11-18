# IoT Greenhouse Monitoring API

MVP REST API (Python Flask + SQLAlchemy ORM, arsitektur MVC) untuk memantau sensor greenhouse:
registrasi perangkat IoT, sensor, telemetri, aturan ambang batas, dan alert otomatis.

> UTS Pemrograman Web Lanjut (TK070) - Universitas AMIKOM Yogyakarta.
> Nama: **[ISI NAMA]** | NIM: **[ISI NIM]**
> Data yang digunakan seluruhnya **data simulasi** (tidak ada scanning/pengujian ke sistem pihak lain).

## Masalah, pengguna, fitur, batasan
- **Masalah:** petani/pengelola greenhouse kecil mengecek suhu, kelembapan udara, dan kelembapan tanah secara manual, sehingga lonjakan kondisi berbahaya terlambat diketahui.
- **Pengguna:** `admin` (kelola user & device), `operator` (pantau sensor, tangani alert), `viewer` (lihat data), serta **perangkat IoT** (ESP32/Raspberry Pi) yang mengirim telemetri dengan API key.
- **Fitur utama:** CRUD user/device/sensor/rule, ingest telemetri (tunggal & batch) dengan API key per perangkat, validasi rentang fisik sensor, evaluasi aturan otomatis -> alert (dengan deduplikasi), siklus status alert (open -> acknowledged -> resolved), statistik telemetri, filter/search/sort/pagination.
- **Batasan MVP:** belum ada autentikasi JWT untuk user (rencana UAS), belum ada MQTT/gateway nyata, belum ada notifikasi eksternal, SQLite untuk lokal.

## Arsitektur (MVC)
```
app/
  models.py        # Model  : entitas ORM (SQLAlchemy)
  views.py         # View   : serializer JSON + format response/pagination
  controllers/     # Controller: blueprint per resource (users, devices, sensors, telemetry, alerts)
  services.py      # Logika bisnis: hash API key, evaluasi alert
  validators.py    # Validasi input, parsing query param
  errors.py        # Format error konsisten
  cli.py           # Perintah init-db, reset-db, seed
tests/             # Automated test (pytest)
docs/              # ERD, OpenAPI, Postman collection
```

## Instalasi
```bash
git clone <URL-REPO-ANDA>
cd iot-greenhouse-api
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # lalu isi SECRET_KEY (opsional untuk lokal)
```

## Konfigurasi
| Variabel | Default | Keterangan |
|---|---|---|
| `SECRET_KEY` | `dev-only-change-me` | Ganti di produksi |
| `DATABASE_URL` | `sqlite:///iot_greenhouse.db` | Bisa MySQL: `mysql+pymysql://user:pass@host/db` (tambahkan `pymysql`) |

## Membuat database & seed
```bash
flask --app run init-db     # membuat tabel
flask --app run seed        # data simulasi + mencetak API key perangkat
flask --app run reset-db    # (opsional) hapus & buat ulang tabel
```

## Menjalankan aplikasi
```bash
flask --app run run --port 5000
# atau: python run.py
```
Cek: `curl http://localhost:5000/health`

## Menjalankan test
```bash
pytest -v
```

## Contoh request & response
**Buat user**
```bash
curl -X POST http://localhost:5000/api/v1/users -H "Content-Type: application/json" \
  -d '{"username":"budi","email":"budi@example.com","password":"Rahasia123","role":"admin"}'
```
```json
{"data":{"id":1,"username":"budi","email":"budi@example.com","role":"admin","created_at":"2026-11-16T03:00:00Z"}}
```
**Registrasi device** (API key hanya tampil sekali)
```bash
curl -X POST http://localhost:5000/api/v1/devices -H "Content-Type: application/json" \
  -d '{"name":"Controller A","serial_number":"GH-ESP32-001","device_type":"esp32","location":"Greenhouse A","owner_id":1}'
```
```json
{"data":{"id":1,"owner_id":1,"name":"Controller A","serial_number":"GH-ESP32-001","device_type":"esp32","location":"Greenhouse A","status":"active","last_seen_at":null,"created_at":"...","api_key":"ghk_xxxxxxxx"}}
```
**Kirim telemetri (perangkat)**
```bash
curl -X POST http://localhost:5000/api/v1/devices/1/telemetry \
  -H "Content-Type: application/json" -H "X-API-Key: ghk_xxxxxxxx" \
  -d '{"sensor_id":1,"value":35.4}'
```
```json
{"data":{"accepted":1,"alerts_triggered":1}}
```
**Daftar device dengan filter + pagination**
`GET /api/v1/devices?status=active&q=greenhouse&sort=-name&page=1&per_page=10`
```json
{"data":[{"id":1,"name":"Controller A","...":"..."}],"meta":{"page":1,"per_page":10,"total":1,"pages":1}}
```
**Error konsisten** (HTTP 422)
```json
{"error":{"code":"validation_error","message":"Validasi input gagal","details":{"email":"format email tidak valid"}}}
```

## Daftar endpoint
Lihat `docs/openapi.yaml` (bisa dibuka di https://editor.swagger.io) atau impor `docs/postman_collection.json` ke Postman/Insomnia. ERD: `docs/ERD.md`.

## Keamanan dasar yang diterapkan
- Password di-hash (Werkzeug), tidak pernah dikembalikan di response.
- API key perangkat di-hash SHA-256, dibandingkan dengan `hmac.compare_digest`, tampil sekali, dapat dirotasi.
- ORM + parameterized query (anti SQL injection); validasi tipe, panjang, regex, enum.
- Foreign key diaktifkan di SQLite; constraint unik; hapus user dengan device ditolak (409).
- Batas ukuran body 1 MB, batas batch telemetri 100, header keamanan, error 500 tidak membocorkan detail.

## Referensi, library, dan bantuan AI
- Library: Flask, Flask-SQLAlchemy, SQLAlchemy, pytest, gunicorn. Dokumentasi resmi masing-masing.
- Bantuan AI: Claude (Anthropic) digunakan untuk membantu menyusun kerangka kode, test, dan dokumentasi; seluruh hasil telah saya baca, jalankan, dan pahami. **[Sesuaikan pernyataan ini dengan kondisi sebenarnya]**

## Rencana UAS
Lihat bagian Soal 6 pada lembar jawaban: JWT + RBAC, rate limiting, deployment, visualisasi telemetri, dan integrasi MQTT gateway.

## Link demo
**[ISI URL DEMO / live API]**
