import os
import random
import sqlite3
from flask import Flask, jsonify, render_template_string, request
from groq import Groq
from pypdf import PdfReader

app = Flask(__name__)

# Groq API anahtarı
API_KEY = os.environ.get("GEMINI_API_KEY")
client = Groq(api_key=GROQ_API_KEY)

# Mutlak yol tanımları
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
PDF_KLASORU = os.path.join(BASE_DIR, "pdf_dosyalari")
DB_YOLU = os.path.join(BASE_DIR, "sohbetler.db")

if not os.path.exists(PDF_KLASORU):
  os.makedirs(PDF_KLASORU)


# Veritabanı ve Tablo Oluşturma
def veritabani_baslat():
  conn = sqlite3.connect(DB_YOLU)
  cursor = conn.cursor()
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS sohbetler (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pdf_adi TEXT,
            rol TEXT,
            icerik TEXT
        )
    """)
  conn.commit()
  conn.close()


veritabani_baslat()


def mesaj_ekle(pdf_adi, rol, icerik):
  conn = sqlite3.connect(DB_YOLU)
  cursor = conn.cursor()
  cursor.execute(
      "INSERT INTO sohbetler (pdf_adi, rol, icerik) VALUES (?, ?, ?)",
      (pdf_adi, rol, icerik),
  )
  conn.commit()
  conn.close()


def gecmisi_getir():
  conn = sqlite3.connect(DB_YOLU)
  cursor = conn.cursor()
  cursor.execute("SELECT pdf_adi, rol, icerik FROM sohbetler")
  kayitlar = cursor.fetchall()
  conn.close()

  sohbet_gecmisi = []
  for k in kayitlar:
    sohbet_gecmisi.append({"pdf_adi": k[0], "rol": k[1], "icerik": k[2]})
  return sohbet_gecmisi


def yuklenen_pdf_leri_getir():
  conn = sqlite3.connect(DB_YOLU)
  cursor = conn.cursor()
  cursor.execute("SELECT DISTINCT pdf_adi FROM sohbetler")
  pdf_listesi = [row[0] for row in cursor.fetchall()]
  conn.close()
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


# Renk havuzu (Tailwind sınıfları)
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
            if (alan) {
                alan.scrollTop = alan.scrollHeight;
            }
        }
        window.addEventListener("DOMContentLoaded", sohbetiEnAltaKaydir);
    </script>
</head>
<body class="bg-gray-100 min-h-screen p-4">
    <div class="max-w-6xl mx-auto grid grid-cols-1 md:grid-cols-4 gap-6">
        
        <!-- Sol Taraf: Kayıtlı PDF / Sohbet Listesi -->
        <div class="md:col-span-1 bg-pink-100 p-4 rounded-xl shadow-md flex flex-col h-[85vh]">
            <h2 class="text-lg font-bold text-pink-900 mb-3 border-b border-pink-200 pb-2">📜 Geçmiş Sohbetler</h2>
            <div class="overflow-y-auto flex-1 space-y-2 pr-1 text-sm">
                {% if not pdf_listesi %}
                    <p class="text-pink-400 text-center py-4 text-xs">Henüz kayıtlı sohbet yok.</p>
                {% endif %}
                {% for p in pdf_listesi %}
                    {% set renk = renkler[loop.index0 % renkler | length] %}
                    <a href="/?pdf={{ p }}" class="block p-2.5 rounded border transition {{ renk }} {% if aktif_pdf == p %}ring-2 ring-pink-500 font-bold{% endif %}">
                        📄 <span class="truncate block">{{ p }}</span>
                    </a>
                {% endfor %}
            </div>
        </div>

        <!-- Sağ Taraf: Ana İşlem ve Sohbet Paneli -->
        <div class="md:col-span-3 bg-white p-6 rounded-xl shadow-md space-y-4 flex flex-col h-[85vh]">
            <h1 class="text-2xl font-bold text-gray-800">Akıllı Asistan</h1>
            
            <!-- Dropzone ve Özet Formu -->
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

            <!-- Sohbet Geçmişi Alanı -->
            <div id="sohbet-alani" class="space-y-3 flex-1 overflow-y-auto p-2 border rounded-lg bg-gray-50 flex flex-col">
                {% set aktif_gecmis = sohbet_gecmisi | selectattr('pdf_adi', 'equalto', aktif_pdf) | list %}
                {% if not aktif_gecmis %}
                    <p id="bos-mesaj" class="text-gray-400 text-center py-4">Bu dosya için henüz bir mesaj geçmişi yok.</p>
                {% endif %}
                {% for mesaj in sohbet_gecmisi %}
                    {% if mesaj.pdf_adi == aktif_pdf %}
                        {% if mesaj.rol == 'Kullanıcı' %}
                            <div class="flex justify-end">
                                <div class="bg-blue-100 p-3 rounded-lg max-w-lg text-right text-gray-800 shadow-sm text-sm">
                                    <strong>Sen:</strong> {{ mesaj.icerik }}
                                </div>
                            </div>
                        {% else %}
                            <div class="flex justify-start">
                                <div class="bg-white p-3 rounded-lg max-w-lg text-gray-800 whitespace-pre-wrap border shadow-sm text-sm">
                                    <strong>Asistan:</strong><br>{{ mesaj.icerik }}
                                </div>
                            </div>
                        {% endif %}
                    {% endif %}
                {% endfor %}
            </div>

            <!-- Soru Sorma Formu -->
            <form id="soru-formu" class="flex gap-2">
                <input type="text" id="soru-input" name="soru" placeholder="PDF hakkında soru sor / Ask a question..." required class="flex-1 border p-2 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-purple-400">
                <button type="submit" id="gonder-btn" class="bg-purple-600 text-white px-4 py-2 rounded-lg text-sm font-medium hover:bg-purple-700">Gönder</button>
            </form>
        </div>
    </div>

    <!-- Dropzone JS -->
    <script src="https://unpkg.com/dropzone@5/dist/min/dropzone.min.js"></script>
    <script>
        Dropzone.options.pdfDropzone = {
            url: "/upload",
            paramName: "file",
            maxFilesize: 10,
            acceptedFiles: ".pdf",
            dictDefaultMessage: "PDF yüklemek için tıklayın veya sürükleyin",
            success: function(file, response) {
                document.getElementById("aktif-pdf").value = response.filename;
                setTimeout(() => {
                    window.location.href = "/?pdf=" + encodeURIComponent(response.filename);
                }, 800);
            }
        };

        document.getElementById("soru-formu").addEventListener("submit", async function(e) {
            e.preventDefault();
            const input = document.getElementById("soru-input");
            const soru = input.value.trim();
            const secilenPdf = document.getElementById("aktif-pdf").value;

            if (!soru || !secilenPdf || secilenPdf === "None") {
                alert("Lütfen önce bir PDF yükleyin veya seçin!");
                return;
            }

            const bosMesaj = document.getElementById("bos-mesaj");
            if (bosMesaj) bosMesaj.remove();

            const sohbetAlani = document.getElementById("sohbet-alani");

            const userDiv = document.createElement("div");
            userDiv.className = "flex justify-end";
            userDiv.innerHTML = `<div class="bg-blue-100 p-3 rounded-lg max-w-lg text-right text-gray-800 shadow-sm text-sm"><strong>Sen:</strong> ${soru}</div>`;
            sohbetAlani.appendChild(userDiv);
            sohbetiEnAltaKaydir();

            input.value = "";
            input.disabled = true;

            const loadingDiv = document.createElement("div");
            loadingDiv.className = "flex justify-start";
            loadingDiv.id = "loading-mesaj";
            loadingDiv.innerHTML = `<div class="bg-white p-3 rounded-lg max-w-lg text-gray-500 border shadow-sm text-sm"><em>Asistan düşünüyor...</em></div>`;
            sohbetAlani.appendChild(loadingDiv);
            sohbetiEnAltaKaydir();

            try {
                const response = await fetch("/ajax-soru", {
                    method: "POST",
                    headers: { "Content-Type": "application/x-www-form-urlencoded" },
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
                const errDiv = document.createElement("div");
                errDiv.className = "flex justify-start";
                errDiv.innerHTML = `<div class="bg-white p-3 rounded-lg max-w-lg text-red-600 border shadow-sm text-sm"><strong>Asistan:</strong><br>❌ Bağlantı hatası oluştu.</div>`;
                sohbetAlani.appendChild(errDiv);
                sohbetiEnAltaKaydir();
            } finally {
                input.disabled = false;
                input.focus();
            }
        });
    </script>
</body>
</html>
"""


