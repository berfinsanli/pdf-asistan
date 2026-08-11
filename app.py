import os
import random
from flask import Flask, jsonify, redirect, render_template_string, request, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from groq import Groq
from pypdf import PdfReader

app = Flask(__name__)
app.secret_key = "gizli_anahtar_berfin"

# Mutlak yol tanımları
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
PDF_KLASORU = os.path.join(BASE_DIR, "pdf_dosyalari")
DB_YOLU = os.path.join(BASE_DIR, "sohbetler.db")

# Veritabanı ve Migration Ayarları
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{DB_YOLU}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)

if not os.path.exists(PDF_KLASORU):
    os.makedirs(PDF_KLASORU)

# Groq API anahtarı
API_KEY = "gsk_B9HydSBErFdV4vb7f89RWgdyb3Fyg0XmkHJAsRYZnGT8bgd3zJb"
client = Groq(api_key=API_KEY)


# SQLAlchemy Model Tanımları (Kullanıcı ID eklendi)
class Kullanici(db.Model):
    __tablename__ = 'kullanicilar'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    kullanici_adi = db.Column(db.String(80), unique=True, nullable=False)
    sifre = db.Column(db.String(120), nullable=False)

class Sohbet(db.Model):
    __tablename__ = 'sohbetler'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, nullable=False)  # Hangi kullanıcıya ait?
    pdf_adi = db.Column(db.Text)
    rol = db.Column(db.Text)
    icerik = db.Column(db.Text)


def mesaj_ekle(user_id, pdf_adi, rol, icerik):
    yeni_mesaj = Sohbet(user_id=user_id, pdf_adi=pdf_adi, rol=rol, icerik=icerik)
    db.session.add(yeni_mesaj)
    db.session.commit()


def gecmisi_getir(user_id):
    kayitlar = Sohbet.query.filter_by(user_id=user_id).all()
    sohbet_gecmisi = []
    for k in kayitlar:
        sohbet_gecmisi.append({"pdf_adi": k.pdf_adi, "rol": k.rol, "icerik": k.icerik})
    return sohbet_gecmisi


def yuklenen_pdf_leri_getir(user_id):
    kayitlar = db.session.query(Sohbet.pdf_adi).filter_by(user_id=user_id).distinct().all()
    pdf_listesi = [row[0] for row in kayitlar if row[0]]
    return pdf_listesi


def pdf_metin_cikar(dosya_adi):
    dosya_yolu = os.path.join(PDF_KLASORU, dosya_adi)
    if not os.path.exists(dosya_yolu):
        return None
    try:
        reader = PdfReader(dosya_yolu)
        text = ""
        for page in reader.pages:
            t = page.extract_text()
            if t:
                text += t + "\n"
        return text
    except Exception as e:
        print(f"PDF Okuma Hatası: {e}")
        return None


RENK_HAVUZU = [
    "bg-amber-100 border-amber-300 text-amber-800 hover:bg-amber-200",
    "bg-emerald-100 border-emerald-300 text-emerald-800 hover:bg-emerald-200",
    "bg-sky-100 border-sky-300 text-sky-800 hover:bg-sky-200",
    "bg-purple-100 border-purple-300 text-purple-800 hover:bg-purple-200",
    "bg-yellow-100 border-yellow-300 text-yellow-800 hover:bg-yellow-200",
    "bg-teal-100 border-teal-300 text-teal-800 hover:bg-teal-200",
    "bg-indigo-100 border-indigo-300 text-indigo-800 hover:bg-indigo-200",
    "bg-orange-100 border-orange-300 text-orange-800 hover:bg-orange-200",
]


# HTML Şablonları
HTML_SABLONU = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8">
    <title>Akıllı Asistan</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://unpkg.com/dropzone@5/dist/min/dropzone.min.css" type="text/css" />
    <script>
        function sohbetiEnAltaKaydir() {
            const alan = document.getElementById("sohbet-alani");
            if (alan) { alan.scrollTop = alan.scrollHeight; }
        }
        window.addEventListener("DOMContentLoaded", sohbetiEnAltaKaydir);
    </script>
