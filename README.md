# Plane (internal)

Fork internal dari [Plane](https://github.com/makeplane/plane) untuk project management tim. Isinya Plane Community Edition ditambah beberapa penyesuaian (lihat [Perbedaan dari upstream](#perbedaan-dari-upstream)), dengan deploy yang membangun semua image langsung dari repo ini.

> **Repo ini publik.** Jangan commit password, token, IP internal, atau data (export ClickUp, backup). Nilai sebenarnya hanya ada di `plane.env` / `db.env` di server. `data/`, `plane.env`, dan `db.env` sudah ada di `.gitignore`.

## Akses

| Dari       | Alamat                          | Catatan                                                                |
| ---------- | ------------------------------- | ---------------------------------------------------------------------- |
| Internet   | `https://<APP_DOMAIN>`          | Lewat Cloudflare Tunnel, HTTPS diurus Cloudflare                       |
| LAN kantor | `http://<APP_LAN_ADDRESS>:2028` | Tetap jalan tanpa internet (Plane, database, dan file semuanya di LAN) |

- Login di tiap alamat terpisah: masuk sekali lewat domain dan sekali lewat LAN.
- Pengaturan instance (admin): `/god-mode/`.
- File (lampiran, avatar) ikut alamat yang sedang dibuka, jadi tidak perlu domain terpisah untuk storage.

## Akun tim

1. Admin mengundang email anggota: **Workspace settings → Members → Invite**. Email undangan tidak terkirim (SMTP belum diatur), jadi kabari orangnya langsung.
2. Anggota mendaftar dengan **email yang sama**, lalu menerima undangan yang muncul di akunnya.
3. Admin memasukkan anggota ke project: **Project settings → Members**.
4. Setelah semua masuk, matikan **"Allow anyone to sign up"** di `/god-mode/` → Authentication. Email yang sudah diundang tetap bisa mendaftar.

Tidak ada aturan kekuatan password (sengaja dihapus), jadi minta tim memakai password yang kuat. Reset password lewat email belum bisa selama SMTP belum diatur.

## Perbedaan dari upstream

- **Tanpa validasi kekuatan password**: password apa pun diterima asal tidak kosong (`is_password_strong` di API, `getPasswordStrength` di `@plane/utils`).
- **Akses hybrid LAN + domain**: redirect setelah login kembali ke alamat yang dipakai, selama alamat itu ada di `CORS_ALLOWED_ORIGINS` (`apps/api/plane/authentication/utils/host.py`). Cookie diberi flag Secure hanya untuk request HTTPS (`apps/api/plane/middleware/secure_cookies.py`).
- **File lewat proxy ke MinIO sendiri**: proxy meneruskan `/<bucket>/*` ke `MINIO_UPSTREAM` (diisi dari `AWS_S3_ENDPOINT_URL`).
- **Form setup admin** menampilkan pesan error (sebelumnya diam saja).
- **Deploy dari source** lewat `deploy.sh`, dengan database bisa dijalankan sebagai stack terpisah.

## Deploy ke server

Prasyarat: Docker dengan plugin `docker compose`, `git`, `curl`, dan RAM minimal ±4 GB (untuk build frontend).

```bash
git clone git@github.com:mersifarma/plane.git && cd plane
```

### 1. Database

Di host database:

```bash
bash deploy.sh db
```

Perintah ini membuat `db.env` dengan password acak lalu menjalankan Postgres 15 di port **5341**. Output-nya berisi `PGHOST` dan `POSTGRES_*` untuk disalin ke `plane.env`. Isi `DB_BIND` di `db.env` dengan IP privat, atau batasi port 5341 lewat firewall supaya hanya server aplikasi yang bisa mengakses.

### 2. Aplikasi

```bash
bash deploy.sh      # run pertama: membuat plane.env dengan secret baru, lalu berhenti
nano plane.env      # isi nilai di tabel bawah
bash deploy.sh      # git pull, build image, jalankan, lalu cek kesehatan dan storage
```

| Variabel                                                                       | Isi                                                            |
| ------------------------------------------------------------------------------ | -------------------------------------------------------------- |
| `APP_DOMAIN`                                                                   | Hostname publik di Cloudflare, tanpa `https://` dan tanpa port |
| `APP_LAN_ADDRESS`                                                              | IP LAN server aplikasi (terdeteksi otomatis)                   |
| `LISTEN_HTTP_PORT`                                                             | `2028`, satu-satunya port yang dibuka (tidak ada 443)          |
| `PGHOST`, `POSTGRES_PORT`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | Dari output `bash deploy.sh db`                                |
| `USE_MINIO`                                                                    | `1` (file dilayani lewat proxy Plane)                          |
| `AWS_S3_ENDPOINT_URL`                                                          | Alamat LAN MinIO, misalnya `http://<ip-minio>:<port>`          |
| `AWS_S3_BUCKET_NAME`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`             | Bucket dan kredensial MinIO                                    |

`WEB_URL` dan `CORS_ALLOWED_ORIGINS` sudah diisi otomatis dari `APP_DOMAIN`, `APP_LAN_ADDRESS`, dan port.

**Update:** cukup jalankan `bash deploy.sh` lagi.

**Cloudflare Tunnel:** buat public hostname `<APP_DOMAIN>` → service `http://localhost:2028` (atau IP server aplikasi).

### Hal yang perlu diperhatikan

- **Jangan buat workspace dengan slug sama dengan nama bucket**, karena URL-nya akan diteruskan ke MinIO.
- **Subnet Docker bentrok dengan LAN:** kalau container timeout saat menghubungi database atau MinIO, cek apakah ada jaringan Docker yang memakai rentang IP LAN, misalnya `192.168.0.0/20`:
  ```bash
  docker network ls -q | xargs docker network inspect -f '{{.Name}} {{range .IPAM.Config}}{{.Subnet}}{{end}}'
  ```
- **Ganti password database** (setelah database pernah dijalankan, mengubah `db.env` saja tidak cukup):
  ```bash
  docker exec plane-db-plane-db-1 psql -U plane -c "ALTER USER plane PASSWORD '<baru>'"
  ```
  Lalu samakan `POSTGRES_PASSWORD` di `db.env` dan `plane.env`, dan jalankan `bash deploy.sh`.
- **Log API:** `docker compose -p plane-server logs --tail 100 api`

## Pengembangan lokal

Butuh Node ≥ 22, Docker Desktop, dan pnpm 11.10.0. Node 26 tidak lagi membawa corepack, jadi pasang pnpm dengan `npm i -g pnpm@11.10.0`.

```bash
bash setup.sh                                        # buat .env + pnpm install (error corepack boleh diabaikan)
docker compose -f docker-compose-local.yml up -d     # API, database, redis, rabbitmq, minio
pnpm dev                                             # web, admin, space
cd apps/live && node --env-file=.env .               # live server (di Windows tidak ikut start lewat pnpm dev)
```

| App   | URL                               |
| ----- | --------------------------------- |
| Web   | http://localhost:3000             |
| Admin | http://localhost:3001/god-mode/   |
| Space | http://localhost:3002/spaces/     |
| API   | http://localhost:8000             |
| Live  | http://localhost:3100/live/health |

- Pengaturan storage lokal ada di `.env` root saja (kredensial, bucket, endpoint). Compose meneruskannya ke API dan worker.
- **Windows:** `packages/i18n/locales` adalah symlink yang di Windows ter-checkout sebagai file teks, sehingga label tampil sebagai key mentah (`issue.new`). Perbaiki sekali setelah clone (PowerShell):
  ```powershell
  Remove-Item packages\i18n\locales
  New-Item -ItemType Junction -Path packages\i18n\locales -Target "$PWD\packages\i18n\src\locales"
  git update-index --skip-worktree packages/i18n/locales
  ```
- **Jangan jalankan `turbo build`/`check:types` saat `pnpm dev` aktif**, karena keduanya menulis `packages/*/dist` bersamaan dan Vite akan error `Failed to load url ... .js`. Kalau terjadi, matikan semua proses dev lalu jalankan ulang.
- Test backend: `docker compose -f docker-compose-local.yml exec api python -m pytest plane/tests/unit`

## Sinkron dengan Plane upstream

```bash
git remote add upstream https://github.com/makeplane/plane.git
git fetch upstream preview --no-tags
git merge upstream/preview      # selesaikan konflik di file yang ada di "Perbedaan dari upstream"
git push
```

Ambil branch `preview` saja. Upstream punya branch yang namanya hanya beda huruf besar/kecil, dan itu bentrok di Windows kalau semua branch di-fetch.

## Migrasi dari ClickUp

Data ClickUp (5 space, 361 task, komentar, dan link lampiran) sudah dimigrasi pada November 2026. Skrip dan data migrasinya tidak disimpan di repo ini karena berisi data internal.

## Lisensi

[AGPL-3.0](LICENSE.txt), sama dengan Plane. Karena Plane ini dijalankan sebagai layanan jaringan, source code beserta modifikasinya harus tersedia bagi penggunanya. Repo publik ini memenuhi syarat itu.
