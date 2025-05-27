# app.py dosyasının içeriği

from flask import Flask, render_template, request
import socket
import threading # Artık threading'i aktif olarak kullanacağız
from queue import Queue # İşleri düzenlemek için Queue kullanacağız

app = Flask(__name__)

# Her bir portu tarayacak fonksiyon (bir "iş parçacığı"nın yapacağı iş)
def port_scan_worker(target_ip, port, results_queue):
    try:
        # socket.AF_INET: İnternet adresi tipi (IPv4)
        # socket.SOCK_STREAM: TCP bağlantı tipi (en yaygın, web siteleri bununla çalışır)
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1) # Bir porta bağlanmak için maksimum 1 saniye bekle (zaman aşımı)

        result = sock.connect_ex((target_ip, port)) # Bağlanmayı dene, eğer hata olursa numara döndür

        if result == 0: # Eğer result 0 ise, bağlantı başarılı, yani port açık!
            # Sonucu kuyruğa ekle
            results_queue.put(f"Port {port}: Açık") 
        # Port kapalıysa, bir şey eklemiyoruz (istersen "Kapalı" mesajı da eklenebilir)

        sock.close() # Soketi kapatmayı unutma
    except Exception as e:
        # Hata durumunda da kuyruğa ekleyebiliriz (örneğin "Port 80: Hata - {e}")
        # Şimdilik sadece geçiyoruz, ana fonksiyondaki genel hataları yakalıyoruz
        pass 

# --- Ana Sayfa için Route ---
@app.route("/")
def index():
    return render_template("index.html", scan_results=[]) 

# --- Tarama İşlemi için Yeni Route ---
@app.route("/scan", methods=["POST"])
def scan_ports():
    target_ip = request.form.get("target_ip")
    start_port = int(request.form.get("start_port"))
    end_port = int(request.form.get("end_port"))

    if not target_ip or not start_port or not end_port:
        return render_template("index.html", scan_results=["Lütfen tüm alanları doldurun."])

    # Sonuçları toplamak için bir kuyruk oluşturuyoruz
    results_queue = Queue() 
    threads = [] # Oluşturacağımız iş parçacıklarını burada tutacağız

    # Her bir port için bir iş parçacığı oluşturuyoruz
    for port in range(start_port, end_port + 1):
        # Her bir iş parçacığı, port_scan_worker fonksiyonunu çalıştıracak
        # args: fonksiyona göndereceğimiz bilgiler (target_ip, port, sonuçları ekleyeceği kuyruk)
        thread = threading.Thread(target=port_scan_worker, args=(target_ip, port, results_queue))
        threads.append(thread) # Oluşturduğumuz iş parçacığını listeye ekle
        thread.start() # İş parçacığını başlat! (Yani "işe başla" de)

    # Tüm iş parçacıklarının bitmesini bekle
    for thread in threads:
        thread.join() # Her iş parçacığının bitmesini bekle ("işin bitene kadar bekle")

    scan_results = []
    # Kuyruktaki tüm sonuçları al
    while not results_queue.empty():
        scan_results.append(results_queue.get())

    # Sonuçları alfabetik sıraya göre sıralayalım (Port 80: Açık, Port 22: Açık yerine)
    # Ayrıca sadece "Açık" portları göstereceğimiz için, sonuçları filtreleyelim
    # Kapalı portlar çok fazla olacağı için listeyi çok uzatmasın
    final_results = sorted([res for res in scan_results if "Açık" in res])
    
    # Hata mesajlarını da yakalamak için genel bir try/except bloğu ekleyebiliriz
    if not final_results and not results_queue.empty(): # Eğer sonuç yok ama hata varsa
        final_results.append("Hata: Tarama sırasında bir sorun oluştu veya hiç açık port bulunamadı.")
    elif not final_results: # Eğer hiç açık port bulunamadıysa
        final_results.append(f"Belirtilen aralıkta açık port bulunamadı ({target_ip}, Port {start_port}-{end_port}).")


    return render_template("index.html", scan_results=final_results)

if __name__ == "__main__":
    app.run(debug=True)