</head>
<body class="bg-gray-100 min-h-screen p-4">
    <div class="max-w-6xl mx-auto flex justify-between items-center mb-4 px-2">
        <span class="text-sm font-semibold text-gray-700">👤 Kullanıcı: <span class="text-purple-600 font-bold">{{ session.get('kullanici_adi') }}</span></span>
        <a href="/cikis" class="text-xs bg-red-500 text-white px-3 py-1.5 rounded-lg hover:bg-red-600 transition shadow-sm">Çıkış Yap</a>
    </div>

    <div class="max-w-6xl mx-auto grid grid-cols-1 md:grid-cols-4 gap-6">
        <div class="md:col-span-1 bg-pink-100 p-4 rounded-xl shadow-md flex flex-col h-[85vh]">
            <h2 class="text-lg font-bold text-pink-900 mb-3 border-b border-pink-200 pb-2">📜 Geçmiş Sohbetlerim</h2>
            <div class="overflow-y-auto flex-1 space-y-2 pr-1 text-sm">
                {% if not pdf_listesi %}
                    <p class="text-pink-400 text-center py-4 text-xs">Henüz kayıtlı sohbetin yok.</p>
                {% endif %}
                {% for p in pdf_listesi %}
                    {% set renk = renkler[loop.index0 % renkler | length] %}
                    <div class="flex items-center gap-1">
                        <a href="/?pdf={{ p }}" class="flex-1 p-2.5 rounded border transition {{ renk }} {% if aktif_pdf == p %}ring-2 ring-pink-500 font-bold{% endif %} truncate">
                            📄 <span class="truncate">{{ p }}</span>
                        </a>
                        <form action="/delete/{{ p }}" method="POST" onsubmit="return confirm('Bu PDF ve sohbet geçmişi silinsin mi?');">
                            <button type="submit" class="p-2.5 bg-red-100 border border-red-300 text-red-600 rounded hover:bg-red-200 transition text-xs" title="Sil">🗑️</button>
                        </form>
                    </div>
                {% endfor %}
            </div>
        </div>

        <div class="md:col-span-3 bg-white p-6 rounded-xl shadow-md space-y-4 flex flex-col h-[85vh]">
            <h1 class="text-2xl font-bold text-gray-800">Akıllı Asistan</h1>
            
            <form action="/islem" method="post" class="p-3 bg-gray-50 rounded-lg border space-y-3">
                <div>
                    <label class="block font-semibold mb-1 text-gray-700 text-sm">Yeni PDF Yükle</label>
                    <div class="dropzone border-dashed border-2 border-blue-300 rounded-lg bg-white p-2 text-center cursor-pointer text-sm" id="pdfDropzone"></div>
                </div>
                <input type="hidden" name="secilen_pdf" id="aktif-pdf" value="{{ aktif_pdf }}">
                <div id="aktif-dosya-bilgi" class="text-sm font-medium text-gray-700">
                    Aktif Dosya: <span class="text-blue-600">{% if aktif_pdf %}{{ aktif_pdf }}{% else %}Seçilmedi{% endif %}</span>
                </div>
                <div class="flex gap-2">
                    <button type="submit" name="action" value="ozetle_tr" class="flex-1 bg-indigo-500 text-white py-1.5 rounded-lg text-sm font-medium hover:bg-indigo-600">🇹🇷 Türkçe Özetle</button>
                    <button type="submit" name="action" value="ozetle_en" class="flex-1 bg-purple-500 text-white py-1.5 rounded-lg text-sm font-medium hover:bg-purple-600">🇬🇧 English Summary</button>
                </div>
            </form>

            <hr>

            <div id="sohbet-alani" class="space-y-3 flex-1 overflow-y-auto p-2 border rounded-lg bg-gray-50 flex flex-col">
                {% set aktif_gecmis = sohbet_gecmisi | selectattr('pdf_adi', 'equalto', aktif_pdf) | list %}
                {% if not aktif_gecmis %}
                    <p id="bos-mesaj" class="text-gray-400 text-center py-4">Bu dosya için henüz bir mesaj geçmişi yok.</p>
                {% endif %}
                {% for mesaj in sohbet_gecmisi %}
                    {% if mesaj.pdf_adi == aktif_pdf %}
                        {% if mesaj.rol == 'Kullanıcı' %}
                            <div class="flex justify-end">
                                <div class="bg-blue-100 p-3 rounded-lg max-w-lg text-right text-gray-800 shadow-sm text-sm"><strong>Sen:</strong> {{ mesaj.icerik }}</div>
                            </div>
                        {% else %}
                            <div class="flex justify-start">
                                <div class="bg-white p-3 rounded-lg max-w-lg text-gray-800 whitespace-pre-wrap border shadow-sm text-sm"><strong>Asistan:</strong><br>{{ mesaj.icerik }}</div>
                            </div>
                        {% endif %}
                    {% endif %}
                {% endfor %}
            </div>

            <form id="soru-formu" class="flex gap-2">
                <input type="text" id="soru-input" name="soru" placeholder="PDF hakkında soru sor / Ask a question..." required class="flex-1 border p-2 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-purple-400">
                <button type="submit" id="gonder-btn" class="bg-purple-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-purple-700">Gönder</button>
            </form>
        </div>
    </div>

    <script src="https://unpkg.com/dropzone@5/dist/min/dropzone.min.js"></script>
    <script>
        Dropzone.options.pdfDropzone = {
            url: "/upload", paramName: "file", maxFilesize: 10, acceptedFiles: ".pdf",
            dictDefaultMessage: "PDF yüklemek için tıklayın veya sürükleyin",
            success: function(file, response) {
                document.getElementById("aktif-pdf").value = response.filename;
                setTimeout(() => { window.location.href = "/?pdf=" + encodeURIComponent(response.filename); }, 800);
            }
        };

        document.getElementById("soru-formu").addEventListener("submit", async function(e) {
            e.preventDefault();
            const input = document.getElementById("soru-input");
            const soru = input.value.trim();
            const secilenPdf = document.getElementById("aktif-pdf").value;
            if (!soru || !secilenPdf || secilenPdf === "None") { alert("Lütfen önce bir PDF yükleyin veya seçin!"); return; }

            const bosMesaj = document.getElementById("bos-mesaj");
            if (bosMesaj) bosMesaj.remove();
            const sohbetAlani = document.getElementById("sohbet-alani");

            const userDiv = document.createElement("div");
            userDiv.className = "flex justify-end";
            userDiv.innerHTML = `<div class="bg-blue-100 p-3 rounded-lg max-w-lg text-right text-gray-800 shadow-sm text-sm"><strong>Sen:</strong> ${soru}</div>`;
            sohbetAlani.appendChild(userDiv);
            sohbetiEnAltaKaydir();
            input.value = ""; input.disabled = true;

            const loadingDiv = document.createElement("div");
            loadingDiv.className = "flex justify-start"; loadingDiv.id = "loading-mesaj";
            loadingDiv.innerHTML = `<div class="bg-white p-3 rounded-lg max-w-lg text-gray-500 border shadow-sm text-sm"><em>Asistan düşünüyor...</em></div>`;
            sohbetAlani.appendChild(loadingDiv);
            sohbetiEnAltaKaydir();

            try {
                const response = await fetch("/ajax-soru", {
                    method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" },
                    body: `soru=${encodeURIComponent(soru)}&secilen_pdf=${encodeURIComponent(secilenPdf)}`
                });
                const data = await response.json();
                document.getElementById("loading-mesaj").remove();
                const assistantDiv = document.createElement("div");
                assistantDiv.className = "flex justify-start";
                assistantDiv.innerHTML = `<div class="bg-white p-3 rounded-lg max-w-lg text-gray-800 whitespace-pre-wrap border shadow-sm text-sm"><strong>Asistan:</strong><br>${data.cevap}</div>`;
                sohbetAlani.appendChild(assistantDiv);
                sohbetiEnAltaKaydir();
                setTimeout(() => { location.reload(); }, 1200);
            } catch (err) {
                document.getElementById("loading-mesaj").remove();
            } finally {
                input.disabled = false; input.focus();
            }
        });
    </script>
