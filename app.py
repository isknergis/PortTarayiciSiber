from flask import Flask, render_template,request 
import  socket #ağ bağlantıları için
import threading #ağları aynı anda taramak için

app=Flask(__name__)

#ana sayfa için route
@app.route("/")
def index():
	#bu fonksiyon ana sayfayı gösterecek
	#scan_results diye boş bir liste gönderiypruz. ilk açıldığında sonuç yok
	return render_template("index.html", scan_results=[])
	
#tarama işlemi için yeni route
@app.route("/scan", methods=["POST"]) # Bu sayfa sadece form gönderildiğinde çalışacak
def scan_ports():
    # Kullanıcının formdan gönderdiği bilgileri alıyoruz
    target_ip = request.form.get("target_ip") 
    start_port = int(request.form.get("start_port")) # Sayıyı metinden sayıya çeviriyoruz
    end_port = int(request.form.get("end_port"))

    # Eğer IP adresi veya portlar boşsa, ana sayfaya geri dönüp hata mesajı gösterebiliriz (şimdilik basit tutalım)
    if not target_ip or not start_port or not end_port:
        return render_template("index.html", scan_results=["Lütfen tüm alanları doldurun."])

    scan_results = [] # Tarama sonuçlarını buraya toplayacağız

    # --- Portları Tarama İşlemi ---
    for port in range(start_port, end_port + 1): # Başlangıçtan bitişe kadar tüm portları geziyoruz
        try:
            # socket.AF_INET: İnternet adresi tipi (IPv4)
            # socket.SOCK_STREAM: TCP bağlantı tipi (en yaygın, web siteleri bununla çalışır)
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM) 
            sock.settimeout(1) # Bir porta bağlanmak için maksimum 1 saniye bekle (zaman aşımı)

            # Porta bağlanmayı deniyoruz
            result = sock.connect_ex((target_ip, port)) # Bağlanmayı dene, eğer hata olursa numara döndür

            if result == 0: # Eğer result 0 ise, bağlantı başarılı, yani port açık!
                scan_results.append(f"Port {port}: Açık")
            else:
                scan_results.append(f"Port {port}: Kapalı") # Bağlantı kurulamadı, port kapalı.

            sock.close() # Soketi kapatmayı unutma, kaynakları serbest bırak.

        except socket.gaierror: # Eğer yanlış bir IP adresi girilirse
            scan_results.append("Hata: Geçersiz IP adresi veya hostname.")
            break # Hata oluştuğu için taramayı durdur

        except socket.error: # Genel bir soket hatası (örneğin, ağ yok)
            scan_results.append("Hata: Ağ bağlantısı kurulamıyor.")
            break

    # Tarama bittiğinde, sonuçları ana sayfaya geri gönderiyoruz
    return render_template("index.html", scan_results=scan_results)

if __name__ == "__main__":
	app.run(debug=True)
