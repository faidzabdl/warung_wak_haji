# Deploy Plan — Warung Wak Haji ke Render.com

## Top-Level Overview

Deploy seluruh aplikasi Warung Wak Haji ke Render.com menggunakan **Render Blueprint** (`render.yaml`) agar backend (FastAPI) dan frontend (Vue 3 SPA) bisa di-deploy sekaligus dari satu push ke GitHub.

**Arsitektur di Render:**
- **Backend**: Render Web Service — FastAPI + Uvicorn, baca `$PORT` dari env
- **Frontend**: Render Static Site — serve `frontend/dist/` hasil `vite build`
- **Database**: Tetap di Supabase (tidak di-migrate ke Render)

**Prinsip:**
- Tidak ada secret di-commit ke Git
- Backend URL diinjeksikan ke frontend via `VITE_API_URL`
- CORS dikonfigurasi via `ALLOWED_ORIGINS` di backend
- Satu file `render.yaml` di root repo = satu klik deploy

---

## Sub-Task 1 — Pisahkan `requirements.txt` untuk production

**Status:** `[ ] pending`

**Intent:**
`requirements.txt` sekarang berisi dev/test deps (pytest, httpx, pytest-asyncio) yang tidak perlu di-install di production. Render akan install semua yang ada di `requirements.txt`. Memisahkan keduanya mempercepat build dan menjaga image tetap lean.

**Expected Outcomes:**
- `requirements.txt` hanya berisi runtime deps (fastapi, uvicorn, supabase, dll)
- `requirements-dev.txt` berisi test deps (pytest, pytest-asyncio, httpx)
- `pytest.ini` tetap berjalan lokal dengan `pip install -r requirements-dev.txt`

**Todo List:**
1. Buat `requirements-dev.txt` yang berisi: `pytest>=8.1.0`, `pytest-asyncio>=0.23.0`, `httpx>=0.27.0`, dan `-r requirements.txt` di baris pertama
2. Hapus `pytest>=8.1.0`, `pytest-asyncio>=0.23.0`, `httpx>=0.27.0` dari `requirements.txt`
3. Verifikasi `pytest.ini` atau README tidak ada instruksi yang perlu diupdate

**Relevant Context:**
- `requirements.txt` — file yang diubah
- Render menggunakan `requirements.txt` sebagai pip install source

---

## Sub-Task 2 — Pastikan backend baca `$PORT` dari environment

**Status:** `[ ] pending`

**Intent:**
Render menginjeksikan port via env var `$PORT` (bukan selalu 8000). Start command harus menggunakan `$PORT`. Di `main.py` tidak ada hardcoded port — port ditentukan saat startup command, bukan di kode. Ini perlu dikonfirmasi dan start command ditulis dengan benar.

**Expected Outcomes:**
- Start command yang digunakan: `uvicorn main:app --host 0.0.0.0 --port $PORT`
- Tidak ada hardcoded `8000` di start command `render.yaml`
- Backend tetap jalan di `localhost:8000` untuk development lokal

**Todo List:**
1. Tidak ada perubahan ke `main.py` (port ditentukan via CLI, bukan kode)
2. Start command di `render.yaml` menggunakan: `uvicorn main:app --host 0.0.0.0 --port $PORT`
3. Untuk lokal, devs tetap gunakan: `uvicorn main:app --host 0.0.0.0 --port 8000`

**Relevant Context:**
- `main.py` — tidak perlu diubah, sudah bersih
- Render auto-sets `$PORT`, biasanya `10000`

---

## Sub-Task 3 — Buat `render.yaml` (Blueprint)

**Status:** `[ ] pending`

**Intent:**
`render.yaml` adalah Infrastructure-as-Code untuk Render. Dengan file ini, satu klik "New Blueprint" di Render Dashboard akan membuat **dua service sekaligus**: backend Web Service dan frontend Static Site. Semua konfigurasi (build commands, env var references, health checks) ada di satu file.