</body>
</html>
"""

GIRIS_SABLONU = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8"><title>Giriş Yap</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-100 min-h-screen flex items-center justify-center">
    <div class="bg-white p-8 rounded-xl shadow-md w-96 space-y-4">
        <h2 class="text-2xl font-bold text-gray-800 text-center">Giriş Yap</h2>
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="p-3 text-sm rounded bg-red-100 text-red-700">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        <form method="POST" class="space-y-4">
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Kullanıcı Adı</label>
                <input type="text" name="kullanici_adi" required class="w-full border p-2 rounded-lg text-sm focus:ring-2 focus:ring-blue-400">
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Şifre</label>
                <input type="password" name="sifre" required class="w-full border p-2 rounded-lg text-sm focus:ring-2 focus:ring-blue-400">
            </div>
            <button type="submit" class="w-full bg-blue-600 text-white py-2 rounded-lg text-sm font-medium hover:bg-blue-700 transition">Giriş Yap</button>
        </form>
        <p class="text-xs text-center text-gray-500 mt-3">Hesabın yok mu? <a href="/kayit" class="text-blue-600 font-bold hover:underline">Kayıt Ol</a></p>
    </div>
</body>
</html>
"""

KAYIT_SABLONU = """
<!DOCTYPE html>
<html lang="tr">
<head>
    <meta charset="UTF-8"><title>Kayıt Ol</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-100 min-h-screen flex items-center justify-center">
    <div class="bg-white p-8 rounded-xl shadow-md w-96 space-y-4">
        <h2 class="text-2xl font-bold text-gray-800 text-center">Kayıt Ol</h2>
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="p-3 text-sm rounded bg-red-100 text-red-700">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}
        <form method="POST" class="space-y-4">
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Kullanıcı Adı</label>
                <input type="text" name="kullanici_adi" required class="w-full border p-2 rounded-lg text-sm focus:ring-2 focus:ring-purple-400">
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-700 mb-1">Şifre</label>
                <input type="password" name="sifre" required class="w-full border p-2 rounded-lg text-sm focus:ring-2 focus:ring-purple-400">
            </div>
            <button type="submit" class="w-full bg-purple-600 text-white py-2 rounded-lg text-sm font-medium hover:bg-purple-700 transition">Kayıt Ol ve Başla</button>
        </form>
        <p class="text-xs text-center text-gray-500 mt-3">Zaten hesabın var mı? <a href="/giris" class="text-purple-600 font-bold hover:underline">Giriş Yap</a></p>
    </div>
</body>
</html>
"""


