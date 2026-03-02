"""
Production server for LAN deployment
"""
import os
import sys
import logging
from waitress import serve
from app import app
from models import db
from config import ProductionConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('server.log'),
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

def start_waitress_server():
    app.config.from_object(ProductionConfig)

    SERVER_IP = "0.0.0.0"
    PORT = 5000

    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        LAN_IP = s.getsockname()[0]
        s.close()
    except:
        LAN_IP = "127.0.0.1"

    print("=" * 50)
    print("ARNDALE CBT SERVER - LAN DEPLOYMENT")
    print(f"http://{LAN_IP}:{PORT}")
    print("=" * 50)

    os.makedirs('logs', exist_ok=True)
    os.makedirs('uploads', exist_ok=True)

    serve(
        app,
        host=SERVER_IP,
        port=PORT,
        threads=10,
        ident="Arndale CBT Server"
    )

if __name__ == "__main__":
    start_waitress_server()