@app.route("/")
def index():
  gecmis = gecmisi_getir()
  pdf_listesi = yuklenen_pdf_leri_getir()

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


@app.route("/ajax-soru", methods=["POST"])
def ajax_soru():
  secilen_pdf = request.form.get("secilen_pdf")
  soru_metni = request.form.get("soru", "").strip()

  if not secilen_pdf or secilen_pdf == "None":
    return jsonify({"cevap": "⚠️ Lütfen önce bir PDF dosyası yükleyin!"})

  pdf_metni = pdf_metin_cikar(secilen_pdf)
  if not pdf_metni or len(pdf_metni.strip()) == 0:
    return jsonify({"cevap": f"❌ '{secilen_pdf}' dosyası okunamadı."})

  mesaj_ekle(secilen_pdf, "Kullanıcı", soru_metni)

  try:
    completion = client.chat.completions.create(
        model="llama-3.1-8b-instant",
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a helpful assistant. Answer the user's question"
                    " using the provided PDF document. CRITICAL RULE: Detect the"
                    " language of the user's question and reply in the exact"
                    " same language (if Turkish, reply in Turkish; if English,"
                    " reply in English)."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"PDF Content:\n{pdf_metni[:8000]}\n\nQuestion:"
                    f" {soru_metni}"
                ),
            },
        ],
        temperature=0.3,
    )
    cevap = completion.choices[0].message.content
  except Exception as e:
    cevap = f"❌ Hata / Error: {str(e)}"

  mesaj_ekle(secilen_pdf, "Asistan", cevap)
  return jsonify({"cevap": cevap})