with app.app_context():
    db.create_all()


# Rotalar
@app.route("/giris", methods=["GET", "POST"])
def giris():
    if request.method == "POST":
        k_adi = request.form.get("kullanici_adi")
        sifre = request.form.get("sifre")
        user = Kullanici.query.filter_by(kullanici_adi=k_adi, sifre=sifre).first()
        if user:
            session['user_id'] = user.id
            session['kullanici_adi'] = user.kullanici_adi
            return redirect(url_for('index'))
        else:
            flash("Hatalı kullanıcı adı veya şifre!", "danger")
    return render_template_string(GIRIS_SABLONU)


@app.route("/kayit", methods=["GET", "POST"])
def kayit():
    if request.method == "POST":
        k_adi = request.form.get("kullanici_adi")
        sifre = request.form.get("sifre")
        
        mevcut = Kullanici.query.filter_by(kullanici_adi=k_adi).first()
        if mevcut:
            flash("Bu kullanıcı adı zaten alınmış!", "danger")
        else:
            yeni_user = Kullanici(kullanici_adi=k_adi, sifre=sifre)
            db.session.add(yeni_user)
            db.session.commit()
            flash("Kayıt başarılı! Şimdi giriş yapabilirsiniz.", "success")
            return redirect(url_for('giris'))
    return render_template_string(KAYIT_SABLONU)


@app.route("/cikis")
def cikis():
    session.clear()
    return redirect(url_for('giris'))


@app.route("/")
def index():
    if 'user_id' not in session:
        return redirect(url_for('giris'))
        
    user_id = session['user_id']
    gecmis = gecmisi_getir(user_id)
    pdf_listesi = yuklenen_pdf_leri_getir(user_id)

    aktif_pdf = request.args.get("pdf")
    if not aktif_pdf:
        if pdf_listesi:
            aktif_pdf = pdf_listesi[-1]
        else:
            aktif_pdf = None

    return render_template_string(
        HTML_SABLONU,
        aktif_pdf=aktif_pdf,
        sohbet_gecmisi=gecmis,
        pdf_listesi=pdf_listesi,
        renkler=RENK_HAVUZU,
    )