**Expected Outcomes:**
- File `render.yaml` di root repo
- Mendefinisikan 2 services: `warung-backend` (web) dan `warung-frontend` (static)
- Backend: build dari Python, start dengan uvicorn `$PORT`
- Frontend: build dari `frontend/`, publish dir `frontend/dist/`
- Semua secret env var ditandai `sync: false` (diisi manual di Render Dashboard, tidak di-commit)
- Non-secret env var (`ENVIRONMENT=production`) bisa di-hardcode di `render.yaml`
- SPA rewrite rule: semua path `/*` → `/index.html` (Vue Router history mode)

**Todo List:**
1. Buat file `render.yaml` di root repo
2. Definisikan service `warung-backend`:
   - `type: web`
   - `runtime: python`
   - `buildCommand: pip install -r requirements.txt`
   - `startCommand: uvicorn main:app --host 0.0.0.0 --port $PORT`
   - `healthCheckPath: /health`
   - `plan: free`
   - Env vars: `ENVIRONMENT=production` (value hardcoded), semua secret (`SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`, `ALLOWED_ORIGINS`, `ALLOWED_SELLER_UID`) dengan `sync: false`
3. Definisikan service `warung-frontend`:
   - `type: static`
   - `buildCommand: cd frontend && npm ci && npm run build`
   - `staticPublishPath: frontend/dist`
   - `plan: free`
   - Env vars: `VITE_API_URL`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY` dengan `sync: false`
   - Routes rewrite: `source: /*` → `destination: /index.html` (SPA fallback)

**Relevant Context:**
- Render Blueprint schema: https://render.com/docs/blueprint-spec
- `ALLOWED_ORIGINS` di backend harus diisi dengan URL frontend Render setelah deploy pertama
- `VITE_API_URL` di frontend harus diisi dengan URL backend Render setelah deploy pertama
- Frontend build command harus `cd frontend &&` karena `render.yaml` ada di root, bukan di `frontend/`

**Catatan penting — Chicken-and-egg URLs:**
Setelah deploy pertama, Render akan assign URL ke kedua service (format: `https://warung-backend.onrender.com` dan `https://warung-frontend.onrender.com`). Lalu perlu update 2 env var:
1. Di backend: `ALLOWED_ORIGINS=https://warung-frontend.onrender.com`
2. Di frontend: `VITE_API_URL=https://warung-backend.onrender.com`
Lalu trigger redeploy kedua service. Ini prosedur normal untuk cross-service Render deployment.

---

## Sub-Task 4 — Update `frontend/src/lib/supabase.ts` agar tidak crash saat env var kosong

**Status:** `[ ] pending`

**Intent:**
Saat ini `supabase.ts` hanya `console.warn` jika env var kosong, lalu melempar string kosong ke `createClient`. Di production, ini menyebabkan error runtime yang susah di-debug. Perlu guard yang lebih jelas.

**Expected Outcomes:**
- Jika `VITE_SUPABASE_URL` atau `VITE_SUPABASE_ANON_KEY` tidak di-set, app tetap load tapi seller login gagal dengan pesan yang jelas
- Tidak ada runtime crash di halaman buyer (mereka tidak butuh Supabase langsung)
- Pesan error yang jelas jika seller mencoba login tanpa env var

**Todo List:**
1. Cek isi `frontend/src/lib/supabase.ts` — pastikan sudah ada guard yang cukup
2. Jika belum, tambahkan fallback yang graceful (throw hanya saat `supabase.auth` dipanggil, bukan saat import)
3. `VITE_SUPABASE_URL` dan `VITE_SUPABASE_ANON_KEY` harus diisi di Render Dashboard env var untuk frontend

**Relevant Context:**
- `frontend/src/lib/supabase.ts` — file yang dicek
- `frontend/src/stores/auth.ts` — menggunakan `supabase.auth.getSession()` dan `signInWithPassword`

---

## Sub-Task 5 — Buat `frontend/.env.example`

**Status:** `[ ] pending`

**Intent:**
Saat ini `frontend/` tidak punya `.env.example`. Developer baru tidak tahu env var apa yang dibutuhkan frontend. Perlu file contoh yang terdokumentasi. File `.env` asli sudah di `.gitignore`.

**Expected Outcomes:**
- File `frontend/.env.example` terdokumentasi, tidak berisi secret sungguhan
- README atau komentar di file menjelaskan cara mendapatkan setiap nilai

**Todo List:**
1. Buat `frontend/.env.example` dengan tiga variabel: `VITE_API_URL`, `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`
2. Tambahkan komentar penjelasan di setiap var

**Relevant Context:**
- `.env.example` yang sudah ada di root sebagai referensi gaya penulisan
- `frontend/src/lib/api.ts` — `VITE_API_URL`
- `frontend/src/lib/supabase.ts` — `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`

---

## Sub-Task 6 — Tambahkan `_redirects` atau konfigurasi SPA routing di Static Site

**Status:** `[ ] pending`

**Intent:**
Vue Router menggunakan `createWebHistory()` (history mode). Saat user mengakses `/seller/orders` langsung (bukan dari navigasi dalam app), Render Static Site akan mengembalikan 404 karena file tersebut tidak ada di `dist/`. Perlu rewrite rule agar semua request dikembalikan ke `index.html`.

**Expected Outcomes:**
- Navigasi langsung ke `/seller/orders`, `/track/TOKEN`, `/checkout` tidak 404
- File `frontend/public/_redirects` berisi satu baris rewrite rule
- Atau dikonfigurasi via `render.yaml` routes (sudah dicakup di Sub-Task 3)

**Todo List:**
1. Buat file `frontend/public/_redirects` dengan isi: `/* /index.html 200`
2. File ini akan otomatis ter-copy ke `frontend/dist/` oleh Vite saat build
3. Render Static Site akan membaca `_redirects` untuk SPA routing

**Catatan:** `render.yaml` routes (Sub-Task 3) dan file `_redirects` adalah dua cara berbeda. File `_redirects` lebih portable (juga berlaku jika deploy ke Netlify/Cloudflare). Gunakan keduanya sebagai fallback.

**Relevant Context:**
- `frontend/src/router/index.ts` — menggunakan `createWebHistory()`
- `frontend/public/` — folder untuk static assets yang di-copy ke dist
- Render Static Site docs: mendukung `_redirects` file (Netlify-style)

---

## Sub-Task 7 — Update README dengan instruksi deploy

**Status:** `[ ] pending`

**Intent:**
Dokumentasi step-by-step cara deploy ke Render agar bisa diikuti tanpa pengetahuan sebelumnya. Termasuk cara mendapatkan nilai setiap env var dari Supabase Dashboard.

**Expected Outcomes:**
- README punya bagian "Deploy ke Render" yang mencakup:
  1. Prasyarat (repo di GitHub, akun Render, project Supabase)
  2. Deploy via Blueprint (render.yaml)
  3. Mengisi env var di Render Dashboard (dengan penjelasan cara mendapatkan setiap nilai dari Supabase)
  4. Prosedur chicken-and-egg URL (update ALLOWED_ORIGINS dan VITE_API_URL setelah deploy pertama)
  5. Menjalankan migration SQL di Supabase SQL Editor

**Todo List:**
1. Baca README yang ada sekarang
2. Tambahkan section "## Deploy ke Render.com" dengan instruksi lengkap
3. Sertakan tabel env var + cara mendapatkan nilainya

**Relevant Context:**
- `README.md` — file yang diupdate
- `.env.example` — referensi daftar env var backend
- `frontend/.env.example` — referensi daftar env var frontend (dibuat di Sub-Task 5)

---

## Urutan Eksekusi

```
1 (pisah requirements) → 2 (konfirmasi $PORT) → 3 (render.yaml) → 4 (supabase guard) → 5 (frontend .env.example) → 6 (_redirects SPA) → 7 (README)
```

## Checklist Akhir (setelah semua sub-task selesai)

- [ ] `requirements.txt` hanya runtime deps
- [ ] `requirements-dev.txt` berisi test deps
- [ ] `render.yaml` ada di root, valid, 2 services
- [ ] `frontend/public/_redirects` berisi `/* /index.html 200`
- [ ] `frontend/.env.example` terdokumentasi
- [ ] README punya instruksi deploy lengkap
- [ ] `vite build` tetap berhasil
- [ ] `pytest tests/` tetap 81 passed