@app.route("/islem", methods=["POST"])
def islem():
  secilen_pdf = request.form.get("secilen_pdf")
  action = request.form.get("action")

  if not secilen_pdf or secilen_pdf == "None":
    return index()

  pdf_metni = pdf_metin_cikar(secilen_pdf)
  if not pdf_metni or len(pdf_metni.strip()) == 0:
    return index()

  if action == "ozetle_tr":
    icerik_iste = f"'{secilen_pdf}' dosyasını özetle."
    mesaj_ekle(secilen_pdf, "Kullanıcı", icerik_iste)
    try:
      completion = client.chat.completions.create(
          model="llama-3.1-8b-instant",
          messages=[
              {
                  "role": "system",
                  "content": (
                      "Sen yardımsever bir asistansın. Sağlanan PDF metnini"
                      " maddeler halinde net ve anlaşılır bir şekilde TÜRKÇE"
                      " olarak özetle."
                  ),
              },
              {"role": "user", "content": pdf_metni[:8000]},
          ],
          temperature=0.3,
      )
      cevap = completion.choices[0].message.content
    except Exception as e:
      cevap = f"❌ Hata oluştu: {str(e)}"
    mesaj_ekle(secilen_pdf, "Asistan", cevap)

  elif action == "ozetle_en":
    icerik_iste = f"Summarize '{secilen_pdf}' file."
    mesaj_ekle(secilen_pdf, "Kullanıcı", icerik_iste)
    try:
      completion = client.chat.completions.create(
          model="llama-3.1-8b-instant",
          messages=[
              {
                  "role": "system",
                  "content": (
                      "You are a helpful assistant. Summarize the provided PDF"
                      " text clearly in bullet points in ENGLISH."
                  ),
              },
              {"role": "user", "content": pdf_metni[:8000]},
          ],
          temperature=0.3,
      )
      cevap = completion.choices[0].message.content
    except Exception as e:
      cevap = f"❌ Error / Error: {str(e)}"
    mesaj_ekle(secilen_pdf, "Asistan", cevap)

  return index()


if __name__ == "__main__":
  app.run(host="0.0.0.0", port=5000, debug=False)