@app.route("/upload", methods=["POST"])
def upload_file():
    if 'user_id' not in session:
        return jsonify({"error": "Oturum açılmadı"}), 401
    if "file" not in request.files:
        return jsonify({"error": "Dosya bulunamadı"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "Dosya seçilmedi"}), 400

    if file and file.filename.endswith(".pdf"):
        dosya_yolu = os.path.join(PDF_KLASORU, file.filename)
        file.save(dosya_yolu)
        return jsonify({"success": True, "filename": file.filename})

    return jsonify({"error": "Sadece PDF dosyaları yüklenebilir"}), 400


@app.route("/delete/<path:pdf_adi>", methods=["POST"])
def delete_pdf(pdf_adi):
    if 'user_id' not in session:
        return redirect(url_for('giris'))
    
    # Sadece o kullanıcının sohbetlerini sil
    Sohbet.query.filter_by(user_id=session['user_id'], pdf_adi=pdf_adi).delete()
    db.session.commit()
    return redirect(url_for("index"))


@app.route("/ajax-soru", methods=["POST"])
def ajax_soru():
    if 'user_id' not in session:
        return jsonify({"cevap": "⚠️ Oturum açmanız gerekiyor!"})

    user_id = session['user_id']
    secilen_pdf = request.form.get("secilen_pdf")
    soru_metni = request.form.get("soru", "").strip()

    if not secilen_pdf or secilen_pdf == "None":
        return jsonify({"cevap": "⚠️ Lütfen önce bir PDF dosyası yükleyin!"})

    pdf_metni = pdf_metin_cikar(secilen_pdf)
    if not pdf_metni or len(pdf_metni.strip()) == 0:
        return jsonify({"cevap": f"❌ '{secilen_pdf}' dosyası okunamadı."})

    mesaj_ekle(user_id, secilen_pdf, "Kullanıcı", soru_metni)

    try:
        completion = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[
                {"role": "system", "content": "You are a helpful assistant. Answer in the user's language."},
                {"role": "user", "content": f"PDF Content:\n{pdf_metni[:8000]}\n\nQuestion: {soru_metni}"},
            ],
            temperature=0.3,
        )
        cevap = completion.choices[0].message.content
    except Exception as e:
        cevap = f"❌ Hata: {str(e)}"

    mesaj_ekle(user_id, secilen_pdf, "Asistan", cevap)
    return jsonify({"cevap": cevap})


@app.route("/islem", methods=["POST"])
def islem():
    if 'user_id' not in session:
        return redirect(url_for('giris'))

    user_id = session['user_id']
    secilen_pdf = request.form.get("secilen_pdf")
    action = request.form.get("action")

    if not secilen_pdf or secilen_pdf == "None":
        return index()

    pdf_metni = pdf_metin_cikar(secilen_pdf)
    if not pdf_metni or len(pdf_metni.strip()) == 0:
        return index()

    if action == "ozetle_tr":
        mesaj_ekle(user_id, secilen_pdf, "Kullanıcı", f"'{secilen_pdf}' dosyasını özetle.")
        try:
            completion = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": "Sen yardımsever bir asistansın. PDF'i Türkçe özetle."},
                    {"role": "user", "content": pdf_metni[:8000]},
                ],
                temperature=0.3,
            )
            cevap = completion.choices[0].message.content
        except Exception as e:
            cevap = f"❌ Hata: {str(e)}"
        mesaj_ekle(user_id, secilen_pdf, "Asistan", cevap)

    elif action == "ozetle_en":
        mesaj_ekle(user_id, secilen_pdf, "Kullanıcı", f"Summarize '{secilen_pdf}'.")
        try:
            completion = client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": "Summarize the PDF in English."},
                    {"role": "user", "content": pdf_metni[:8000]},
                ],
                temperature=0.3,
            )
            cevap = completion.choices[0].message.content
        except Exception as e:
            cevap = f"❌ Error: {str(e)}"
        mesaj_ekle(user_id, secilen_pdf, "Asistan", cevap)

    return index()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)