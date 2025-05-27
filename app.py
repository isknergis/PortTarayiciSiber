# app.py dosyasının içeriği

from flask import Flask, render_template, request, flash, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
import socket
import threading
from queue import Queue
import datetime
import os # Gizli anahtar için kullanılacak

app = Flask(__name__)

# --- GİZLİ ANAHTAR ---
# Bu anahtar, Flask'ın oturum (session) verilerini güvenli bir şekilde imzalaması için gereklidir.
# Gerçek bir uygulamada bu değeri rastgele, uzun ve tahmin edilemez bir dizeyle değiştirmelisin.
# Örneğin, Python konsolunda os.urandom(24).hex() komutuyla üretebilirsin.
app.secret_key = os.urandom(24).hex() # Güvenli ve rastgele bir anahtar oluşturduk

# --- Veritabanı Ayarları ---
# app.db adında bir SQLite veritabanı dosyası oluşturacak veya bağlanacak
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False # Bu ayar genelde False yapılır, gereksiz uyarıları engeller

db = SQLAlchemy(app) # Flask uygulamamız ile veritabanını bağlıyoruz

# --- Veritabanı Modelleri (Tablolarımızın Yapısı) ---
# ScanResult adında yeni bir "tablo" (model) oluşturuyoruz
class ScanResult(db.Model):
    id = db.Column(db.Integer, primary_key=True) # Her sonucun benzersiz kimliği (otomatik artar)
    target_ip = db.Column(db.String(100), nullable=False) # Hangi IP'ye tarama yapıldı
    port = db.Column(db.Integer, nullable=False) # Hangi port
    status = db.Column(db.String(10), nullable=False) # Açık mı, Kapalı mı
    scan_time = db.Column(db.DateTime, default=datetime.datetime.now) # Ne zaman tarandı

    def __repr__(self): # Sonucu daha okunur göstermek için (opsiyonel)
        return f'<ScanResult {self.target_ip}:{self.port} - {self.status}>'

# --- Yardımcı Fonksiyon: Her Bir Portu Tarayan İş Parçacığı ---
# Bu fonksiyonu threading ile aynı anda birden fazla kez çalıştıracağız
def port_scan_worker(target_ip, port, results_queue):
    try:
        # Bir soket (ağ bağlantı noktası) oluşturuyoruz
        # socket.AF_INET: IPv4 adresleri için
        # socket.SOCK_STREAM: TCP bağlantısı için (web siteleri, SSH gibi)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1) # Bir porta bağlanmak için maksimum 1 saniye bekle

        # Belirtilen IP'deki porta bağlanmayı dene
        result = sock.connect_ex((target_ip, port)) # Eğer bağlantı başarılıysa 0 döndürür

        if result == 0: # Port açıksa
            results_queue.put({"port": port, "status": "Açık"})
        # Kapalı portları kuyruğa eklemiyoruz ki veritabanı ve liste çok büyümesin
        # else:
        #    results_queue.put({"port": port, "status": "Kapalı"})

        sock.close() # Soketi kapatmayı unutma, kaynakları serbest bırak
    except Exception as e:
        # Hata durumunda (örneğin, ağ hatası), sessizce geçebiliriz veya kuyruğa hata mesajı ekleyebiliriz
        pass

# --- Flask Route: Ana Sayfa ---
@app.route("/")
def index():
    # Veritabanından en son 10 tarama sonucunu alıyoruz (en yeniler üste gelsin)
    # `all()` komutu, tüm sonuçları bir liste olarak bize verir
    recent_scans = ScanResult.query.order_by(ScanResult.id.desc()).limit(10).all()
    # Ana sayfayı render ederken, yeni tarama sonuçları için boş bir liste, 
    # geçmiş taramalar için ise veritabanından aldıklarımızı gönderiyoruz
    return render_template("index.html", scan_results=[], recent_scans=recent_scans)

# --- Flask Route: Port Tarama İşlemi ---
@app.route("/scan", methods=["POST"]) # Bu sayfa sadece form gönderildiğinde çalışacak
def scan_ports():
    # Formdan gelen verileri alıyoruz
    target_ip = request.form.get("target_ip")
    start_port = request.form.get("start_port")
    end_port = request.form.get("end_port")

    # Gelen verilerin boş olup olmadığını kontrol et
    if not target_ip or not start_port or not end_port:
        flash("Lütfen tüm alanları doldurun.", "error") # Kullanıcıya hata mesajı göster
        return redirect(url_for("index")) # Ana sayfaya geri yönlendir

    try:
        start_port = int(start_port)
        end_port = int(end_port)
    except ValueError:
        flash("Port numaraları geçerli sayılar olmalıdır.", "error")
        return redirect(url_for("index"))

    # Port aralığı kontrolü
    if not (0 <= start_port <= 65535 and 0 <= end_port <= 65535 and start_port <= end_port):
        flash("Geçerli bir port aralığı girin (0-65535).", "error")
        return redirect(url_for("index"))

    # Hedef IP adresinin geçerli olup olmadığını kontrol et
    try:
        # socket.gethostbyname, domain adını IP'ye çevirir. Geçersizse hata verir.
        socket.gethostbyname(target_ip) 
    except socket.gaierror:
        flash(f"Hata: Geçersiz IP adresi veya hostname '{target_ip}'.", "error")
        return redirect(url_for("index"))

    # Tarama sonuçlarını iş parçacıklarından toplamak için bir kuyruk oluşturuyoruz
    results_queue = Queue() 
    threads = [] # Oluşturacağımız iş parçacıklarını (thread) burada tutacağız

    # Her bir port için bir iş parçacığı oluşturup başlatıyoruz
    for port in range(start_port, end_port + 1):
        # Her bir iş parçacığı port_scan_worker fonksiyonunu çalıştıracak
        # args: fonksiyona göndereceğimiz bilgiler (hedef IP, port, sonuçları ekleyeceği kuyruk)
        thread = threading.Thread(target=port_scan_worker, args=(target_ip, port, results_queue))
        threads.append(thread) # Oluşturduğumuz iş parçacığını listeye ekle
        thread.start() # İş parçacığını başlat!

    # Tüm iş parçacıklarının bitmesini bekle
    for thread in threads:
        thread.join() # Her iş parçacığının bitmesini bekle ("işin bitene kadar bekle")

    # Kuyruktaki tüm sonuçları al
    raw_results = []
    while not results_queue.empty():
        raw_results.append(results_queue.get())

    # Sadece açık portları veritabanına kaydet ve ekranda gösterilecek listeye ekle
    added_to_db_count = 0
    display_results = [] # Ekranda göstereceğimiz sonuçlar

    for res_dict in raw_results:
        # Veritabanına kaydedilecek yeni bir ScanResult objesi oluştur
        new_scan = ScanResult(
            target_ip=target_ip,
            port=res_dict["port"],
            status=res_dict["status"]
        )
        db.session.add(new_scan) # Veritabanına ekle
        added_to_db_count += 1
        display_results.append(f"Port {res_dict['port']}: {res_dict['status']}")

    # Veritabanı değişikliklerini kaydet (commit)
    try:
        db.session.commit()
        if added_to_db_count > 0:
            flash(f"Tarama tamamlandı! {added_to_db_count} açık port veritabanına kaydedildi.", "success")
        else:
            flash(f"Tarama tamamlandı. Belirtilen aralıkta açık port bulunamadı ({target_ip}, Port {start_port}-{end_port}).", "info")
    except Exception as e:
        db.session.rollback() # Bir hata olursa değişiklikleri geri al
        flash(f"Veritabanına kaydedilirken hata oluştu: {e}", "error")

    # Tarama bittikten sonra kullanıcıyı tekrar ana sayfaya yönlendiriyoruz
    # Bu sayede veritabanına kaydedilen en son sonuçlar da ana sayfada görünecek
    return redirect(url_for("index")) 


# --- Uygulama İlk Kez Başladığında Veritabanını Oluşturma ---
# Bu kod, Flask uygulaması ilk kez başladığında çalışacak
# Eğer 'app.db' dosyası yoksa, veritabanını ve tabloları oluşturur
with app.app_context():
    db.create_all() # Tüm tanımlanmış tabloları oluşturur

# Uygulamayı çalıştır (debug=True sadece geliştirme aşamasında kullanılmalı)
if __name__ == "__main__":
    app.run(debug=True)
